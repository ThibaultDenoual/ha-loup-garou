"""Tests for GameEngine — state machine, persistence, win conditions."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.loup_garou.game_engine import GameEngine
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
        "custom_components.loup_garou.game_engine.Store",
        return_value=mock_store,
    ):
        eng = GameEngine(hass, "test_entry_id")
    return eng


FIVE_PLAYERS = ["Alice", "Bob", "Carol", "Dave", "Eve"]
# 3 villagers, 1 wolf, 1 seer
ROLE_CONFIG_5 = {"villagers": 3, "werewolves": 1, "seers": 1}


async def _start(engine: GameEngine, players=FIVE_PLAYERS, config=ROLE_CONFIG_5):
    """Helper: start a game and return player ids."""
    await engine.start_game(players, config)
    return list(engine.state.players.keys())


# ── start_game ────────────────────────────────────────────────────────────────

class TestStartGame:
    @pytest.mark.asyncio
    async def test_phase_is_role_reveal(self, engine):
        await _start(engine)
        assert engine.state.phase == Phase.ROLE_REVEAL

    @pytest.mark.asyncio
    async def test_all_players_created(self, engine):
        await _start(engine)
        assert len(engine.state.players) == 5

    @pytest.mark.asyncio
    async def test_role_counts(self, engine):
        await _start(engine)
        roles = [p.role for p in engine.state.players.values()]
        assert roles.count(Role.WEREWOLF) == 1
        assert roles.count(Role.SEER) == 1
        assert roles.count(Role.VILLAGER) == 3

    @pytest.mark.asyncio
    async def test_reveal_order_shuffled_length(self, engine):
        await _start(engine)
        assert len(engine.state.reveal_order) == 5

    @pytest.mark.asyncio
    async def test_too_few_players_raises(self, engine):
        with pytest.raises(ValueError):
            await engine.start_game(["A", "B", "C"], ROLE_CONFIG_5)

    @pytest.mark.asyncio
    async def test_round_starts_at_zero(self, engine):
        await _start(engine)
        assert engine.state.round == 0


# ── confirm_role_seen ─────────────────────────────────────────────────────────

class TestConfirmRoleSeen:
    @pytest.mark.asyncio
    async def test_wrong_player_raises(self, engine):
        await _start(engine)
        correct_id = engine.state.reveal_order[0]
        other_id = engine.state.reveal_order[1]
        with pytest.raises(ValueError):
            await engine.confirm_role_seen(other_id)

    @pytest.mark.asyncio
    async def test_advances_reveal_index(self, engine):
        await _start(engine)
        pid = engine.state.reveal_order[0]
        await engine.confirm_role_seen(pid)
        assert engine.state.reveal_index == 1

    @pytest.mark.asyncio
    async def test_all_confirmed_transitions_to_night(self, engine):
        await _start(engine)
        for pid in engine.state.reveal_order:
            await engine.confirm_role_seen(pid)
        assert engine.state.phase == Phase.NIGHT

    @pytest.mark.asyncio
    async def test_night_round_becomes_1(self, engine):
        await _start(engine)
        for pid in engine.state.reveal_order:
            await engine.confirm_role_seen(pid)
        assert engine.state.round == 1


# ── Night actions ─────────────────────────────────────────────────────────────

class TestNightActions:
    async def _setup_night(self, engine):
        """Start game and confirm all roles so we're in NIGHT phase."""
        await _start(engine)
        for pid in engine.state.reveal_order:
            await engine.confirm_role_seen(pid)

    def _wolf_id(self, engine) -> str:
        return next(
            p.id for p in engine.state.players.values() if p.role == Role.WEREWOLF
        )

    def _seer_id(self, engine) -> str:
        return next(
            p.id for p in engine.state.players.values() if p.role == Role.SEER
        )

    def _non_wolf_id(self, engine) -> str:
        return next(
            p.id for p in engine.state.players.values() if p.role != Role.WEREWOLF
        )

    @pytest.mark.asyncio
    async def test_seer_is_first_acting_role(self, engine):
        await self._setup_night(engine)
        assert engine._current_night_role() == Role.SEER

    @pytest.mark.asyncio
    async def test_wolf_cannot_target_wolf(self, engine):
        await self._setup_night(engine)
        # Skip seer turn first
        await engine.submit_night_action(NightActionType.SEER_INVESTIGATE, self._non_wolf_id(engine))
        # Now wolves act
        assert engine._current_night_role() == Role.WEREWOLF
        wolf_id = self._wolf_id(engine)
        with pytest.raises(ValueError, match="cannot target"):
            await engine.submit_night_action(NightActionType.WOLF_KILL, wolf_id)

    @pytest.mark.asyncio
    async def test_wolf_action_recorded(self, engine):
        await self._setup_night(engine)
        target = self._non_wolf_id(engine)
        # Skip seer
        await engine.submit_night_action(NightActionType.SEER_INVESTIGATE, target)
        await engine.submit_night_action(NightActionType.WOLF_KILL, target)
        assert Role.WEREWOLF in engine.state.night_actions

    @pytest.mark.asyncio
    async def test_all_actions_complete_triggers_day(self, engine):
        await self._setup_night(engine)
        target = self._non_wolf_id(engine)
        # Seer acts first
        await engine.submit_night_action(NightActionType.SEER_INVESTIGATE, target)
        # Wolf acts second → day starts automatically
        await engine.submit_night_action(NightActionType.WOLF_KILL, target)
        assert engine.state.phase in (Phase.DAY, Phase.GAME_OVER)


