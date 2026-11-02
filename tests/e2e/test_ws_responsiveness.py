"""The one-phone flow: one socket must stay readable while the game waits on it.

The phone that receives a prompt (hunter shot, narration) is also the only one
that can answer it, on the same socket that sent the command which caused it.
"""
from __future__ import annotations

import asyncio

import aiohttp
from aiohttp.test_utils import TestServer

from loup_garou.const import GameEvent
from loup_garou.narration import NarrationMessage
from loup_garou.roles.impl.hunter import Hunter
from loup_garou.roles.impl.seer import Seer
from loup_garou.roles.impl.villager import Villager
from loup_garou.roles.impl.werewolf import Werewolf
from tests.e2e.conftest import drain, make_app, make_server

ROLES = (Villager, Werewolf, Seer, Hunter)


async def _play(fn, *, narrate_on=None):
    """Run fn(connect, engine, server) against a live server; connect() opens a socket."""
    engine, server = make_server(ROLES)
    if narrate_on:
        async def _narrate(_data):
            await server.narrate(NarrationMessage(text="line", lang="en"))
        for event in narrate_on:
            engine.on(event, _narrate)

    async with TestServer(make_app(server)) as ts:
        async with aiohttp.ClientSession() as session:
            async def connect():
                return await session.ws_connect(ts.make_url("/ws"))
            try:
                await fn(connect, engine, server)
            finally:
                await server.async_shutdown()


async def _start(ws, roles):
    names = [f"P{i}" for i in range(len(roles))]
    await ws.send_json({"cmd": "start_game", "data": {"players": names, "roles": roles}})
    await drain(ws, until_type="state",
                predicate=lambda m: m["state"]["phase"] == "role_reveal")


HUNTER_ROSTER = ["werewolf", "hunter", "villager", "villager", "villager"]
ALL_VOTE_HUNTER = {"p0": "p1", "p2": "p1", "p3": "p1", "p4": "p1"}


async def test_hunter_voted_out_can_shoot_on_the_same_socket():
    async def _test(connect, engine, server):
        ws = await connect()
        await _start(ws, HUNTER_ROSTER)
        await ws.send_json({"cmd": "begin_vote"})
        await ws.send_json({"cmd": "resolve_vote", "data": {"votes": ALL_VOTE_HUNTER}})
        await drain(ws, until_type="night_role_wake",
                    predicate=lambda m: m["data"]["role"] == "hunter")

        await ws.send_json({"cmd": "submit_pending_action",
                            "data": {"role": "hunter", "action": {"target": "p2"}}})
        msgs = await drain(ws, until_type="state",
                           predicate=lambda m: m["state"]["phase"] == "day")

        dead = {m["data"]["player_id"] for m in msgs if m["type"] == "player_eliminated"}
        assert dead == {"p1", "p2"}

    await _play(_test)


async def test_narration_during_vote_is_released_by_tts_done():
    """tts_done must be read at once, not after the narration's 10 s timeout."""
    async def _test(connect, engine, server):
        ws = await connect()
        await _start(ws, ["werewolf", "villager", "villager", "villager"])
        await ws.send_json({"cmd": "begin_vote"})
        await drain(ws, until_type="narrate")
        await ws.send_json({"cmd": "tts_done"})

        await ws.send_json({"cmd": "resolve_vote",
                            "data": {"votes": {"p1": "p2", "p2": "p1", "p3": "p2"}}})
        await drain(ws, until_type="narrate", timeout=2.0)
        await ws.send_json({"cmd": "tts_done"})
        await drain(ws, until_type="state",
                    predicate=lambda m: m["state"]["phase"] == "day", timeout=2.0)

    await _play(_test, narrate_on=(GameEvent.VOTE_STARTED, GameEvent.VOTE_RESOLVED))


async def test_game_commands_run_in_the_order_they_were_sent():
    """A vote sent during the vote narration waits for it instead of overlapping."""
    async def _test(connect, engine, server):
        ws = await connect()
        await _start(ws, ["werewolf", "villager", "villager", "villager"])
        await ws.send_json({"cmd": "begin_vote"})
        await drain(ws, until_type="narrate")
        await ws.send_json({"cmd": "resolve_vote",
                            "data": {"votes": {"p1": "p0", "p2": "p0", "p3": "p0"}}})
        await asyncio.sleep(0.05)
        assert engine.get_public_state()["phase"] == "vote"

        await ws.send_json({"cmd": "tts_done"})
        await drain(ws, until_type="state",
                    predicate=lambda m: m["state"]["phase"] == "game_over", timeout=2.0)

    await _play(_test, narrate_on=(GameEvent.VOTE_STARTED,))


async def test_failing_background_command_reports_to_the_client():
    async def _test(connect, engine, server):
        ws = await connect()
        await _start(ws, HUNTER_ROSTER)
        await ws.send_json({"cmd": "resolve_vote", "data": {"votes": "not-a-mapping"}})
        msgs = await drain(ws, until_type="error")
        assert msgs[-1]["code"] == "internal_error"

    await _play(_test)


