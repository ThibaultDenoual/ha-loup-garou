"""Tests for core_game/io_adapters/ha_adapter.py"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock

from custom_components.loup_garou.core_game.io_adapters.ha_adapter import (
    AsyncGameAdapter,
    HAIntegrationState,
)


@pytest.fixture
def mock_hass():
    hass = MagicMock()
    hass.data = {}
    return hass


@pytest.fixture
def adapter(mock_hass):
    return AsyncGameAdapter(hass=mock_hass, config_entry_id="test_entry")


class TestHAIntegrationState:
    def test_default_values(self):
        state = HAIntegrationState()
        assert state.phase == "setup"
        assert state.round == 0
        assert state.players == []
        assert state.winner is None
        assert state.language == "fr"


class TestAsyncGameAdapterInit:
    def test_initializes_with_defaults(self, adapter):
        assert adapter._hass is not None
        assert adapter._config_entry_id == "test_entry"
        assert adapter._engine is None
        assert adapter._state.phase == "setup"

    def test_state_property(self, adapter):
        assert adapter.state is adapter._state


class TestAsyncGameAdapterStartGame:
    @pytest.mark.asyncio
    async def test_start_game_assigns_roles(self, adapter):
        state = await adapter.async_start_game(
            player_names=["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank"],
            role_config={"preset": "small"},
        )
        assert len(state["players"]) == 6
        assert state["phase"] == "role_reveal"

    @pytest.mark.asyncio
    async def test_start_game_sets_reveal_order(self, adapter):
        await adapter.async_start_game(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_config={"preset": "small"},
        )
        assert len(adapter._state.reveal_order) == 6
        assert adapter._state.reveal_index == 0

    @pytest.mark.asyncio
    async def test_start_game_role_count_mismatch_raises(self, adapter):
        with pytest.raises(ValueError, match="must match player count"):
            await adapter.async_start_game(
                player_names=["A", "B", "C"],
                role_config={"preset": "small"},
            )

    @pytest.mark.asyncio
    async def test_start_game_sets_language(self, adapter):
        await adapter.async_start_game(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_config={"preset": "small"},
            language="en",
        )
        assert adapter._state.language == "en"


class TestAsyncGameAdapterConfirmRoleSeen:
    @pytest.mark.asyncio
    async def test_confirm_role_seen_marks_player(self, adapter):
        await adapter.async_start_game(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_config={"preset": "small"},
        )
        player_id = adapter._state.players[0]["id"]
        await adapter.async_confirm_role_seen(player_id)
        assert adapter._state.players[0]["role_seen"] is True

    @pytest.mark.asyncio
    async def test_confirm_role_seen_advances_reveal(self, adapter):
        await adapter.async_start_game(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_config={"preset": "small"},
        )
        for i in range(6):
            await adapter.async_confirm_role_seen(adapter._state.players[i]["id"])
        assert adapter._state.phase == "night_start"
        assert adapter._state.round == 1

    @pytest.mark.asyncio
    async def test_confirm_role_seen_partial_reveal(self, adapter):
        await adapter.async_start_game(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_config={"preset": "small"},
        )
        await adapter.async_confirm_role_seen(adapter._state.players[0]["id"])
        assert adapter._state.phase == "role_reveal"
        assert adapter._state.reveal_index == 1


class TestAsyncGameAdapterNightAction:
    @pytest.mark.asyncio
    async def test_submit_night_action_wolf_kill(self, adapter):
        await adapter.async_start_game(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_config={"preset": "small"},
        )
        for i in range(6):
            await adapter.async_confirm_role_seen(adapter._state.players[i]["id"])
        target_id = adapter._state.players[5]["id"]
        state = await adapter.async_submit_night_action("wolf_kill", target_id)
        assert state is not None

    @pytest.mark.asyncio
    async def test_submit_night_action_seer_investigate(self, adapter):
        await adapter.async_start_game(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_config={"preset": "small"},
        )
        for i in range(6):
            await adapter.async_confirm_role_seen(adapter._state.players[i]["id"])
        target_id = adapter._state.players[5]["id"]
        state = await adapter.async_submit_night_action("seer_investigate", target_id)
        assert state is not None
        assert adapter._state.night_actions["seer_target_id"] == target_id

    @pytest.mark.asyncio
    async def test_submit_night_action_not_started_raises(self, adapter):
        with pytest.raises(ValueError, match="Game not started"):
            await adapter.async_submit_night_action("wolf_kill", "fake_id")

    @pytest.mark.asyncio
    async def test_submit_night_action_invalid_target_raises(self, adapter):
        await adapter.async_start_game(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_config={"preset": "small"},
        )
        with pytest.raises(ValueError, match="Invalid target"):
            await adapter.async_submit_night_action("wolf_kill", "fake_id")


class TestAsyncGameAdapterVotes:
    @pytest.mark.asyncio
    async def test_submit_vote(self, adapter):
        await adapter.async_start_game(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_config={"preset": "small"},
        )
        state = await adapter.async_submit_vote("A", "B")
        assert state["votes_cast"] == 1
        assert adapter._state.vote_tallies["B"] == ["A"]

    @pytest.mark.asyncio
    async def test_submit_vote_multiple_votes(self, adapter):
        await adapter.async_start_game(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_config={"preset": "small"},
        )
        await adapter.async_submit_vote("A", "C")
        await adapter.async_submit_vote("B", "C")
        assert adapter._state.vote_tallies["C"] == ["A", "B"]

    @pytest.mark.asyncio
    async def test_resolve_vote_eliminates_top_voted(self, adapter):
        await adapter.async_start_game(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_config={"preset": "small"},
        )
        await adapter.async_submit_vote("A", "C")
        await adapter.async_submit_vote("B", "C")
        await adapter.async_resolve_vote()
        assert adapter._state.eliminated_this_round == ["C"]

    @pytest.mark.asyncio
    async def test_resolve_vote_tie_no_elimination(self, adapter):
        await adapter.async_start_game(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_config={"preset": "small"},
        )
        await adapter.async_submit_vote("A", "C")
        await adapter.async_submit_vote("B", "C")
        await adapter.async_submit_vote("C", "A")
        await adapter.async_submit_vote("D", "A")
        await adapter.async_resolve_vote()
        assert adapter._state.eliminated_this_round == []

    @pytest.mark.asyncio
    async def test_resolve_vote_empty_no_elimination(self, adapter):
        await adapter.async_start_game(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_config={"preset": "small"},
        )
        await adapter.async_resolve_vote()
        assert adapter._state.eliminated_this_round == []


class TestAsyncGameAdapterEliminatePlayer:
    @pytest.mark.asyncio
    async def test_eliminate_player_marks_dead(self, adapter):
        await adapter.async_start_game(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_config={"preset": "small"},
        )
        player_id = adapter._state.players[0]["id"]
        await adapter.async_eliminate_player(player_id, "vote")
        assert adapter._state.players[0]["alive"] is False

    @pytest.mark.asyncio
    async def test_eliminate_player_unknown_raises(self, adapter):
        await adapter.async_start_game(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_config={"preset": "small"},
        )
        with pytest.raises(ValueError, match="Unknown player"):
            await adapter.async_eliminate_player("fake_id", "vote")

    @pytest.mark.asyncio
    async def test_eliminate_player_all_wolves_triggers_game_over(self, adapter):
        await adapter.async_start_game(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_config={"preset": "small"},
        )
        werewolf_player = None
        for p in adapter._state.players:
            if p["team"] == "werewolf":
                werewolf_player = p["id"]
                break
        if werewolf_player:
            await adapter.async_eliminate_player(werewolf_player, "vote")
            assert adapter._state.winner == "village"
            assert adapter._state.phase == "game_over"


class TestAsyncGameAdapterPhaseTransition:
    @pytest.mark.asyncio
    async def test_next_phase_night_start_to_seer_wake(self, adapter):
        adapter._state.phase = "night_start"
        await adapter.async_next_phase()
        assert adapter._state.phase == "night_seer_wake"

    @pytest.mark.asyncio
    async def test_next_phase_full_night_cycle(self, adapter):
        adapter._state.phase = "night_start"
        adapter._state.night_actions = {}
        phases = ["night_seer_wake", "night_seer_act", "night_seer_sleep",
                 "night_wolf_wake", "night_wolf_act", "night_wolf_sleep"]
        for expected in phases:
            await adapter.async_next_phase()
            assert adapter._state.phase == expected
        assert adapter._state.phase == "night_wolf_sleep"
        await adapter.async_next_phase()
        assert adapter._state.phase == "day"
        assert adapter._state.round == 1

    @pytest.mark.asyncio
    async def test_next_phase_day_to_discussion(self, adapter):
        adapter._state.phase = "day"
        await adapter.async_next_phase()
        assert adapter._state.phase == "discussion"

    @pytest.mark.asyncio
    async def test_next_phase_discussion_to_vote(self, adapter):
        adapter._state.phase = "discussion"
        await adapter.async_next_phase()
        assert adapter._state.phase == "vote"

    @pytest.mark.asyncio
    async def test_next_phase_vote_with_elimination_goes_to_day(self, adapter):
        await adapter.async_start_game(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_config={"preset": "small"},
        )
        await adapter.async_submit_vote("A", "C")
        await adapter.async_submit_vote("B", "C")
        await adapter.async_submit_vote("C", "C")
        await adapter.async_submit_vote("D", "C")
        adapter._state.phase = "vote"
        await adapter.async_next_phase()
        assert adapter._state.phase == "day"
        assert adapter._state.eliminated_this_round == ["C"]

    @pytest.mark.asyncio
    async def test_next_phase_vote_tie_goes_to_night(self, adapter):
        adapter._state.phase = "vote"
        adapter._state.vote_tallies = {}
        adapter._state.eliminated_this_round = []
        await adapter.async_next_phase()
        assert adapter._state.phase == "night_start"


class TestAsyncGameAdapterMisc:
    @pytest.mark.asyncio
    async def test_begin_vote(self, adapter):
        adapter._state.phase = "day"
        await adapter.async_begin_vote()
        assert adapter._state.phase == "vote"
        assert adapter._state.vote_tallies == {}

    @pytest.mark.asyncio
    async def test_select_target(self, adapter):
        await adapter.async_select_target("player_123")
        assert adapter._state.current_target_id == "player_123"

    @pytest.mark.asyncio
    async def test_skip_night_action(self, adapter):
        await adapter.async_skip_night_action()
        assert "current" in adapter._state.night_actions.get("completed_roles", [])

    @pytest.mark.asyncio
    async def test_reset(self, adapter):
        await adapter.async_start_game(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_config={"preset": "small"},
        )
        state = await adapter.async_reset()
        assert state["phase"] == "setup"
        assert adapter._state.phase == "setup"
        assert adapter._engine is None


class TestAsyncGameAdapterGetPublicState:
    @pytest.mark.asyncio
    async def test_get_public_state_structure(self, adapter):
        await adapter.async_start_game(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_config={"preset": "small"},
        )
        state = adapter.get_public_state()
        assert "phase" in state
        assert "round" in state
        assert "players" in state
        assert "alive_count" in state
        assert "reveal_index" in state
        assert "reveal_total" in state

    @pytest.mark.asyncio
    async def test_get_public_state_excludes_roles(self, adapter):
        await adapter.async_start_game(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_config={"preset": "small"},
        )
        state = adapter.get_public_state()
        for player in state["players"]:
            assert "role" not in player

    @pytest.mark.asyncio
    async def test_get_public_state_alive_counts(self, adapter):
        await adapter.async_start_game(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_config={"preset": "small"},
        )
        state = adapter.get_public_state()
        assert state["alive_count"] == 6
        assert state["dead_count"] == 0


class TestAsyncGameAdapterGetPrivateData:
    @pytest.mark.asyncio
    async def test_get_role_reveal_data(self, adapter):
        await adapter.async_start_game(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_config={"preset": "small"},
        )
        player_id = adapter._state.reveal_order[0]
        data = adapter.get_role_reveal_data(player_id)
        assert "player_id" in data
        assert "player_name" in data
        assert "role" in data

    @pytest.mark.asyncio
    async def test_get_role_reveal_data_wrong_order_raises(self, adapter):
        await adapter.async_start_game(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_config={"preset": "small"},
        )
        with pytest.raises(ValueError, match="Not this player's turn"):
            adapter.get_role_reveal_data("B")

    @pytest.mark.asyncio
    async def test_get_seer_result_not_seer_raises(self, adapter):
        await adapter.async_start_game(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_config={"preset": "small"},
        )
        non_seer = adapter._state.players[0]["id"]
        with pytest.raises(ValueError, match="Not a seer"):
            adapter.get_seer_result(non_seer)

    @pytest.mark.asyncio
    async def test_get_full_state_for_end(self, adapter):
        adapter._state.phase = "game_over"
        adapter._state.winner = "village"
        data = adapter.get_full_state_for_end()
        assert "players_full" in data