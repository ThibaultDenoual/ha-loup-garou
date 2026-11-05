"""End-to-end tests for the demo mode — the JSON protocol the launcher depends on."""
from __future__ import annotations

import asyncio

import aiohttp
from aiohttp.test_utils import TestServer

from loup_garou.roles.impl.seer import Seer
from loup_garou.roles.impl.villager import Villager
from loup_garou.roles.impl.werewolf import Werewolf
from tests.e2e.conftest import answer, drain, make_app, make_server, wait_prompt

ROLES = [Villager, Werewolf, Seer]
# The demo paces itself with sleeps; tests run it as fast as the engine allows.
FAST = {"demo_action_delay": 0, "demo_step_delay": 0}


async def ws_for(fn, role_classes=None, **server_kwargs):
    engine, srv = make_server(role_classes or ROLES, **{**FAST, **server_kwargs})
    app = make_app(srv)
    async with TestServer(app) as ts:
        async with aiohttp.ClientSession() as sess:
            async with sess.ws_connect(ts.make_url("/ws")) as ws:
                try:
                    return await fn(ws, engine, srv)
                finally:
                    if srv._demo_running():
                        await srv._cmd_stop_demo()
                    await srv.async_shutdown()


async def send(ws, cmd, **data):
    await ws.send_json({"cmd": cmd, "data": data})


# ═══════════════════════════════════════════════════════════════════════════════
# Preset discovery
# ═══════════════════════════════════════════════════════════════════════════════


async def test_get_demos_lists_the_presets():
    async def _test(ws, engine, srv):
        await send(ws, "get_demos")
        msgs = await drain(ws, until_type="demo_presets")
        presets = msgs[-1]["presets"]
        assert [p["key"] for p in presets] == ["smoke_test", "wolves_win", "lovers_win"]
        assert [p["label_key"] for p in presets] == [f"demo.preset.{p['key']}" for p in presets]

    await ws_for(_test)


# ═══════════════════════════════════════════════════════════════════════════════
# Running a demo
# ═══════════════════════════════════════════════════════════════════════════════


async def test_run_demo_plays_the_whole_game_and_finishes():
    async def _test(ws, engine, srv):
        await send(ws, "run_demo", preset="smoke_test")
        msgs = await drain(ws, until_type="demo_finished", timeout=5)

        assert msgs[-1]["data"]["preset"] == "smoke_test"

        steps = [m["data"]["step"] for m in msgs if m["type"] == "demo_step"]
        assert steps == [
            "game_started",
            "night_start",
            "role_action:seer",
            "role_action:seer",
            "role_action:werewolf",
            "vote_cast",
            "finished",
        ]

        # The real engine events went out over the wire, so lights/TTS see them too.
        prompts = [m["state"]["prompt"] for m in msgs if m["type"] == "snapshot"]
        assert any(p and p["kind"] == "night_action" for p in prompts)

        game_over = [m for m in msgs if m["type"] == "snapshot"
                     and m["state"].get("phase") == "game_over"]
        assert game_over and game_over[-1]["state"]["winner"] == "village"

    await ws_for(_test)


async def test_run_demo_returns_the_engine_to_setup():
    async def _test(ws, engine, srv):
        await send(ws, "run_demo", preset="smoke_test")
        await drain(ws, until_type="demo_finished", timeout=5)

        await send(ws, "get_state")
        msgs = await drain(ws, until_type="snapshot")
        state = msgs[-1]["state"]
        assert state["phase"] == "setup"
        assert state["winner"] is None
        assert state["players"] == []

    await ws_for(_test)


async def test_run_demo_broadcasts_progress_to_every_client():
    engine, srv = make_server(ROLES, **FAST)
    app = make_app(srv)
    async with TestServer(app) as ts:
        async with aiohttp.ClientSession() as sess:
            async with sess.ws_connect(ts.make_url("/ws")) as ws1:
                async with sess.ws_connect(ts.make_url("/ws")) as ws2:
                    await send(ws1, "run_demo", preset="smoke_test")
                    got1 = await drain(ws1, until_type="demo_started", timeout=5)
                    got2 = await drain(ws2, until_type="demo_started", timeout=5)
                    assert got1[-1]["data"]["preset"] == "smoke_test"
                    assert got2[-1]["data"]["preset"] == "smoke_test"

                    done1 = await drain(ws1, until_type="demo_finished", timeout=5)
                    done2 = await drain(ws2, until_type="demo_finished", timeout=5)
                    assert done1[-1]["type"] == done2[-1]["type"] == "demo_finished"


# ═══════════════════════════════════════════════════════════════════════════════
# Rejections
# ═══════════════════════════════════════════════════════════════════════════════


