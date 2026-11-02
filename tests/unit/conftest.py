"""Shared fixtures for unit tests."""
from __future__ import annotations

import asyncio

import pytest

from loup_garou.game_engine import GameEngine, GameState, Player
from loup_garou.roles.base import RoleContext
from loup_garou.roles.impl.villager import Villager
from loup_garou.roles.impl.werewolf import Werewolf
from loup_garou.roles.impl.seer import Seer


def make_engine(*role_classes) -> GameEngine:
    """Build a GameEngine with only the specified role classes registered."""
    roles = {cls.id: cls() for cls in role_classes}
    return GameEngine(roles=roles)


async def noop_emit(event, data=None):
    pass


def make_ctx(state: GameState, emit=None) -> RoleContext:
    return RoleContext(state, emit or noop_emit)


async def answer_turn(engine: GameEngine, role: str, action: dict) -> None:
    """Wait for this role's prompt to open, then answer it."""
    for _ in range(1000):
        prompt = engine.prompt
        if prompt is not None and prompt.role == role:
            result = await engine.answer(prompt.id, action)
            assert result == "accepted", f"{role}: {action} was {result}: {prompt}"
            return
        await asyncio.sleep(0)
    raise AssertionError(f"no prompt opened for {role}; open: {engine.prompt}")