# ── check_win_condition ───────────────────────────────────────────────────────

class TestWinCondition:
    @pytest.mark.asyncio
    async def test_no_winner_initially(self, engine):
        await _start(engine)
        assert engine.check_win_condition() is None

    @pytest.mark.asyncio
    async def test_village_wins_when_wolf_dead(self, engine):
        await _start(engine)
        wolf = next(p for p in engine.state.players.values() if p.role == Role.WEREWOLF)
        wolf.alive = False
        assert engine.check_win_condition() == WinCondition.VILLAGERS

    @pytest.mark.asyncio
    async def test_wolves_win_when_majority(self, engine):
        await _start(engine)
        villagers = [p for p in engine.state.players.values() if p.role != Role.WEREWOLF]
        # Kill all but one villager so wolves >= village
        for p in villagers[:-1]:
            p.alive = False
        # Now 1 wolf vs 1 villager → wolves win
        assert engine.check_win_condition() == WinCondition.WOLVES

    @pytest.mark.asyncio
    async def test_no_winner_balanced(self, engine):
        """2 wolves vs 3 villagers → no winner yet."""
        await engine.start_game(
            ["A", "B", "C", "D", "E", "F"],
            {"villagers": 4, "werewolves": 2, "seers": 0},
        )
        assert engine.check_win_condition() is None


# ── eliminate_player ──────────────────────────────────────────────────────────

class TestEliminatePlayer:
    @pytest.mark.asyncio
    async def test_player_marked_dead(self, engine):
        await _start(engine)
        pid = list(engine.state.players.keys())[0]
        await engine.eliminate_player(pid, EliminationCause.VILLAGE_VOTE)
        assert not engine.state.players[pid].alive

    @pytest.mark.asyncio
    async def test_elimination_logged(self, engine):
        await _start(engine)
        pid = list(engine.state.players.keys())[0]
        await engine.eliminate_player(pid, EliminationCause.VILLAGE_VOTE)
        assert any(e["player_id"] == pid for e in engine.state.eliminations)

    @pytest.mark.asyncio
    async def test_cannot_eliminate_dead_player(self, engine):
        await _start(engine)
        pid = list(engine.state.players.keys())[0]
        await engine.eliminate_player(pid, EliminationCause.VILLAGE_VOTE)
        with pytest.raises(ValueError, match="already dead"):
            await engine.eliminate_player(pid, EliminationCause.VILLAGE_VOTE)

    @pytest.mark.asyncio
    async def test_game_over_when_wolf_eliminated(self, engine):
        await _start(engine)
        wolf = next(p for p in engine.state.players.values() if p.role == Role.WEREWOLF)
        winner = await engine.eliminate_player(wolf.id, EliminationCause.VILLAGE_VOTE)
        assert winner == WinCondition.VILLAGERS
        assert engine.state.phase == Phase.GAME_OVER


