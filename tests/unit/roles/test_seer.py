"""Tests for Seer role."""
import asyncio
import pytest

from loup_garou.game_engine import GameEngine
from loup_garou.const import GameEvent
from loup_garou.roles.impl.villager import Villager
from loup_garou.roles.impl.werewolf import Werewolf
from loup_garou.roles.impl.seer import Seer
from tests.unit.conftest import make_engine, make_ctx


async def test_seer_has_night_action():
    assert Seer.has_night_action is True


async def test_seer_night_priority_before_wolf():
    assert Seer.night_priority < Werewolf.night_priority


async def test_seer_reveals_role_via_event():
    engine = make_engine(Villager, Werewolf, Seer)
    await engine.start_game(["Alice", "Bob", "Carol"], ["seer", "villager", "werewolf"])
    state = engine._state

    events = []

    async def capture(data):
        events.append(data)

    engine.on(GameEvent.NIGHT_ROLE_WAKE, capture)

    wolf_id = next(p.id for p in state.players.values() if p.role_id == "werewolf")
    ctx = make_ctx(state, engine._emit)
    role = engine._roles["seer"]

    # Seer's on_night_action uses request_action which awaits acknowledgement
    async def ack():
        await asyncio.sleep(0)
        await engine.submit_pending_action("seer", {})

    asyncio.get_event_loop().create_task(ack())
    await role.on_night_action(ctx, {"target": wolf_id})

    results = [e for e in events if "result" in e]
    assert len(results) == 1
    assert results[0]["result"]["player_id"] == wolf_id
    assert results[0]["result"]["role_id"] == "werewolf"


async def test_seer_no_result_for_missing_target():
    engine = make_engine(Villager, Werewolf, Seer)
    await engine.start_game(["Alice", "Bob", "Carol"], ["seer", "villager", "werewolf"])
    state = engine._state

    events = []

    async def capture(data):
        events.append(data)

    engine.on(GameEvent.NIGHT_ROLE_WAKE, capture)
    ctx = make_ctx(state, engine._emit)
    role = engine._roles["seer"]
    # No target → returns immediately, no request_action call
    await role.on_night_action(ctx, {})

    results = [e for e in events if "result" in e]
    assert results == []


async def test_seer_no_result_for_dead_target():
    engine = make_engine(Villager, Werewolf, Seer)
    await engine.start_game(["Alice", "Bob", "Carol"], ["seer", "villager", "werewolf"])
    state = engine._state
    villager_id = next(p.id for p in state.players.values() if p.role_id == "villager")
    state.players[villager_id].alive = False

    events = []

    async def capture(data):
        events.append(data)

    engine.on(GameEvent.NIGHT_ROLE_WAKE, capture)
    ctx = make_ctx(state, engine._emit)
    role = engine._roles["seer"]
    await role.on_night_action(ctx, {"target": villager_id})

    results = [e for e in events if "result" in e]
    assert results == []


async def test_seer_result_requires_acknowledgement():
    """After seeing result, NIGHT_ROLE_SLEEP must not fire until player acks."""
    engine = make_engine(Villager, Werewolf, Seer)
    await engine.start_game(
        ["Alice", "Bob", "Carol", "Dave"],
        ["seer", "villager", "villager", "werewolf"],
    )
    wolf_id = next(p.id for p in engine._state.players.values() if p.role_id == "werewolf")
    seer_id = next(p.id for p in engine._state.players.values() if p.role_id == "seer")

    sleep_events = []

    async def on_sleep(d):
        sleep_events.append(d)

    engine.on(GameEvent.NIGHT_ROLE_SLEEP, on_sleep)

    # Run full night sequence
    async def drive():
        await asyncio.sleep(0)
        # seer picks target first (priority 10 < werewolf priority)
        await engine.submit_night_action("seer", {"target": wolf_id})
        # Sleep should NOT have fired yet - seer hasn't acknowledged result
        assert not any(e.get("role") == "seer" for e in sleep_events)
        await asyncio.sleep(0)
        # Seer acknowledges result
        await engine.submit_pending_action("seer", {})
        await asyncio.sleep(0)
        # wolf acts second
        await engine.submit_night_action("werewolf", {"target": seer_id})

    asyncio.get_event_loop().create_task(drive())
    await engine.begin_night()

    # After ack, seer sleep fires
    assert any(e.get("role") == "seer" for e in sleep_events)
