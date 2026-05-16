"""
ha_adapter.py — Async adapter bridging sync core_game with Home Assistant.

This adapter wraps the synchronous GameEngine and provides async methods
compatible with the HA integration, using run_in_executor for thread-safety.
"""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from .. import (
    GameState,
    Player,
    ROLE_REGISTRY,
    PRESETS as CORE_PRESETS,
)
from ..io_adapters.ha_io import HomeAssistantIO
from ..engine import GameEngine, GameEvents
from ...const import EVENT_GAME_STARTED, EVENT_GAME_STATE_CHANGED

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


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
    current_acting_player_id: Optional[str] = None
    current_action_type: Optional[str] = None
    pending_seer_result: Optional[str] = None
    night_action_actor_ids: list = field(default_factory=list)
    night_action_actor_index: int = 0
    completed_night_actions: list = field(default_factory=list)


class HAGameEvents(GameEvents):
    """GameEvents implementation for Home Assistant integration."""

    def __init__(self, adapter: "AsyncGameAdapter"):
        self._adapter = adapter

    def on_phase_changed(self, old_phase: str, new_phase: str) -> None:
        self._adapter._on_phase_changed(old_phase, new_phase)

    def on_night_resolved(
        self,
        deaths: list[tuple[Player, str]],
        protections: set[Player]
    ) -> None:
        self._adapter._on_night_resolved(deaths, protections)

    def on_player_eliminated(self, player: Player, cause: str) -> None:
        self._adapter._on_player_eliminated(player, cause)

    def on_game_over(self, winner: Optional[str]) -> None:
        self._adapter._on_game_over(winner)

    def on_role_acting(self, player: Player, action_type: str) -> None:
        self._adapter._on_role_acting(player, action_type)


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
        tts_controller=None,
        light_controller=None,
    ):
        self._hass = hass
        self._config_entry_id = config_entry_id
        self._tts = tts_controller
        self._lights = light_controller
        self._engine: Optional[GameEngine] = None
        self._io: Optional[HomeAssistantIO] = None
        self._state = HAIntegrationState()
        self._loop = None

    @property
    def state(self) -> HAIntegrationState:
        return self._state

    def _run_sync(self, func, *args, **kwargs):
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(None, func, *args, **kwargs)

    def _on_phase_changed(self, old_phase: str, new_phase: str) -> None:
        self._state.phase = new_phase
        if self._hass:
            self._hass.bus.fire(EVENT_GAME_STATE_CHANGED, {"phase": new_phase})

    def _on_night_resolved(
        self,
        deaths: list[tuple[Player, str]],
        protections: set[Player]
    ) -> None:
        self._state.eliminated_this_round = [p.name for p, _ in deaths]
        for player, _ in deaths:
            ha_player = self._get_player(player.name)
            if ha_player:
                ha_player["alive"] = False

    def _on_player_eliminated(self, player: Player, cause: str) -> None:
        ha_player = self._get_player(player.name)
        if ha_player:
            ha_player["alive"] = False
        if player.name not in self._state.eliminated_this_round:
            self._state.eliminated_this_round.append(player.name)

    def _on_game_over(self, winner: Optional[str]) -> None:
        self._state.winner = winner
        self._state.phase = "game_over"
        if self._hass:
            self._hass.bus.fire(EVENT_GAME_STATE_CHANGED, {"phase": "game_over"})

    def _on_role_acting(self, player: Player, action_type: str) -> None:
        self._state.current_acting_player_id = player.name
        self._state.current_action_type = action_type

    async def async_start_game(
        self,
        player_names: list[str],
        role_config: dict,
        language: str = "fr",
    ) -> dict:
        if "preset" in role_config:
            role_cfg = role_config.get("preset", "medium")
            role_names = CORE_PRESETS.get(role_cfg, CORE_PRESETS["small"])
        else:
            villagers = role_config.get("villagers", 3)
            werewolves = role_config.get("werewolves", 1)
            seers = role_config.get("seers", 1)
            role_names = (
                ["Werewolf"] * werewolves +
                ["Seer"] * seers +
                ["Villager"] * villagers
            )
        _LOGGER.warning(f"Starting game with players: {player_names} and roles: {role_names}")
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

        self._io = HomeAssistantIO(
            tts_controller=self._tts,
            light_controller=self._lights,
            hass=self._hass,
        )
        game_events = HAGameEvents(self)
        self._engine = GameEngine(
            player_names=player_names,
            role_names=shuffled_roles,
            io=self._io,
            seed=None,
            events=game_events,
        )

        self._state = HAIntegrationState(
            phase="role_reveal",
            round=0,
            players=[self._player_to_ha(p) for p in players],
            reveal_order=[p.name for p in players],
            reveal_index=0,
            language=language,
        )

        if self._hass:
            self._hass.bus.fire(EVENT_GAME_STARTED, {"io": self._io})

        if self._hass:
            self._hass.bus.fire(EVENT_GAME_STATE_CHANGED, {"phase": self._state.phase})

        return self.get_public_state()

    def _player_to_ha(self, player: Player) -> dict:
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

        if self._hass:
            self._hass.bus.fire(EVENT_GAME_STATE_CHANGED, {"phase": self._state.phase})

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
        if not self._engine:
            raise ValueError("Game not started")

        actor_id = self._state.current_acting_player_id
        if not actor_id:
            raise ValueError("No actor currently acting")

        actor = self._get_core_player(actor_id)
        if not actor or not actor.alive:
            raise ValueError(f"Invalid actor: {actor_id}")

        target = self._get_core_player(target_id)
        if not target or not target.alive:
            raise ValueError(f"Invalid target: {target_id}")

        action_type_map = {
            "seer_investigate": "investigate",
            "wolf_kill": "kill",
            "doctor_protect": "protect",
            "bodyguard_guard": "protect",
            "witch_heal": "protect",
            "witch_poison": "kill",
            "alpha_convert": "convert",
            "cupid_link": "none",
            "serial_killer_kill": "kill",
        }
        engine_action_type = action_type_map.get(action_type, action_type)

        self._engine.submit_night_action(actor_id, engine_action_type, target_id)

        if action_type == "seer_investigate":
            self._state.pending_seer_result = target.role.team

        if actor_id not in self._state.completed_night_actions:
            self._state.completed_night_actions.append(actor_id)

        self._advance_to_next_actor()

        return self.get_public_state()

    def _advance_to_next_actor(self) -> None:
        idx = self._state.night_action_actor_index
        actors = self._state.night_action_actor_ids

        if idx >= len(actors):
            self._state.current_acting_player_id = None
            self._state.current_action_type = None
            return

        next_actor_id = actors[idx]
        next_actor = self._get_core_player(next_actor_id)

        if next_actor and next_actor.alive:
            self._state.current_acting_player_id = next_actor_id
            self._state.current_action_type = self._get_action_type_for_role(next_actor.role.role_key)
        else:
            self._state.night_action_actor_index += 1
            self._advance_to_next_actor()

    def _get_action_type_for_role(self, role_key: str) -> str:
        mapping = {
            "Seer": "seer_investigate",
            "Werewolf": "wolf_kill",
            "Doctor": "doctor_protect",
            "Bodyguard": "bodyguard_guard",
            "Witch": "witch_heal",
            "Alpha Wolf": "alpha_convert",
            "Serial Killer": "serial_killer_kill",
            "Cupid": "cupid_link",
        }
        return mapping.get(role_key, "")

    async def async_submit_vote(self, voter_id: str, target_id: str) -> dict:
        if target_id not in self._state.vote_tallies:
            self._state.vote_tallies[target_id] = []
        self._state.vote_tallies[target_id].append(voter_id)

        return self.get_public_state()

    async def async_resolve_vote(self) -> dict:
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
        alive = [p for p in self._state.players if p["alive"]]
        wolves = [p for p in alive if p["team"] == "werewolf"]
        village = [p for p in alive if p["team"] in ("village", "solo")]

        if not wolves:
            return "village"
        if len(wolves) >= len(village):
            return "werewolf"
        return None

    async def async_next_phase(self, skip_delay: bool = False) -> dict:
        current = self._state.phase

        if current == "night_start":
            self._init_night_actions()
            self._state.phase = "night_seer_wake"
        elif current == "night_seer_wake":
            self._state.phase = "night_seer_act"
        elif current == "night_seer_act":
            self._advance_to_next_actor()
            if self._state.current_acting_player_id:
                self._state.phase = "night_seer_sleep"
            else:
                self._state.phase = "night_wolf_wake"
        elif current == "night_seer_sleep":
            if self._state.night_action_actor_index < len(self._state.night_action_actor_ids):
                self._state.phase = "night_wolf_wake"
            else:
                self._state.phase = "night_wolf_wake"
        elif current == "night_wolf_wake":
            self._state.phase = "night_wolf_act"
        elif current == "night_wolf_act":
            self._advance_to_next_actor()
            if self._state.current_acting_player_id:
                self._state.phase = "night_wolf_sleep"
            else:
                self._state.phase = "night_wolf_sleep"
        elif current == "night_wolf_sleep":
            self._state.round += 1
            self._state.phase = "day"
            self._state.night_action_actor_ids = []
            self._state.night_action_actor_index = 0
            self._state.pending_seer_result = None
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

        if self._hass:
            self._hass.bus.fire(EVENT_GAME_STATE_CHANGED, {"phase": self._state.phase})

        return self.get_public_state()

    def _init_night_actions(self) -> None:
        if not self._engine:
            return
        actors = self._engine.get_night_action_actors()
        self._state.night_action_actor_ids = [p.name for p in actors]
        self._state.night_action_actor_index = 0

        if actors:
            first_actor = actors[0]
            self._state.current_acting_player_id = first_actor.name
            self._state.current_action_type = self._get_action_type_for_role(first_actor.role.role_key)

    async def async_begin_vote(self) -> dict:
        self._state.phase = "vote"
        self._state.vote_tallies = {}
        return self.get_public_state()

    async def async_select_target(self, target_id: str) -> dict:
        self._state.current_target_id = target_id
        return self.get_public_state()

    async def async_skip_night_action(self, skip_delay: bool = False) -> dict:
        self._state.night_actions["completed_roles"] = (
            self._state.night_actions.get("completed_roles", []) + ["current"]
        )
        self._state.current_target_id = None
        return self.get_public_state()

    async def async_reset(self) -> dict:
        self._engine = None
        self._io = None
        self._state = HAIntegrationState()
        return {"phase": "setup"}

    def get_public_state(self) -> dict:
        if not self._engine:
            return {"phase": "setup", "players": []}

        engine_phase = self._engine._fsm_state
        gs = self._engine.state

        if engine_phase == "setup" and self._state.phase == "role_reveal":
            phase = "role_reveal"
        else:
            phase = engine_phase

        alive_players = gs.alive_players

        next_reveal_player = None
        current_reveal_role = None

        if phase == "role_reveal" and self._state.reveal_index < len(self._state.reveal_order):
            next_reveal_name = self._state.reveal_order[self._state.reveal_index]
            core_player = self._get_core_player(next_reveal_name)
            if core_player:
                current_reveal_role = core_player.role.name
                next_reveal_player = {
                    "id": core_player.name,
                    "name": core_player.name,
                    "role": core_player.role.name,
                    "role_key": core_player.role.role_key,
                    "team": core_player.role.team,
                    "alive": core_player.alive,
                }

        players_data = []
        for p in gs.players:
            player_data = {
                "id": p.name,
                "name": p.name,
                "alive": p.alive,
                "role_seen": False,
            }
            if phase == "role_reveal":
                player_data["role"] = p.role.name
                player_data["role_key"] = p.role.role_key
                player_data["team"] = p.role.team
            players_data.append(player_data)

        current_night_role = None
        if self._state.current_acting_player_id:
            acting_player = self._get_core_player(self._state.current_acting_player_id)
            if acting_player:
                current_night_role = acting_player.role.role_key

        return {
            "phase": phase,
            "round": gs.round_number,
            "language": self._state.language,
            "winner": gs.winner,
            "players": players_data,
            "current_reveal_role": current_reveal_role,
            "current_reveal_player": next_reveal_player,
            "alive_count": len(alive_players),
            "dead_count": len(gs.players) - len(alive_players),
            "reveal_index": self._state.reveal_index,
            "reveal_total": len(gs.players),
            "next_reveal_player": next_reveal_player,
            "eliminated_this_round": self._state.eliminated_this_round,
            "vote_tallies_count": {
                pid: len(voters)
                for pid, voters in self._state.vote_tallies.items()
            },
            "votes_cast": sum(len(v) for v in self._state.vote_tallies.values()),
            "alive_voter_count": len(alive_players),
            "current_night_role": current_night_role,
            "current_action_type": self._state.current_action_type,
            "current_acting_player_id": self._state.current_acting_player_id,
            "current_target_id": self._state.current_target_id,
            "pending_seer_result": self._state.pending_seer_result,
            "night_actions_completed": self._state.completed_night_actions,
        }

    def get_role_reveal_data(self, player_id: str) -> dict:
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
        if self._state.phase != "game_over":
            raise ValueError("Game not over yet")

        return {
            **self.get_public_state(),
            "players_full": [
                {"id": p["id"], "name": p["name"], "role": p["role"], "alive": p["alive"], "team": p.get("team")}
                for p in self._state.players
            ],
        }