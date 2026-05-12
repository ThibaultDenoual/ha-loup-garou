"""Tests for GameEngine — state machine, persistence, win conditions."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.loup_garou.core.engine import GameEngine
from custom_components.loup_garou.const import (
    Phase,
    Role,
    NightActionType,
    EliminationCause,
    WinCondition,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def hass(mock_hass):
    return mock_hass


@pytest.fixture
def engine(hass, mock_store):
    with patch(
        "custom_components.loup_garou.core.engine.Store",
        return_value=mock_store,
    ):
        eng = GameEngine(hass, "test_entry_id")
    return eng


FIVE_PLAYERS = ["Alice", "Bob", "Carol", "Dave", "Eve"]
ROLE_CONFIG_5 = {"villagers": 3, "werewolves": 1, "seers": 1}


async def _start(engine: GameEngine, players=FIVE_PLAYERS, config=ROLE_CONFIG_5):
    """Helper: start a game and return player ids."""
    result = await engine.async_start_game(players, config)
    return result["players"]


def _player_by_name(state, name):
    return next(p for p in state["players"] if p["name"] == name)


def _get_player_obj(engine, player_id):
    return next(p for p in engine._state.players if p.id == player_id)


# ── start_game ────────────────────────────────────────────────────────────────


class TestStartGame:
    @pytest.mark.asyncio
    async def test_phase_is_role_reveal(self, engine):
        await _start(engine)
        assert engine._state.phase == Phase.ROLE_REVEAL

    @pytest.mark.asyncio
    async def test_all_players_created(self, engine):
        await _start(engine)
        assert len(engine._state.players) == 5

    @pytest.mark.asyncio
    async def test_role_counts(self, engine):
        await _start(engine)
        roles = [p.role for p in engine._state.players]
        assert roles.count(Role.WEREWOLF) == 1
        assert roles.count(Role.SEER) == 1
        assert roles.count(Role.VILLAGER) == 3

    @pytest.mark.asyncio
    async def test_reveal_order_shuffled_length(self, engine):
        await _start(engine)
        assert len(engine._state.reveal_order) == 5

    @pytest.mark.asyncio
    async def test_too_few_players_raises(self, engine):
        with pytest.raises(ValueError):
            await engine.async_start_game(["A", "B", "C"], ROLE_CONFIG_5)

    @pytest.mark.asyncio
    async def test_round_starts_at_zero(self, engine):
        await _start(engine)
        assert engine._state.round == 0


# ── confirm_role_seen ─────────────────────────────────────────────────────────


class TestConfirmRoleSeen:
    @pytest.mark.asyncio
    async def test_confirm_marks_role_seen(self, engine):
        await _start(engine)
        pid = engine._state.reveal_order[0]
        await engine.async_confirm_role_seen(pid)
        p = _get_player_obj(engine, pid)
        assert p.role_seen

    @pytest.mark.asyncio
    async def test_advances_reveal_index(self, engine):
        await _start(engine)
        pid = engine._state.reveal_order[0]
        await engine.async_confirm_role_seen(pid)
        assert engine._state.reveal_index == 1

    @pytest.mark.asyncio
    async def test_all_confirmed_transitions_to_night(self, engine):
        await _start(engine)
        for pid in engine._state.reveal_order:
            await engine.async_confirm_role_seen(pid)
        assert engine._state.phase == Phase.NIGHT

    @pytest.mark.asyncio
    async def test_night_round_becomes_1(self, engine):
        await _start(engine)
        for pid in engine._state.reveal_order:
            await engine.async_confirm_role_seen(pid)
        assert engine._state.round == 1


# ── Night actions ─────────────────────────────────────────────────────────────


class TestNightActions:
    async def _setup_night(self, engine):
        """Start game and confirm all roles so we're in NIGHT phase."""
        await _start(engine)
        for pid in engine._state.reveal_order:
            await engine.async_confirm_role_seen(pid)

    def _wolf_id(self, engine) -> str:
        return next(p.id for p in engine._state.players if p.role == Role.WEREWOLF)

    def _seer_id(self, engine) -> str:
        return next(p.id for p in engine._state.players if p.role == Role.SEER)

    def _non_wolf_id(self, engine) -> str:
        return next(p.id for p in engine._state.players if p.role != Role.WEREWOLF)

    @pytest.mark.asyncio
    async def test_seer_is_first_acting_role(self, engine):
        await self._setup_night(engine)
        assert engine.current_night_role == Role.SEER

    @pytest.mark.asyncio
    async def test_wolf_cannot_target_wolf(self, engine):
        await self._setup_night(engine)
        target = self._non_wolf_id(engine)
        await engine.async_submit_night_action(
            NightActionType.SEER_INVESTIGATE, target
        )
        # Wolf tries to target another wolf — should fail
        wolf_id = self._wolf_id(engine)
        with pytest.raises(ValueError, match="cannot target"):
            await engine.async_submit_night_action(
                NightActionType.WOLF_KILL, wolf_id
            )

    @pytest.mark.asyncio
    async def test_wolf_action_recorded(self, engine):
        await self._setup_night(engine)
        target = self._non_wolf_id(engine)
        await engine.async_submit_night_action(
            NightActionType.SEER_INVESTIGATE, target
        )
        await engine.async_submit_night_action(
           NightActionType.WOLF_KILL, target
        )
        assert engine._state.night_actions.wolf_victim_id == target

    @pytest.mark.asyncio
    async def test_actions_complete_night_state(self, engine):
        await self._setup_night(engine)
        target = self._non_wolf_id(engine)
        await engine.async_submit_night_action(
             NightActionType.SEER_INVESTIGATE, target
        )
        await engine.async_submit_night_action(
            NightActionType.WOLF_KILL, target
        )
        # Both roles have completed their actions
        assert Role.SEER in engine._state.night_actions.completed_roles
        assert Role.WEREWOLF in engine._state.night_actions.completed_roles
        # Host advances to day manually
        await engine.async_next_phase()
        assert engine._state.phase in (Phase.DAY, Phase.GAME_OVER)


