"""Unit tests for server/handlers.py"""
from __future__ import annotations

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from custom_components.loup_garou.server.handlers import HANDLERS
from custom_components.loup_garou.const import Phase


def run_async(coro):
    """Run a coroutine synchronously for testing."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def mock_engine():
    """Create a mock GameEngine."""
    engine = MagicMock()
    engine.get_public_state.return_value = {"phase": Phase.SETUP}
    engine.async_start_game = AsyncMock(return_value={"phase": Phase.ROLE_REVEAL})
    engine.async_confirm_role_seen = AsyncMock(return_value={})
    engine.async_submit_night_action = AsyncMock(return_value={})
    engine.async_submit_vote = AsyncMock(return_value={"votes_cast": 1})
    engine.async_resolve_vote = AsyncMock(return_value={})
    engine.async_eliminate_player = AsyncMock(return_value=None)
    engine.async_begin_vote = AsyncMock()
    engine.async_reset = AsyncMock()
    engine.async_next_phase = AsyncMock()
    engine.current_night_role = "werewolf"
    return engine


@pytest.fixture
def mock_ws():
    """Create a mock WebSocket response."""
    ws = MagicMock()
    ws.send_json = AsyncMock()
    return ws


class TestGetStateHandler:
    def test_returns_current_state(self, mock_ws, mock_engine):
        """get_state returns public state from engine."""
        handler = HANDLERS["get_state"]

        state = {"phase": Phase.SETUP, "players": []}
        mock_engine.get_public_state.return_value = state

        run_async(handler(mock_ws, {"callback_id": "cb_123"}, mock_engine, None))

        mock_ws.send_json.assert_called_once_with({
            "type": "state",
            "data": state,
            "callback_id": "cb_123",
        })


class TestStartGameHandler:
    def test_calls_engine_start_game(self, mock_ws, mock_engine):
        """start_game calls engine method and returns state."""
        handler = HANDLERS["start_game"]

        run_async(handler(mock_ws, {
            "player_names": ["A", "B", "C", "D", "E"],
            "role_config": {"villagers": 3, "werewolves": 1, "seers": 1},
            "callback_id": "cb_123",
        }, mock_engine, None))

        mock_engine.async_start_game.assert_called_once()
        mock_ws.send_json.assert_called_once()

    def test_calls_phase_manager_on_game_started(self, mock_ws, mock_engine, mock_phase_manager):
        """Phase manager on_game_started is called after starting."""
        handler = HANDLERS["start_game"]

        run_async(handler(mock_ws, {
            "player_names": ["A", "B", "C", "D", "E"],
            "role_config": {"villagers": 3, "werewolves": 1, "seers": 1},
            "callback_id": "cb_123",
        }, mock_engine, mock_phase_manager))

        mock_phase_manager.on_game_started.assert_called_once()

    def test_error_returns_error_message(self, mock_ws, mock_engine):
        """Exceptions return error type with message."""
        mock_engine.async_start_game.side_effect = ValueError("Test error")

        handler = HANDLERS["start_game"]

        run_async(handler(mock_ws, {"callback_id": "cb_123"}, mock_engine, None))

        mock_ws.send_json.assert_called_once_with({
            "type": "error",
            "message": "Test error",
            "callback_id": "cb_123",
        })


class TestConfirmRoleSeenHandler:
    def test_calls_engine_confirm_role_seen(self, mock_ws, mock_engine):
        """Handler calls engine method with player_id."""
        handler = HANDLERS["confirm_role_seen"]

        run_async(handler(mock_ws, {"player_id": "p123", "callback_id": "cb_123"}, mock_engine, None))

        mock_engine.async_confirm_role_seen.assert_called_once_with("p123")


class TestNightActionHandler:
    def test_calls_engine_submit_night_action(self, mock_ws, mock_engine):
        """Handler passes action_type and target_id to engine."""
        handler = HANDLERS["night_action"]

        run_async(handler(mock_ws, {
            "action_type": "seer_investigate",
            "target_id": "p456",
            "callback_id": "cb_123",
        }, mock_engine, None))

        mock_engine.async_submit_night_action.assert_called_once()

    def test_notifies_phase_manager_on_action(self, mock_ws, mock_engine, mock_phase_manager):
        """Phase manager is notified after night action."""
        handler = HANDLERS["night_action"]

        run_async(handler(mock_ws, {
            "action_type": "seer_investigate",
            "target_id": "p456",
            "callback_id": "cb_123",
        }, mock_engine, mock_phase_manager))

        mock_phase_manager.on_night_action_submitted.assert_called_once()


class TestSubmitVoteHandler:
    def test_calls_engine_submit_vote(self, mock_ws, mock_engine):
        """Handler passes voter_id and target_id to engine."""
        handler = HANDLERS["submit_vote"]

        run_async(handler(mock_ws, {
            "voter_id": "voter",
            "target_id": "target",
            "callback_id": "cb_123",
        }, mock_engine, None))

        mock_engine.async_submit_vote.assert_called_once_with("voter", "target")


class TestResetHandler:
    def test_calls_engine_reset(self, mock_ws, mock_engine):
        """Handler calls engine reset method."""
        handler = HANDLERS["reset"]

        run_async(handler(mock_ws, {"callback_id": "cb_123"}, mock_engine, None))

        mock_engine.async_reset.assert_called_once()


class TestNextPhaseHandler:
    def test_calls_engine_next_phase(self, mock_ws, mock_engine):
        """Handler calls engine next_phase method."""
        handler = HANDLERS["next_phase"]

        run_async(handler(mock_ws, {"callback_id": "cb_123"}, mock_engine, None))

        mock_engine.async_next_phase.assert_called_once()


class TestHandlerRegistry:
    def test_all_expected_handlers_present(self):
        """All message types have handlers."""
        expected = [
            "get_state", "start_game", "confirm_role_seen",
            "night_action", "submit_vote", "resolve_votes",
            "eliminate_player", "begin_vote", "reset", "next_phase",
        ]

        for cmd in expected:
            assert cmd in HANDLERS, f"Missing handler for {cmd}"