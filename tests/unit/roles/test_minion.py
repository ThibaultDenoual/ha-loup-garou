"""Tests for Minion role."""
import pytest

from loup_garou.roles.impl.villager import Villager
from loup_garou.roles.impl.werewolf import Werewolf
from loup_garou.roles.impl.minion import Minion
from tests.unit.conftest import make_engine, make_ctx


async def test_minion_no_night_action():
    assert Minion.has_night_action is False


async def test_minion_team_is_wolves():
    assert Minion.team == "wolves"


async def test_minion_wins_with_wolves():
    engine = make_engine(Villager, Werewolf, Minion)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "werewolf", "minion"])
    state = engine._state
    villager_id = next(p.id for p in state.players.values() if p.role_id == "villager")
    state.players[villager_id].alive = False

    ctx = make_ctx(state)
    role = engine._roles["minion"]
    result = await role.check_win(ctx)
    assert result == "wolves"


async def test_minion_does_not_win_while_wolves_outnumbered():
    engine = make_engine(Villager, Werewolf, Minion)
    await engine.start_game(
        ["Alice", "Bob", "Carol", "Dave"],
        ["villager", "villager", "werewolf", "minion"],
    )
    state = engine._state
    ctx = make_ctx(state)
    role = engine._roles["minion"]
    result = await role.check_win(ctx)
    assert result is None


async def test_minion_not_counted_as_villager_for_win():
    """Minion is excluded from villager count so wolves win condition is correct."""
    engine = make_engine(Villager, Werewolf, Minion)
    await engine.start_game(["Alice", "Bob", "Carol"], ["minion", "werewolf", "villager"])
    state = engine._state
    villager_id = next(p.id for p in state.players.values() if p.role_id == "villager")
    state.players[villager_id].alive = False
    # minion + wolf alive — wolf count (1) >= non-wolf non-minion count (0)

    ctx = make_ctx(state)
    role = engine._roles["minion"]
    result = await role.check_win(ctx)
    assert result == "wolves"
