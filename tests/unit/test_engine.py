"""Unit tests for core/engine.py"""
from __future__ import annotations

import pytest
from unittest.mock import patch

from custom_components.loup_garou.core.engine import GameEngine
from custom_components.loup_garou.const import Phase, Role, NightActionType, WinCondition

from tests.conftest import run_async


class TestAsyncStartGame:
    def test_start_game_transitions_to_role_reveal(self, mock_hass, mock_store):
        """Game starts in role_reveal phase."""
        with patch("homeassistant.helpers.storage.Store", return_value=mock_store):
            engine = GameEngine(mock_hass, "test_entry")

        state = run_async(engine.async_start_game(
            ["A", "B", "C", "D", "E"],
            {"villagers": 3, "werewolves": 1, "seers": 1},
            "fr"
        ))

        assert state["phase"] == Phase.ROLE_REVEAL
        assert len(state["players"]) == 5

    def test_start_game_validates_role_count(self, mock_hass, mock_store):
        """Raises error if roles don't sum to player count."""
        with patch("homeassistant.helpers.storage.Store", return_value=mock_store):
            engine = GameEngine(mock_hass, "test_entry")

        with pytest.raises(ValueError, match="must equal player count"):
            run_async(engine.async_start_game(
                ["A", "B", "C", "D", "E"],
                {"villagers": 10, "werewolves": 0, "seers": 0},
                "fr"
            ))

    def test_start_game_requires_werewolf(self, mock_hass, mock_store):
        """Raises error if no werewolf configured."""
        with patch("homeassistant.helpers.storage.Store", return_value=mock_store):
            engine = GameEngine(mock_hass, "test_entry")

        with pytest.raises(ValueError, match="at least 1 werewolf"):
            run_async(engine.async_start_game(
                ["A", "B", "C", "D", "E"],
                {"villagers": 5, "werewolves": 0, "seers": 0},
                "fr"
            ))


class TestConfirmRoleSeen:
    def test_confirm_role_seen_marks_player(self, mock_hass, mock_store):
        """Player's role_seen flag is set after confirmation."""
        with patch("homeassistant.helpers.storage.Store", return_value=mock_store):
            engine = GameEngine(mock_hass, "test_entry")

        run_async(engine.async_start_game(
            ["A", "B", "C", "D", "E"],
            {"villagers": 3, "werewolves": 1, "seers": 1},
            "fr"
        ))

        first_id = engine.state.reveal_order[0]
        run_async(engine.async_confirm_role_seen(first_id))

        player = next(p for p in engine.state.players if p.id == first_id)
        assert player.role_seen is True

    def test_confirm_role_seen_unknown_player_raises(self, mock_hass, mock_store):
        """Unknown player ID raises ValueError."""
        with patch("homeassistant.helpers.storage.Store", return_value=mock_store):
            engine = GameEngine(mock_hass, "test_entry")

        with pytest.raises(ValueError, match="Unknown player"):
            run_async(engine.async_confirm_role_seen("fake_id"))

    def test_all_players_confirmed_starts_night(self, mock_hass, mock_store):
        """When all players confirm, phase transitions to night."""
        with patch("homeassistant.helpers.storage.Store", return_value=mock_store):
            engine = GameEngine(mock_hass, "test_entry")

        run_async(engine.async_start_game(
            ["A", "B", "C", "D", "E"],
            {"villagers": 3, "werewolves": 1, "seers": 1},
            "fr"
        ))

        for player_id in engine.state.reveal_order:
            run_async(engine.async_confirm_role_seen(player_id))

        assert engine.state.phase == Phase.NIGHT
        assert engine.state.round == 1


class TestSubmitNightAction:
    def test_seer_investigate_stores_result(self, mock_hass, mock_store):
        """Seer investigate stores the target's role."""
        with patch("homeassistant.helpers.storage.Store", return_value=mock_store):
            engine = GameEngine(mock_hass, "test_entry")

        run_async(engine.async_start_game(
            ["Seer", "Wolf", "Vill1", "Vill2", "Vill3"],
            {"villagers": 3, "werewolves": 1, "seers": 1},
            "fr"
        ))

        for pid in engine.state.reveal_order:
            run_async(engine.async_confirm_role_seen(pid))

        seer = next(p for p in engine.state.players if p.role == Role.SEER)
        target = next(p for p in engine.state.players if p.role == Role.VILLAGER)

        state = run_async(engine.async_submit_night_action(
            NightActionType.SEER_INVESTIGATE,
            target.id,
        ))

        assert Role.SEER in state["night_actions_completed"]

    def test_wolf_kill_cannot_target_wolf(self, mock_hass, mock_store):
        """Wolf cannot kill another wolf."""
        with patch("homeassistant.helpers.storage.Store", return_value=mock_store):
            engine = GameEngine(mock_hass, "test_entry")

        run_async(engine.async_start_game(
            ["Wolf1", "Wolf2", "Vill1", "Vill2", "Vill3"],
            {"villagers": 3, "werewolves": 2, "seers": 0},
            "fr"
        ))

        for pid in engine.state.reveal_order:
            run_async(engine.async_confirm_role_seen(pid))

        wolves = [p for p in engine.state.players if p.role == Role.WEREWOLF]

        with pytest.raises(ValueError, match="Wolves cannot target each other"):
            run_async(engine.async_submit_night_action(
                NightActionType.WOLF_KILL,
                wolves[1].id,
            ))


