"""Tests for PhaseManager — verifies lights and TTS fire on correct events."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from custom_components.loup_garou.services.phase_manager import PhaseManager
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
def io_mock():
    io = MagicMock()
    io.speak = MagicMock()
    io.set_scene = MagicMock()
    return io


@pytest.fixture
def pm(hass, engine, io_mock):
    pm = PhaseManager(hass, engine, io_interface=None, language="en")
    pm._io = io_mock  # Set the IO mock directly
    return pm


class TestOnNightStarted:
    @pytest.mark.asyncio
    async def test_sets_night_scene(self, pm, io_mock):
        await pm.on_night_started()
        io_mock.set_scene.assert_any_call("night")

    @pytest.mark.asyncio
    async def test_speaks_night_start(self, pm, io_mock):
        await pm.on_night_started()
        spoken = io_mock.speak.call_args_list[0][0][0]
        assert "sleep" in spoken.lower() or "asleep" in spoken.lower()


class TestOnRoleWake:
    @pytest.mark.asyncio
    async def test_seer_sets_seer_scene(self, pm, io_mock):
        await pm.on_role_wake(Role.SEER)
        io_mock.set_scene.assert_called_with("seer_wake")

    @pytest.mark.asyncio
    async def test_wolf_sets_wolf_scene(self, pm, io_mock):
        await pm.on_role_wake(Role.WEREWOLF)
        io_mock.set_scene.assert_called_with("wolf_wake")

    @pytest.mark.asyncio
    async def test_seer_wake_tts(self, pm, io_mock):
        await pm.on_role_wake(Role.SEER)
        spoken = io_mock.speak.call_args[0][0]
        assert "seer" in spoken.lower()

    @pytest.mark.asyncio
    async def test_wolf_wake_tts(self, pm, io_mock):
        await pm.on_role_wake(Role.WEREWOLF)
        spoken = io_mock.speak.call_args[0][0]
        assert "werewol" in spoken.lower() or "wolf" in spoken.lower()


class TestOnDayStarted:
    def _make_player(self, name="Alice", role=Role.VILLAGER):
        p = MagicMock()
        p.name = name
        p.role = role
        p.alive = False
        return p

    @pytest.mark.asyncio
    async def test_sets_day_scene(self, pm, io_mock):
        await pm.on_day_started(None)
        io_mock.set_scene.assert_called_with("day")

    @pytest.mark.asyncio
    async def test_no_death_tts(self, pm, io_mock):
        await pm.on_day_started(None)
        spoken = io_mock.speak.call_args[0][0]
        assert "no one died" in spoken.lower() or "miraculously" in spoken.lower()

    @pytest.mark.asyncio
    async def test_death_tts_includes_name(self, pm, io_mock, engine):
        player = self._make_player("Bob", Role.VILLAGER)
        engine.state.players = {"pid_bob": player}
        await pm.on_day_started("pid_bob")
        spoken = io_mock.speak.call_args[0][0]
        assert "Bob" in spoken


class TestOnPlayerEliminated:
    @pytest.mark.asyncio
    async def test_sets_death_scene(self, pm, io_mock, engine):
        player = MagicMock()
        player.name = "Carol"
        player.role = Role.VILLAGER
        engine.state.players = {"p1": player}
        await pm.on_player_eliminated("p1", EliminationCause.VILLAGE_VOTE)
        io_mock.set_scene.assert_called_with("death")

    @pytest.mark.asyncio
    async def test_elimination_tts_includes_name(self, pm, io_mock, engine):
        player = MagicMock()
        player.name = "Dave"
        player.role = Role.WEREWOLF
        engine.state.players = {"p2": player}
        await pm.on_player_eliminated("p2", EliminationCause.VILLAGE_VOTE)
        spoken = io_mock.speak.call_args[0][0]
        assert "Dave" in spoken


class TestOnGameOver:
    @pytest.mark.asyncio
    async def test_wolves_win_scene(self, pm, io_mock):
        await pm.on_game_over(WinCondition.WOLVES)
        io_mock.set_scene.assert_called_with("wolves_win")

    @pytest.mark.asyncio
    async def test_village_win_scene(self, pm, io_mock):
        await pm.on_game_over(WinCondition.VILLAGERS)
        io_mock.set_scene.assert_called_with("village_win")

    @pytest.mark.asyncio
    async def test_wolves_win_tts(self, pm, io_mock):
        await pm.on_game_over(WinCondition.WOLVES)
        spoken = io_mock.speak.call_args[0][0]
        assert "werewol" in spoken.lower() or "wolf" in spoken.lower()

    @pytest.mark.asyncio
    async def test_village_win_tts(self, pm, io_mock):
        await pm.on_game_over(WinCondition.VILLAGERS)
        spoken = io_mock.speak.call_args[0][0]
        assert "village" in spoken.lower()