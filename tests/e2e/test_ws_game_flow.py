"""The JSON protocol the browser depends on: prompts, answers and snapshots."""
from __future__ import annotations

import aiohttp
import pytest
from aiohttp.test_utils import TestServer

from loup_garou.const import GameEvent
from loup_garou.narration import NarrationMessage
from loup_garou.roles.impl.cupid import Cupid
from loup_garou.roles.impl.elder import Elder
from loup_garou.roles.impl.hunter import Hunter
from loup_garou.roles.impl.scapegoat import Scapegoat
from loup_garou.roles.impl.seer import Seer
from loup_garou.roles.impl.sheriff import Sheriff
from loup_garou.roles.impl.villager import Villager
from loup_garou.roles.impl.werewolf import Werewolf
from loup_garou.roles.impl.witch import Witch
from tests.e2e.conftest import (
    answer, deal, drain, make_app, make_server, prompt_of, vote_out, wait_day_choice, wait_prompt,
)

ROLES = (Villager, Werewolf, Seer, Witch, Hunter, Scapegoat, Cupid, Sheriff, Elder)
FIVE = ["werewolf", "villager", "villager", "villager", "villager"]


async def play(fn, *, narrate_on=()):
    """Run fn(connect, engine, server); connect() opens one more socket."""
    engine, server = make_server(ROLES)

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


def in_phase(phase):
    return lambda m: m["state"]["phase"] == phase


async def wait_phase(ws, phase, timeout=2.0):
    msgs = await drain(ws, until_type="snapshot", predicate=in_phase(phase), timeout=timeout)
    return msgs[-1]["state"], msgs


async def error_code(ws):
    return (await drain(ws, until_type="error"))[-1]["code"]


# ── Basics ────────────────────────────────────────────────────────────────────

async def test_get_state_returns_setup_snapshot():
    async def _test(connect, engine, server):
        ws = await connect()
        await ws.send_json({"cmd": "get_state"})
        state = (await drain(ws, until_type="snapshot"))[-1]["state"]
        assert state["phase"] == "setup"
        assert state["players"] == [] and state["prompt"] is None
    await play(_test)


async def test_unknown_command_returns_error():
    async def _test(connect, engine, server):
        ws = await connect()
        await ws.send_json({"cmd": "bogus"})
        assert "unknown command" in (await drain(ws, until_type="error"))[-1]["msg"]
    await play(_test)


async def test_get_config_returns_config():
    async def _test(connect, engine, server):
        ws = await connect()
        await ws.send_json({"cmd": "get_config"})
        assert "config" in (await drain(ws, until_type="config"))[-1]
    await play(_test)


@pytest.mark.parametrize("result", ["played", "not_started", None])
async def test_test_audio_reports_what_the_speaker_did(result):
    async def _test(connect, engine, server):
        async def _speak():
            return result
        server.set_test_audio_callback(_speak)
        ws = await connect()
        await ws.send_json({"cmd": "test_audio"})
        done = (await drain(ws, until_type="test_audio_done"))[-1]
        assert done["result"] == result
    await play(_test)


async def test_old_game_commands_are_gone():
    async def _test(connect, engine, server):
        ws = await connect()
        await deal(ws, FIVE)
        await wait_prompt(ws, "night_action")
        for cmd in ("begin_night", "begin_vote", "resolve_vote", "submit_night_action",
                    "submit_pending_action", "elect_sheriff"):
            await ws.send_json({"cmd": cmd, "data": {"votes": {"p1": "p2"}, "role": "werewolf"}})
            assert "unknown command" in (await drain(ws, until_type="error"))[-1]["msg"]
        assert all(p["alive"] for p in engine.get_public_state()["players"])
    await play(_test)


# ── Start and reveal ──────────────────────────────────────────────────────────

