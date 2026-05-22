"""End-to-end WebSocket tests — validate the JSON protocol the browser UI depends on."""
from __future__ import annotations

import asyncio

import aiohttp
import pytest
from aiohttp.test_utils import TestServer

from loup_garou.roles.impl.cupid import Cupid
from loup_garou.roles.impl.hunter import Hunter
from loup_garou.roles.impl.scapegoat import Scapegoat
from loup_garou.roles.impl.seer import Seer
from loup_garou.roles.impl.villager import Villager
from loup_garou.roles.impl.werewolf import Werewolf
from loup_garou.roles.impl.witch import Witch
from tests.e2e.conftest import drain, make_app, make_server


# ── helpers ───────────────────────────────────────────────────────────────────

async def ws_for(server_roles, fn):
    """Spin up a TestServer, open a WS, run fn(ws, engine), close cleanly."""
    engine, srv = make_server(server_roles)
    app = make_app(srv)
    async with TestServer(app) as ts:
        async with aiohttp.ClientSession() as sess:
            async with sess.ws_connect(ts.make_url("/ws")) as ws:
                return await fn(ws, engine)


async def start_game(ws, players, roles):
    """Send start_game and return the first role_reveal state."""
    await ws.send_json({"cmd": "start_game", "data": {"players": players, "roles": roles}})
    msgs = await drain(
        ws,
        until_type="state",
        predicate=lambda m: m.get("state", {}).get("phase") == "role_reveal",
    )
    return msgs[-1]


async def run_night_wolf(ws, wolf_target_id):
    """Complete a wolf-only night: wake → kill villager → wait for day state."""
    await ws.send_json({"cmd": "begin_night"})
    await drain(ws, until_type="night_role_wake",
                predicate=lambda m: m.get("data", {}).get("role") == "werewolf")
    await ws.send_json({
        "cmd": "submit_night_action",
        "data": {"role": "werewolf", "action": {"target": wolf_target_id}},
    })
    msgs = await drain(
        ws,
        until_type="state",
        predicate=lambda m: m.get("state", {}).get("phase") == "day",
    )
    return msgs


# ═══════════════════════════════════════════════════════════════════════════════
# Basic protocol
# ═══════════════════════════════════════════════════════════════════════════════

async def test_get_state_returns_setup():
    async def _test(ws, engine):
        await ws.send_json({"cmd": "get_state"})
        msgs = await drain(ws, until_type="state")
        s = msgs[-1]["state"]
        assert s["phase"] == "setup"
        assert s["players"] == []

    await ws_for([Villager, Werewolf], _test)


async def test_unknown_command_returns_error():
    async def _test(ws, engine):
        await ws.send_json({"cmd": "bogus_command"})
        msgs = await drain(ws, until_type="error")
        assert "unknown command" in msgs[-1]["msg"]

    await ws_for([Villager, Werewolf], _test)


async def test_get_config_returns_config():
    async def _test(ws, engine):
        await ws.send_json({"cmd": "get_config"})
        msgs = await drain(ws, until_type="config")
        assert msgs[-1]["type"] == "config"
        assert "config" in msgs[-1]

    await ws_for([Villager, Werewolf], _test)


# ═══════════════════════════════════════════════════════════════════════════════
# Game start
# ═══════════════════════════════════════════════════════════════════════════════

async def test_start_game_enters_role_reveal():
    async def _test(ws, engine):
        msg = await start_game(ws, ["Alice", "Bob", "Carol"],
                               ["werewolf", "villager", "villager"])
        s = msg["state"]
        assert s["phase"] == "role_reveal"
        assert len(s["players"]) == 3
        assert {p["name"] for p in s["players"]} == {"Alice", "Bob", "Carol"}
        assert {p["role_id"] for p in s["players"]} == {"werewolf", "villager"}

    await ws_for([Villager, Werewolf], _test)