async def test_run_demo_with_unknown_preset_is_rejected():
    async def _test(ws, engine, srv):
        await send(ws, "run_demo", preset="does_not_exist")
        msgs = await drain(ws, until_type="demo_rejected")
        assert msgs[-1]["data"]["reason"] == "unknown_preset"

    await ws_for(_test)


async def test_run_demo_without_preset_field_errors():
    async def _test(ws, engine, srv):
        await send(ws, "run_demo")
        msgs = await drain(ws, until_type="error")
        assert "preset" in msgs[-1]["msg"]

    await ws_for(_test)


async def test_run_demo_during_a_real_game_is_rejected():
    async def _test(ws, engine, srv):
        await send(ws, "start_game", players=["Alice", "Bob", "Carol"], roles=["werewolf", "villager", "villager"])
        await drain(ws, until_type="snapshot",
                    predicate=lambda m: m["state"]["phase"] == "role_reveal")

        await send(ws, "run_demo", preset="smoke_test")
        msgs = await drain(ws, until_type="demo_rejected")
        assert msgs[-1]["data"]["reason"] == "game_in_progress"

    await ws_for(_test)


async def test_second_concurrent_demo_is_rejected():
    async def _test(ws, engine, srv):
        await send(ws, "run_demo", preset="smoke_test")
        await drain(ws, until_type="demo_started")
        await send(ws, "run_demo", preset="smoke_test")
        msgs = await drain(ws, until_type="demo_rejected")
        assert msgs[-1]["data"]["reason"] == "already_running"

    await ws_for(_test, demo_action_delay=0.2, demo_step_delay=0.2)


async def test_start_game_during_a_demo_is_refused():
    async def _test(ws, engine, srv):
        await send(ws, "run_demo", preset="smoke_test")
        await drain(ws, until_type="demo_started")
        await send(ws, "start_game", players=["Alice", "Bob", "Carol"], roles=["werewolf", "villager", "villager"])
        msgs = await drain(ws, until_type="error")
        assert "demo already running" in msgs[-1]["msg"]

    await ws_for(_test, demo_action_delay=0.2, demo_step_delay=0.2)


# ═══════════════════════════════════════════════════════════════════════════════
# Stopping a demo
# ═══════════════════════════════════════════════════════════════════════════════


async def test_stop_demo_halts_the_game_and_resets():
    async def _test(ws, engine, srv):
        await send(ws, "run_demo", preset="smoke_test")
        await wait_prompt(ws, "night_action")

        await send(ws, "stop_demo")
        msgs = await drain(ws, until_type="demo_stopped", timeout=5)
        assert msgs[-1]["type"] == "demo_stopped"

        await send(ws, "get_state")
        state = (await drain(ws, until_type="snapshot"))[-1]["state"]
        assert state["phase"] == "setup"
        assert state["players"] == []

    await ws_for(_test, demo_action_delay=30, demo_step_delay=0)


async def test_stop_demo_when_nothing_runs_is_harmless():
    async def _test(ws, engine, srv):
        await send(ws, "stop_demo")
        msgs = await drain(ws, until_type="demo_stopped")
        assert msgs[-1]["type"] == "demo_stopped"

        await send(ws, "get_state")
        state = (await drain(ws, until_type="snapshot"))[-1]["state"]
        assert state["phase"] == "setup"

    await ws_for(_test)


async def test_engine_is_playable_again_after_a_stopped_demo():
    async def _test(ws, engine, srv):
        await send(ws, "run_demo", preset="smoke_test")
        await wait_prompt(ws, "night_action")
        await send(ws, "stop_demo")
        await drain(ws, until_type="demo_stopped")

        await send(ws, "start_game", players=["Alice", "Bob", "Carol"], roles=["werewolf", "villager", "villager"])
        msgs = await drain(ws, until_type="snapshot",
                           predicate=lambda m: m["state"]["phase"] == "role_reveal")
        assert [p["name"] for p in msgs[-1]["state"]["players"]] == ["Alice", "Bob", "Carol"]

    await ws_for(_test, demo_action_delay=30, demo_step_delay=0)


async def test_stop_demo_cancels_the_pending_night():
    """No orphan night survives a stopped demo."""
    async def _test(ws, engine, srv):
        await send(ws, "run_demo", preset="smoke_test")
        await wait_prompt(ws, "night_action")
        await send(ws, "stop_demo")
        await drain(ws, until_type="demo_stopped")

        # A new game must not be blocked by the stopped demo.
        await send(ws, "start_game", players=["A", "B", "C"], roles=["seer", "werewolf", "villager"])
        for _ in range(3):
            await answer(ws, await wait_prompt(ws, "reveal"))
        await wait_prompt(ws, "night_action", "seer")
        assert engine.prompt.role == "seer"

    await ws_for(_test, demo_action_delay=30, demo_step_delay=0)
