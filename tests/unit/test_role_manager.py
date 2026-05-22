"""Unit tests for core/role_manager.py"""
from __future__ import annotations

import pytest

from custom_components.loup_garou.core.role_manager import RoleManager, RoleConfig, RoleConfigError
from custom_components.loup_garou.const import Role, WOLF_TEAM, VILLAGE_TEAM


class TestRoleConfig:
    def test_total_calculation(self):
        """Total is sum of all role counts."""
        config = RoleConfig(villagers=3, werewolves=1, seers=1)
        assert config.total == 5

    def test_to_role_list(self):
        """Converts config to flat list of Role values."""
        config = RoleConfig(villagers=2, werewolves=1, seers=0)
        roles = config.to_role_list()

        assert roles.count(Role.VILLAGER) == 2
        assert roles.count(Role.WEREWOLF) == 1
        assert roles.count(Role.SEER) == 0
        assert len(roles) == 3

    def test_suggest_for_4_players(self):
        """Suggest returns valid config for 4 players."""
        config = RoleConfig.suggest_for(4)

        assert config.total == 4
        assert config.werewolves == 1
        assert config.seers == 0
        assert config.villagers == 3

    def test_suggest_for_5_players(self):
        """Suggest includes seer for 5+ players."""
        config = RoleConfig.suggest_for(5)

        assert config.total == 5
        assert config.werewolves == 1
        assert config.seers == 1
        assert config.villagers == 3

    def test_suggest_for_8_players(self):
        """Suggest returns balanced config for 8 players."""
        config = RoleConfig.suggest_for(8)

        assert config.total == 8
        assert config.werewolves == 2
        assert config.seers == 1
        assert config.villagers == 5

    def test_suggest_raises_for_less_than_4(self):
        """Cannot suggest for fewer than 4 players."""
        with pytest.raises(RoleConfigError, match="at least 4 players"):
            RoleConfig.suggest_for(3)

    def test_from_dict(self):
        """Creates config from dict."""
        config = RoleConfig.from_dict({"villagers": 4, "werewolves": 2, "seers": 0})

        assert config.villagers == 4
        assert config.werewolves == 2
        assert config.seers == 0

    def test_to_dict(self):
        """Serializes config to dict."""
        config = RoleConfig(villagers=3, werewolves=1, seers=1)
        data = config.to_dict()

        assert data == {"villagers": 3, "werewolves": 1, "seers": 1}


class TestRoleManager:
    def test_validate_raises_negative_counts(self):
        """Negative role counts are rejected."""
        manager = RoleManager()

        with pytest.raises(RoleConfigError, match="cannot be negative"):
            manager.validate(RoleConfig(-1, 1, 1), 1)

    def test_validate_raises_total_mismatch(self):
        """Roles must sum to player count."""
        manager = RoleManager()

        with pytest.raises(RoleConfigError, match="must equal player count"):
            manager.validate(RoleConfig(2, 1, 1), 5)

    def test_validate_raises_no_werewolf(self):
        """At least one werewolf required."""
        manager = RoleManager()

        with pytest.raises(RoleConfigError, match="at least 1 werewolf"):
            manager.validate(RoleConfig(5, 0, 0), 5)

    def test_validate_raises_no_village_team(self):
        """At least one village team player required."""
        manager = RoleManager()

        with pytest.raises(RoleConfigError, match="at least 1 village-team"):
            manager.validate(RoleConfig(0, 5, 0), 5)

    def test_validate_passes_valid_config(self):
        """Valid config passes validation."""
        manager = RoleManager()

        config = RoleConfig(villagers=3, werewolves=1, seers=1)
        manager.validate(config, 5)

    def test_assign_roles_shuffles(self):
        """Role assignment is randomized."""
        manager = RoleManager()
        player_ids = ["p1", "p2", "p3", "p4", "p5"]
        config = RoleConfig(villagers=3, werewolves=1, seers=1)

        assignments = manager.assign_roles(player_ids, config)

        assert len(assignments) == 5
        assert set(assignments.keys()) == set(player_ids)
        assert all(r in [Role.VILLAGER, Role.WEREWOLF, Role.SEER] for r in assignments.values())

    def test_assign_roles_validates_first(self):
        """assign_roles validates before assigning."""
        manager = RoleManager()

        with pytest.raises(RoleConfigError):
            manager.assign_roles(["p1", "p2"], RoleConfig(0, 0, 0))

    def test_get_wolves(self):
        """Returns player IDs in wolf team."""
        manager = RoleManager()
        assignment = {
            "p1": Role.WEREWOLF,
            "p2": Role.VILLAGER,
            "p3": Role.WEREWOLF,
            "p4": Role.SEER,
        }

        wolves = manager.get_wolves(assignment)

        assert "p1" in wolves
        assert "p3" in wolves
        assert "p2" not in wolves
        assert "p4" not in wolves

    def test_get_village(self):
        """Returns player IDs in village team."""
        manager = RoleManager()
        assignment = {
            "p1": Role.WEREWOLF,
            "p2": Role.VILLAGER,
            "p3": Role.SEER,
        }

        village = manager.get_village(assignment)

        assert "p2" in village
        assert "p3" in village
        assert "p1" not in village

    def test_role_meta_returns_metadata(self):
        """role_meta returns display metadata for a role."""
        manager = RoleManager()

        meta = manager.role_meta(Role.WEREWOLF)

        assert meta["team"] == "wolves"
        assert "icon" in meta
        assert "description_fr" in meta