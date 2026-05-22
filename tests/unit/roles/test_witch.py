"""Tests for Witch role."""
import pytest

from loup_garou.game_engine import GameEngine
from loup_garou.roles.impl.villager import Villager
from loup_garou.roles.impl.werewolf import Werewolf
from loup_garou.roles.impl.witch import Witch
from tests.unit.conftest import make_engine, make_ctx


async def test_witch_has_night_action():
    assert Witch.has_night_action is True


async def test_witch_priority_after_wolf():
    from loup_garou.roles.impl.werewolf import Werewolf
    assert Witch.night_priority > Werewolf.night_priority


async def test_witch_flags_set_on_game_start():
    engine = make_engine(Villager, Werewolf, Witch)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "werewolf", "witch"])
    state = engine._state
    witch_id = next(p.id for p in state.players.values() if p.role_id == "witch")
    assert state.player_flags[witch_id]["witch_save_used"] is False
    assert state.player_flags[witch_id]["witch_poison_used"] is False


async def test_witch_save_removes_pending_kill():
    engine = make_engine(Villager, Werewolf, Witch)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "werewolf", "witch"])
    state = engine._state
    villager_id = next(p.id for p in state.players.values() if p.role_id == "villager")
    witch_id = next(p.id for p in state.players.values() if p.role_id == "witch")

    state.pending_kills.append((villager_id, "wolf_kill"))

    ctx = make_ctx(state)
    role = engine._roles["witch"]
    await role.on_night_action(ctx, {"player_id": witch_id, "save_target": villager_id})

    assert villager_id not in ctx.pending_kills
    assert state.player_flags[witch_id]["witch_save_used"] is True


async def test_witch_cannot_save_twice():
    engine = make_engine(Villager, Werewolf, Witch)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "werewolf", "witch"])
    state = engine._state
    villager_id = next(p.id for p in state.players.values() if p.role_id == "villager")
    witch_id = next(p.id for p in state.players.values() if p.role_id == "witch")

    state.pending_kills.append((villager_id, "wolf_kill"))
    state.player_flags[witch_id]["witch_save_used"] = True

    ctx = make_ctx(state)
    role = engine._roles["witch"]
    await role.on_night_action(ctx, {"player_id": witch_id, "save_target": villager_id})

    assert villager_id in ctx.pending_kills


async def test_witch_poison_adds_pending_kill():
    engine = make_engine(Villager, Werewolf, Witch)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "werewolf", "witch"])
    state = engine._state
    villager_id = next(p.id for p in state.players.values() if p.role_id == "villager")
    witch_id = next(p.id for p in state.players.values() if p.role_id == "witch")

    ctx = make_ctx(state)
    role = engine._roles["witch"]
    await role.on_night_action(ctx, {"player_id": witch_id, "poison_target": villager_id})

    assert villager_id in ctx.pending_kills
    assert state.player_flags[witch_id]["witch_poison_used"] is True


async def test_witch_cannot_poison_twice():
    engine = make_engine(Villager, Werewolf, Witch)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "werewolf", "witch"])
    state = engine._state
    villager_id = next(p.id for p in state.players.values() if p.role_id == "villager")
    witch_id = next(p.id for p in state.players.values() if p.role_id == "witch")
    state.player_flags[witch_id]["witch_poison_used"] = True

    ctx = make_ctx(state)
    role = engine._roles["witch"]
    await role.on_night_action(ctx, {"player_id": witch_id, "poison_target": villager_id})

    assert villager_id not in ctx.pending_kills


async def test_witch_cannot_poison_dead_player():
    engine = make_engine(Villager, Werewolf, Witch)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "werewolf", "witch"])
    state = engine._state
    villager_id = next(p.id for p in state.players.values() if p.role_id == "villager")
    witch_id = next(p.id for p in state.players.values() if p.role_id == "witch")
    state.players[villager_id].alive = False

    ctx = make_ctx(state)
    role = engine._roles["witch"]
    await role.on_night_action(ctx, {"player_id": witch_id, "poison_target": villager_id})

    assert villager_id not in ctx.pending_kills


async def test_witch_sees_pending_kill():
    engine = make_engine(Villager, Werewolf, Witch)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "werewolf", "witch"])
    state = engine._state
    villager_id = next(p.id for p in state.players.values() if p.role_id == "villager")

    # Simulate wolf adding a pending kill before witch acts
    state.pending_kills.append((villager_id, "wolf_kill"))

    ctx = make_ctx(state)
    assert villager_id in ctx.pending_kills
