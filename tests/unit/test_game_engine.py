"""Tests for GameEngine lifecycle, event system, and elimination chain."""
import asyncio
import pytest

from loup_garou.game_engine import GameEngine
from loup_garou.const import GameEvent, Phase
from loup_garou.roles.impl.villager import Villager
from loup_garou.roles.impl.werewolf import Werewolf
from loup_garou.roles.impl.seer import Seer
from loup_garou.roles.impl.elder import Elder
from loup_garou.roles.impl.witch import Witch
from loup_garou.roles.impl.cupid import Cupid
from tests.unit.conftest import make_engine


# ── Setup ─────────────────────────────────────────────────────────────────────

async def test_start_game_emits_game_started():
    engine = make_engine(Villager, Werewolf)
    events = []
    async def capture(d): events.append(d)
    engine.on(GameEvent.GAME_STARTED, capture)
    await engine.start_game(["Alice", "Bob"], ["villager", "werewolf"])
    assert len(events) == 1


async def test_start_game_phase_becomes_role_reveal():
    engine = make_engine(Villager, Werewolf)
    await engine.start_game(["Alice", "Bob"], ["villager", "werewolf"])
    assert engine._state.phase == Phase.ROLE_REVEAL


async def test_start_game_mismatched_lengths_raises():
    engine = make_engine(Villager, Werewolf)
    with pytest.raises(ValueError):
        await engine.start_game(["Alice", "Bob"], ["villager"])


async def test_start_game_assigns_sequential_ids():
    engine = make_engine(Villager, Werewolf)
    await engine.start_game(["Alice", "Bob"], ["villager", "werewolf"])
    ids = list(engine._state.players.keys())
    assert ids == ["p0", "p1"]


# ── Night flow ────────────────────────────────────────────────────────────────

async def test_begin_night_increments_night_number():
    engine = make_engine(Villager, Werewolf)
    await engine.start_game(["Alice", "Bob"], ["villager", "werewolf"])

    async def submit():
        await asyncio.sleep(0)
        await engine.submit_night_action("werewolf", {"target": "p0"})

    asyncio.get_event_loop().create_task(submit())
    await engine.begin_night()
    assert engine._state.night_number == 1


async def test_begin_night_emits_wake_sleep_events():
    engine = make_engine(Villager, Werewolf)
    await engine.start_game(["Alice", "Bob"], ["villager", "werewolf"])
    wake_events = []
    sleep_events = []

    async def on_wake(d): wake_events.append(d)
    async def on_sleep(d): sleep_events.append(d)
    engine.on(GameEvent.NIGHT_ROLE_WAKE, on_wake)
    engine.on(GameEvent.NIGHT_ROLE_SLEEP, on_sleep)

    async def submit():
        await asyncio.sleep(0)
        await engine.submit_night_action("werewolf", {"target": "p0"})

    asyncio.get_event_loop().create_task(submit())
    await engine.begin_night()

    assert any(e.get("role") == "werewolf" for e in wake_events)
    assert any(e.get("role") == "werewolf" for e in sleep_events)


async def test_wolf_kill_eliminates_player():
    engine = make_engine(Villager, Werewolf)
    await engine.start_game(["Alice", "Bob"], ["villager", "werewolf"])
    villager_id = next(p.id for p in engine._state.players.values() if p.role_id == "villager")

    async def submit():
        await asyncio.sleep(0)
        await engine.submit_night_action("werewolf", {"target": villager_id})

    asyncio.get_event_loop().create_task(submit())
    await engine.begin_night()

    assert not engine._state.players[villager_id].alive


async def test_night_resolved_emitted_after_night():
    engine = make_engine(Villager, Werewolf)
    await engine.start_game(["Alice", "Bob"], ["villager", "werewolf"])
    villager_id = next(p.id for p in engine._state.players.values() if p.role_id == "villager")
    events = []
    async def capture(d): events.append(d)
    engine.on(GameEvent.NIGHT_RESOLVED, capture)

    async def submit():
        await asyncio.sleep(0)
        await engine.submit_night_action("werewolf", {"target": villager_id})

    asyncio.get_event_loop().create_task(submit())
    await engine.begin_night()
    assert len(events) == 1


async def test_wolf_kill_triggers_game_over():
    engine = make_engine(Villager, Werewolf)
    await engine.start_game(["Alice", "Bob"], ["villager", "werewolf"])
    villager_id = next(p.id for p in engine._state.players.values() if p.role_id == "villager")

    async def submit():
        await asyncio.sleep(0)
        await engine.submit_night_action("werewolf", {"target": villager_id})

    asyncio.get_event_loop().create_task(submit())
    await engine.begin_night()
    assert engine._state.phase == Phase.GAME_OVER
    assert engine._state.winner == "wolves"


