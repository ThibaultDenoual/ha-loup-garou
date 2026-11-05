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
from .game_engine import AnswerResult, GameEngine
from .narration import NarrationMessage
from .setup_rules import InvalidSetup, check_players

_LOGGER = logging.getLogger(__name__)

# How long a new connection may take to send its auth message.
AUTH_TIMEOUT = 10.0

INTERNAL_ERROR = "An internal error occurred. Check the server logs."


class GameInProgress(Exception):
    """start_game arrived outside the setup phase."""


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
        self._game_task: asyncio.Task | None = None
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
        if self._demo_task and not self._demo_task.done():
            self._demo_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._demo_task
        await self._stop_game()
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
                case "answer":
                    _require(data, "prompt_id")
                    await self._cmd_answer(ws, data["prompt_id"], data.get("answer", {}))
                case "abandon_game":
                    await self._cmd_abandon_game()
                case "get_state":
                    await ws.send_json(self._snapshot_message())
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
                            result = None
                            try:
                                result = await self._test_audio_cb()
                            finally:
                                # result says what the HA speaker did; None in the browser.
                                with contextlib.suppress(Exception):
                                    await target_ws.send_json(
                                        {"type": "test_audio_done", "result": result}
                                    )
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
        except Exception as exc:
            await self._report_error(ws, cmd, exc)

    async def _report_error(self, ws: web.WebSocketResponse, cmd, exc: Exception) -> None:
        if isinstance(exc, GameInProgress):
            error = {"type": "error", "code": "game_in_progress", "msg": "A game is in progress."}
        elif isinstance(exc, InvalidSetup):
            error = {"type": "error", "code": "invalid_setup", "reason": exc.reason, "msg": str(exc)}
        elif isinstance(exc, (KeyError, TypeError, ValueError)):
            _LOGGER.info("Rejected invalid command %s: %s", cmd, exc)
            if isinstance(exc, KeyError):
                message = f"Missing required field: {exc.args[0]}"
            elif isinstance(exc, ValueError):
                message = str(exc)
            else:
                message = "Invalid request."
            error = {"type": "error", "code": "bad_request", "msg": message}
        else:
            _LOGGER.error("Error handling command %s", cmd, exc_info=exc)
            error = {"type": "error", "code": "internal_error", "msg": INTERNAL_ERROR}
        # A background command can outlive the socket that sent it.
        with contextlib.suppress(Exception):
            await ws.send_json(error)

    def _snapshot_message(self) -> dict:
        return {"type": "snapshot", "state": self._engine.snapshot()}

    async def _cmd_start_game(self, data: dict) -> None:
        if self._demo_running():
            raise ValueError("demo already running")
        if self._engine.get_public_state()["phase"] != Phase.SETUP:
            raise GameInProgress
        players = check_players(data["players"])
        await self._engine.start_game(players, data["roles"])
        self._game_task = asyncio.create_task(self._run_game())

    async def _run_game(self) -> None:
        """The game loop lives here, so that no socket ever waits on it."""
        try:
            await self._engine.run_game()
        except Exception:
            _LOGGER.exception("The game loop failed")
            await self.broadcast({"type": "error", "code": "internal_error", "msg": INTERNAL_ERROR})
            await self._engine.reset()

    async def _cmd_answer(self, ws: web.WebSocketResponse, prompt_id, answer) -> None:
        result = await self._engine.answer(prompt_id, answer)
        code = {AnswerResult.STALE: "stale_prompt", AnswerResult.ILLEGAL: "illegal_answer"}.get(result)
        if code:
            await ws.send_json({"type": "error", "code": code, "msg": code})
            await ws.send_json(self._snapshot_message())

    async def _cmd_abandon_game(self) -> None:
        if self._demo_running():
            raise ValueError("demo already running")
        await self._stop_game()
        await self._engine.reset()

    async def _stop_game(self) -> None:
        task, self._game_task = self._game_task, None
        if task and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

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
        await self.broadcast({"type": "demo_stopped", "data": {}})

    # ── Engine event → broadcast ──────────────────────────────────────────────

    def wire_events(self) -> None:
        """Subscribe to engine events so all clients stay in sync."""
        from .const import GameEvent

        async def broadcast_snapshot(state: dict) -> None:
            await self.broadcast({"type": "snapshot", "state": state})

        self._engine.on(GameEvent.STATE_CHANGED, broadcast_snapshot)