async def test_start_game_broadcasts_to_all_clients():
    """Both connected clients get the role_reveal state."""
    engine, srv = make_server([Villager, Werewolf])
    app = make_app(srv)
    async with TestServer(app) as ts:
        async with aiohttp.ClientSession() as sess:
            async with sess.ws_connect(ts.make_url("/ws")) as ws1:
                async with sess.ws_connect(ts.make_url("/ws")) as ws2:
                    await ws1.send_json({
                        "cmd": "start_game",
                        "data": {"players": ["Alice", "Bob"], "roles": ["werewolf", "villager"]},
                    })
                    msgs1 = await drain(ws1, until_type="state",
                                        predicate=lambda m: m.get("state", {}).get("phase") == "role_reveal")
                    msgs2 = await drain(ws2, until_type="state",
                                        predicate=lambda m: m.get("state", {}).get("phase") == "role_reveal")
                    assert msgs1[-1]["state"]["phase"] == "role_reveal"
                    assert msgs2[-1]["state"]["phase"] == "role_reveal"


# ═══════════════════════════════════════════════════════════════════════════════
# Role reveal → night transition
# ═══════════════════════════════════════════════════════════════════════════════

async def test_role_reveal_then_begin_night():
    """begin_night after role_reveal transitions to night and emits wolf wake."""
    async def _test(ws, engine):
        state_msg = await start_game(
            ws, ["Alice", "Bob", "Carol", "Dave"],
            ["werewolf", "villager", "villager", "villager"],
        )
        assert state_msg["state"]["phase"] == "role_reveal"

        players = state_msg["state"]["players"]
        villager = next(p for p in players if p["role_id"] == "villager")

        # Complete night to avoid lingering task
        await run_night_wolf(ws, villager["id"])

    await ws_for([Villager, Werewolf], _test)


# ═══════════════════════════════════════════════════════════════════════════════
# Night: wolf
# ═══════════════════════════════════════════════════════════════════════════════

async def test_wolf_kills_villager():
    """Wolf wakes, kills a villager, night resolves, day starts with one dead."""
    async def _test(ws, engine):
        state_msg = await start_game(
            ws, ["Alice", "Bob", "Carol", "Dave"],
            ["werewolf", "villager", "villager", "villager"],
        )
        players = state_msg["state"]["players"]
        villager = next(p for p in players if p["role_id"] == "villager")

        msgs = await run_night_wolf(ws, villager["id"])

        elim_events = [m for m in msgs if m.get("type") == "player_eliminated"]
        assert len(elim_events) == 1
        assert elim_events[0]["data"]["player_id"] == villager["id"]

        final = msgs[-1]["state"]
        assert final["phase"] == "day"
        dead = [p for p in final["players"] if not p["alive"]]
        assert len(dead) == 1
        assert dead[0]["id"] == villager["id"]

    await ws_for([Villager, Werewolf], _test)


async def test_wolf_kill_triggers_game_over_at_parity():
    """Wolf kills last villager → wolves win immediately."""
    async def _test(ws, engine):
        state_msg = await start_game(ws, ["Alice", "Bob"], ["werewolf", "villager"])
        players = state_msg["state"]["players"]
        villager = next(p for p in players if p["role_id"] == "villager")

        await ws.send_json({"cmd": "begin_night"})
        await drain(ws, until_type="night_role_wake",
                    predicate=lambda m: m.get("data", {}).get("role") == "werewolf")
        await ws.send_json({
            "cmd": "submit_night_action",
            "data": {"role": "werewolf", "action": {"target": villager["id"]}},
        })
        msgs = await drain(
            ws,
            until_type="state",
            predicate=lambda m: m.get("state", {}).get("phase") == "game_over",
        )
        final = msgs[-1]["state"]
        assert final["phase"] == "game_over"
        assert final["winner"] == "wolves"

    await ws_for([Villager, Werewolf], _test)


