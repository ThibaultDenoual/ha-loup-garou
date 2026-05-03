"""Role assignment and validation for Loup Garou."""
from __future__ import annotations

import random

from .const import ROLE_WEREWOLF, ROLE_VILLAGER, ROLE_SEER, ROLE_TEAMS


class RoleManagerError(ValueError):
    """Raised when role configuration is invalid."""


class RoleManager:
    """Handles role assignment and validation."""

    def validate_role_config(
        self, n_players: int, role_config: dict[str, int]
    ) -> None:
        """
        Raise RoleManagerError if the config is invalid.

        Rules (Phase 1):
        - Total role count must equal n_players
        - At least 1 werewolf
        - At least 1 non-wolf player
        - At least 4 players total
        """
        if n_players < 4:
            raise RoleManagerError(
                f"Need at least 4 players, got {n_players}"
            )

        total_roles = sum(role_config.values())
        if total_roles != n_players:
            raise RoleManagerError(
                f"Role count ({total_roles}) does not match player count ({n_players})"
            )

        wolf_count = role_config.get(ROLE_WEREWOLF, 0)
        if wolf_count < 1:
            raise RoleManagerError("Need at least 1 werewolf")

        village_count = n_players - wolf_count
        if village_count < 1:
            raise RoleManagerError("Need at least 1 non-wolf player")

        if wolf_count >= village_count:
            raise RoleManagerError(
                f"Too many wolves ({wolf_count}) for {village_count} villagers — "
                "wolves would win immediately"
            )

    def assign_roles(
        self,
        player_names: list[str],
        role_config: dict[str, int],
    ) -> dict[str, str]:
        """
        Return {player_name: role} with roles shuffled randomly.

        Validates before assigning.
        """
        self.validate_role_config(len(player_names), role_config)

        # Build flat list of roles
        role_pool: list[str] = []
        for role, count in role_config.items():
            role_pool.extend([role] * count)

        random.shuffle(role_pool)

        return dict(zip(player_names, role_pool))

    def suggest_role_distribution(self, n_players: int) -> dict[str, int]:
        """
        Return a sensible default role distribution for n players.
        Used by the setup UI as a starting suggestion.
        """
        from .const import DEFAULT_ROLE_DISTRIBUTION

        if n_players in DEFAULT_ROLE_DISTRIBUTION:
            return dict(DEFAULT_ROLE_DISTRIBUTION[n_players])

        # For larger counts: ~1 wolf per 4 players, 1 seer, rest villagers
        wolf_count = max(1, n_players // 4)
        seer_count = 1
        villager_count = n_players - wolf_count - seer_count

        if villager_count < 1:
            # Edge case: adjust
            seer_count = 0
            villager_count = n_players - wolf_count

        return {
            ROLE_VILLAGER: villager_count,
            ROLE_WEREWOLF: wolf_count,
            ROLE_SEER: seer_count if seer_count > 0 else 0,
        }

    def get_role_team(self, role: str) -> str:
        return ROLE_TEAMS.get(role, "village")