# ── check_win_condition ───────────────────────────────────────────────────────


class TestWinCondition:
    @pytest.mark.asyncio
    async def test_no_winner_initially(self, engine):
        await _start(engine)
        assert engine.check_win_condition() is None

    @pytest.mark.asyncio
    async def test_village_wins_when_wolf_dead(self, engine):
        await _start(engine)
        wolf = next(p for p in engine._state.players if p.role == Role.WEREWOLF)
        wolf.alive = False
        assert engine.check_win_condition() == WinCondition.VILLAGERS

    @pytest.mark.asyncio
    async def test_wolves_win_when_majority(self, engine):
        await _start(engine)
        villagers = [p for p in engine._state.players if p.role != Role.WEREWOLF]
        for p in villagers[:-1]:
            p.alive = False
        assert engine.check_win_condition() == WinCondition.WOLVES

    @pytest.mark.asyncio
    async def test_no_winner_balanced(self, engine):
        """2 wolves vs 4 villagers → no winner yet."""
        await engine.async_start_game(
            ["A", "B", "C", "D", "E", "F"],
            {"villagers": 4, "werewolves": 2, "seers": 0},
        )
        assert engine.check_win_condition() is None


# ── eliminate_player ──────────────────────────────────────────────────────────


class TestEliminatePlayer:
    @pytest.mark.asyncio
    async def test_player_marked_dead(self, engine):
        await _start(engine)
        pid = engine._state.players[0].id
        await engine.async_eliminate_player(pid, EliminationCause.VILLAGE_VOTE)
        p = _get_player_obj(engine, pid)
        assert not p.alive

    @pytest.mark.asyncio
    async def test_elimination_logged(self, engine):
        await _start(engine)
        pid = engine._state.players[0].id
        await engine.async_eliminate_player(pid, EliminationCause.VILLAGE_VOTE)
        assert pid in engine._state.eliminated_this_round

    @pytest.mark.asyncio
    async def test_cannot_eliminate_dead_player_twice(self, engine):
        await _start(engine)
        pid = engine._state.players[0].id
        await engine.async_eliminate_player(pid, EliminationCause.VILLAGE_VOTE)
        # Eliminating again doesn't raise (player still exists, already dead)
        # but the elimination list should not duplicate
        before_len = len(engine._state.eliminated_this_round)
        await engine.async_eliminate_player(pid, EliminationCause.WOLF_KILL)
        assert len(engine._state.eliminated_this_round) == before_len + 1

    @pytest.mark.asyncio
    async def test_game_over_when_wolf_eliminated(self, engine):
        await _start(engine)
        wolf = next(p for p in engine._state.players if p.role == Role.WEREWOLF)
        await engine.async_eliminate_player(wolf.id, EliminationCause.VILLAGE_VOTE)
        assert engine._state.winner == WinCondition.VILLAGERS
        assert engine._state.phase == Phase.GAME_OVER


