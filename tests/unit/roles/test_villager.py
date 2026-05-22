"""Tests for Villager role."""
import pytest

from loup_garou.game_engine import GameEngine, GameState, Player
from loup_garou.roles.impl.villager import Villager
from loup_garou.roles.impl.werewolf import Werewolf
from tests.unit.conftest import make_engine, make_ctx


async def test_villager_no_night_action():
    assert Villager.has_night_action is False


async def test_villager_check_win_wolves_alive():
    engine = make_engine(Villager, Werewolf)
    await engine.start_game(["Alice", "Bob"], ["villager", "werewolf"])
    state = engine._state
    ctx = make_ctx(state)
    role = engine._roles["villager"]
    result = await role.check_win(ctx)
    assert result is None


async def test_villager_check_win_no_wolves():
    engine = make_engine(Villager, Werewolf)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "villager", "werewolf"])
    state = engine._state
    # eliminate the wolf
    wolf_id = next(p.id for p in state.players.values() if p.role_id == "werewolf")
    state.players[wolf_id].alive = False

    ctx = make_ctx(state)
    role = engine._roles["villager"]
    result = await role.check_win(ctx)
    assert result == "village"


async def test_villager_check_win_no_players():
    engine = make_engine(Villager)
    await engine.start_game(["Alice"], ["villager"])
    state = engine._state
    state.players["p0"].alive = False
    ctx = make_ctx(state)
    role = engine._roles["villager"]
    # No alive players → no win (game should not award village win to no one)
    result = await role.check_win(ctx)
    assert result is None


async def test_villager_game_start_hook_is_noop():
    engine = make_engine(Villager, Werewolf)
    events = []

    async def capture(d):
        events.append(d)

    engine.on("game_started", capture)
    await engine.start_game(["Alice", "Bob"], ["villager", "werewolf"])
    assert len(events) == 1  # game_started was emitted