# ── Vote ──────────────────────────────────────────────────────────────────────

class TestVotes:
    @pytest.mark.asyncio
    async def test_vote_recorded(self, engine):
        await _start(engine)
        # Force to VOTE phase
        engine.state.phase = Phase.VOTE
        pids = list(engine.state.players.keys())
        await engine.submit_vote(pids[0], pids[1])
        assert pids[0] in engine.state.voted_player_ids

    @pytest.mark.asyncio
    async def test_no_self_vote(self, engine):
        await _start(engine)
        engine.state.phase = Phase.VOTE
        pid = list(engine.state.players.keys())[0]
        with pytest.raises(ValueError, match="themselves"):
            await engine.submit_vote(pid, pid)

    @pytest.mark.asyncio
    async def test_no_double_vote(self, engine):
        await _start(engine)
        engine.state.phase = Phase.VOTE
        pids = list(engine.state.players.keys())
        await engine.submit_vote(pids[0], pids[1])
        with pytest.raises(ValueError, match="already voted"):
            await engine.submit_vote(pids[0], pids[2])

    @pytest.mark.asyncio
    async def test_resolve_votes_finds_winner(self, engine):
        await _start(engine)
        engine.state.phase = Phase.VOTE
        pids = list(engine.state.players.keys())
        # 3 players vote for pids[1]
        await engine.submit_vote(pids[0], pids[1])
        await engine.submit_vote(pids[2], pids[1])
        await engine.submit_vote(pids[3], pids[1])
        await engine.submit_vote(pids[4], pids[0])
        result = await engine.resolve_votes()
        assert result["winner"] == pids[1]
        assert not result["tied"]

    @pytest.mark.asyncio
    async def test_resolve_votes_detects_tie(self, engine):
        await _start(engine)
        engine.state.phase = Phase.VOTE
        pids = list(engine.state.players.keys())
        await engine.submit_vote(pids[0], pids[1])
        await engine.submit_vote(pids[2], pids[1])
        await engine.submit_vote(pids[3], pids[0])
        await engine.submit_vote(pids[4], pids[0])
        result = await engine.resolve_votes()
        assert result["tied"]
        assert result["winner"] is None


# ── Persistence ───────────────────────────────────────────────────────────────

class TestPersistence:
    @pytest.mark.asyncio
    async def test_save_called_after_start(self, engine, mock_store):
        await _start(engine)
        mock_store.async_save.assert_called()

    @pytest.mark.asyncio
    async def test_load_restores_state(self, engine, hass, mock_store):
        await _start(engine)
        saved = engine.state.to_dict()

        # Create a new engine and load from the saved state
        mock_store.async_load = AsyncMock(return_value=saved)
        with patch(
            "custom_components.loup_garou.game_engine.Store",
            return_value=mock_store,
        ):
            engine2 = GameEngine(hass, "test_entry_id_2")
        await engine2.async_load()

        assert engine2.state.phase == engine.state.phase
        assert set(engine2.state.players.keys()) == set(engine.state.players.keys())


# ── get_state_public ──────────────────────────────────────────────────────────

class TestPublicState:
    @pytest.mark.asyncio
    async def test_no_roles_in_public_state(self, engine):
        await _start(engine)
        state = engine.get_state_public()
        for player in state["players"]:
            assert "role" not in player

    @pytest.mark.asyncio
    async def test_wolves_in_private_state(self, engine):
        await _start(engine)
        wolf = next(p for p in engine.state.players.values() if p.role == Role.WEREWOLF)
        private = engine.get_player_private(wolf.id)
        assert private["role"] == Role.WEREWOLF