async def test_start_game_opens_a_reveal_for_each_player_in_turn():
    async def _test(connect, engine, server):
        ws = await connect()
        await ws.send_json({"cmd": "start_game", "data": {
            "players": ["Alice", "Bob", "Carol"], "roles": ["werewolf", "villager", "villager"]}})
        first = await wait_prompt(ws, "reveal")
        assert (first["actor"], first["info"]["role_id"], first["info"]["done"]) == ("p0", "werewolf", 1)
        await answer(ws, first)
        second = await wait_prompt(ws, "reveal")
        assert (second["actor"], second["info"]["role_id"]) == ("p1", "villager")
    await play(_test)


async def test_every_client_receives_the_snapshots():
    async def _test(connect, engine, server):
        ws1, ws2 = await connect(), await connect()
        await ws1.send_json({"cmd": "start_game", "data": {
            "players": ["A", "B", "C"], "roles": ["werewolf", "villager", "villager"]}})
        assert (await wait_prompt(ws1, "reveal"))["id"] == (await wait_prompt(ws2, "reveal"))["id"]
    await play(_test)


async def test_mismatched_start_is_a_bad_request_and_stays_in_setup():
    async def _test(connect, engine, server):
        ws = await connect()
        await ws.send_json({"cmd": "start_game", "data": {
            "players": ["A", "B", "C"], "roles": ["werewolf", "villager"]}})
        assert await error_code(ws) == "bad_request"
        assert engine.get_public_state()["phase"] == "setup"
    await play(_test)


@pytest.mark.parametrize("players, reason", [
    (["A", "B"], "need_players"),
    (["A", " ", "C"], "empty_name"),
    (["A", "B", "C" * 21], "long_name"),
    (["A", "B", "{name}"], "bad_chars"),
    (["Alice", "Bob", "alice "], "duplicate"),
])
async def test_start_game_checks_the_names_like_the_setup_screen(players, reason):
    async def _test(connect, engine, server):
        ws = await connect()
        roles = ["werewolf"] + ["villager"] * (len(players) - 1)
        await ws.send_json({"cmd": "start_game", "data": {"players": players, "roles": roles}})
        error = (await drain(ws, until_type="error"))[-1]
        assert (error["code"], error["reason"]) == ("invalid_setup", reason)
        assert engine.get_public_state()["phase"] == "setup"
    await play(_test)


async def test_start_game_trims_the_names():
    async def _test(connect, engine, server):
        ws = await connect()
        await ws.send_json({"cmd": "start_game", "data": {
            "players": [" Alice", "Bob ", "Carol"], "roles": ["werewolf", "villager", "villager"]}})
        await wait_prompt(ws, "reveal")
        assert [p["name"] for p in engine.get_public_state()["players"]] == ["Alice", "Bob", "Carol"]
    await play(_test)


async def test_start_game_during_a_game_is_refused():
    async def _test(connect, engine, server):
        ws = await connect()
        await deal(ws, FIVE)
        await wait_prompt(ws, "night_action")
        await ws.send_json({"cmd": "start_game", "data": {"players": ["A"], "roles": ["villager"]}})
        assert await error_code(ws) == "game_in_progress"
        assert len(engine.get_public_state()["players"]) == 5
    await play(_test)


# ── Answers ───────────────────────────────────────────────────────────────────

async def test_double_tap_is_ignored():
    async def _test(connect, engine, server):
        ws = await connect()
        await ws.send_json({"cmd": "start_game", "data": {
            "players": ["A", "B", "C"], "roles": ["werewolf", "villager", "villager"]}})
        first = await wait_prompt(ws, "reveal")
        await answer(ws, first)
        await answer(ws, first)
        await ws.send_json({"cmd": "get_config"})
        msgs = await drain(ws, until_type="config")
        assert not [m for m in msgs if m["type"] == "error"]
        assert engine.prompt.actor == "p1"
    await play(_test)


async def test_stale_answer_gets_an_error_and_a_fresh_snapshot():
    async def _test(connect, engine, server):
        ws = await connect()
        await deal(ws, FIVE)
        prompt = await wait_prompt(ws, "night_action")
        await ws.send_json({"cmd": "answer", "data": {"prompt_id": "q999", "answer": {}}})
        assert await error_code(ws) == "stale_prompt"
        assert (await wait_prompt(ws, "night_action"))["id"] == prompt["id"]
    await play(_test)