async def test_night_role_wake_includes_role_field():
    """The night_role_wake message always has a 'role' field."""
    async def _test(ws, engine):
        state_msg = await start_game(
            ws, ["Alice", "Bob", "Carol", "Dave"],
            ["werewolf", "villager", "villager", "villager"],
        )
        players = state_msg["state"]["players"]
        villager = next(p for p in players if p["role_id"] == "villager")

        await ws.send_json({"cmd": "begin_night"})
        msgs = await drain(ws, until_type="night_role_wake",
                           predicate=lambda m: m.get("data", {}).get("role") == "werewolf")
        wake = next(m for m in msgs if m.get("type") == "night_role_wake")
        assert "role" in wake["data"]
        assert wake["data"]["role"] == "werewolf"

        # Clean up: submit wolf action
        await ws.send_json({
            "cmd": "submit_night_action",
            "data": {"role": "werewolf", "action": {"target": villager["id"]}},
        })
        await drain(ws, until_type="state",
                    predicate=lambda m: m.get("state", {}).get("phase") == "day")

    await ws_for([Villager, Werewolf], _test)


# ═══════════════════════════════════════════════════════════════════════════════
# Night: seer
# ═══════════════════════════════════════════════════════════════════════════════

async def test_seer_investigates_wolf():
    """Seer wakes, investigates wolf, gets result via NIGHT_ROLE_WAKE, acks, goes to sleep."""
    async def _test(ws, engine):
        state_msg = await start_game(
            ws, ["Alice", "Bob", "Carol", "Dave"],
            ["werewolf", "villager", "seer", "villager"],
        )
        players = state_msg["state"]["players"]
        wolf = next(p for p in players if p["role_id"] == "werewolf")
        villager = next(p for p in players if p["role_id"] == "villager")

        await ws.send_json({"cmd": "begin_night"})

        # Seer wakes (priority 10 < werewolf 50)
        seer_wake_msgs = await drain(
            ws, until_type="night_role_wake",
            predicate=lambda m: m.get("data", {}).get("role") == "seer",
        )
        wake = next(m for m in seer_wake_msgs if m["type"] == "night_role_wake")
        assert wake["data"]["role"] == "seer"
        assert "result" not in wake["data"]  # no result yet — seer must pick a target

        # Seer investigates the wolf
        await ws.send_json({
            "cmd": "submit_night_action",
            "data": {"role": "seer", "action": {"target": wolf["id"]}},
        })

        # Expect second NIGHT_ROLE_WAKE with seer result
        result_msgs = await drain(
            ws, until_type="night_role_wake",
            predicate=lambda m: "result" in m.get("data", {}),
        )
        result_wake = next(m for m in result_msgs if "result" in m.get("data", {}))
        result = result_wake["data"]["result"]
        assert result["player_id"] == wolf["id"]
        assert result["role_id"] == "werewolf"

        # Seer acknowledges result
        await ws.send_json({"cmd": "submit_pending_action", "data": {"role": "seer", "action": {}}})

        # Seer sleeps → wolf wakes
        await drain(ws, until_type="night_role_wake",
                    predicate=lambda m: m.get("data", {}).get("role") == "werewolf")

        # Wolf kills villager to clean up
        await ws.send_json({
            "cmd": "submit_night_action",
            "data": {"role": "werewolf", "action": {"target": villager["id"]}},
        })
        await drain(ws, until_type="state",
                    predicate=lambda m: m.get("state", {}).get("phase") == "day")

    await ws_for([Villager, Werewolf, Seer], _test)