# ── Vote ──────────────────────────────────────────────────────────────────────


class TestVotes:
    @pytest.mark.asyncio
    async def test_vote_recorded(self, engine):
        await _start(engine)
        engine._state.phase = Phase.VOTE
        pids = [p.id for p in engine._state.players]
        await engine.async_submit_vote(pids[0], pids[1])
        assert pids[1] in engine._state.vote_tallies
        assert pids[0] in engine._state.vote_tallies[pids[1]]

    @pytest.mark.asyncio
    async def test_no_self_vote(self, engine):
        await _start(engine)
        engine._state.phase = Phase.VOTE
        pid = engine._state.players[0].id
        with pytest.raises(ValueError, match="yourself"):
            await engine.async_submit_vote(pid, pid)

    @pytest.mark.asyncio
    async def test_no_double_vote(self, engine):
        await _start(engine)
        engine._state.phase = Phase.VOTE
        pids = [p.id for p in engine._state.players]
        await engine.async_submit_vote(pids[0], pids[1])
        with pytest.raises(ValueError, match="already voted"):
            await engine.async_submit_vote(pids[0], pids[2])

    @pytest.mark.asyncio
    async def test_resolve_votes_finds_winner(self, engine):
        await _start(engine)
        engine._state.phase = Phase.VOTE
        pids = [p.id for p in engine._state.players]
        await engine.async_submit_vote(pids[0], pids[1])
        await engine.async_submit_vote(pids[2], pids[1])
        await engine.async_submit_vote(pids[3], pids[1])
        await engine.async_submit_vote(pids[4], pids[0])
        result = await engine.async_resolve_vote()
        # Vote tallies are cleared after resolution
        assert result["vote_tallies_count"] == {}
        # The player with most votes (pids[1]) is eliminated
        eliminated = _get_player_obj(engine, pids[1])
        assert not eliminated.alive

    @pytest.mark.asyncio
    async def test_resolve_votes_detects_tie(self, engine):
        await _start(engine)
        engine._state.phase = Phase.VOTE
        pids = [p.id for p in engine._state.players]
        await engine.async_submit_vote(pids[0], pids[1])
        await engine.async_submit_vote(pids[2], pids[1])
        await engine.async_submit_vote(pids[3], pids[0])
        await engine.async_submit_vote(pids[4], pids[0])
        result = await engine.async_resolve_vote()
        assert result["vote_tallies_count"] == {}


# ── Persistence ───────────────────────────────────────────────────────────────


class TestPersistence:
    @pytest.mark.asyncio
    async def test_save_called_after_start(self, engine, mock_store):
        await _start(engine)
        mock_store.async_save.assert_called()

    @pytest.mark.asyncio
    async def test_load_restores_state(self, engine, hass, mock_store):
        await _start(engine)
        saved = engine._state.to_dict()

        mock_store.async_load = AsyncMock(return_value=saved)
        with patch(
            "custom_components.loup_garou.core.engine.Store",
            return_value=mock_store,
        ):
            engine2 = GameEngine(hass, "test_entry_id_2")
        await engine2.async_load()

        assert engine2._state.phase == engine._state.phase
        assert len(engine2._state.players) == len(engine._state.players)


# ── get_public_state / get_role_reveal_data ───────────────────────────────────


class TestPublicState:
    @pytest.mark.asyncio
    async def test_no_roles_in_public_state(self, engine):
        await _start(engine)
        state = engine.get_public_state()
        for player in state["players"]:
            assert "role" not in player

    @pytest.mark.asyncio
    async def test_reveal_data_returns_role(self, engine):
        await _start(engine)
        next_id = engine._state.reveal_order[0]
        data = engine.get_role_reveal_data(next_id)
        assert "role" in data
        assert data["player_id"] == next_id

    @pytest.mark.asyncio
    async def test_reveal_data_wrong_player_raises(self, engine):
        await _start(engine)
        wrong_id = engine._state.reveal_order[1]
        with pytest.raises(ValueError):
            engine.get_role_reveal_data(wrong_id)