async def test_illegal_answer_leaves_the_prompt_open():
    async def _test(connect, engine, server):
        ws = await connect()
        await deal(ws, FIVE)
        prompt = await wait_prompt(ws, "night_action", "werewolf")
        await answer(ws, prompt, target="p0")   # wolves can't eat a wolf
        assert await error_code(ws) == "illegal_answer"
        assert (await wait_prompt(ws, "night_action", "werewolf"))["id"] == prompt["id"]
        await answer(ws, prompt, target="p1")
        await wait_phase(ws, "day")
    await play(_test)


async def test_answer_without_prompt_id_is_a_bad_request():
    async def _test(connect, engine, server):
        ws = await connect()
        await ws.send_json({"cmd": "answer", "data": {}})
        assert await error_code(ws) == "bad_request"
    await play(_test)


# ── Secrets ───────────────────────────────────────────────────────────────────

async def test_snapshots_hide_living_roles_until_the_game_is_over():
    async def _test(connect, engine, server):
        ws = await connect()
        await deal(ws, FIVE)
        await answer(ws, await wait_prompt(ws, "night_action"), target="p1")
        state, _ = await wait_phase(ws, "day")
        assert {p["id"] for p in state["players"] if "role_id" in p} == {"p1"}

        await vote_out(ws, "p0", ["p0", "p2", "p3", "p4"])
        state, _ = await wait_phase(ws, "game_over")
        assert all("role_id" in p for p in state["players"])
    await play(_test)


# ── Night ─────────────────────────────────────────────────────────────────────

async def test_wolf_kill_is_reported_in_the_news():
    async def _test(connect, engine, server):
        ws = await connect()
        await deal(ws, FIVE)
        prompt = await wait_prompt(ws, "night_action", "werewolf")
        assert prompt["picks"]["target"]["options"] == ["p1", "p2", "p3", "p4"]
        await answer(ws, prompt, target="p1")
        state, _ = await wait_phase(ws, "day")
        assert state["news"]["source"] == "night"
        assert [(d["player_id"], d["cause"]) for d in state["news"]["deaths"]] == [("p1", "wolf_kill")]
    await play(_test)


async def test_wolf_kill_can_end_the_game():
    async def _test(connect, engine, server):
        ws = await connect()
        await deal(ws, ["werewolf", "villager", "villager"])
        await answer(ws, await wait_prompt(ws, "night_action"), target="p1")
        state, _ = await wait_phase(ws, "game_over")
        assert state["winner"] == "wolves"
        assert state["prompt"] is None or state["prompt"]["kind"] == "new_game"
    await play(_test)


async def test_seer_sees_the_role_then_acknowledges():
    async def _test(connect, engine, server):
        ws = await connect()
        await deal(ws, ["seer", "werewolf", "villager", "villager", "villager"])
        await answer(ws, await wait_prompt(ws, "night_action", "seer"), target="p1")
        result = await wait_prompt(ws, "seer_result")
        assert result["info"]["player_id"] == "p1" and result["info"]["role_id"] == "werewolf"
        await answer(ws, result)
        await wait_prompt(ws, "night_action", "werewolf")
    await play(_test)


async def test_seer_skip_shows_no_result():
    async def _test(connect, engine, server):
        ws = await connect()
        await deal(ws, ["seer", "werewolf", "villager", "villager", "villager"])
        await answer(ws, await wait_prompt(ws, "night_action", "seer"))
        msgs = await drain(ws, until_type="snapshot", predicate=prompt_of("night_action", "werewolf"))
        assert not [m for m in msgs if m["state"]["prompt"] and m["state"]["prompt"]["kind"] == "seer_result"]
    await play(_test)


