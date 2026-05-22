"""End-to-end WebSocket tests — validate the JSON protocol the browser UI depends on."""
from __future__ import annotations

import asyncio

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from loup_garou.roles.impl.villager import Villager
from loup_garou.roles.impl.werewolf import Werewolf
from loup_garou.roles.impl.seer import Seer
from tests.e2e.conftest import drain, make_server, make_app


# ── helpers ───────────────────────────────────────────────────────────────────

async def start_game(ws: aiohttp.ClientWebSocketResponse, players: list[str], roles: list[str]) -> dict:
    """Send start_game and return the resulting state message."""
    await ws.send_json({"cmd": "start_game", "data": {"players": players, "roles": roles}})
    msgs = await drain(ws, until_type="state")
    return msgs[-1]


# ── tests ─────────────────────────────────────────────────────────────────────

async def test_get_state_on_connect(ws_session):
    ws, engine = ws_session
    await ws.send_json({"cmd": "get_state"})
    msgs = await drain(ws, until_type="state")
    state_msg = msgs[-1]
    assert state_msg["type"] == "state"
    assert state_msg["state"]["phase"] == "setup"
    assert state_msg["state"]["players"] == []


async def test_unknown_command_returns_error(ws_session):
    ws, engine = ws_session
    await ws.send_json({"cmd": "bogus_command"})
    msgs = await drain(ws, until_type="error")
    err = msgs[-1]
    assert err["type"] == "error"
    assert "unknown command" in err["msg"]


async def test_start_game_broadcasts_state(ws_session):
    ws, engine = ws_session
    state_msg = await start_game(ws, ["Alice", "Bob", "Carol"], ["werewolf", "villager", "villager"])

    assert state_msg["type"] == "state"
    state = state_msg["state"]
    assert state["phase"] == "role_reveal"
    assert len(state["players"]) == 3
    names = {p["name"] for p in state["players"]}
    assert names == {"Alice", "Bob", "Carol"}
    roles = {p["role_id"] for p in state["players"]}
    assert roles == {"werewolf", "villager"}


async def test_start_game_broadcasts_to_all_clients():
    """Both connected clients receive the state broadcast from start_game."""
    engine, srv = make_server((Villager, Werewolf))
    app = make_app(srv)
    async with TestServer(app) as test_server:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(test_server.make_url("/ws")) as ws1:
                async with session.ws_connect(test_server.make_url("/ws")) as ws2:
                    await ws1.send_json({
                        "cmd": "start_game",
                        "data": {
                            "players": ["Alice", "Bob"],
                            "roles": ["werewolf", "villager"],
                        },
                    })
                    msgs1 = await drain(ws1, until_type="state")
                    msgs2 = await drain(ws2, until_type="state")
                    assert msgs1[-1]["state"]["phase"] == "role_reveal"
                    assert msgs2[-1]["state"]["phase"] == "role_reveal"

async def test_role_reveal_flow(ws_session):
    """start_game → role_reveal → begin_night.

    Uses 3 players (1 wolf + 2 villagers) so the wolf doesn't win at parity after one kill.
    TODO : This test should also validate that the correct role_reveal messages are sent to each player, but for now just check the phase transitions.
    """
    ws, engine = ws_session
    state_msg = await start_game(
        ws,
        ["Alice", "Bob", "Carol"],
        ["werewolf", "villager", "villager"],
    )

    assert state_msg["state"]["phase"] == "role_reveal" # TODO :Fails here, the phase is "night" instead of "role_reveal"
    await ws.send_json({"cmd": "begin_night"})
    night_msgs = await drain(ws, until_type="state")
    assert night_msgs[-1]["state"]["phase"] == "night"

async def test_night_flow(ws_session):
    """begin_night → wolf gets wake event → submits target → night resolves → day starts.

    Uses 4 players (1 wolf + 3 villagers) so wolves don't win at parity after one kill.
    """
    ws, engine = ws_session
    # 4 players: after wolf kills one, 1 wolf + 2 villagers remain → no parity win yet
    state_msg = await start_game(
        ws,
        ["Alice", "Bob", "Carol", "Dave"],
        ["werewolf", "villager", "villager", "villager"],
    )

    players = state_msg["state"]["players"]
    villager = next(p for p in players if p["role_id"] == "villager")

    await ws.send_json({"cmd": "begin_night"})
    wake_msgs = await drain(ws, until_type="night_role_wake")
    wake = next(m for m in wake_msgs if m.get("type") == "night_role_wake")
    assert wake["data"]["role"] == "werewolf"

    await ws.send_json({
        "cmd": "submit_night_action",
        "data": {"role": "werewolf", "action": {"target": villager["id"]}},
    })
    # Drain until the state message shows day phase
    day_msgs = await drain(
        ws,
        until_type="state",
        predicate=lambda m: m.get("state", {}).get("phase") == "day",
    )

    eliminated_events = [m for m in day_msgs if m.get("type") == "player_eliminated"]
    assert len(eliminated_events) == 1
    assert eliminated_events[0]["data"]["player_id"] == villager["id"]

    dead = [p for p in day_msgs[-1]["state"]["players"] if not p["alive"]]
    assert len(dead) == 1
    assert dead[0]["id"] == villager["id"]


async def test_vote_and_game_over(ws_session):
    """After killing a villager, village votes out the wolf → game over.

    Uses 4 players so the wolf doesn't win at night parity (1 wolf + 2 villagers after kill).
    """
    ws, engine = ws_session
    state_msg = await start_game(
        ws,
        ["Alice", "Bob", "Carol", "Dave"],
        ["werewolf", "villager", "villager", "villager"],
    )

    players = state_msg["state"]["players"]
    wolf = next(p for p in players if p["role_id"] == "werewolf")
    villagers = [p for p in players if p["role_id"] == "villager"]

    # Night: wolf kills one villager → 1 wolf + 2 villagers survive
    await ws.send_json({"cmd": "begin_night"})
    await drain(ws, until_type="night_role_wake")
    await ws.send_json({
        "cmd": "submit_night_action",
        "data": {"role": "werewolf", "action": {"target": villagers[0]["id"]}},
    })
    await drain(
        ws,
        until_type="state",
        predicate=lambda m: m.get("state", {}).get("phase") == "day",
    )

    # Vote: both surviving villagers vote wolf out → village wins
    await ws.send_json({"cmd": "begin_vote"})
    await drain(ws, until_type="state")

    await ws.send_json({
        "cmd": "resolve_vote",
        "data": {"votes": {villagers[1]["id"]: wolf["id"], villagers[2]["id"]: wolf["id"]}},
    })
    game_over_msgs = await drain(
        ws,
        until_type="state",
        predicate=lambda m: m.get("state", {}).get("phase") == "game_over",
    )

    final_state = game_over_msgs[-1]["state"]
    assert final_state["phase"] == "game_over"
    assert final_state["winner"] == "village"