class TestSubmitVote:
    def test_submit_vote_not_in_vote_phase(self, mock_hass, mock_store):
        """Submitting vote outside vote phase raises error."""
        with patch("homeassistant.helpers.storage.Store", return_value=mock_store):
            engine = GameEngine(mock_hass, "test_entry")

        run_async(engine.async_start_game(
            ["A", "B", "C", "D", "E"],
            {"villagers": 3, "werewolves": 1, "seers": 1},
            "fr"
        ))

        player = engine.state.players[0]

        with pytest.raises(ValueError, match="Not in vote phase"):
            run_async(engine.async_submit_vote(player.id, player.id))


class TestWinCondition:
    def test_villagers_win_when_all_wolves_dead(self, mock_hass, mock_store):
        """Villagers win when all wolves eliminated."""
        with patch("homeassistant.helpers.storage.Store", return_value=mock_store):
            engine = GameEngine(mock_hass, "test_entry")

        run_async(engine.async_start_game(
            ["A", "B", "C", "D"],
            {"villagers": 3, "werewolves": 1, "seers": 0},
            "fr"
        ))

        wolf = next(p for p in engine.state.players if p.role == Role.WEREWOLF)
        run_async(engine.async_eliminate_player(wolf.id, "village_vote"))

        assert engine.state.winner == WinCondition.VILLAGERS
        assert engine.state.phase == Phase.GAME_OVER

    def test_wolves_win_when_equal_count(self, mock_hass, mock_store):
        """Wolves win when their count equals village."""
        with patch("homeassistant.helpers.storage.Store", return_value=mock_store):
            engine = GameEngine(mock_hass, "test_entry")

        run_async(engine.async_start_game(
            ["Wolf1", "Wolf2", "Villager"],
            {"villagers": 1, "werewolves": 2, "seers": 0},
            "fr"
        ))

        villager = next(p for p in engine.state.players if p.role == Role.VILLAGER)
        run_async(engine.async_eliminate_player(villager.id, "village_vote"))

        assert engine.state.winner == WinCondition.WOLVES
        assert engine.state.phase == Phase.GAME_OVER


class TestGetPublicState:
    def test_public_state_excludes_roles(self, mock_hass, mock_store):
        """Public state does not reveal player roles."""
        with patch("homeassistant.helpers.storage.Store", return_value=mock_store):
            engine = GameEngine(mock_hass, "test_entry")

        run_async(engine.async_start_game(
            ["A", "B", "C", "D", "E"],
            {"villagers": 3, "werewolves": 1, "seers": 1},
            "fr"
        ))

        state = engine.get_public_state()

        for player in state["players"]:
            assert "role" not in player

    def test_public_state_includes_next_reveal_player(self, mock_hass, mock_store):
        """Public state includes the next player to receive their role."""
        with patch("homeassistant.helpers.storage.Store", return_value=mock_store):
            engine = GameEngine(mock_hass, "test_entry")

        run_async(engine.async_start_game(
            ["A", "B", "C", "D", "E"],
            {"villagers": 3, "werewolves": 1, "seers": 1},
            "fr"
        ))

        state = engine.get_public_state()

        assert state["next_reveal_player"] is not None
        assert state["reveal_index"] == 0
        assert state["reveal_total"] == 5


class TestReset:
    def test_reset_clears_game_state(self, mock_hass, mock_store):
        """Reset returns game to initial state."""
        with patch("homeassistant.helpers.storage.Store", return_value=mock_store):
            engine = GameEngine(mock_hass, "test_entry")

        run_async(engine.async_start_game(
            ["A", "B", "C", "D", "E"],
            {"villagers": 3, "werewolves": 1, "seers": 1},
            "fr"
        ))

        run_async(engine.async_reset())

        assert engine.state.phase == Phase.SETUP
        assert len(engine.state.players) == 0


class TestCurrentNightRole:
    def test_current_night_role_returns_seer_first(self, mock_hass, mock_store):
        """Seer acts before werewolf during night."""
        with patch("homeassistant.helpers.storage.Store", return_value=mock_store):
            engine = GameEngine(mock_hass, "test_entry")

        run_async(engine.async_start_game(
            ["Seer", "Wolf", "Vill1", "Vill2", "Vill3"],
            {"villagers": 3, "werewolves": 1, "seers": 1},
            "fr"
        ))

        for pid in engine.state.reveal_order:
            run_async(engine.async_confirm_role_seen(pid))

        assert engine.current_night_role == Role.SEER

        seer = next(p for p in engine.state.players if p.role == Role.SEER)
        target = next(p for p in engine.state.players if p.role == Role.VILLAGER)
        state = run_async(engine.async_submit_night_action(NightActionType.SEER_INVESTIGATE, target.id))

        assert state["night_actions_completed"] == [Role.SEER]
        assert engine.current_night_role == Role.WEREWOLF # Role advance to next one 