async def test_witch_is_offered_the_victim_and_saves_them():
    async def _test(connect, engine, server):
        ws = await connect()
        await deal(ws, ["werewolf", "witch", "villager", "villager", "villager"])
        await answer(ws, await wait_prompt(ws, "night_action", "werewolf"), target="p2")
        witch = await wait_prompt(ws, "night_action", "witch")
        assert [v["id"] for v in witch["info"]["victims"]] == ["p2"]
        assert witch["picks"]["save_target"]["options"] == ["p2"]
        assert "p2" not in witch["picks"]["poison_target"]["options"]

        await answer(ws, witch, save_target="p2")
        state, _ = await wait_phase(ws, "day")
        assert state["news"]["deaths"] == []
    await play(_test)


async def test_used_potion_is_no_longer_offered():
    async def _test(connect, engine, server):
        ws = await connect()
        await deal(ws, ["werewolf", "witch", "villager", "villager", "villager"])
        await answer(ws, await wait_prompt(ws, "night_action", "werewolf"), target="p2")
        await answer(ws, await wait_prompt(ws, "night_action", "witch"), save_target="p2")

        await answer(ws, await wait_day_choice(ws), next="night")
        await answer(ws, await wait_prompt(ws, "night_action", "werewolf"), target="p3")
        witch = await wait_prompt(ws, "night_action", "witch")
        assert witch["info"]["save_used"] is True
        assert witch["picks"]["save_target"]["options"] == []
    await play(_test)


async def test_protected_elder_is_not_offered_to_the_witch():
    async def _test(connect, engine, server):
        ws = await connect()
        await deal(ws, ["werewolf", "witch", "elder", "villager", "villager"])
        await answer(ws, await wait_prompt(ws, "night_action", "werewolf"), target="p2")
        witch = await wait_prompt(ws, "night_action", "witch")
        assert witch["info"]["victims"] == []
        assert witch["picks"]["save_target"]["options"] == []
    await play(_test)


# ── Day and vote ──────────────────────────────────────────────────────────────

async def test_vote_takes_one_ballot_per_living_player_excluding_themselves():
    async def _test(connect, engine, server):
        ws = await connect()
        await deal(ws, FIVE)
        await answer(ws, await wait_prompt(ws, "night_action"), target="p1")
        await answer(ws, await wait_day_choice(ws, options=["vote", "night"]), next="vote")
        for voter in ("p0", "p2", "p3", "p4"):
            ballot = await wait_prompt(ws, "ballot")
            assert ballot["actor"] == voter
            assert voter not in ballot["picks"]["target"]["options"]
            assert "p1" not in ballot["picks"]["target"]["options"]
            await answer(ws, ballot, target="p0" if voter != "p0" else "p2")
        state, _ = await wait_phase(ws, "game_over")
        assert state["winner"] == "village"
    await play(_test)


async def test_one_vote_a_day_then_only_night_is_offered():
    async def _test(connect, engine, server):
        ws = await connect()
        await deal(ws, ["werewolf"] + ["villager"] * 6)
        await answer(ws, await wait_prompt(ws, "night_action"), target="p1")
        await vote_out(ws, "p2", ["p0", "p2", "p3", "p4", "p5", "p6"])
        state, _ = await wait_phase(ws, "day")
        assert state["news"]["source"] == "vote"
        assert [d["player_id"] for d in state["news"]["deaths"]] == ["p2"]
        await answer(ws, await wait_day_choice(ws, options=["night"]), next="night")
        await wait_phase(ws, "night")
    await play(_test)


async def test_tie_kills_no_one_and_is_reported():
    async def _test(connect, engine, server):
        ws = await connect()
        await deal(ws, ["werewolf", "villager", "villager", "villager"])
        await answer(ws, await wait_prompt(ws, "night_action"))
        await answer(ws, await wait_day_choice(ws), next="vote")
        for target in ("p1", "p0", "p0", "p1"):
            await answer(ws, await wait_prompt(ws, "ballot"), target=target)
        state, _ = await wait_phase(ws, "day")
        assert state["news"]["tie"] is True and state["news"]["deaths"] == []
    await play(_test)


