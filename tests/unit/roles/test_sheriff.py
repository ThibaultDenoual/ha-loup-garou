"""Tests for Sheriff role — double vote weight."""
import pytest

from loup_garou.game_engine import GameEngine
from loup_garou.const import GameEvent
from loup_garou.roles.impl.villager import Villager
from loup_garou.roles.impl.werewolf import Werewolf
from loup_garou.roles.impl.sheriff import Sheriff
from tests.unit.conftest import make_engine, make_ctx


async def test_sheriff_no_night_action():
    assert Sheriff.has_night_action is False


async def test_sheriff_double_vote():
    engine = make_engine(Villager, Werewolf, Sheriff)
    await engine.start_game(
        ["Alice", "Bob", "Carol", "Dave"],
        ["sheriff", "villager", "villager", "werewolf"],
    )

    alice_id = next(p.id for p in engine._state.players.values() if p.name == "Alice")
    bob_id = next(p.id for p in engine._state.players.values() if p.name == "Bob")
    carol_id = next(p.id for p in engine._state.players.values() if p.name == "Carol")
    dave_id = next(p.id for p in engine._state.players.values() if p.name == "Dave")

    engine.elect_sheriff(alice_id)
    await engine.begin_vote()

    # Alice (sheriff, 2 votes) votes Bob; Carol and Dave vote Alice
    # Bob: 2 votes (from Alice), Alice: 2 votes (from Carol + Dave) → tie
    # Without sheriff, Alice's vote would only be 1, Bob gets 1, clear winner
    eliminated = await engine.resolve_vote({
        alice_id: bob_id,
        carol_id: alice_id,
        dave_id: alice_id,
    })

    # Alice has 2 votes (Carol + Dave), Bob has 2 votes (Alice x2) → tie
    assert eliminated is None


async def test_sheriff_elect_transfers():
    engine = make_engine(Villager, Werewolf, Sheriff)
    await engine.start_game(["Alice", "Bob", "Carol"], ["sheriff", "villager", "werewolf"])
    alice_id = next(p.id for p in engine._state.players.values() if p.name == "Alice")
    bob_id = next(p.id for p in engine._state.players.values() if p.name == "Bob")

    engine.elect_sheriff(alice_id)
    assert engine._state.player_flags[alice_id].get("sheriff") is True

    engine.elect_sheriff(bob_id)
    assert not engine._state.player_flags[alice_id].get("sheriff")
    assert engine._state.player_flags[bob_id].get("sheriff") is True
