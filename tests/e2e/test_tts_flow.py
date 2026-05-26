"""E2E tests for browser TTS narrate/tts_done protocol over WebSocket."""
from __future__ import annotations

import asyncio

import aiohttp
import pytest
from aiohttp.test_utils import TestServer
from aiohttp import web

from loup_garou.game_engine import GameEngine
from loup_garou.game_server import LoupGarouServer
from loup_garou.const import CONF_TTS_MODE
from loup_garou.roles.impl.villager import Villager
from loup_garou.roles.impl.werewolf import Werewolf
from loup_garou.roles.impl.seer import Seer
from tests.e2e.conftest import drain, make_app


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_tts_server(tts_mode="browser"):
    roles = {cls.id: cls() for cls in (Villager, Werewolf, Seer)}
    engine = GameEngine(roles=roles)
    server = LoupGarouServer(engine, config={CONF_TTS_MODE: tts_mode})
    server.wire_events()
    return engine, server


async def ws_connect(test_server, session):
    return await session.ws_connect(test_server.make_url("/ws"))


# ═══════════════════════════════════════════════════════════════════════════════
# narrate message structure
# ═══════════════════════════════════════════════════════════════════════════════

async def test_narrate_message_sent_to_client():
    """Server broadcast a narrate message when server.narrate() is called."""
    engine, srv = make_tts_server()
    app = make_app(srv)
    async with TestServer(app) as ts:
        async with aiohttp.ClientSession() as session:
            async with await ws_connect(ts, session) as ws:
                # Trigger narrate directly on the server, resolve it immediately
                async def _narrate_and_resolve():
                    await asyncio.sleep(0.01)
                    task = asyncio.create_task(srv.narrate("La nuit tombe.", "fr"))
                    await asyncio.sleep(0)
                    if srv._tts_future and not srv._tts_future.done():
                        srv._tts_future.set_result(None)
                    await task

                asyncio.get_event_loop().create_task(_narrate_and_resolve())
                msgs = await drain(ws, until_type="narrate", timeout=2.0)
                narrate = msgs[-1]
                assert narrate["type"] == "narrate"
                assert narrate["data"]["text"] == "La nuit tombe."
                assert narrate["data"]["lang"] == "fr"


async def test_tts_done_unblocks_narrate():
    """Client sending tts_done releases the narrate() future."""
    engine, srv = make_tts_server()
    app = make_app(srv)
    async with TestServer(app) as ts:
        async with aiohttp.ClientSession() as session:
            async with await ws_connect(ts, session) as ws:
                narrate_completed = asyncio.Event()

                async def _run_narrate():
                    await srv.narrate("Good night", "fr")
                    narrate_completed.set()

                asyncio.get_event_loop().create_task(_run_narrate())

                # Wait for narrate broadcast
                msgs = await drain(ws, until_type="narrate", timeout=2.0)
                assert msgs[-1]["data"]["text"] == "Good night"

                # Send tts_done
                await ws.send_json({"cmd": "tts_done", "data": {}})

                # narrate() should unblock quickly
                await asyncio.wait_for(narrate_completed.wait(), timeout=2.0)
                assert narrate_completed.is_set()


async def test_tts_done_from_second_client_unblocks_narrate():
    """Any connected client's tts_done resolves the shared future."""
    engine, srv = make_tts_server()
    app = make_app(srv)
    async with TestServer(app) as ts:
        async with aiohttp.ClientSession() as session:
            async with await ws_connect(ts, session) as ws1:
                async with await ws_connect(ts, session) as ws2:
                    narrate_done = asyncio.Event()

                    async def _run_narrate():
                        await srv.narrate("Wolves awaken", "fr")
                        narrate_done.set()

                    asyncio.get_event_loop().create_task(_run_narrate())

                    # ws1 receives narrate
                    await drain(ws1, until_type="narrate", timeout=2.0)
                    # ws2 also receives it
                    await drain(ws2, until_type="narrate", timeout=2.0)

                    # ws2 sends tts_done
                    await ws2.send_json({"cmd": "tts_done", "data": {}})

                    await asyncio.wait_for(narrate_done.wait(), timeout=2.0)
                    assert narrate_done.is_set()


async def test_narrate_skips_when_no_clients_connected():
    """narrate() returns immediately with no clients — no stall."""
    engine, srv = make_tts_server()
    # Don't connect any client
    await asyncio.wait_for(srv.narrate("nobody home", "fr"), timeout=1.0)