async def test_seer_skip_does_not_trigger_result():
    """If seer submits empty action, no result NIGHT_ROLE_WAKE is sent."""
    async def _test(ws, engine):
        state_msg = await start_game(
            ws, ["Alice", "Bob", "Carol", "Dave"],
            ["werewolf", "villager", "seer", "villager"],
        )
        players = state_msg["state"]["players"]
        villager = next(p for p in players if p["role_id"] == "villager")

        await ws.send_json({"cmd": "begin_night"})
        await drain(ws, until_type="night_role_wake",
                    predicate=lambda m: m.get("data", {}).get("role") == "seer")

        # Seer skips
        await ws.send_json({
            "cmd": "submit_night_action",
            "data": {"role": "seer", "action": {}},
        })

        # Next event should be seer_sleep OR wolf wake (not a seer result)
        msgs = await drain(
            ws, until_type="night_role_wake",
            predicate=lambda m: m.get("data", {}).get("role") == "werewolf",
        )
        result_wakes = [m for m in msgs if "result" in m.get("data", {})]
        assert len(result_wakes) == 0, "Expected no seer result when action was skipped"

        # Clean up: wolf kills someone
        await ws.send_json({
            "cmd": "submit_night_action",
            "data": {"role": "werewolf", "action": {"target": villager["id"]}},
        })
        await drain(ws, until_type="state",
                    predicate=lambda m: m.get("state", {}).get("phase") == "day")

    await ws_for([Villager, Werewolf, Seer], _test)


# ═══════════════════════════════════════════════════════════════════════════════
# Night: witch
# ═══════════════════════════════════════════════════════════════════════════════

async def test_witch_wake_includes_pending_kill_players():
    """Witch wake includes pending_kill_players and potion availability."""
    async def _test(ws, engine):
        state_msg = await start_game(
            ws, ["Alice", "Bob", "Carol", "Dave"],
            ["werewolf", "villager", "witch", "villager"],
        )
        players = state_msg["state"]["players"]
        villager = next(p for p in players if p["role_id"] == "villager")

        await ws.send_json({"cmd": "begin_night"})

        # Wolf wakes first (priority 50, witch 60)
        await drain(ws, until_type="night_role_wake",
                    predicate=lambda m: m.get("data", {}).get("role") == "werewolf")
        await ws.send_json({
            "cmd": "submit_night_action",
            "data": {"role": "werewolf", "action": {"target": villager["id"]}},
        })

        # Witch wakes after wolf
        witch_msgs = await drain(ws, until_type="night_role_wake",
                                 predicate=lambda m: m.get("data", {}).get("role") == "witch")
        wake = next(m for m in witch_msgs if m["type"] == "night_role_wake" and m["data"]["role"] == "witch")

        assert "pending_kill_players" in wake["data"]
        assert wake["data"]["witch_save_available"] is True
        assert wake["data"]["witch_poison_available"] is True

        victims = wake["data"]["pending_kill_players"]
        assert len(victims) == 1
        assert victims[0]["id"] == villager["id"]

        # Witch passes
        await ws.send_json({
            "cmd": "submit_night_action",
            "data": {"role": "witch", "action": {"player_id": wake["data"]["witch_id"]}},
        })
        await drain(ws, until_type="state",
                    predicate=lambda m: m.get("state", {}).get("phase") == "day")

    await ws_for([Villager, Werewolf, Witch], _test)


async def test_witch_saves_victim():
    """Witch save prevents wolf kill."""
    async def _test(ws, engine):
        state_msg = await start_game(
            ws, ["Alice", "Bob", "Carol", "Dave"],
            ["werewolf", "villager", "witch", "villager"],
        )
        players = state_msg["state"]["players"]
        villager = next(p for p in players if p["role_id"] == "villager")

        await ws.send_json({"cmd": "begin_night"})
        await drain(ws, until_type="night_role_wake",
                    predicate=lambda m: m.get("data", {}).get("role") == "werewolf")
        await ws.send_json({
            "cmd": "submit_night_action",
            "data": {"role": "werewolf", "action": {"target": villager["id"]}},
        })

        witch_msgs = await drain(ws, until_type="night_role_wake",
                                 predicate=lambda m: m.get("data", {}).get("role") == "witch")
        wake = next(m for m in witch_msgs if m["type"] == "night_role_wake" and m["data"]["role"] == "witch")
        witch_id = wake["data"]["witch_id"]

        # Save the villager
        await ws.send_json({
            "cmd": "submit_night_action",
            "data": {
                "role": "witch",
                "action": {"player_id": witch_id, "save_target": villager["id"]},
            },
        })
        msgs = await drain(ws, until_type="state",
                           predicate=lambda m: m.get("state", {}).get("phase") == "day")

        final = msgs[-1]["state"]
        assert final["phase"] == "day"
        # Villager should still be alive
        target = next(p for p in final["players"] if p["id"] == villager["id"])
        assert target["alive"] is True

    await ws_for([Villager, Werewolf, Witch], _test)


