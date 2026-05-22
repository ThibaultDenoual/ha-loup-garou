"""Tests for Little Girl role — passive, no engine hooks."""
import pytest

from loup_garou.roles.impl.little_girl import LittleGirl
from loup_garou.roles.impl.villager import Villager
from loup_garou.roles.impl.werewolf import Werewolf
from tests.unit.conftest import make_engine, make_ctx


async def test_little_girl_no_night_action():
    assert LittleGirl.has_night_action is False


async def test_little_girl_team():
    assert LittleGirl.team == "village"


async def test_little_girl_on_before_eliminate_is_noop():
    engine = make_engine(Villager, Werewolf, LittleGirl)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "werewolf", "little_girl"])
    state = engine._state
    lg_id = next(p.id for p in state.players.values() if p.role_id == "little_girl")

    ctx = make_ctx(state)
    role = engine._roles["little_girl"]
    decision = await role.on_before_eliminate(ctx, lg_id, "wolf_kill")
    assert decision.cancel is False
    assert decision.add_eliminations == []
