"""Tests for Cupid role."""
import pytest

from loup_garou.game_engine import GameEngine
from loup_garou.roles.impl.villager import Villager
from loup_garou.roles.impl.werewolf import Werewolf
from loup_garou.roles.impl.cupid import Cupid
from tests.unit.conftest import make_engine, make_ctx


async def test_cupid_has_night_action():
    assert Cupid.has_night_action is True


async def test_cupid_priority_is_first():
    from loup_garou.roles.impl.seer import Seer
    assert Cupid.night_priority < Seer.night_priority


async def test_cupid_links_two_lovers_on_night_1():
    engine = make_engine(Villager, Werewolf, Cupid)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "villager", "cupid"])
    state = engine._state
    state.night_number = 1
    alice_id = next(p.id for p in state.players.values() if p.name == "Alice")
    bob_id = next(p.id for p in state.players.values() if p.name == "Bob")

    ctx = make_ctx(state)
    role = engine._roles["cupid"]
    await role.on_night_action(ctx, {"lovers": [alice_id, bob_id]})

    assert state.player_links.get("lovers") == [alice_id, bob_id]


async def test_cupid_does_not_link_after_night_1():
    engine = make_engine(Villager, Werewolf, Cupid)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "villager", "cupid"])
    state = engine._state
    state.night_number = 2
    alice_id = next(p.id for p in state.players.values() if p.name == "Alice")
    bob_id = next(p.id for p in state.players.values() if p.name == "Bob")

    ctx = make_ctx(state)
    role = engine._roles["cupid"]
    await role.on_night_action(ctx, {"lovers": [alice_id, bob_id]})

    assert "lovers" not in state.player_links


async def test_lover_death_triggers_partner_elimination():
    engine = make_engine(Villager, Werewolf, Cupid)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "villager", "cupid"])
    state = engine._state
    alice_id = next(p.id for p in state.players.values() if p.name == "Alice")
    bob_id = next(p.id for p in state.players.values() if p.name == "Bob")
    state.player_links["lovers"] = [alice_id, bob_id]

    ctx = make_ctx(state)
    role = engine._roles["cupid"]
    decision = await role.on_before_eliminate(ctx, alice_id, "wolf_kill")

    assert bob_id in decision.add_eliminations


async def test_lover_death_no_extra_if_partner_already_dead():
    engine = make_engine(Villager, Werewolf, Cupid)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "villager", "cupid"])
    state = engine._state
    alice_id = next(p.id for p in state.players.values() if p.name == "Alice")
    bob_id = next(p.id for p in state.players.values() if p.name == "Bob")
    state.player_links["lovers"] = [alice_id, bob_id]
    state.players[bob_id].alive = False

    ctx = make_ctx(state)
    role = engine._roles["cupid"]
    decision = await role.on_before_eliminate(ctx, alice_id, "wolf_kill")

    assert decision.add_eliminations == []


async def test_lovers_win_when_only_two_left():
    engine = make_engine(Villager, Werewolf, Cupid)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "villager", "cupid"])
    state = engine._state
    alice_id = next(p.id for p in state.players.values() if p.name == "Alice")
    bob_id = next(p.id for p in state.players.values() if p.name == "Bob")
    carol_id = next(p.id for p in state.players.values() if p.name == "Carol")
    state.player_links["lovers"] = [alice_id, bob_id]
    state.players[carol_id].alive = False

    ctx = make_ctx(state)
    role = engine._roles["cupid"]
    result = await role.check_win(ctx)
    assert result == "lovers"


async def test_lovers_do_not_win_while_others_alive():
    engine = make_engine(Villager, Werewolf, Cupid)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "villager", "cupid"])
    state = engine._state
    alice_id = next(p.id for p in state.players.values() if p.name == "Alice")
    bob_id = next(p.id for p in state.players.values() if p.name == "Bob")
    state.player_links["lovers"] = [alice_id, bob_id]

    ctx = make_ctx(state)
    role = engine._roles["cupid"]
    result = await role.check_win(ctx)
    assert result is None