# ── Vote flow ─────────────────────────────────────────────────────────────────

async def test_vote_eliminates_top_player():
    engine = make_engine(Villager, Werewolf)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "villager", "werewolf"])
    alice_id = next(p.id for p in engine._state.players.values() if p.name == "Alice")
    bob_id = next(p.id for p in engine._state.players.values() if p.name == "Bob")
    carol_id = next(p.id for p in engine._state.players.values() if p.name == "Carol")

    await engine.begin_vote()
    eliminated = await engine.resolve_vote({alice_id: bob_id, carol_id: bob_id})
    assert eliminated == bob_id
    assert not engine._state.players[bob_id].alive


async def test_vote_tie_no_elimination():
    engine = make_engine(Villager, Werewolf)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "villager", "werewolf"])
    alice_id = next(p.id for p in engine._state.players.values() if p.name == "Alice")
    bob_id = next(p.id for p in engine._state.players.values() if p.name == "Bob")
    carol_id = next(p.id for p in engine._state.players.values() if p.name == "Carol")

    await engine.begin_vote()
    eliminated = await engine.resolve_vote({alice_id: bob_id, carol_id: alice_id})
    assert eliminated is None


async def test_vote_emits_vote_resolved():
    engine = make_engine(Villager, Werewolf)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "villager", "werewolf"])
    alice_id = next(p.id for p in engine._state.players.values() if p.name == "Alice")
    bob_id = next(p.id for p in engine._state.players.values() if p.name == "Bob")
    carol_id = next(p.id for p in engine._state.players.values() if p.name == "Carol")

    events = []
    async def capture(d): events.append(d)
    engine.on(GameEvent.VOTE_RESOLVED, capture)

    await engine.begin_vote()
    await engine.resolve_vote({alice_id: carol_id, bob_id: carol_id})
    assert len(events) == 1
    assert events[0]["eliminated"] == carol_id


# ── Witch integration ─────────────────────────────────────────────────────────

async def test_witch_save_prevents_wolf_kill():
    engine = make_engine(Villager, Werewolf, Witch)
    await engine.start_game(
        ["Alice", "Bob", "Carol"],
        ["villager", "werewolf", "witch"],
    )
    villager_id = next(p.id for p in engine._state.players.values() if p.role_id == "villager")
    witch_id = next(p.id for p in engine._state.players.values() if p.role_id == "witch")

    call_order = []

    async def submit():
        await asyncio.sleep(0)
        call_order.append("wolf")
        await engine.submit_night_action("werewolf", {"target": villager_id})
        await asyncio.sleep(0)
        call_order.append("witch")
        await engine.submit_night_action("witch", {
            "player_id": witch_id,
            "save_target": villager_id,
        })

    asyncio.get_event_loop().create_task(submit())
    await engine.begin_night()

    assert engine._state.players[villager_id].alive


# ── Elder integration ─────────────────────────────────────────────────────────

async def test_elder_survives_first_wolf_kill_integration():
    engine = make_engine(Villager, Werewolf, Elder)
    await engine.start_game(
        ["Alice", "Bob", "Carol"],
        ["elder", "villager", "werewolf"],
    )
    elder_id = next(p.id for p in engine._state.players.values() if p.role_id == "elder")

    async def submit():
        await asyncio.sleep(0)
        await engine.submit_night_action("werewolf", {"target": elder_id})

    asyncio.get_event_loop().create_task(submit())
    await engine.begin_night()

    assert engine._state.players[elder_id].alive


# ── Cupid lovers integration ──────────────────────────────────────────────────

async def test_lover_dies_when_partner_eliminated():
    engine = make_engine(Villager, Werewolf, Cupid)
    await engine.start_game(
        ["Alice", "Bob", "Carol", "Dave"],
        ["villager", "villager", "werewolf", "cupid"],
    )
    alice_id = next(p.id for p in engine._state.players.values() if p.name == "Alice")
    bob_id = next(p.id for p in engine._state.players.values() if p.name == "Bob")
    carol_id = next(p.id for p in engine._state.players.values() if p.name == "Carol")

    engine._state.player_links["lovers"] = [alice_id, bob_id]

    async def submit():
        await asyncio.sleep(0)
        await engine.submit_night_action("cupid", {"lovers": []})  # skip night 1 link
        await asyncio.sleep(0)
        await engine.submit_night_action("werewolf", {"target": alice_id})

    asyncio.get_event_loop().create_task(submit())
    await engine.begin_night()

    assert not engine._state.players[alice_id].alive
    assert not engine._state.players[bob_id].alive