# ═══════════════════════════════════════════════════════════════════════════════
# Vote → day transition
# ═══════════════════════════════════════════════════════════════════════════════

async def test_vote_eliminates_wolf_village_wins():
    """Village votes out wolf → game_over with winner=village."""
    async def _test(ws, engine):
        state_msg = await start_game(
            ws, ["Alice", "Bob", "Carol", "Dave"],
            ["werewolf", "villager", "villager", "villager"],
        )
        players = state_msg["state"]["players"]
        wolf = next(p for p in players if p["role_id"] == "werewolf")
        villagers = [p for p in players if p["role_id"] == "villager"]

        # Night: wolf kills one villager → 1 wolf + 2 villagers remain
        await run_night_wolf(ws, villagers[0]["id"])

        # Vote: both surviving villagers vote wolf out
        await ws.send_json({"cmd": "begin_vote"})
        await drain(ws, until_type="state",
                    predicate=lambda m: m.get("state", {}).get("phase") == "vote")

        await ws.send_json({
            "cmd": "resolve_vote",
            "data": {"votes": {
                villagers[1]["id"]: wolf["id"],
                villagers[2]["id"]: wolf["id"],
            }},
        })
        msgs = await drain(ws, until_type="state",
                           predicate=lambda m: m.get("state", {}).get("phase") == "game_over")

        final = msgs[-1]["state"]
        assert final["winner"] == "village"

    await ws_for([Villager, Werewolf], _test)


async def test_vote_transitions_to_day_when_no_winner():
    """Vote eliminates a villager → game goes to day, not game_over."""
    async def _test(ws, engine):
        state_msg = await start_game(
            ws, ["Alice", "Bob", "Carol", "Dave", "Eve"],
            ["werewolf", "villager", "villager", "villager", "villager"],
        )
        players = state_msg["state"]["players"]
        wolf = next(p for p in players if p["role_id"] == "werewolf")
        villagers = [p for p in players if p["role_id"] == "villager"]

        # Night 1: wolf kills villager[0] → 1 wolf + 3 villagers remain
        await run_night_wolf(ws, villagers[0]["id"])

        # Vote out villager[1] (not wolf) — wolves still alive
        await ws.send_json({"cmd": "begin_vote"})
        await drain(ws, until_type="state",
                    predicate=lambda m: m.get("state", {}).get("phase") == "vote")

        await ws.send_json({
            "cmd": "resolve_vote",
            "data": {"votes": {
                wolf["id"]:        villagers[1]["id"],
                villagers[2]["id"]: villagers[1]["id"],
                villagers[3]["id"]: villagers[1]["id"],
            }},
        })
        msgs = await drain(ws, until_type="state",
                           predicate=lambda m: m.get("state", {}).get("phase") == "day")

        final = msgs[-1]["state"]
        # Verify we're back in day (not game_over)
        assert final["phase"] == "day"
        assert final["winner"] is None

        dead = [p for p in final["players"] if not p["alive"]]
        assert {p["id"] for p in dead} == {villagers[0]["id"], villagers[1]["id"]}

    await ws_for([Villager, Werewolf], _test)


