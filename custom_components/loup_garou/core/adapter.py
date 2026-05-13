"""
adapter.py — Async adapter that bridges sync core_game with Home Assistant.

This adapter wraps the synchronous GameEngine and provides async methods
compatible with the HA integration, using run_in_executor for thread-safety.
"""

from __future__ import annotations

import asyncio
import logging
import random
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from ..core_game import (
    GameEngine,
    GameState,
    Player,
    ROLE_REGISTRY,
    PRESETS as CORE_PRESETS,
)
from ..core_game.io_adapters import HomeAssistantIO, MockIO

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


# Phase mapping between HA phases and core_game phases
HA_PHASE_MAP = {
    "setup": "setup",
    "role_reveal": "setup",
    "night_start": "night_start",
    "night_seer_wake": "night_start",
    "night_seer_act": "night_actions",
    "night_seer_sleep": "night_actions",
    "night_wolf_wake": "night_actions",
    "night_wolf_act": "night_actions",
    "night_wolf_sleep": "resolve_night",
    "day": "day_start",
    "discussion": "discussion",
    "vote": "vote",
    "resolve_day": "resolve_day",
    "game_over": "game_over",
}


@dataclass
class HAIntegrationState:
    """Extended state for HA integration."""
    phase: str = "setup"
    round: int = 0
    players: list = field(default_factory=list)
    night_actions: dict = field(default_factory=dict)
    vote_tallies: dict = field(default_factory=dict)
    eliminated_this_round: list = field(default_factory=list)
    current_target_id: Optional[str] = None
    reveal_order: list = field(default_factory=list)
    reveal_index: int = 0
    winner: Optional[str] = None
    language: str = "fr"