async def test_new_game_replaces_a_game_stuck_on_a_prompt():
    async def _test(connect, engine, server):
        ws = await connect()
        await _start(ws, HUNTER_ROSTER)
        await ws.send_json({"cmd": "resolve_vote", "data": {"votes": ALL_VOTE_HUNTER}})
        await drain(ws, until_type="night_role_wake",
                    predicate=lambda m: m["data"]["role"] == "hunter")

        await _start(ws, ["werewolf", "villager", "villager", "villager"])
        await ws.send_json({"cmd": "begin_night"})
        msgs = await drain(ws, until_type="night_role_wake")
        assert msgs[-1]["data"]["role"] == "werewolf"

    await _play(_test)


# ── Reconnecting during a turn ────────────────────────────────────────────────

async def _reconnect(connect, old_ws):
    await old_ws.close()
    ws = await connect()
    await ws.send_json({"cmd": "get_state"})
    return ws


async def _no_wake_after_state(ws):
    """Sync with a second get_state: anything replayed would arrive before its reply."""
    await ws.send_json({"cmd": "get_config"})
    msgs = await drain(ws, until_type="config")
    assert not [m for m in msgs if m["type"] == "night_role_wake"]


async def test_reconnect_restores_a_night_turn_and_it_can_be_played():
    async def _test(connect, engine, server):
        ws = await connect()
        await _start(ws, ["werewolf", "villager", "villager", "villager", "villager"])
        await ws.send_json({"cmd": "begin_night"})
        first = (await drain(ws, until_type="night_role_wake"))[-1]

        ws = await _reconnect(connect, ws)
        replay = (await drain(ws, until_type="night_role_wake"))[-1]
        assert replay == first

        await ws.send_json({"cmd": "submit_night_action",
                            "data": {"role": "werewolf", "action": {"target": "p1"}}})
        await drain(ws, until_type="state",
                    predicate=lambda m: m["state"]["phase"] == "day")

    await _play(_test)


async def test_reconnect_restores_the_seer_result_not_the_target_prompt():
    async def _test(connect, engine, server):
        ws = await connect()
        await _start(ws, ["seer", "werewolf", "villager", "villager", "villager"])
        await ws.send_json({"cmd": "begin_night"})
        await drain(ws, until_type="night_role_wake")
        await ws.send_json({"cmd": "submit_night_action",
                            "data": {"role": "seer", "action": {"target": "p1"}}})
        await drain(ws, until_type="night_role_wake", predicate=lambda m: "result" in m["data"])

        ws = await _reconnect(connect, ws)
        replay = (await drain(ws, until_type="night_role_wake"))[-1]
        assert replay["data"]["result"]["player_id"] == "p1"

    await _play(_test)


async def test_reconnect_restores_a_hunter_shot_after_a_vote():
    async def _test(connect, engine, server):
        ws = await connect()
        await _start(ws, HUNTER_ROSTER)
        await ws.send_json({"cmd": "resolve_vote", "data": {"votes": ALL_VOTE_HUNTER}})
        await drain(ws, until_type="night_role_wake",
                    predicate=lambda m: m["data"]["role"] == "hunter")

        ws = await _reconnect(connect, ws)
        replay = (await drain(ws, until_type="night_role_wake"))[-1]
        assert replay["data"]["player_id"] == "p1"

        await ws.send_json({"cmd": "submit_pending_action",
                            "data": {"role": "hunter", "action": {"target": "p2"}}})
        await drain(ws, until_type="state",
                    predicate=lambda m: m["state"]["phase"] == "day")

    await _play(_test)


async def test_reconnect_does_not_replay_an_answered_turn():
    async def _test(connect, engine, server):
        ws = await connect()
        await _start(ws, ["werewolf", "villager", "villager", "villager", "villager"])
        await ws.send_json({"cmd": "begin_night"})
        await drain(ws, until_type="night_role_wake")
        await ws.send_json({"cmd": "submit_night_action",
                            "data": {"role": "werewolf", "action": {"target": "p1"}}})
        await drain(ws, until_type="state",
                    predicate=lambda m: m["state"]["phase"] == "day")

        ws = await _reconnect(connect, ws)
        await drain(ws, until_type="state")
        await _no_wake_after_state(ws)

    await _play(_test)


async def test_turn_survives_a_submission_for_another_role():
    """A rejected submission has not answered the turn: it must still be replayed."""
    async def _test(connect, engine, server):
        ws = await connect()
        await _start(ws, ["werewolf", "villager", "villager", "villager", "villager"])
        await ws.send_json({"cmd": "begin_night"})
        await drain(ws, until_type="night_role_wake")
        await ws.send_json({"cmd": "submit_night_action", "data": {"role": "witch", "action": {}}})

        ws = await _reconnect(connect, ws)
        replay = (await drain(ws, until_type="night_role_wake"))[-1]
        assert replay["data"]["role"] == "werewolf"

    await _play(_test)