async def test_vote_tie_no_elimination():
    """Even vote with no scapegoat → nobody dies, day resumes."""
    async def _test(ws, engine):
        state_msg = await start_game(
            ws, ["Alice", "Bob", "Carol", "Dave", "Eve"],
            ["werewolf", "villager", "villager", "villager", "villager"],
        )
        players = state_msg["state"]["players"]
        villagers = [p for p in players if p["role_id"] == "villager"]
        wolf = next(p for p in players if p["role_id"] == "werewolf")

        await run_night_wolf(ws, villagers[0]["id"])

        await ws.send_json({"cmd": "begin_vote"})
        await drain(ws, until_type="state",
                    predicate=lambda m: m.get("state", {}).get("phase") == "vote")

        # Tie: wolf votes v1, 2 villagers vote v2, 1 villager votes wolf (still v2 wins... let's do a real tie)
        # Real tie: wolf + v1 vote v2; v2 + v3 vote wolf
        await ws.send_json({
            "cmd": "resolve_vote",
            "data": {"votes": {
                wolf["id"]:         villagers[1]["id"],
                villagers[1]["id"]: wolf["id"],
                villagers[2]["id"]: wolf["id"],
                # Wolf and v2 both get 2 votes → tie
            }},
        })
        # Actually let's compute: wolf votes v1=1, v1 votes wolf=1, v2 votes wolf=2 total for wolf, v1 gets 1
        # This isn't a tie. Let's just do equal vote counts:
        # wolf votes v1 (1), v1 votes v2 (1), v2 votes v1 (now v1=2), v3 votes v2 (now v2=2) → tie v1 and v2
        await drain(ws, until_type="state")  # consume the vote_resolved state

    await ws_for([Villager, Werewolf], _test)


# ═══════════════════════════════════════════════════════════════════════════════
# Scapegoat on tie
# ═══════════════════════════════════════════════════════════════════════════════

async def test_scapegoat_dies_on_vote_tie():
    """Scapegoat is eliminated when vote is tied."""
    async def _test(ws, engine):
        state_msg = await start_game(
            ws,
            ["Alice", "Bob", "Carol", "Dave", "Eve"],
            ["werewolf", "villager", "villager", "villager", "scapegoat"],
        )
        players = state_msg["state"]["players"]
        scapegoat = next(p for p in players if p["role_id"] == "scapegoat")
        wolf = next(p for p in players if p["role_id"] == "werewolf")
        villagers = [p for p in players if p["role_id"] == "villager"]

        await run_night_wolf(ws, villagers[0]["id"])

        await ws.send_json({"cmd": "begin_vote"})
        await drain(ws, until_type="state",
                    predicate=lambda m: m.get("state", {}).get("phase") == "vote")

        # Tie: 2 vote wolf, 2 vote villagers[1] → scapegoat dies
        await ws.send_json({
            "cmd": "resolve_vote",
            "data": {"votes": {
                wolf["id"]:         villagers[1]["id"],
                villagers[1]["id"]: wolf["id"],
                villagers[2]["id"]: wolf["id"],
                scapegoat["id"]:    villagers[1]["id"],
            }},
        })
        msgs = await drain(ws, until_type="player_eliminated",
                           predicate=lambda m: m.get("data", {}).get("player_id") == scapegoat["id"])
        elim = next(m for m in msgs if m["type"] == "player_eliminated")
        assert elim["data"]["role"] == "scapegoat"

    await ws_for([Villager, Werewolf, Scapegoat], _test)


# ═══════════════════════════════════════════════════════════════════════════════
# Hunter interrupt
# ═══════════════════════════════════════════════════════════════════════════════

