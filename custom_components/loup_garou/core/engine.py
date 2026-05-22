"""Core game state machine for Loup Garou."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from homeassistant.helpers.storage import Store

from ..const import (
    DOMAIN,
    Phase,
    Role,
    WOLF_TEAM,
    VILLAGE_TEAM,
    NIGHT_WAKE_ORDER,
    ROLE_PHASE_MAP,
    NightActionType,
    EliminationCause,
    WinCondition,
    EVENT_GAME_STATE_CHANGED,
    EVENT_GAME_OVER,
)
from .state import GameState, Player, NightActions
from .role_manager import RoleManager, RoleConfig, RoleConfigError

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY = f"{DOMAIN}.game_state"
STORAGE_VERSION = 1


class GameEngine:
    """Central game state machine.

    All public methods are coroutines that mutate state, persist to HA storage,
    fire HA events, and return the updated sanitized state dict for the caller.
    """

    def __init__(self, hass: HomeAssistant, config_entry_id: str) -> None:
        self.hass = hass
        self.config_entry_id = config_entry_id
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._state = GameState()
        self._role_manager = RoleManager()

    @property
    def state(self) -> GameState:
        """Expose the internal state for read access by PhaseManager."""
        return self._state

    # ─── Lifecycle ────────────────────────────────────────────────────────────

    async def async_load(self) -> None:
        """Load persisted state from HA storage on startup."""
        data = await self._store.async_load()
        if data:
            self._state = GameState.from_dict(data)
            _LOGGER.info("Loup Garou: restored game state (phase=%s)", self._state.phase)
        else:
            _LOGGER.info("Loup Garou: no saved state, starting fresh")

    async def _async_save(self) -> None:
        await self._store.async_save(self._state.to_dict())

    # ─── Public API ───────────────────────────────────────────────────────────

    async def async_start_game(
        self,
        player_names: list[str],
        role_config: dict,
        language: str = "fr",
    ) -> dict:
        """Assign roles, build player list, move to ROLE_REVEAL."""
        import random

        role_cfg = RoleConfig.from_dict(role_config) if isinstance(role_config, dict) else role_config
        self._role_manager.validate(role_cfg, len(player_names))

        role_assignments = self._role_manager.assign_roles(player_names, role_cfg)

        players = [
            Player(id=str(uuid.uuid4()), name=name, role=role.value)
            for name, role in role_assignments.items()
        ]

        reveal_order = [p.id for p in players]
        random.shuffle(reveal_order)

        self._state = GameState(
            phase=Phase.ROLE_REVEAL,
            round=0,
            players=players,
            reveal_order=reveal_order,
            reveal_index=0,
            language=language,
        )

        await self._async_save()
        self._fire_event(EVENT_GAME_STATE_CHANGED, {"phase": Phase.ROLE_REVEAL})
        return self.get_public_state()

    async def async_confirm_role_seen(self, player_id: str) -> dict:
        """Mark a player as having seen their role. Advances when all done."""
        player = self._get_player(player_id)
        if player is None:
            raise ValueError(f"Unknown player: {player_id}")

        player.role_seen = True
        self._state.reveal_index += 1

        if self._state.reveal_index >= len(self._state.players):
            await self._async_start_night()
        else:
            await self._async_save()

        return self.get_public_state()

    async def async_submit_night_action(
        self, action_type: str, target_id: str, skip_delay: bool = False
    ) -> dict:
        """Record a night action from the device."""
        if not Phase.is_night_subphase(self._state.phase):
            raise ValueError("Not in night phase")

        if self._state.phase != Phase.NIGHT_SEER_ACT and self._state.phase != Phase.NIGHT_WOLF_ACT:
            raise ValueError("Not waiting for night action")

        target = self._get_player(target_id)
        if target is None or not target.alive:
            raise ValueError(f"Invalid target: {target_id}")

        acting_role = self.current_night_role
        if not acting_role:
            raise ValueError("No role is acting right now")

        if action_type == NightActionType.WOLF_KILL:
            if acting_role != Role.WEREWOLF:
                raise ValueError(f"Wolf kill action but wrong acting role: {acting_role}")
            if self._state.night_actions.wolf_victim_id is not None:
                raise ValueError("Wolf action already submitted")
            if target.role in WOLF_TEAM:
                raise ValueError("Wolves cannot target each other")
            self._state.night_actions.wolf_victim_id = target_id
            await self._async_advance_to_wolf_sleep(skip_delay)

        elif action_type == NightActionType.SEER_INVESTIGATE:
            if self._state.night_actions.seer_target_id is not None:
                raise ValueError("Seer action already submitted")
            if acting_role != Role.SEER:
                raise ValueError(f"Seer investigate action but wrong acting role: {acting_role}")
            self._state.night_actions.seer_target_id = target_id
            self._state.night_actions.seer_result = target.role
            await self._async_advance_to_seer_sleep(skip_delay)

        if acting_role not in self._state.night_actions.completed_roles:
            self._state.night_actions.completed_roles.append(acting_role)

        await self._async_save()
        return self.get_public_state()

    async def async_submit_vote(self, voter_id: str, target_id: str) -> dict:
        """Record a day vote."""
        if self._state.phase != Phase.VOTE:
            raise ValueError("Not in vote phase")

        voter = self._get_player(voter_id)
        target = self._get_player(target_id)

        if voter is None or not voter.alive:
            raise ValueError(f"Invalid voter: {voter_id}")
        if target is None or not target.alive:
            raise ValueError(f"Invalid target: {target_id}")
        if voter_id == target_id:
            raise ValueError("Cannot vote for yourself")

        for votes in self._state.vote_tallies.values():
            if voter_id in votes:
                raise ValueError(f"{voter_id} has already voted")

        if target_id not in self._state.vote_tallies:
            self._state.vote_tallies[target_id] = []
        self._state.vote_tallies[target_id].append(voter_id)

        await self._async_save()
        return self.get_public_state()

    async def async_resolve_vote(self) -> dict:
        """Host triggers end of vote. Eliminate plurality leader (or no-one on tie)."""
        if not self._state.vote_tallies:
            self._state.eliminated_this_round = []
            await self._async_advance_to_night()
            return self.get_public_state()

        max_votes = max(len(v) for v in self._state.vote_tallies.values())
        leaders = [
            pid for pid, voters in self._state.vote_tallies.items()
            if len(voters) == max_votes
        ]

        if len(leaders) > 1:
            self._state.eliminated_this_round = []
        else:
            eliminated_id = leaders[0]
            await self.async_eliminate_player(eliminated_id, EliminationCause.VILLAGE_VOTE)

        self._state.vote_tallies = {}
        await self._async_save()
        return self.get_public_state()

    async def async_eliminate_player(self, player_id: str, cause: str) -> dict:
        """Eliminate a player and check win condition."""
        player = self._get_player(player_id)
        if player is None:
            raise ValueError(f"Unknown player: {player_id}")

        player.alive = False
        self._state.eliminated_this_round.append(player_id)

        self._fire_event(EVENT_GAME_STATE_CHANGED, {
            "player_id": player_id,
            "player_name": player.name,
            "role": player.role,
            "cause": cause,
        })

        winner = self.check_win_condition()
        if winner:
            self._state.winner = winner
            self._state.phase = Phase.GAME_OVER
            self._fire_event(EVENT_GAME_OVER, {"winner": winner})

        await self._async_save()
        return self.get_public_state()

    async def async_next_phase(self, skip_delay: bool = False) -> dict:
        """Host override to advance phase."""
        current = self._state.phase

        if current == Phase.NIGHT_START:
            await self._async_advance_to_seer_wake(skip_delay)
        elif current == Phase.NIGHT_SEER_WAKE:
            await self._async_advance_to_seer_act(skip_delay)
        elif current == Phase.NIGHT_SEER_SLEEP:
            await self._async_advance_to_wolf_wake(skip_delay)
        elif current == Phase.NIGHT_WOLF_WAKE:
            await self._async_advance_to_wolf_act(skip_delay)
        elif current == Phase.NIGHT_WOLF_SLEEP:
            await self._async_advance_to_day()
        elif current == Phase.DAY:
            self._state.phase = Phase.VOTE
            self._state.vote_tallies = {}
            self._fire_event(EVENT_GAME_STATE_CHANGED, {"phase": Phase.VOTE})
            await self._async_save()
        elif current == Phase.VOTE:
            result = await self.async_resolve_vote()
            return result
        else:
            _LOGGER.warning("next_phase called in unexpected phase: %s", current)
            await self._async_save()

        return self.get_public_state()

    async def async_begin_vote(self) -> None:
        """Start the vote phase."""
        if self._state.phase != Phase.DAY:
            raise ValueError("Can only begin vote during DAY phase")
        self._state.phase = Phase.VOTE
        self._state.vote_tallies = {}
        self._fire_event(EVENT_GAME_STATE_CHANGED, {"phase": Phase.VOTE})
        await self._async_save()

    async def async_select_target(self, target_id: str) -> dict:
        """Record selected target during night/role reveal for UI feedback."""
        target = self._get_player(target_id)
        if target is None:
            raise ValueError(f"Unknown player: {target_id}")
        if not target.alive:
            raise ValueError(f"Target is not alive: {target_id}")
        self._state.current_target_id = target_id
        await self._async_save()
        return self.get_public_state()

    async def async_skip_night_action(self, skip_delay: bool = False) -> dict:
        """Skip the current role's night action without targeting anyone."""
        current_role = self.current_night_role
        if not current_role:
            raise ValueError("No role is acting right now")

        if current_role not in self._state.night_actions.completed_roles:
            self._state.night_actions.completed_roles.append(current_role)

        self._state.current_target_id = None

        if self._state.phase == Phase.NIGHT_SEER_ACT:
            await self._async_advance_to_seer_sleep(skip_delay)
        elif self._state.phase == Phase.NIGHT_WOLF_ACT:
            await self._async_advance_to_wolf_sleep(skip_delay)
        else:
            raise ValueError("Cannot skip at this phase")

        return self.get_public_state()

    async def async_reset(self) -> None:
        """Reset game to initial state."""
        self._state = GameState()
        self._fire_event(EVENT_GAME_STATE_CHANGED, {"phase": Phase.SETUP})
        await self._async_save()

    # ─── Query methods ────────────────────────────────────────────────────────

    def check_win_condition(self) -> str | None:
        """Return winner string or None if game continues."""
        alive = [p for p in self._state.players if p.alive]
        alive_wolves = [p for p in alive if p.role == Role.WEREWOLF]
        alive_village = [p for p in alive if p.role in VILLAGE_TEAM]

        if not alive_wolves:
            return WinCondition.VILLAGERS
        if len(alive_wolves) >= len(alive_village):
            return WinCondition.WOLVES
        return None

    @property
    def current_night_role(self) -> str | None:
        """The role whose action is currently expected at night, or None."""
        if not Phase.is_night_subphase(self._state.phase):
            return None
        if not Phase.is_active_night_phase(self._state.phase):
            return None
        phase_to_role = {
            Phase.NIGHT_SEER_WAKE: Role.SEER,
            Phase.NIGHT_SEER_ACT: Role.SEER,
            Phase.NIGHT_WOLF_WAKE: Role.WEREWOLF,
            Phase.NIGHT_WOLF_ACT: Role.WEREWOLF,
        }
        return phase_to_role.get(self._state.phase)

    def get_public_state(self) -> dict:
        """Return sanitized state safe to send to frontend. No roles included."""
        alive_players = [p for p in self._state.players if p.alive]

        next_reveal_player: str | None = None
        if (
            self._state.phase == Phase.ROLE_REVEAL
            and self._state.reveal_index < len(self._state.reveal_order)
        ):
            next_id = self._state.reveal_order[self._state.reveal_index]
            p = self._get_player(next_id)
            next_reveal_player = p.name if p else None

        return {
            "phase": self._state.phase,
            "round": self._state.round,
            "language": self._state.language,
            "winner": self._state.winner,
            "players": [
                {"id": p.id, "name": p.name, "alive": p.alive, "role_seen": p.role_seen}
                for p in self._state.players
            ],
            "alive_count": len(alive_players),
            "dead_count": len(self._state.players) - len(alive_players),
            "reveal_index": self._state.reveal_index,
            "reveal_total": len(self._state.players),
            "next_reveal_player": next_reveal_player,
            "eliminated_this_round": self._state.eliminated_this_round,
            "vote_tallies_count": {
                pid: len(voters)
                for pid, voters in self._state.vote_tallies.items()
            },
            "votes_cast": sum(len(v) for v in self._state.vote_tallies.values()),
            "alive_voter_count": len(alive_players),
            "current_night_role": self.current_night_role,
            "current_target_id": self._state.current_target_id,
            "night_actions_completed": list(self._state.night_actions.completed_roles),
        }

    def get_role_reveal_data(self, player_id: str) -> dict:
        """Return role data for the next player in the reveal sequence."""
        if self._state.phase != Phase.ROLE_REVEAL:
            raise ValueError("Not in role reveal phase")

        expected_id = (
            self._state.reveal_order[self._state.reveal_index]
            if self._state.reveal_index < len(self._state.reveal_order)
            else None
        )
        if player_id != expected_id:
            raise ValueError("Not this player's turn to reveal")

        player = self._get_player(player_id)
        if player is None:
            raise ValueError(f"Unknown player: {player_id}")

        return {
            "player_id": player.id,
            "player_name": player.name,
            "role": player.role,
        }

    def get_seer_result(self, seer_player_id: str) -> dict:
        """Return seer investigation result from last night."""
        player = self._get_player(seer_player_id)
        if player is None or player.role != "seer":
            raise ValueError("Not a seer")
        if self._state.night_actions.seer_target_id is None:
            raise ValueError("Seer has not investigated yet")

        target = self._get_player(self._state.night_actions.seer_target_id)
        return {
            "target_name": target.name if target else "?",
            "target_role": self._state.night_actions.seer_result,
        }

    def get_full_state_for_end(self) -> dict:
        """Full state including all roles — only sent at game over."""
        if self._state.phase != Phase.GAME_OVER:
            raise ValueError("Game not over yet")
        return {
            **self.get_public_state(),
            "players_full": [
                {"id": p.id, "name": p.name, "role": p.role, "alive": p.alive}
                for p in self._state.players
            ],
        }

    # ─── Internal helpers ────────────────────────────────────────────────────

    def _get_player(self, player_id: str) -> Player | None:
        for p in self._state.players:
            if p.id == player_id:
                return p
        return None

    def _active_night_roles(self) -> list[str]:
        """Night wake order filtered to roles present and alive."""
        present_roles = {p.role for p in self._state.players if p.alive}
        return [r for r in NIGHT_WAKE_ORDER if r in present_roles]

    async def _async_delay(self, skip_delay: bool) -> None:
        """Wait for configured delay unless skipped (for tests)."""
        if not skip_delay and self._state.delay_seconds > 0:
            import asyncio
            await asyncio.sleep(self._state.delay_seconds)

    async def _async_start_night(self) -> None:
        """Start the night cycle at NIGHT_START."""
        self._state.round += 1
        self._state.phase = Phase.NIGHT_START
        self._state.night_actions = NightActions()
        self._state.eliminated_this_round = []
        self._state.current_target_id = None
        self._fire_event(EVENT_GAME_STATE_CHANGED, {"phase": Phase.NIGHT_START, "round": self._state.round})
        await self._async_save()

    async def _async_advance_to_seer_wake(self, skip_delay: bool = False) -> None:
        """Transition from NIGHT_START to SEER wake."""
        await self._async_delay(skip_delay)
        if not self._has_role(Role.SEER):
            await self._async_advance_to_wolf_wake(skip_delay)
            return
        self._state.phase = Phase.NIGHT_SEER_WAKE
        self._fire_event(EVENT_GAME_STATE_CHANGED, {"phase": Phase.NIGHT_SEER_WAKE})
        await self._async_save()

    async def _async_advance_to_seer_act(self, skip_delay: bool = False) -> None:
        """Transition from SEER wake to SEER act (choosing target)."""
        await self._async_delay(skip_delay)
        self._state.phase = Phase.NIGHT_SEER_ACT
        self._fire_event(EVENT_GAME_STATE_CHANGED, {"phase": Phase.NIGHT_SEER_ACT})
        await self._async_save()

    async def _async_advance_to_seer_sleep(self, skip_delay: bool = False) -> None:
        """Transition from SEER act to SEER sleep, then auto-advance to wolf."""
        await self._async_delay(skip_delay)
        self._state.phase = Phase.NIGHT_SEER_SLEEP
        self._state.current_target_id = None
        self._fire_event(EVENT_GAME_STATE_CHANGED, {"phase": Phase.NIGHT_SEER_SLEEP})
        await self._async_save()
        await self._async_advance_to_wolf_wake(skip_delay)

    async def _async_advance_to_wolf_wake(self, skip_delay: bool = False) -> None:
        """Transition to wolf wake."""
        await self._async_delay(skip_delay)
        if not self._has_role(Role.WEREWOLF):
            await self._async_advance_to_day()
            return
        self._state.phase = Phase.NIGHT_WOLF_WAKE
        self._fire_event(EVENT_GAME_STATE_CHANGED, {"phase": Phase.NIGHT_WOLF_WAKE})
        await self._async_save()

    async def _async_advance_to_wolf_act(self, skip_delay: bool = False) -> None:
        """Transition from wolf wake to wolf act (choosing target)."""
        await self._async_delay(skip_delay)
        self._state.phase = Phase.NIGHT_WOLF_ACT
        self._fire_event(EVENT_GAME_STATE_CHANGED, {"phase": Phase.NIGHT_WOLF_ACT})
        await self._async_save()

    async def _async_advance_to_wolf_sleep(self, skip_delay: bool = False) -> None:
        """Transition from wolf act to wolf sleep, then auto-advance to day."""
        await self._async_delay(skip_delay)
        self._state.phase = Phase.NIGHT_WOLF_SLEEP
        self._state.current_target_id = None
        self._fire_event(EVENT_GAME_STATE_CHANGED, {"phase": Phase.NIGHT_WOLF_SLEEP})
        await self._async_save()
        await self._async_advance_to_day()

    async def _async_advance_to_day(self) -> None:
        """Resolve night actions and move to day phase."""
        await self._async_delay(False)
        victim_id = self._state.night_actions.wolf_victim_id
        if victim_id:
            await self.async_eliminate_player(victim_id, EliminationCause.WOLF_KILL)
            if self._state.phase == Phase.GAME_OVER:
                return

        self._state.phase = Phase.DAY
        self._state.current_target_id = None
        self._fire_event(EVENT_GAME_STATE_CHANGED, {
            "phase": Phase.DAY,
            "eliminated": self._state.eliminated_this_round,
        })
        await self._async_save()

    async def _async_advance_to_night(self) -> None:
        await self._async_start_night()

    def _has_role(self, role: Role) -> bool:
        """Check if any alive player has the given role."""
        return any(p.role == role and p.alive for p in self._state.players)

    def _fire_event(self, event_type: str, data: dict) -> None:
        self.hass.bus.async_fire(event_type, {
            "config_entry_id": self.config_entry_id,
            **data,
        })
