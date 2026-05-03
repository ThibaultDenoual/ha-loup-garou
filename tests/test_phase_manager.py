"""Tests for PhaseManager — verifies lights and TTS fire on correct events."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from custom_components.loup_garou.phase_manager import PhaseManager
from custom_components.loup_garou.const import Role, WinCondition, EliminationCause


@pytest.fixture
def hass(mock_hass):
    return mock_hass


@pytest.fixture
def engine():
    eng = MagicMock()
    eng.state = MagicMock()
    eng.state.phase = "night"
    eng.state.round = 1
    eng.state.eliminations = []
    eng.state.players = {}
    eng._current_night_role = MagicMock(return_value=Role.SEER)
    return eng


@pytest.fixture
def lights():
    lc = MagicMock()
    lc.async_set_scene = AsyncMock()
    return lc


@pytest.fixture
def speaker():
    sp = MagicMock()
    sp.async_speak = AsyncMock()
    return sp


@pytest.fixture
def pm(hass, engine, lights, speaker):
    return PhaseManager(hass, engine, lights, speaker, language="en")


class TestOnNightStarted:
    @pytest.mark.asyncio
    async def test_sets_night_scene(self, pm, lights):
        await pm.on_night_started()
        lights.async_set_scene.assert_any_call("night")

    @pytest.mark.asyncio
    async def test_speaks_night_start(self, pm, speaker):
        await pm.on_night_started()
        spoken = speaker.async_speak.call_args_list[0][0][0]
        assert "sleep" in spoken.lower() or "asleep" in spoken.lower()


class TestOnRoleWake:
    @pytest.mark.asyncio
    async def test_seer_sets_seer_scene(self, pm, lights):
        await pm.on_role_wake(Role.SEER)
        lights.async_set_scene.assert_called_with("seer_wake")

    @pytest.mark.asyncio
    async def test_wolf_sets_wolf_scene(self, pm, lights):
        await pm.on_role_wake(Role.WEREWOLF)
        lights.async_set_scene.assert_called_with("wolf_wake")

    @pytest.mark.asyncio
    async def test_seer_wake_tts(self, pm, speaker):
        await pm.on_role_wake(Role.SEER)
        spoken = speaker.async_speak.call_args[0][0]
        assert "seer" in spoken.lower()

    @pytest.mark.asyncio
    async def test_wolf_wake_tts(self, pm, speaker):
        await pm.on_role_wake(Role.WEREWOLF)
        spoken = speaker.async_speak.call_args[0][0]
        assert "werewol" in spoken.lower() or "wolf" in spoken.lower()


class TestOnDayStarted:
    def _make_player(self, name="Alice", role=Role.VILLAGER):
        p = MagicMock()
        p.name = name
        p.role = role
        p.alive = False
        return p

    @pytest.mark.asyncio
    async def test_sets_day_scene(self, pm, lights):
        await pm.on_day_started(None)
        lights.async_set_scene.assert_called_with("day")

    @pytest.mark.asyncio
    async def test_no_death_tts(self, pm, speaker):
        await pm.on_day_started(None)
        spoken = speaker.async_speak.call_args[0][0]
        assert "no one died" in spoken.lower() or "miraculously" in spoken.lower()

    @pytest.mark.asyncio
    async def test_death_tts_includes_name(self, pm, speaker, engine):
        player = self._make_player("Bob", Role.VILLAGER)
        engine.state.players = {"pid_bob": player}
        await pm.on_day_started("pid_bob")
        spoken = speaker.async_speak.call_args[0][0]
        assert "Bob" in spoken


class TestOnPlayerEliminated:
    @pytest.mark.asyncio
    async def test_sets_death_scene(self, pm, lights, engine):
        player = MagicMock()
        player.name = "Carol"
        player.role = Role.VILLAGER
        engine.state.players = {"p1": player}
        await pm.on_player_eliminated("p1", EliminationCause.VILLAGE_VOTE)
        lights.async_set_scene.assert_called_with("death")

    @pytest.mark.asyncio
    async def test_elimination_tts_includes_name(self, pm, speaker, engine):
        player = MagicMock()
        player.name = "Dave"
        player.role = Role.WEREWOLF
        engine.state.players = {"p2": player}
        await pm.on_player_eliminated("p2", EliminationCause.VILLAGE_VOTE)
        spoken = speaker.async_speak.call_args[0][0]
        assert "Dave" in spoken


class TestOnGameOver:
    @pytest.mark.asyncio
    async def test_wolves_win_scene(self, pm, lights):
        await pm.on_game_over(WinCondition.WOLVES)
        lights.async_set_scene.assert_called_with("wolves_win")

    @pytest.mark.asyncio
    async def test_village_win_scene(self, pm, lights):
        await pm.on_game_over(WinCondition.VILLAGERS)
        lights.async_set_scene.assert_called_with("village_win")

    @pytest.mark.asyncio
    async def test_wolves_win_tts(self, pm, speaker):
        await pm.on_game_over(WinCondition.WOLVES)
        spoken = speaker.async_speak.call_args[0][0]
        assert "werewol" in spoken.lower() or "wolf" in spoken.lower()

    @pytest.mark.asyncio
    async def test_village_win_tts(self, pm, speaker):
        await pm.on_game_over(WinCondition.VILLAGERS)
        spoken = speaker.async_speak.call_args[0][0]
        assert "village" in spoken.lower()