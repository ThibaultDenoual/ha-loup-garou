"""Role assignment logic for Loup Garou."""
from __future__ import annotations

import random
import logging
from dataclasses import dataclass

from ..const import Role, WOLF_TEAM, VILLAGE_TEAM, ROLE_META

_LOGGER = logging.getLogger(__name__)


class RoleConfigError(ValueError):
    """Raised when the role configuration is invalid for the given player count."""


@dataclass
class RoleConfig:
    """How many of each role to include in a game."""

    villagers: int = 0
    werewolves: int = 0
    seers: int = 0

    @property
    def total(self) -> int:
        return self.villagers + self.werewolves + self.seers

    def to_role_list(self) -> list[Role]:
        """Expand config into a flat list of Role values."""
        roles: list[Role] = []
        roles.extend([Role.VILLAGER] * self.villagers)
        roles.extend([Role.WEREWOLF] * self.werewolves)
        roles.extend([Role.SEER] * self.seers)
        return roles

    @classmethod
    def suggest_for(cls, n_players: int) -> "RoleConfig":
        """Return a sensible default role distribution for n_players.

        Rules:
        - At least 1 werewolf.
        - 1 seer if n_players >= 5.
        - Rest are villagers.
        - Never more wolves than (n_players // 3).
        """
        if n_players < 4:
            raise RoleConfigError(
                f"Need at least 4 players, got {n_players}."
            )

        n_wolves = max(1, n_players // 3)
        n_seers = 1 if n_players >= 5 else 0
        n_villagers = n_players - n_wolves - n_seers

        config = cls(
            villagers=n_villagers,
            werewolves=n_wolves,
            seers=n_seers,
        )
        _LOGGER.debug("Suggested roles for %d players: %s", n_players, config)
        return config

    @classmethod
    def from_dict(cls, data: dict) -> "RoleConfig":
        return cls(
            villagers=int(data.get("villagers", 0)),
            werewolves=int(data.get("werewolves", 0)),
            seers=int(data.get("seers", 0)),
        )

    def to_dict(self) -> dict:
        return {
            "villagers": self.villagers,
            "werewolves": self.werewolves,
            "seers": self.seers,
        }


class RoleManager:
    """Assigns and validates roles for a game."""

    def validate(self, config: RoleConfig, n_players: int) -> None:
        """Raise RoleConfigError if the config is not valid.

        Checks:
        - Total roles == n_players.
        - At least 1 werewolf.
        - At least 1 village-team player.
        - No negative counts.
        """
        if config.villagers < 0 or config.werewolves < 0 or config.seers < 0:
            raise RoleConfigError("Role counts cannot be negative.")
        if config.total != n_players:
            raise RoleConfigError(
                f"Role total ({config.total}) must equal player count ({n_players})."
            )
        if config.werewolves < 1:
            raise RoleConfigError("There must be at least 1 werewolf.")
        village_count = config.villagers + config.seers
        if village_count < 1:
            raise RoleConfigError("There must be at least 1 village-team player.")

    def assign_roles(
        self,
        player_ids: list[str],
        config: RoleConfig,
    ) -> dict[str, Role]:
        """Return a shuffled mapping of player_id → Role.

        Args:
            player_ids: Ordered list of player IDs (from GameState).
            config: Role configuration to use.

        Returns:
            Dict mapping each player_id to a Role.
        """
        self.validate(config, len(player_ids))

        role_list = config.to_role_list()
        random.shuffle(role_list)

        assignment = dict(zip(player_ids, role_list))
        _LOGGER.debug("Role assignment: %s", assignment)
        return assignment

    def get_wolves(self, assignment: dict[str, Role]) -> list[str]:
        """Return player IDs whose role is in the wolf team."""
        return [pid for pid, role in assignment.items() if role in WOLF_TEAM]

    def get_village(self, assignment: dict[str, Role]) -> list[str]:
        """Return player IDs whose role is in the village team."""
        return [pid for pid, role in assignment.items() if role in VILLAGE_TEAM]

    def role_meta(self, role: Role) -> dict:
        """Return display metadata for a role."""
        return ROLE_META.get(role, {})