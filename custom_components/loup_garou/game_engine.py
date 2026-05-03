"""Core game state machine for Loup Garou."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import (
    DOMAIN,
    Phase,
    Role,
    WOLF_TEAM,
    VILLAGE_TEAM,
    NIGHT_WAKE_ORDER,
    NightActionType,
    EliminationCause,
    WinCondition,
    EVENT_GAME_STATE_CHANGED,
    EVENT_GAME_OVER,
)
from .role_manager import RoleManager, RoleConfig, RoleConfigError

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY = f"{DOMAIN}.game_state"
STORAGE_VERSION = 1


@dataclass
class Player:
    id: str
    name: str
    role: str
    alive: bool = True
    role_seen: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Player":
        return cls(**data)


@dataclass
class NightActions:
    """Tracks which night actions have been submitted this round."""
    wolf_victim_id: str | None = None
    seer_target_id: str | None = None
    seer_result: str | None = None          # role name, shown on screen only
    completed_roles: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "NightActions":
        return cls(**data)


@dataclass
class GameState:
    phase: str = Phase.SETUP
    round: int = 0
    players: list[Player] = field(default_factory=list)
    night_actions: NightActions = field(default_factory=NightActions)
    vote_tallies: dict[str, list[str]] = field(default_factory=dict)
    eliminated_this_round: list[str] = field(default_factory=list)
    current_night_role_index: int = 0       # index into NIGHT_WAKE_ORDER
    reveal_order: list[str] = field(default_factory=list)  # player ids in reveal order
    reveal_index: int = 0
    winner: str | None = None
    language: str = "fr"

    def to_dict(self) -> dict:
        return {
            "phase": self.phase,
            "round": self.round,
            "players": [p.to_dict() for p in self.players],
            "night_actions": self.night_actions.to_dict(),
            "vote_tallies": self.vote_tallies,
            "eliminated_this_round": self.eliminated_this_round,
            "current_night_role_index": self.current_night_role_index,
            "reveal_order": self.reveal_order,
            "reveal_index": self.reveal_index,
            "winner": self.winner,
            "language": self.language,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GameState":
        state = cls()
        state.phase = data.get("phase", Phase.SETUP)
        state.round = data.get("round", 0)
        state.players = [Player.from_dict(p) for p in data.get("players", [])]
        na = data.get("night_actions", {})
        state.night_actions = NightActions.from_dict(na) if na else NightActions()
        state.vote_tallies = data.get("vote_tallies", {})
        state.eliminated_this_round = data.get("eliminated_this_round", [])
        state.current_night_role_index = data.get("current_night_role_index", 0)
        state.reveal_order = data.get("reveal_order", [])
        state.reveal_index = data.get("reveal_index", 0)
        state.winner = data.get("winner")
        state.language = data.get("language", "fr")
        return state


class GameEngine:
    """
    Central game state machine.

    All public methods are coroutines that mutate state, persist to HA storage,
    fire HA events, and return the updated sanitized state dict for the caller.
    """

    def __init__(self, hass: HomeAssistant, config_entry_id: str) -> None:
        self.hass = hass
        self.config_entry_id = config_entry_id
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._state = GameState()
        self._role_manager = RoleManager()

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
        role_config: dict[str, int],
        language: str = "fr",
    ) -> dict:
        """
        Assign roles, build player list, move to ROLE_REVEAL.

        role_config example: {"villager": 3, "werewolf": 1, "seer": 1}
        """
        import random

        role_cfg = RoleConfig.from_dict(role_config) if isinstance(role_config, dict) else role_config
        self._role_manager.validate(role_cfg, len(player_names))

        role_assignments = self._role_manager.assign_roles(player_names, role_cfg)

        players = [
            Player(id=str(uuid.uuid4()), name=name, role=role.value)
            for name, role in role_assignments.items()
        ]

        # Randomise reveal order (not alphabetical — avoids inference)
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
            # All players have seen their roles → start first night
            await self._async_start_night()
        else:
            await self._async_save()

        return self.get_public_state()

    async def async_submit_night_action(
        self, role: str, action_type: str, target_id: str
    ) -> dict:
        """Record a night action from the device."""
        if self._state.phase != Phase.NIGHT:
            raise ValueError("Not in night phase")

        target = self._get_player(target_id)
        if target is None or not target.alive:
            raise ValueError(f"Invalid target: {target_id}")

        if action_type == NightActionType.WOLF_KILL:
            if self._state.night_actions.wolf_victim_id is not None:
                raise ValueError("Wolf action already submitted")
            if target.role in WOLF_TEAM:
                raise ValueError("Wolves cannot target each other")
            self._state.night_actions.wolf_victim_id = target_id

        elif action_type == NightActionType.SEER_INVESTIGATE:
            if self._state.night_actions.seer_target_id is not None:
                raise ValueError("Seer action already submitted")
            self._state.night_actions.seer_target_id = target_id
            # Result stored server-side, sent only to the seer screen
            self._state.night_actions.seer_result = target.role

        if role not in self._state.night_actions.completed_roles:
            self._state.night_actions.completed_roles.append(role)

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

        # Each player votes once
        for votes in self._state.vote_tallies.values():
            if voter_id in votes:
                raise ValueError(f"{voter_id} has already voted")

        if target_id not in self._state.vote_tallies:
            self._state.vote_tallies[target_id] = []
        self._state.vote_tallies[target_id].append(voter_id)

        await self._async_save()
        return self.get_public_state()

    async def async_resolve_vote(self) -> dict:
        """
        Host triggers end of vote. Eliminate plurality leader (or no-one on tie).
        Returns updated state; caller handles TTS/lights.
        """
        if not self._state.vote_tallies:
            # No votes cast — skip elimination
            self._state.eliminated_this_round = []
            await self._async_advance_to_night()
            return self.get_public_state()

        max_votes = max(len(v) for v in self._state.vote_tallies.values())
        leaders = [
            pid for pid, voters in self._state.vote_tallies.items()
            if len(voters) == max_votes
        ]

        if len(leaders) > 1:
            # Tie — no elimination (Phase 1 simple resolution)
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

    async def async_next_phase(self) -> dict:
        """Host override to advance phase."""
        current = self._state.phase

        if current == Phase.NIGHT:
            await self._async_advance_to_day()
        elif current == Phase.DAY:
            self._state.phase = Phase.VOTE
            self._state.vote_tallies = {}
            self._fire_event(EVENT_GAME_STATE_CHANGED, {"phase": Phase.VOTE})
        elif current == Phase.VOTE:
            await self.async_resolve_vote()
        else:
            _LOGGER.warning("next_phase called in unexpected phase: %s", current)

        await self._async_save()
        return self.get_public_state()

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

    def get_public_state(self) -> dict:
        """
        Return a sanitized state dict safe to send to the frontend.
        Roles are NOT included — they are sent only on the role reveal screen
        via a dedicated endpoint, one player at a time.
        """
        alive_players = [p for p in self._state.players if p.alive]
        all_players = self._state.players

        # Build next-to-reveal player name (for the phone-passing prompt)
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
                {
                    "id": p.id,
                    "name": p.name,
                    "alive": p.alive,
                    "role_seen": p.role_seen,
                }
                for p in all_players
            ],
            "alive_count": len(alive_players),
            "dead_count": len(all_players) - len(alive_players),
            "reveal_index": self._state.reveal_index,
            "reveal_total": len(self._state.players),
            "next_reveal_player": next_reveal_player,
            "eliminated_this_round": self._state.eliminated_this_round,
            "vote_tallies_count": {
                pid: len(voters)
                for pid, voters in self._state.vote_tallies.items()
            },
            "votes_cast": sum(
                len(v) for v in self._state.vote_tallies.values()
            ),
            "alive_voter_count": len(alive_players),
            "current_night_role": self._current_night_role(),
            "night_actions_completed": list(
                self._state.night_actions.completed_roles
            ),
        }

    def get_role_reveal_data(self, player_id: str) -> dict:
        """
        Return role data for a specific player (only when it's their turn to reveal).
        Raises if it's not their turn.
        """
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
        """Return seer investigation result. Only callable after seer has acted."""
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
        """Full state including all roles — only sent when game is over."""
        if self._state.phase != Phase.GAME_OVER:
            raise ValueError("Game not over yet")
        return {
            **self.get_public_state(),
            "players_full": [
                {"id": p.id, "name": p.name, "role": p.role, "alive": p.alive}
                for p in self._state.players
            ],
        }

    # ─── Internal helpers ─────────────────────────────────────────────────────

    def _get_player(self, player_id: str) -> Player | None:
        for p in self._state.players:
            if p.id == player_id:
                return p
        return None

    def _current_night_role(self) -> str | None:
        """Return the role whose action is currently expected, or None."""
        if self._state.phase != Phase.NIGHT:
            return None
        active_roles = self._active_night_roles()
        idx = self._state.current_night_role_index
        if idx < len(active_roles):
            return active_roles[idx]
        return None

    def _active_night_roles(self) -> list[str]:
        """Night wake order filtered to roles actually present and alive."""
        present_roles = {p.role for p in self._state.players if p.alive}
        return [r for r in NIGHT_WAKE_ORDER if r in present_roles]

    async def _async_start_night(self) -> None:
        self._state.round += 1
        self._state.phase = Phase.NIGHT
        self._state.night_actions = NightActions()
        self._state.eliminated_this_round = []
        self._state.current_night_role_index = 0
        self._fire_event(EVENT_GAME_STATE_CHANGED, {"phase": Phase.NIGHT, "round": self._state.round})
        await self._async_save()

    async def _async_advance_to_day(self) -> None:
        """Resolve night actions and move to day phase."""
        # Apply wolf kill
        victim_id = self._state.night_actions.wolf_victim_id
        if victim_id:
            await self.async_eliminate_player(victim_id, EliminationCause.WOLF_KILL)
            if self._state.phase == Phase.GAME_OVER:
                return  # game ended mid-resolution

        self._state.phase = Phase.DAY
        self._fire_event(EVENT_GAME_STATE_CHANGED, {
            "phase": Phase.DAY,
            "eliminated": self._state.eliminated_this_round,
        })
        await self._async_save()

    async def _async_advance_to_night(self) -> None:
        await self._async_start_night()

    def _fire_event(self, event_type: str, data: dict) -> None:
        self.hass.bus.async_fire(event_type, {
            "config_entry_id": self.config_entry_id,
            **data,
        })