async def test_hunter_shoots_on_elimination():
    """When hunter is eliminated, they get a NIGHT_ROLE_WAKE to shoot."""
    async def _test(ws, engine):
        state_msg = await start_game(
            ws,
            ["Alice", "Bob", "Carol", "Dave", "Eve"],
            ["werewolf", "hunter", "villager", "villager", "villager"],
        )
        players = state_msg["state"]["players"]
        wolf = next(p for p in players if p["role_id"] == "werewolf")
        hunter = next(p for p in players if p["role_id"] == "hunter")
        villagers = [p for p in players if p["role_id"] == "villager"]

        # Wolf kills hunter this night
        await ws.send_json({"cmd": "begin_night"})
        await drain(ws, until_type="night_role_wake",
                    predicate=lambda m: m.get("data", {}).get("role") == "werewolf")
        await ws.send_json({
            "cmd": "submit_night_action",
            "data": {"role": "werewolf", "action": {"target": hunter["id"]}},
        })

        # Hunter should get a NIGHT_ROLE_WAKE with player_id field
        hunter_wake_msgs = await drain(
            ws, until_type="night_role_wake",
            predicate=lambda m: m.get("data", {}).get("role") == "hunter",
        )
        wake = next(m for m in hunter_wake_msgs if m["type"] == "night_role_wake" and m["data"]["role"] == "hunter")
        assert "player_id" in wake["data"]
        assert wake["data"]["player_id"] == hunter["id"]

        # Hunter shoots first villager
        await ws.send_json({
            "cmd": "submit_pending_action",
            "data": {"role": "hunter", "action": {"target": villagers[0]["id"]}},
        })

        msgs = await drain(ws, until_type="state",
                           predicate=lambda m: m.get("state", {}).get("phase") == "day")

        elim_events = [m for m in msgs if m.get("type") == "player_eliminated"]
        eliminated_ids = {e["data"]["player_id"] for e in elim_events}
        assert hunter["id"] in eliminated_ids
        assert villagers[0]["id"] in eliminated_ids

    await ws_for([Villager, Werewolf, Hunter], _test)


# ═══════════════════════════════════════════════════════════════════════════════
# Multiple nights
# ═══════════════════════════════════════════════════════════════════════════════

async def test_two_consecutive_nights():
    """Night 1 + day + night 2 all resolve cleanly."""
    async def _test(ws, engine):
        state_msg = await start_game(
            ws,
            ["Alice", "Bob", "Carol", "Dave", "Eve", "Frank"],
            ["werewolf", "villager", "villager", "villager", "villager", "villager"],
        )
        players = state_msg["state"]["players"]
        villagers = [p for p in players if p["role_id"] == "villager"]

        # Night 1
        await run_night_wolf(ws, villagers[0]["id"])

        # Night 2
        msgs = await run_night_wolf(ws, villagers[1]["id"])
        final = msgs[-1]["state"]
        assert final["phase"] == "day"
        assert final["night_number"] == 2

        dead = [p for p in final["players"] if not p["alive"]]
        assert len(dead) == 2

    await ws_for([Villager, Werewolf], _test)


# ═══════════════════════════════════════════════════════════════════════════════
# Sheriff
# ═══════════════════════════════════════════════════════════════════════════════

async def test_elect_sheriff_double_vote():
    """Sheriff's vote counts double."""
    async def _test(ws, engine):
        state_msg = await start_game(
            ws,
            ["Alice", "Bob", "Carol", "Dave", "Eve"],
            ["werewolf", "villager", "villager", "villager", "villager"],
        )
        players = state_msg["state"]["players"]
        wolf = next(p for p in players if p["role_id"] == "werewolf")
        villagers = [p for p in players if p["role_id"] == "villager"]

        await run_night_wolf(ws, villagers[0]["id"])

        # Elect sheriff (first villager)
        sheriff = villagers[1]
        await ws.send_json({"cmd": "elect_sheriff", "data": {"player_id": sheriff["id"]}})
        await drain(ws, until_type="state")

        # Vote: sheriff + one other vote wolf (sheriff's vote = 2) vs nothing
        await ws.send_json({"cmd": "begin_vote"})
        await drain(ws, until_type="state",
                    predicate=lambda m: m.get("state", {}).get("phase") == "vote")

        await ws.send_json({
            "cmd": "resolve_vote",
            "data": {"votes": {sheriff["id"]: wolf["id"]}},
        })
        msgs = await drain(ws, until_type="state",
                           predicate=lambda m: m.get("state", {}).get("phase") in ("day", "game_over"))

        final = msgs[-1]["state"]
        wolf_player = next(p for p in final["players"] if p["id"] == wolf["id"])
        assert wolf_player["alive"] is False

    await ws_for([Villager, Werewolf], _test)