class AsyncGameAdapter:
    """
    Async wrapper around the sync GameEngine for HA compatibility.

    This adapter:
    1. Runs the sync engine in a thread pool via run_in_executor
    2. Provides async methods matching the current HA interface
    3. Handles phase transitions between HA and core_game
    """

    def __init__(
        self,
        hass: "HomeAssistant" = None,
        config_entry_id: str = "",
    ):
        self._hass = hass
        self._config_entry_id = config_entry_id
        self._engine: Optional[GameEngine] = None
        self._io: Optional[HomeAssistantIO] = None
        self._state = HAIntegrationState()
        self._loop = None

    @property
    def state(self) -> HAIntegrationState:
        return self._state

    def _run_sync(self, func, *args, **kwargs):
        """Execute a sync function in a thread pool."""
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(None, func, *args, **kwargs)

    async def async_start_game(
        self,
        player_names: list[str],
        role_config: dict,
        language: str = "fr",
    ) -> dict:
        """Initialize a new game with given players and roles."""
        role_cfg = role_config.get("preset") or "medium"
        role_names = CORE_PRESETS.get(role_cfg, CORE_PRESETS["small"])

        if len(role_names) != len(player_names):
            raise ValueError(
                f"Role count ({len(role_names)}) must match player count ({len(player_names)})"
            )

        shuffled_roles = role_names[:]
        random.shuffle(shuffled_roles)

        players = [
            Player(name=name, role=ROLE_REGISTRY[rname](None))
            for name, rname in zip(player_names, shuffled_roles)
        ]
        for p in players:
            p.role.player = p

        self._io = MockIO()
        self._engine = GameEngine(
            player_names=player_names,
            role_names=shuffled_roles,
            io=self._io,
            seed=None,
        )

        self._state = HAIntegrationState(
            phase="role_reveal",
            round=0,
            players=[self._player_to_ha(p) for p in players],
            reveal_order=[p.name for p in players],
            reveal_index=0,
            language=language,
        )

        return self.get_public_state()

    def _player_to_ha(self, player: Player) -> dict:
        """Convert core_game Player to HA player dict."""
        return {
            "id": player.name,
            "name": player.name,
            "role": player.role.name,
            "role_key": player.role.role_key,
            "team": player.role.team,
            "alive": player.alive,
            "role_seen": False,
        }

    async def async_confirm_role_seen(self, player_id: str) -> dict:
        """Mark player's role as seen, advance reveal if complete."""
        player = self._get_player(player_id)
        if player:
            player["role_seen"] = True

        self._state.reveal_index += 1

        if self._state.reveal_index >= len(self._state.players):
            self._state.phase = "night_start"
            self._state.round = 1
            self._state.night_actions = {
                "wolf_victim_id": None,
                "seer_target_id": None,
                "seer_result": None,
                "completed_roles": [],
            }
        else:
            self._state.phase = "role_reveal"

        return self.get_public_state()

    def _get_player(self, player_id: str) -> Optional[dict]:
        for p in self._state.players:
            if p["id"] == player_id:
                return p
        return None

    def _get_core_player(self, player_id: str) -> Optional[Player]:
        if not self._engine:
            return None
        for p in self._engine.state.players:
            if p.name == player_id:
                return p
        return None

    async def async_submit_night_action(
        self,
        action_type: str,
        target_id: str,
        skip_delay: bool = False,
    ) -> dict:
        """Submit a night action (wolf kill, seer investigate)."""
        if not self._engine:
            raise ValueError("Game not started")

        target = self._get_core_player(target_id)
        if not target or not target.alive:
            raise ValueError(f"Invalid target: {target_id}")

        if action_type == "wolf_kill":
            self._state.night_actions["wolf_victim_id"] = target_id

        elif action_type == "seer_investigate":
            self._state.night_actions["seer_target_id"] = target_id
            self._state.night_actions["seer_result"] = target.role.team

        return self.get_public_state()

    async def async_submit_vote(self, voter_id: str, target_id: str) -> dict:
        """Record a day vote."""
        if target_id not in self._state.vote_tallies:
            self._state.vote_tallies[target_id] = []
        self._state.vote_tallies[target_id].append(voter_id)

        return self.get_public_state()

    async def async_resolve_vote(self) -> dict:
        """Resolve the current vote and eliminate the player with most votes."""
        if not self._state.vote_tallies:
            self._state.eliminated_this_round = []
            return self.get_public_state()

        max_votes = max(len(v) for v in self._state.vote_tallies.values())
        leaders = [
            pid for pid, voters in self._state.vote_tallies.items()
            if len(voters) == max_votes
        ]

        if len(leaders) > 1:
            self._state.eliminated_this_round = []
        else:
            self._state.eliminated_this_round = leaders

        self._state.vote_tallies = {}
        return self.get_public_state()

    async def async_eliminate_player(self, player_id: str, cause: str) -> dict:
        """Eliminate a player and check win condition."""
        player = self._get_player(player_id)
        if not player:
            raise ValueError(f"Unknown player: {player_id}")

        player["alive"] = False
        self._state.eliminated_this_round.append(player_id)

        winner = self._check_win_condition()
        if winner:
            self._state.winner = winner
            self._state.phase = "game_over"

        return self.get_public_state()

    def _check_win_condition(self) -> Optional[str]:
        """Check win conditions and return winner."""
        alive = [p for p in self._state.players if p["alive"]]
        wolves = [p for p in alive if p["team"] == "werewolf"]
        village = [p for p in alive if p["team"] in ("village", "solo")]

        if not wolves:
            return "village"
        if len(wolves) >= len(village):
            return "werewolf"
        return None

    async def async_next_phase(self, skip_delay: bool = False) -> dict:
        """Advance to the next phase."""
        current = self._state.phase

        if current == "night_start":
            self._state.phase = "night_seer_wake"
        elif current == "night_seer_wake":
            self._state.phase = "night_seer_act"
        elif current == "night_seer_act":
            self._state.phase = "night_seer_sleep"
        elif current == "night_seer_sleep":
            self._state.phase = "night_wolf_wake"
        elif current == "night_wolf_wake":
            self._state.phase = "night_wolf_act"
        elif current == "night_wolf_act":
            self._state.phase = "night_wolf_sleep"
        elif current == "night_wolf_sleep":
            self._state.round += 1
            self._state.phase = "day"
            self._state.night_actions = {
                "wolf_victim_id": None,
                "seer_target_id": None,
                "seer_result": None,
                "completed_roles": [],
            }
        elif current == "day":
            self._state.phase = "discussion"
        elif current == "discussion":
            self._state.phase = "vote"
            self._state.vote_tallies = {}
        elif current == "vote":
            result = await self.async_resolve_vote()
            if self._state.eliminated_this_round:
                self._state.phase = "day"
            else:
                self._state.phase = "night_start"
        elif current == "game_over":
            pass

        return self.get_public_state()

    async def async_begin_vote(self) -> dict:
        """Start the vote phase."""
        self._state.phase = "vote"
        self._state.vote_tallies = {}
        return self.get_public_state()

    async def async_select_target(self, target_id: str) -> dict:
        """Record the currently selected target for UI feedback."""
        self._state.current_target_id = target_id
        return self.get_public_state()

    async def async_skip_night_action(self, skip_delay: bool = False) -> dict:
        """Skip the current role's night action."""
        self._state.night_actions["completed_roles"] = (
            self._state.night_actions.get("completed_roles", []) + ["current"]
        )
        self._state.current_target_id = None
        return self.get_public_state()

    async def async_reset(self) -> dict:
        """Reset game to initial state."""
        self._engine = None
        self._io = None
        self._state = HAIntegrationState()
        return {"phase": "setup"}

    def get_public_state(self) -> dict:
        """Return sanitized state for frontend."""
        alive_players = [p for p in self._state.players if p["alive"]]

        next_reveal_player = None
        if (
            self._state.phase == "role_reveal"
            and self._state.reveal_index < len(self._state.reveal_order)
        ):
            next_reveal_player = self._state.reveal_order[self._state.reveal_index]

        return {
            "phase": self._state.phase,
            "round": self._state.round,
            "language": self._state.language,
            "winner": self._state.winner,
            "players": [
                {"id": p["id"], "name": p["name"], "alive": p["alive"], "role_seen": p.get("role_seen", False)}
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
            "current_night_role": self._get_current_night_role(),
            "current_target_id": self._state.current_target_id,
            "night_actions_completed": self._state.night_actions.get("completed_roles", []),
        }

    def _get_current_night_role(self) -> Optional[str]:
        """Get the role that should act in the current night phase."""
        phase = self._state.phase
        if phase == "night_seer_wake" or phase == "night_seer_act":
            return "seer"
        if phase == "night_wolf_wake" or phase == "night_wolf_act":
            return "werewolf"
        return None

    def get_role_reveal_data(self, player_id: str) -> dict:
        """Return role data for a specific player during reveal."""
        player = self._get_player(player_id)
        if not player:
            raise ValueError(f"Unknown player: {player_id}")

        expected_id = (
            self._state.reveal_order[self._state.reveal_index]
            if self._state.reveal_index < len(self._state.reveal_order)
            else None
        )
        if player_id != expected_id:
            raise ValueError("Not this player's turn to reveal")

        return {
            "player_id": player["id"],
            "player_name": player["name"],
            "role": player["role"],
            "role_key": player.get("role_key"),
            "team": player.get("team"),
        }

    def get_seer_result(self, seer_player_id: str) -> dict:
        """Return seer investigation result."""
        player = self._get_player(seer_player_id)
        if not player or player.get("role_key") != "Seer":
            raise ValueError("Not a seer")

        target_id = self._state.night_actions.get("seer_target_id")
        if not target_id:
            raise ValueError("Seer has not investigated yet")

        target = self._get_player(target_id)
        return {
            "target_name": target["name"] if target else "?",
            "target_team": target.get("team") if target else "?",
        }

    def get_full_state_for_end(self) -> dict:
        """Full state including all roles — only sent at game over."""
        if self._state.phase != "game_over":
            raise ValueError("Game not over yet")

        return {
            **self.get_public_state(),
            "players_full": [
                {"id": p["id"], "name": p["name"], "role": p["role"], "alive": p["alive"], "team": p.get("team")}
                for p in self._state.players
            ],
        }