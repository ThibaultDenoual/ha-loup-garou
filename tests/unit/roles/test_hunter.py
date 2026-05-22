"""Tests for Hunter role."""
import asyncio
import pytest

from loup_garou.game_engine import GameEngine
from loup_garou.const import GameEvent
from loup_garou.roles.impl.villager import Villager
from loup_garou.roles.impl.werewolf import Werewolf
from loup_garou.roles.impl.hunter import Hunter
from tests.unit.conftest import make_engine, make_ctx


async def test_hunter_no_night_action():
    assert Hunter.has_night_action is False


async def test_hunter_does_not_fire_for_other_player():
    engine = make_engine(Villager, Werewolf, Hunter)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "werewolf", "hunter"])
    state = engine._state
    villager_id = next(p.id for p in state.players.values() if p.role_id == "villager")

    ctx = make_ctx(state, engine._emit)
    role = engine._roles["hunter"]
    decision = await role.on_before_eliminate(ctx, villager_id, "wolf_kill")
    assert decision.cancel is False
    assert decision.add_eliminations == []


async def test_hunter_fires_on_own_elimination():
    engine = make_engine(Villager, Werewolf, Hunter)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "werewolf", "hunter"])
    state = engine._state
    hunter_id = next(p.id for p in state.players.values() if p.role_id == "hunter")
    villager_id = next(p.id for p in state.players.values() if p.role_id == "villager")

    ctx = make_ctx(state, engine._emit)
    role = engine._roles["hunter"]

    async def resolve_shot():
        await asyncio.sleep(0)  # yield to let request_action set up the future
        await engine.submit_pending_action("hunter", {"target": villager_id})

    asyncio.get_event_loop().create_task(resolve_shot())
    decision = await role.on_before_eliminate(ctx, hunter_id, "village_vote")

    assert villager_id in decision.add_eliminations


async def test_hunter_no_shot_if_no_target():
    engine = make_engine(Villager, Werewolf, Hunter)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "werewolf", "hunter"])
    state = engine._state
    hunter_id = next(p.id for p in state.players.values() if p.role_id == "hunter")

    ctx = make_ctx(state, engine._emit)
    role = engine._roles["hunter"]

    async def resolve_shot():
        await asyncio.sleep(0)
        await engine.submit_pending_action("hunter", {})

    asyncio.get_event_loop().create_task(resolve_shot())
    decision = await role.on_before_eliminate(ctx, hunter_id, "wolf_kill")

    assert decision.add_eliminations == []


async def test_hunter_cannot_shoot_dead_player():
    engine = make_engine(Villager, Werewolf, Hunter)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "werewolf", "hunter"])
    state = engine._state
    hunter_id = next(p.id for p in state.players.values() if p.role_id == "hunter")
    villager_id = next(p.id for p in state.players.values() if p.role_id == "villager")
    state.players[villager_id].alive = False

    ctx = make_ctx(state, engine._emit)
    role = engine._roles["hunter"]

    async def resolve_shot():
        await asyncio.sleep(0)
        await engine.submit_pending_action("hunter", {"target": villager_id})

    asyncio.get_event_loop().create_task(resolve_shot())
    decision = await role.on_before_eliminate(ctx, hunter_id, "wolf_kill")

    assert decision.add_eliminations == []
