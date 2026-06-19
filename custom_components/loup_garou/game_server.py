"""WebSocket server — routes client commands to GameEngine."""
from __future__ import annotations

import asyncio
import json
import logging

from aiohttp import WSMsgType, web

from .game_engine import GameEngine
from .narration import NarrationMessage

_LOGGER = logging.getLogger(__name__)


class LoupGarouServer:
    def __init__(self, engine: GameEngine, config: dict | None = None) -> None:
        self._engine = engine
        self._config: dict = config or {}
        self._clients: set[web.WebSocketResponse] = set()
        self._night_task: asyncio.Task | None = None
        self._tts_future: asyncio.Future | None = None
        self._save_config_cb = None
        self._get_entities_cb = None
        self._test_audio_cb = None

    def set_save_callback(self, fn) -> None:
        self._save_config_cb = fn

    def set_entities_callback(self, fn) -> None:
        self._get_entities_cb = fn

    def set_test_audio_callback(self, fn) -> None:
        self._test_audio_cb = fn

    # ── aiohttp request handler ───────────────────────────────────────────────

    async def handle_ws(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self._clients.add(ws)
        _LOGGER.debug("WS client connected")

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    await self._dispatch(ws, json.loads(msg.data))
                elif msg.type == WSMsgType.ERROR:
                    _LOGGER.warning("WS error: %s", ws.exception())
        finally:
            self._clients.discard(ws)
            _LOGGER.debug("WS client disconnected")

        return ws

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
            pass
        finally:
            self._tts_future = None

    # ── Command dispatch ──────────────────────────────────────────────────────

    async def _dispatch(self, ws: web.WebSocketResponse, msg: dict) -> None:
        cmd = msg.get("cmd")
        data = msg.get("data", {})
        try:
            if cmd == "start_game":
                await self._cmd_start_game(data)
            elif cmd == "begin_night":
                await self._cmd_begin_night()
            elif cmd == "submit_night_action":
                await self._engine.submit_night_action(
                    data["role"], data.get("action", {})
                )
            elif cmd == "submit_pending_action":
                await self._engine.submit_pending_action(
                    data["role"], data.get("action", {})
                )
            elif cmd == "begin_vote":
                await self._engine.begin_vote()
            elif cmd == "resolve_vote":
                await self._engine.resolve_vote(data["votes"])
            elif cmd == "elect_sheriff":
                self._engine.elect_sheriff(data["player_id"])
                await self.broadcast({"type": "state", "state": self._engine.get_public_state()})
            elif cmd == "get_state":
                await ws.send_json({"type": "state", "state": self._engine.get_public_state()})
            elif cmd == "get_config":
                await ws.send_json({"type": "config", "config": self._config})
            elif cmd == "tts_done":
                if self._tts_future and not self._tts_future.done():
                    self._tts_future.set_result(None)
            elif cmd == "save_config":
                if self._save_config_cb:
                    await self._save_config_cb(data)
                await self.broadcast({"type": "config", "config": self._config})
            elif cmd == "get_entities":
                entities = self._get_entities_cb() if self._get_entities_cb else {}
                await ws.send_json({"type": "entities", "data": entities})
            elif cmd == "test_audio":
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
            else:
                await ws.send_json({"type": "error", "msg": f"unknown command: {cmd}"})
        except Exception as exc:
            _LOGGER.exception("Error handling command %s", cmd)
            await ws.send_json({"type": "error", "msg": str(exc)})

    async def _cmd_start_game(self, data: dict) -> None:
        players = data["players"]
        role_ids = data["roles"]
        await self._engine.start_game(players, role_ids)
        # Events (GAME_STARTED, PHASE_CHANGED) already broadcast state via wire_events

    async def _cmd_begin_night(self) -> None:
        if self._night_task and not self._night_task.done():
            _LOGGER.warning("begin_night: night already in progress")
            return
        self._night_task = asyncio.create_task(self._engine.begin_night())

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
                witch = next(
                    (p for p in pub["players"] if p["role_id"] == "witch" and p["alive"]), None
                )
                if witch:
                    flags = self._engine._state.player_flags.get(witch["id"], {})
                    enriched["witch_id"] = witch["id"]
                    enriched["witch_save_available"] = not flags.get("witch_save_used", False)
                    enriched["witch_poison_available"] = not flags.get("witch_poison_used", False)

            await self.broadcast({"type": "night_role_wake", "data": enriched})

        self._engine.on(GameEvent.NIGHT_ROLE_WAKE, on_night_role_wake)

        async def on_night_role_sleep(data: dict) -> None:
            await self.broadcast({"type": "night_role_sleep", "data": data})

        self._engine.on(GameEvent.NIGHT_ROLE_SLEEP, on_night_role_sleep)
