"""Tests for Scapegoat role."""
import pytest

from loup_garou.game_engine import GameEngine
from loup_garou.const import GameEvent
from loup_garou.roles.impl.villager import Villager
from loup_garou.roles.impl.werewolf import Werewolf
from loup_garou.roles.impl.scapegoat import Scapegoat
from tests.unit.conftest import make_engine, make_ctx


async def test_scapegoat_no_night_action():
    assert Scapegoat.has_night_action is False


async def test_scapegoat_dies_on_vote_tie():
    engine = make_engine(Villager, Werewolf, Scapegoat)
    await engine.start_game(
        ["Alice", "Bob", "Carol", "Dave"],
        ["villager", "werewolf", "scapegoat", "villager"],
    )

    events = []

    async def capture(data):
        events.append(data)

    engine.on(GameEvent.PLAYER_ELIMINATED, capture)
    await engine.begin_vote()

    # Equal votes between Alice and Bob → tie → scapegoat dies
    state = engine._state
    alice_id = next(p.id for p in state.players.values() if p.name == "Alice")
    bob_id = next(p.id for p in state.players.values() if p.name == "Bob")
    carol_id = next(p.id for p in state.players.values() if p.name == "Carol")
    dave_id = next(p.id for p in state.players.values() if p.name == "Dave")

    eliminated = await engine.resolve_vote({
        alice_id: bob_id,
        bob_id: alice_id,
        carol_id: bob_id,
        dave_id: alice_id,
    })

    scapegoat_id = next(p.id for p in state.players.values() if p.role_id == "scapegoat")
    assert eliminated == scapegoat_id
    assert not state.players[scapegoat_id].alive


async def test_scapegoat_does_not_die_without_tie():
    engine = make_engine(Villager, Werewolf, Scapegoat)
    await engine.start_game(
        ["Alice", "Bob", "Carol"],
        ["villager", "werewolf", "scapegoat"],
    )

    engine.on(GameEvent.PLAYER_ELIMINATED, lambda d: None)
    await engine.begin_vote()

    state = engine._state
    alice_id = next(p.id for p in state.players.values() if p.name == "Alice")
    bob_id = next(p.id for p in state.players.values() if p.name == "Bob")
    carol_id = next(p.id for p in state.players.values() if p.name == "Carol")

    eliminated = await engine.resolve_vote({
        alice_id: bob_id,
        carol_id: bob_id,
    })

    scapegoat_id = next(p.id for p in state.players.values() if p.role_id == "scapegoat")
    assert eliminated == bob_id
    assert state.players[scapegoat_id].alive