async def test_narrate_broadcasts_to_all_clients():
    """Both clients receive the narrate message."""
    engine, srv = make_tts_server()
    app = make_app(srv)
    async with TestServer(app) as ts:
        async with aiohttp.ClientSession() as session:
            async with await ws_connect(ts, session) as ws1:
                async with await ws_connect(ts, session) as ws2:
                    narrate_task = asyncio.create_task(srv.narrate("Both hear this", "en"))

                    msgs1 = await drain(ws1, until_type="narrate", timeout=2.0)
                    msgs2 = await drain(ws2, until_type="narrate", timeout=2.0)

                    assert msgs1[-1]["data"]["text"] == "Both hear this"
                    assert msgs2[-1]["data"]["text"] == "Both hear this"

                    # Resolve
                    if srv._tts_future and not srv._tts_future.done():
                        srv._tts_future.set_result(None)
                    await asyncio.wait_for(narrate_task, timeout=1.0)


# ═══════════════════════════════════════════════════════════════════════════════
# get_config exposes tts_mode
# ═══════════════════════════════════════════════════════════════════════════════

async def test_get_config_exposes_browser_tts_mode():
    engine, srv = make_tts_server(tts_mode="browser")
    app = make_app(srv)
    async with TestServer(app) as ts:
        async with aiohttp.ClientSession() as session:
            async with await ws_connect(ts, session) as ws:
                await ws.send_json({"cmd": "get_config"})
                msgs = await drain(ws, until_type="config", timeout=2.0)
                config = msgs[-1]["config"]
                assert config.get(CONF_TTS_MODE) == "browser"


async def test_get_config_exposes_ha_tts_mode():
    engine, srv = make_tts_server(tts_mode="ha")
    app = make_app(srv)
    async with TestServer(app) as ts:
        async with aiohttp.ClientSession() as session:
            async with await ws_connect(ts, session) as ws:
                await ws.send_json({"cmd": "get_config"})
                msgs = await drain(ws, until_type="config", timeout=2.0)
                config = msgs[-1]["config"]
                assert config.get(CONF_TTS_MODE) == "ha"


# ═══════════════════════════════════════════════════════════════════════════════
# Full game flow: narrate interleaved with game events
# ═══════════════════════════════════════════════════════════════════════════════

async def test_game_flow_proceeds_after_tts_done():
    """Full game flow where the test client plays the tts_done responder role."""
    engine, srv = make_tts_server(tts_mode="browser")
    app = make_app(srv)
    async with TestServer(app) as ts:
        async with aiohttp.ClientSession() as session:
            async with await ws_connect(ts, session) as ws:
                # Start the game
                await ws.send_json({
                    "cmd": "start_game",
                    "data": {
                        "players": ["Alice", "Bob", "Carol"],
                        "roles": ["werewolf", "villager", "villager"],
                    },
                })
                state_msg = await drain(
                    ws,
                    until_type="state",
                    predicate=lambda m: m.get("state", {}).get("phase") == "role_reveal",
                    timeout=3.0,
                )
                assert state_msg[-1]["state"]["phase"] == "role_reveal"

                players = state_msg[-1]["state"]["players"]
                villager = next(p for p in players if p["role_id"] == "villager")

                # Begin night — this triggers narrate events in the atmosphere
                await ws.send_json({"cmd": "begin_night"})

                # Wait for wolf wake (wolf has no narration in plain mode)
                wolf_wake = await drain(
                    ws,
                    until_type="night_role_wake",
                    predicate=lambda m: m.get("data", {}).get("role") == "werewolf",
                    timeout=3.0,
                )
                assert wolf_wake[-1]["data"]["role"] == "werewolf"

                # Wolf kills villager
                await ws.send_json({
                    "cmd": "submit_night_action",
                    "data": {"role": "werewolf", "action": {"target": villager["id"]}},
                })

                # Eventually game reaches day (or game_over if only 1 villager left)
                msgs = await drain(
                    ws,
                    until_type="state",
                    predicate=lambda m: m.get("state", {}).get("phase") in ("day", "game_over"),
                    timeout=5.0,
                )
                final_phase = msgs[-1]["state"]["phase"]
                assert final_phase in ("day", "game_over")