async def test_scapegoat_dies_on_a_tie():
    async def _test(connect, engine, server):
        ws = await connect()
        await deal(ws, ["werewolf", "scapegoat", "villager", "villager"])
        await answer(ws, await wait_prompt(ws, "night_action"))
        await answer(ws, await wait_day_choice(ws), next="vote")
        for target in ("p2", "p0", "p0", "p2"):
            await answer(ws, await wait_prompt(ws, "ballot"), target=target)
        state, _ = await wait_phase(ws, "day")
        assert [(d["player_id"], d["cause"]) for d in state["news"]["deaths"]] == [("p1", "scapegoat")]
    await play(_test)


async def test_two_nights_in_a_row():
    async def _test(connect, engine, server):
        ws = await connect()
        await deal(ws, ["werewolf"] + ["villager"] * 6)
        await answer(ws, await wait_prompt(ws, "night_action"), target="p1")
        await answer(ws, await wait_day_choice(ws), next="night")
        await answer(ws, await wait_prompt(ws, "night_action"), target="p2")
        state, _ = await wait_phase(ws, "day")
        assert state["night"] == 2
    await play(_test)


async def test_sheriff_is_elected_on_the_first_day_and_votes_double():
    async def _test(connect, engine, server):
        ws = await connect()
        await deal(ws, ["werewolf", "sheriff", "villager", "villager"])
        await answer(ws, await wait_prompt(ws, "night_action"))
        election = await wait_prompt(ws, "sheriff_election")
        await answer(ws, election, target="p2")
        await answer(ws, await wait_day_choice(ws), next="vote")
        # p0 gets p1's vote and the sheriff's double vote: 3 against 2 for p1.
        for target in ("p1", "p0", "p0", "p1"):
            await answer(ws, await wait_prompt(ws, "ballot"), target=target)
        state, _ = await wait_phase(ws, "game_over")
        assert state["winner"] == "village"
        assert next(p for p in state["players"] if p["id"] == "p2")["sheriff"] is True
    await play(_test)


# ── Regressions: the one phone must always be able to answer ─────────────────

async def test_hunter_voted_out_shoots_on_the_same_socket():
    async def _test(connect, engine, server):
        ws = await connect()
        await deal(ws, ["werewolf", "hunter", "villager", "villager", "villager", "villager", "villager"])
        await answer(ws, await wait_prompt(ws, "night_action"))
        await vote_out(ws, "p1", ["p0", "p1", "p2", "p3", "p4", "p5", "p6"])

        shot = await wait_prompt(ws, "hunter_shot")
        assert shot["actor"] == "p1" and "p1" not in shot["picks"]["target"]["options"]
        await answer(ws, shot, target="p2")
        state, _ = await wait_phase(ws, "day")
        assert [(d["player_id"], d["cause"]) for d in state["news"]["deaths"]] == [
            ("p1", "village_vote"), ("p2", "hunter_shot"),
        ]
    await play(_test)


async def test_hunter_shot_by_wolves_shoots_at_dawn():
    async def _test(connect, engine, server):
        ws = await connect()
        await deal(ws, ["werewolf", "hunter", "villager", "villager", "villager", "villager"])
        await answer(ws, await wait_prompt(ws, "night_action"), target="p1")
        await answer(ws, await wait_prompt(ws, "hunter_shot"), target="p2")
        state, _ = await wait_phase(ws, "day")
        assert [(d["player_id"], d["cause"]) for d in state["news"]["deaths"]] == [
            ("p1", "wolf_kill"), ("p2", "hunter_shot"),
        ]
    await play(_test)


async def test_narration_is_released_by_tts_done_during_a_vote():
    """tts_done must be read at once, not after the narration's 10 s timeout."""
    async def _test(connect, engine, server):
        ws = await connect()
        await deal(ws, FIVE)
        await answer(ws, await wait_prompt(ws, "night_action"))
        await answer(ws, await wait_day_choice(ws), next="vote")
        await drain(ws, until_type="narrate")
        await ws.send_json({"cmd": "tts_done"})
        await wait_prompt(ws, "ballot")
    await play(_test, narrate_on=(GameEvent.VOTE_STARTED,))


