"""Tests for Alpha Wolf role."""
import pytest

from loup_garou.game_engine import GameEngine
from loup_garou.roles.impl.villager import Villager
from loup_garou.roles.impl.werewolf import Werewolf
from loup_garou.roles.impl.alpha_wolf import AlphaWolf
from tests.unit.conftest import make_engine, make_ctx


async def test_alpha_wolf_has_night_action():
    assert AlphaWolf.has_night_action is True


async def test_alpha_wolf_flag_set_on_game_start():
    engine = make_engine(Villager, Werewolf, AlphaWolf)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "werewolf", "alpha_wolf"])
    state = engine._state
    alpha_id = next(p.id for p in state.players.values() if p.role_id == "alpha_wolf")
    assert state.player_flags[alpha_id]["alpha_conversion_used"] is False


async def test_alpha_wolf_converts_villager():
    engine = make_engine(Villager, Werewolf, AlphaWolf)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "werewolf", "alpha_wolf"])
    state = engine._state
    alpha_id = next(p.id for p in state.players.values() if p.role_id == "alpha_wolf")
    villager_id = next(p.id for p in state.players.values() if p.role_id == "villager")

    ctx = make_ctx(state)
    role = engine._roles["alpha_wolf"]
    await role.on_night_action(ctx, {"player_id": alpha_id, "convert_target": villager_id})

    assert state.players[villager_id].role_id == "werewolf"
    assert state.player_flags[alpha_id]["alpha_conversion_used"] is True


async def test_alpha_wolf_cannot_convert_twice():
    engine = make_engine(Villager, Werewolf, AlphaWolf)
    await engine.start_game(
        ["Alice", "Bob", "Carol", "Dave"],
        ["villager", "villager", "werewolf", "alpha_wolf"],
    )
    state = engine._state
    alpha_id = next(p.id for p in state.players.values() if p.role_id == "alpha_wolf")
    villagers = [p.id for p in state.players.values() if p.role_id == "villager"]
    state.player_flags[alpha_id]["alpha_conversion_used"] = True

    ctx = make_ctx(state)
    role = engine._roles["alpha_wolf"]
    await role.on_night_action(ctx, {"player_id": alpha_id, "convert_target": villagers[0]})

    assert state.players[villagers[0]].role_id == "villager"


async def test_alpha_wolf_cannot_convert_another_wolf():
    engine = make_engine(Villager, Werewolf, AlphaWolf)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "werewolf", "alpha_wolf"])
    state = engine._state
    alpha_id = next(p.id for p in state.players.values() if p.role_id == "alpha_wolf")
    wolf_id = next(p.id for p in state.players.values() if p.role_id == "werewolf")

    ctx = make_ctx(state)
    role = engine._roles["alpha_wolf"]
    await role.on_night_action(ctx, {"player_id": alpha_id, "convert_target": wolf_id})

    assert state.players[wolf_id].role_id == "werewolf"
    assert not state.player_flags[alpha_id]["alpha_conversion_used"]


async def test_alpha_wolf_check_win():
    engine = make_engine(Villager, AlphaWolf)
    await engine.start_game(["Alice", "Bob"], ["villager", "alpha_wolf"])
    state = engine._state
    villager_id = next(p.id for p in state.players.values() if p.role_id == "villager")
    state.players[villager_id].alive = False

    ctx = make_ctx(state)
    role = engine._roles["alpha_wolf"]
    result = await role.check_win(ctx)
    assert result == "wolves"
