"""E2E tests for browser TTS narrate/tts_done protocol over WebSocket."""
from __future__ import annotations

import asyncio

import aiohttp
import pytest
from aiohttp.test_utils import TestServer
from aiohttp import web

from loup_garou.game_engine import GameEngine
from loup_garou.game_server import LoupGarouServer
from loup_garou.const import CONF_AUDIO_SOURCE, CONF_AUDIO_OUTPUT
from loup_garou.narration import NarrationMessage
from loup_garou.roles.impl.villager import Villager
from loup_garou.roles.impl.werewolf import Werewolf
from loup_garou.roles.impl.seer import Seer
from tests.e2e.conftest import answer, wait_prompt, drain, make_app


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_tts_server(audio_source="tts", audio_output="browser"):
    roles = {cls.id: cls() for cls in (Villager, Werewolf, Seer)}
    engine = GameEngine(roles=roles)
    server = LoupGarouServer(engine, config={
        CONF_AUDIO_SOURCE: audio_source,
        CONF_AUDIO_OUTPUT: audio_output,
    })
    server.wire_events()
    return engine, server


async def ws_connect(test_server, session):
    return await session.ws_connect(test_server.make_url("/ws"))


# ═══════════════════════════════════════════════════════════════════════════════
# narrate message structure + tts_done round-trip
# ═══════════════════════════════════════════════════════════════════════════════

async def test_tts_done_unblocks_narrate():
    """Client sending tts_done releases the narrate() future."""
    engine, srv = make_tts_server()
    app = make_app(srv)
    async with TestServer(app) as ts:
        async with aiohttp.ClientSession() as session:
            async with await ws_connect(ts, session) as ws:
                narrate_completed = asyncio.Event()

                async def _run_narrate():
                    await srv.narrate(NarrationMessage("Good night", "fr"))
                    narrate_completed.set()

                narrate_task = asyncio.create_task(_run_narrate())

                # Wait for narrate broadcast — verify both text and lang are sent
                msgs = await drain(ws, until_type="narrate", timeout=2.0)
                assert msgs[-1]["data"]["text"] == "Good night"
                assert msgs[-1]["data"]["lang"] == "fr"

                # Send tts_done
                await ws.send_json({"cmd": "tts_done", "data": {}})

                # narrate() should unblock quickly
                await asyncio.wait_for(narrate_completed.wait(), timeout=2.0)
                assert narrate_completed.is_set()
                await narrate_task  # clean up the task before teardown


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
                        await srv.narrate(NarrationMessage("Wolves awaken", "fr"))
                        narrate_done.set()

                    narrate_task = asyncio.create_task(_run_narrate())

                    # ws1 receives narrate
                    await drain(ws1, until_type="narrate", timeout=2.0)
                    # ws2 also receives it
                    await drain(ws2, until_type="narrate", timeout=2.0)

                    # ws2 sends tts_done
                    await ws2.send_json({"cmd": "tts_done", "data": {}})

                    await asyncio.wait_for(narrate_done.wait(), timeout=2.0)
                    assert narrate_done.is_set()
                    await narrate_task  # clean up the task before teardown


async def test_narrate_skips_when_no_clients_connected():
    """narrate() returns immediately with no clients — no stall."""
    engine, srv = make_tts_server()
    # Don't connect any client
    await asyncio.wait_for(srv.narrate(NarrationMessage("nobody home", "fr")), timeout=1.0)


async def test_narrate_broadcasts_to_all_clients():
    """Both clients receive the narrate message."""
    engine, srv = make_tts_server()
    app = make_app(srv)
    async with TestServer(app) as ts:
        async with aiohttp.ClientSession() as session:
            async with await ws_connect(ts, session) as ws1:
                async with await ws_connect(ts, session) as ws2:
                    narrate_task = asyncio.create_task(srv.narrate(NarrationMessage("Both hear this", "en")))

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

async def test_get_config_exposes_browser_output():
    engine, srv = make_tts_server(audio_source="tts", audio_output="browser")
    app = make_app(srv)
    async with TestServer(app) as ts:
        async with aiohttp.ClientSession() as session:
            async with await ws_connect(ts, session) as ws:
                await ws.send_json({"cmd": "get_config"})
                msgs = await drain(ws, until_type="config", timeout=2.0)
                config = msgs[-1]["config"]
                assert config.get(CONF_AUDIO_OUTPUT) == "browser"
                assert config.get(CONF_AUDIO_SOURCE) == "tts"


async def test_get_config_exposes_ha_output():
    engine, srv = make_tts_server(audio_source="tts", audio_output="ha")
    app = make_app(srv)
    async with TestServer(app) as ts:
        async with aiohttp.ClientSession() as session:
            async with await ws_connect(ts, session) as ws:
                await ws.send_json({"cmd": "get_config"})
                msgs = await drain(ws, until_type="config", timeout=2.0)
                config = msgs[-1]["config"]
                assert config.get(CONF_AUDIO_OUTPUT) == "ha"


# ═══════════════════════════════════════════════════════════════════════════════
# Full game flow: narrate interleaved with game events
# ═══════════════════════════════════════════════════════════════════════════════

async def test_game_flow_proceeds_after_tts_done():
    """Full game flow where the test client plays the tts_done responder role."""
    engine, srv = make_tts_server(audio_source="tts", audio_output="browser")
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
                for _ in range(3):
                    await answer(ws, await wait_prompt(ws, "reveal", timeout=3.0))

                # The wolf's prompt opens once the night narration has been confirmed.
                wolf = await wait_prompt(ws, "night_action", "werewolf", timeout=3.0)
                await answer(ws, wolf, target=wolf["picks"]["target"]["options"][0])

                # Eventually game reaches day (or game_over if only 1 villager left)
                msgs = await drain(
                    ws,
                    until_type="snapshot",
                    predicate=lambda m: m.get("state", {}).get("phase") in ("day", "game_over"),
                    timeout=5.0,
                )
                final_phase = msgs[-1]["state"]["phase"]
                assert final_phase in ("day", "game_over")
                await srv.async_shutdown()