async def test_role_prompt_opens_only_after_its_wake_narration():
    """An action can't be sent during narration: no control exists to send it."""
    async def _test(connect, engine, server):
        ws = await connect()
        await deal(ws, FIVE)
        msgs = await drain(ws, until_type="narrate")
        latest = [m for m in msgs if m["type"] == "snapshot"][-1]["state"]
        assert latest["phase"] == "night" and latest["prompt"] is None
        assert engine.prompt is None

        await ws.send_json({"cmd": "tts_done"})
        await answer(ws, await wait_prompt(ws, "night_action", "werewolf"), target="p1")
        await wait_phase(ws, "day")
    await play(_test, narrate_on=(GameEvent.NIGHT_ROLE_WAKE,))


# ── Reconnecting: the snapshot is everything ─────────────────────────────────

async def _reconnect(connect, ws):
    await ws.close()
    ws = await connect()
    await ws.send_json({"cmd": "get_state"})
    return (await drain(ws, until_type="snapshot"))[-1]["state"], ws


async def test_reconnect_restores_a_night_turn_which_can_then_be_played():
    async def _test(connect, engine, server):
        ws = await connect()
        await deal(ws, FIVE)
        prompt = await wait_prompt(ws, "night_action")
        state, ws = await _reconnect(connect, ws)
        assert state["prompt"]["id"] == prompt["id"]
        await answer(ws, prompt, target="p1")
        await wait_phase(ws, "day")
    await play(_test)


async def test_reconnect_restores_the_seer_result():
    async def _test(connect, engine, server):
        ws = await connect()
        await deal(ws, ["seer", "werewolf", "villager", "villager", "villager"])
        await answer(ws, await wait_prompt(ws, "night_action", "seer"), target="p1")
        await wait_prompt(ws, "seer_result")
        state, ws = await _reconnect(connect, ws)
        assert state["prompt"]["kind"] == "seer_result"
        assert state["prompt"]["info"]["player_id"] == "p1"
    await play(_test)


async def test_reconnect_mid_vote_keeps_earlier_ballots():
    async def _test(connect, engine, server):
        ws = await connect()
        await deal(ws, FIVE)
        await answer(ws, await wait_prompt(ws, "night_action"))
        await answer(ws, await wait_day_choice(ws), next="vote")
        for _ in range(4):
            await answer(ws, await wait_prompt(ws, "ballot"), target="p0" if engine.prompt.actor != "p0" else "p1")
        last = await wait_prompt(ws, "ballot")
        state, ws = await _reconnect(connect, ws)
        assert state["prompt"]["id"] == last["id"]
        assert state["prompt"]["info"]["done"] == 4
        await answer(ws, last, target="p0")
        state, _ = await wait_phase(ws, "game_over")
        assert state["winner"] == "village"
    await play(_test)


# ── Ending ────────────────────────────────────────────────────────────────────

async def test_new_game_prompt_returns_to_setup_and_a_game_can_start_again():
    async def _test(connect, engine, server):
        ws = await connect()
        await deal(ws, ["werewolf", "villager", "villager"])
        await answer(ws, await wait_prompt(ws, "night_action"), target="p1")
        await answer(ws, await wait_prompt(ws, "new_game"))
        await wait_phase(ws, "setup")
        await deal(ws, ["werewolf", "villager", "villager"])
        await wait_prompt(ws, "night_action")
    await play(_test)


async def test_abandon_game_returns_to_setup_from_any_prompt():
    async def _test(connect, engine, server):
        ws = await connect()
        await deal(ws, FIVE)
        await wait_prompt(ws, "night_action")
        await ws.send_json({"cmd": "abandon_game"})
        state, _ = await wait_phase(ws, "setup")
        assert state["prompt"] is None and state["players"] == []
        assert server._game_task is None

        await deal(ws, FIVE)
        await wait_prompt(ws, "night_action")
    await play(_test)
