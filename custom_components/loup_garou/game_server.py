"""WebSocket server — routes client commands to GameEngine."""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging

from typing import Callable

from aiohttp import WSMsgType, web

from .const import Phase
from .demo import DEMOS, DemoRunner, list_demos
from .game_engine import GameEngine
from .narration import NarrationMessage

_LOGGER = logging.getLogger(__name__)

# How long a new connection may take to send its auth message.
AUTH_TIMEOUT = 10.0


class LoupGarouServer:
    def __init__(
        self,
        engine: GameEngine,
        config: dict | None = None,
        *,
        demo_action_delay: float = 1.5,
        demo_step_delay: float = 1.0,
    ) -> None:
        self._engine = engine
        self._config: dict = config or {}
        self._clients: set[web.WebSocketResponse] = set()
        self._night_task: asyncio.Task | None = None
        self._tts_future: asyncio.Future | None = None
        self._demo_task: asyncio.Task | None = None
        self._demo_runner: DemoRunner | None = None
        # Pacing between scripted demo steps; lowered to 0 in tests.
        self._demo_action_delay = demo_action_delay
        self._demo_step_delay = demo_step_delay
        self._save_config_cb = None
        self._get_entities_cb = None
        self._test_audio_cb = None
        self._auth_cb: Callable[[str], bool] | None = None

    def set_save_callback(self, fn) -> None:
        self._save_config_cb = fn

    def set_entities_callback(self, fn) -> None:
        self._get_entities_cb = fn

    def set_test_audio_callback(self, fn) -> None:
        self._test_audio_cb = fn

    def set_auth_callback(self, fn: Callable[[str], bool]) -> None:
        """Require every connection to open with {"type": "auth", "access_token": ...}.

        fn returns whether the token is valid. Without it (standalone dev server)
        connections are trusted and an auth message is simply acknowledged.
        """
        self._auth_cb = fn

    # ── aiohttp request handler ───────────────────────────────────────────────

    async def handle_ws(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        if self._auth_cb is not None and not await self._authenticate(ws):
            await ws.close()
            return ws
        self._clients.add(ws)
        _LOGGER.debug("WS client connected")

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        payload = json.loads(msg.data)
                    except json.JSONDecodeError:
                        await ws.send_json({
                            "type": "error",
                            "code": "bad_request",
                            "msg": "Invalid JSON message.",
                        })
                        continue
                    if not isinstance(payload, dict):
                        await ws.send_json({
                            "type": "error",
                            "code": "bad_request",
                            "msg": "WebSocket message must be a JSON object.",
                        })
                        continue
                    if payload.get("type") == "auth":
                        # Already authenticated, or no auth required.
                        await ws.send_json({"type": "auth_ok"})
                        continue
                    await self._dispatch(ws, payload)
                elif msg.type == WSMsgType.ERROR:
                    _LOGGER.warning("WS error: %s", ws.exception())
        finally:
            self._clients.discard(ws)
            _LOGGER.debug("WS client disconnected")

        return ws

    async def _authenticate(self, ws: web.WebSocketResponse) -> bool:
        """Wait for the opening auth message; reply auth_ok or auth_invalid."""
        token = None
        try:
            msg = await ws.receive(timeout=AUTH_TIMEOUT)
            if msg.type == WSMsgType.TEXT:
                payload = json.loads(msg.data)
                if isinstance(payload, dict) and payload.get("type") == "auth":
                    token = payload.get("access_token")
        except (asyncio.TimeoutError, json.JSONDecodeError):
            pass
        if isinstance(token, str) and token and self._auth_cb(token):
            await ws.send_json({"type": "auth_ok"})
            return True
        _LOGGER.info("Rejected WebSocket connection without a valid access token")
        with contextlib.suppress(Exception):
            await ws.send_json({"type": "auth_invalid"})
        return False

    async def async_shutdown(self) -> None:
        """Stop any game task and disconnect every client (entry unload)."""
        for task in (self._demo_task, self._night_task):
            if task and not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        for ws in list(self._clients):
            with contextlib.suppress(Exception):
                await ws.close()
        self._clients.clear()

    # ── Broadcast + browser TTS ───────────────────────────────────────────────

    async def broadcast(self, message: dict) -> None:
        dead: set[web.WebSocketResponse] = set()
        for ws in self._clients:
            try:
                await ws.send_json(message)
            except Exception:
                dead.add(ws)
        self._clients -= dead

    async def narrate(self, msg: NarrationMessage) -> None:
        """Broadcast a narration request and wait for the browser to confirm playback.

        Blocks until any connected client sends tts_done, or until the 10-second
        timeout fires so a disconnected client never stalls the game.
        When msg.audio_url is set the browser plays a pre-recorded MP3 instead of
        synthesising speech, falling back to Web Speech API on error.
        """
        if not self._clients:
            return
        self._tts_future = asyncio.get_running_loop().create_future()
        try:
            await self.broadcast({"type": "narrate", "data": msg.to_payload()})
            await asyncio.wait_for(self._tts_future, timeout=10.0)
        except asyncio.TimeoutError:
            _LOGGER.warning("Browser TTS timed out after 10 s for: %.60s", msg.text)
        except asyncio.CancelledError:
            # Expected when a demo is stopped mid-narration — the caller unwinds.
            _LOGGER.debug("Narration cancelled: %.60s", msg.text)
            raise
        finally:
            self._tts_future = None

    # ── Command dispatch ──────────────────────────────────────────────────────

    async def _dispatch(self, ws: web.WebSocketResponse, msg: dict) -> None:
        cmd = msg.get("cmd")
        data = msg.get("data", {})
        
        # local dispatch helper
        def _require(data: dict, *keys: str) -> None:
            missing = [k for k in keys if k not in data]
            if missing:
                raise ValueError(f"Missing required fields: {missing}")
        
        try:
            match cmd:
                case "start_game":
                    await self._cmd_start_game(data)
                case "begin_night":
                    await self._cmd_begin_night()
                case "submit_night_action":
                    _require(data, "role")
                    await self._engine.submit_night_action(data["role"], data.get("action", {}))
                case "submit_pending_action":
                    _require(data, "role")
                    await self._engine.submit_pending_action(data["role"], data.get("action", {}))
                case "begin_vote":
                    await self._engine.begin_vote()
                case "resolve_vote":
                    _require(data, "votes")
                    await self._engine.resolve_vote(data["votes"])
                case "elect_sheriff":
                    _require(data, "player_id")
                    self._engine.elect_sheriff(data["player_id"])
                    await self.broadcast({"type": "state", "state": self._engine.get_public_state()})
                case "get_state":
                    await ws.send_json({"type": "state", "state": self._engine.get_public_state()})
                case "get_config":
                    await ws.send_json({"type": "config", "config": self._config})
                case "tts_done":
                    if self._tts_future and not self._tts_future.done():
                        self._tts_future.set_result(None)
                case "save_config":
                    if self._save_config_cb:
                        await self._save_config_cb(data)
                    await self.broadcast({"type": "config", "config": self._config})
                case "get_entities":
                    entities = self._get_entities_cb() if self._get_entities_cb else {}
                    await ws.send_json({"type": "entities", "data": entities})
                case "test_audio":
                    if self._test_audio_cb:
                        async def _run_test(target_ws=ws):
                            try:
                                await self._test_audio_cb()
                            finally:
                                try:
                                    await target_ws.send_json({"type": "test_audio_done"})
                                except Exception:
                                    pass
                        asyncio.create_task(_run_test())
                case "get_demos":
                    await ws.send_json({"type": "demo_presets", "presets": list_demos()})
                case "run_demo":
                    _require(data, "preset")
                    reason = self._demo_rejection_reason(data["preset"])
                    if reason:
                        await ws.send_json({"type": "demo_rejected", "data": {"reason": reason}})
                    else:
                        await self._cmd_run_demo(data["preset"])
                case "stop_demo":
                    await self._cmd_stop_demo()
                case _:
                    await ws.send_json({"type": "error", "msg": f"unknown command: {cmd}"})
        except (KeyError, TypeError, ValueError) as exc:
            _LOGGER.info("Rejected invalid command %s: %s", cmd, exc)
            if isinstance(exc, KeyError):
                message = f"Missing required field: {exc.args[0]}"
            elif isinstance(exc, ValueError):
                message = str(exc)
            else:
                message = "Invalid request."
            await ws.send_json({"type": "error", "code": "bad_request", "msg": message})
        except Exception:
            _LOGGER.exception("Error handling command %s", cmd)
            await ws.send_json({
                "type": "error",
                "code": "internal_error",
                "msg": "An internal error occurred. Check the server logs.",
            })

    async def _cmd_start_game(self, data: dict) -> None:
        if self._demo_running():
            raise ValueError("demo already running")
        players = data["players"]
        role_ids = data["roles"]
        await self._engine.start_game(players, role_ids)
        # Events (GAME_STARTED, PHASE_CHANGED) already broadcast state via wire_events

    async def _cmd_begin_night(self) -> None:
        if self._night_task and not self._night_task.done():
            _LOGGER.warning("begin_night: night already in progress")
            return
        self._night_task = asyncio.create_task(self._engine.begin_night())

    # ── Demo games ───────────────────────────────────────────────────────────

    def _demo_running(self) -> bool:
        return self._demo_task is not None and not self._demo_task.done()

    def _demo_rejection_reason(self, preset: str) -> str | None:
        """Why this demo cannot start right now, or None if it can."""
        if self._demo_running():
            return "already_running"
        if preset not in DEMOS:
            return "unknown_preset"
        if self._engine.get_public_state()["phase"] != Phase.SETUP:
            return "game_in_progress"
        return None

    async def _cmd_run_demo(self, preset: str) -> None:
        script = DEMOS[preset]

        async def _on_step(step: str) -> None:
            await self.broadcast({"type": "demo_step", "data": {"preset": script.key, "step": step}})

        runner = DemoRunner(
            self._engine,
            script,
            action_delay=self._demo_action_delay,
            step_delay=self._demo_step_delay,
            on_step=_on_step,
        )
        self._demo_runner = runner
        self._demo_task = asyncio.create_task(self._run_demo(runner))
        # Share the slot so a real begin_night cannot race the demo's own night.
        self._night_task = self._demo_task
        await self.broadcast({"type": "demo_started", "data": {"preset": script.key}})

    async def _run_demo(self, runner: DemoRunner) -> None:
        try:
            await runner.run()
        except asyncio.CancelledError:
            _LOGGER.debug("Demo cancelled")
        except Exception:
            _LOGGER.exception("Demo failed")
            await self.broadcast({"type": "demo_error", "data": {"msg": "demo_failed"}})
        else:
            await self.broadcast({"type": "demo_finished", "data": {"preset": runner.key}})

    async def _cmd_stop_demo(self) -> None:
        task = self._demo_task
        if task is None or task.done():
            await self.broadcast({"type": "demo_stopped", "data": {}})
            return
        if self._demo_runner:
            self._demo_runner.cancel()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        # The runner resets on its way out, but a cancel can cut that short.
        await self._engine.reset()
        self._demo_runner = None
        self._demo_task = None
        self._night_task = None
        await self.broadcast({"type": "demo_stopped", "data": {}})

    # ── Engine event → broadcast ──────────────────────────────────────────────

    def wire_events(self) -> None:
        """Subscribe to engine events so all clients stay in sync."""
        from .const import GameEvent

        async def broadcast_state(data: dict) -> None:
            await self.broadcast({"type": "state", "state": self._engine.get_public_state()})

        async def broadcast_event(event_type: str):
            async def handler(data: dict) -> None:
                await self.broadcast({"type": event_type, "data": data})
            return handler

        for event in (
            GameEvent.GAME_STARTED,
            GameEvent.PHASE_CHANGED,
            GameEvent.NIGHT_RESOLVED,
            GameEvent.DAY_STARTED,
            GameEvent.VOTE_STARTED,
            GameEvent.VOTE_RESOLVED,
            GameEvent.GAME_OVER,
        ):
            self._engine.on(event, broadcast_state)

        async def on_hunter_shot(data: dict) -> None:
            await self.broadcast({"type": "hunter_shot", "data": data})

        self._engine.on(GameEvent.HUNTER_SHOT, on_hunter_shot)

        async def on_player_eliminated(data: dict) -> None:
            await self.broadcast({"type": "player_eliminated", "data": data})
            await self.broadcast({"type": "state", "state": self._engine.get_public_state()})

        self._engine.on(GameEvent.PLAYER_ELIMINATED, on_player_eliminated)

        async def on_night_role_wake(data: dict) -> None:
            enriched = dict(data)
            role_id = data.get("role", "")
            pub = self._engine.get_public_state()
            players_map = {p["id"]: p for p in pub["players"]}

            # Resolve pending_kill IDs → player objects the UI can display
            # pending_kills may be [str, ...] or [{"player_id": str, "cause": str}, ...]
            kill_entries = data.get("pending_kills", [])
            kill_ids: list[str] = [
                e["player_id"] if isinstance(e, dict) else e for e in kill_entries
            ]
            if kill_ids:
                enriched["pending_kill_players"] = [
                    players_map[pid] for pid in kill_ids if pid in players_map
                ]

            # For witch: include her potion availability
            if role_id == "witch":
                enriched.update(self._engine.get_role_public_state("witch"))

            await self.broadcast({"type": "night_role_wake", "data": enriched})

        self._engine.on(GameEvent.NIGHT_ROLE_WAKE, on_night_role_wake)

        async def on_night_role_sleep(data: dict) -> None:
            await self.broadcast({"type": "night_role_sleep", "data": data})

        self._engine.on(GameEvent.NIGHT_ROLE_SLEEP, on_night_role_sleep)
