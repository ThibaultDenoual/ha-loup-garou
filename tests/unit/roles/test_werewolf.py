"""Tests for Werewolf role."""
import pytest

from loup_garou.game_engine import GameEngine, GameState, Player
from loup_garou.roles.impl.villager import Villager
from loup_garou.roles.impl.werewolf import Werewolf
from loup_garou.roles.impl.alpha_wolf import AlphaWolf
from tests.unit.conftest import make_engine, make_ctx


async def test_werewolf_has_night_action():
    assert Werewolf.has_night_action is True


async def test_werewolf_night_priority():
    assert Werewolf.night_priority == 50


async def test_werewolf_adds_kill_to_pending():
    engine = make_engine(Villager, Werewolf)
    await engine.start_game(["Alice", "Bob"], ["villager", "werewolf"])
    state = engine._state
    villager_id = next(p.id for p in state.players.values() if p.role_id == "villager")

    ctx = make_ctx(state)
    role = engine._roles["werewolf"]
    await role.on_night_action(ctx, {"target": villager_id})

    assert villager_id in ctx.pending_kills


async def test_werewolf_invalid_target_ignored():
    engine = make_engine(Villager, Werewolf)
    await engine.start_game(["Alice", "Bob"], ["villager", "werewolf"])
    state = engine._state

    ctx = make_ctx(state)
    role = engine._roles["werewolf"]
    await role.on_night_action(ctx, {"target": "nonexistent"})

    assert ctx.pending_kills == []


async def test_werewolf_dead_target_ignored():
    engine = make_engine(Villager, Werewolf)
    await engine.start_game(["Alice", "Bob"], ["villager", "werewolf"])
    state = engine._state
    villager_id = next(p.id for p in state.players.values() if p.role_id == "villager")
    state.players[villager_id].alive = False

    ctx = make_ctx(state)
    role = engine._roles["werewolf"]
    await role.on_night_action(ctx, {"target": villager_id})

    assert ctx.pending_kills == []


async def test_werewolf_cannot_target_fellow_wolf():
    engine = make_engine(Villager, Werewolf)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "werewolf", "werewolf"])
    state = engine._state
    wolf_ids = [p.id for p in state.players.values() if p.role_id == "werewolf"]

    ctx = make_ctx(state)
    role = engine._roles["werewolf"]
    await role.on_night_action(ctx, {"target": wolf_ids[1]})

    assert ctx.pending_kills == []


async def test_werewolf_cannot_target_alpha_wolf():
    engine = make_engine(Villager, Werewolf, AlphaWolf)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "werewolf", "alpha_wolf"])
    state = engine._state
    alpha_id = next(p.id for p in state.players.values() if p.role_id == "alpha_wolf")

    ctx = make_ctx(state)
    role = engine._roles["werewolf"]
    await role.on_night_action(ctx, {"target": alpha_id})

    assert ctx.pending_kills == []


async def test_werewolf_check_win_outnumber_villagers():
    engine = make_engine(Villager, Werewolf)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "werewolf", "werewolf"])
    state = engine._state
    villager_id = next(p.id for p in state.players.values() if p.role_id == "villager")
    state.players[villager_id].alive = False

    ctx = make_ctx(state)
    role = engine._roles["werewolf"]
    result = await role.check_win(ctx)
    assert result == "wolves"


async def test_werewolf_check_win_equal_counts():
    engine = make_engine(Villager, Werewolf)
    await engine.start_game(["Alice", "Bob"], ["villager", "werewolf"])
    state = engine._state
    ctx = make_ctx(state)
    role = engine._roles["werewolf"]
    result = await role.check_win(ctx)
    assert result == "wolves"


async def test_werewolf_no_win_when_outnumbered():
    engine = make_engine(Villager, Werewolf)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "villager", "werewolf"])
    state = engine._state
    ctx = make_ctx(state)
    role = engine._roles["werewolf"]
    result = await role.check_win(ctx)
    assert result is None
