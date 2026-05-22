"""Tests for Elder role."""
import pytest

from loup_garou.game_engine import GameEngine
from loup_garou.roles.impl.villager import Villager
from loup_garou.roles.impl.werewolf import Werewolf
from loup_garou.roles.impl.elder import Elder
from tests.unit.conftest import make_engine, make_ctx


async def test_elder_no_night_action():
    assert Elder.has_night_action is False


async def test_elder_flag_set_on_game_start():
    engine = make_engine(Villager, Werewolf, Elder)
    await engine.start_game(["Alice", "Bob", "Carol"], ["elder", "villager", "werewolf"])
    state = engine._state
    elder_id = next(p.id for p in state.players.values() if p.role_id == "elder")
    assert state.player_flags[elder_id]["elder_first_life"] is True


async def test_elder_survives_first_wolf_kill():
    engine = make_engine(Villager, Werewolf, Elder)
    await engine.start_game(["Alice", "Bob", "Carol"], ["elder", "villager", "werewolf"])
    state = engine._state
    elder_id = next(p.id for p in state.players.values() if p.role_id == "elder")

    ctx = make_ctx(state)
    role = engine._roles["elder"]
    decision = await role.on_before_eliminate(ctx, elder_id, "wolf_kill")

    assert decision.cancel is True
    assert state.player_flags[elder_id]["elder_first_life"] is False


async def test_elder_dies_on_second_wolf_kill():
    engine = make_engine(Villager, Werewolf, Elder)
    await engine.start_game(["Alice", "Bob", "Carol"], ["elder", "villager", "werewolf"])
    state = engine._state
    elder_id = next(p.id for p in state.players.values() if p.role_id == "elder")
    state.player_flags[elder_id]["elder_first_life"] = False

    ctx = make_ctx(state)
    role = engine._roles["elder"]
    decision = await role.on_before_eliminate(ctx, elder_id, "wolf_kill")

    assert decision.cancel is False


async def test_elder_dies_from_vote_even_with_first_life():
    engine = make_engine(Villager, Werewolf, Elder)
    await engine.start_game(["Alice", "Bob", "Carol"], ["elder", "villager", "werewolf"])
    state = engine._state
    elder_id = next(p.id for p in state.players.values() if p.role_id == "elder")

    ctx = make_ctx(state)
    role = engine._roles["elder"]
    decision = await role.on_before_eliminate(ctx, elder_id, "village_vote")

    assert decision.cancel is False


async def test_elder_does_not_affect_other_players():
    engine = make_engine(Villager, Werewolf, Elder)
    await engine.start_game(["Alice", "Bob", "Carol"], ["elder", "villager", "werewolf"])
    state = engine._state
    villager_id = next(p.id for p in state.players.values() if p.role_id == "villager")

    ctx = make_ctx(state)
    role = engine._roles["elder"]
    decision = await role.on_before_eliminate(ctx, villager_id, "wolf_kill")

    assert decision.cancel is False
