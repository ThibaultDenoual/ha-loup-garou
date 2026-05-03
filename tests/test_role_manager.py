"""Tests for RoleManager and RoleConfig."""
from __future__ import annotations

import pytest

from custom_components.loup_garou.role_manager import RoleManager, RoleConfig, RoleConfigError
from custom_components.loup_garou.const import Role, WOLF_TEAM, VILLAGE_TEAM


@pytest.fixture
def manager():
    return RoleManager()


# ── RoleConfig.suggest_for ───────────────────────────────────────────────────

class TestSuggestFor:
    def test_minimum_4_players(self):
        config = RoleConfig.suggest_for(4)
        assert config.total == 4
        assert config.werewolves >= 1

    def test_no_seer_below_5(self):
        config = RoleConfig.suggest_for(4)
        assert config.seers == 0

    def test_seer_at_5_players(self):
        config = RoleConfig.suggest_for(5)
        assert config.seers == 1

    def test_wolf_count_scales(self):
        config = RoleConfig.suggest_for(9)
        assert config.werewolves == 3  # 9 // 3

    def test_total_equals_player_count(self):
        for n in range(4, 13):
            assert RoleConfig.suggest_for(n).total == n

    def test_raises_below_4(self):
        with pytest.raises(RoleConfigError):
            RoleConfig.suggest_for(3)


# ── RoleManager.validate ─────────────────────────────────────────────────────

class TestValidate:
    def test_valid_config(self, manager):
        config = RoleConfig(villagers=3, werewolves=1, seers=1)
        manager.validate(config, 5)  # should not raise

    def test_wrong_total(self, manager):
        config = RoleConfig(villagers=3, werewolves=1, seers=0)
        with pytest.raises(RoleConfigError, match="total"):
            manager.validate(config, 6)

    def test_no_wolves(self, manager):
        config = RoleConfig(villagers=5, werewolves=0, seers=0)
        with pytest.raises(RoleConfigError, match="werewolf"):
            manager.validate(config, 5)

    def test_no_village_team(self, manager):
        config = RoleConfig(villagers=0, werewolves=5, seers=0)
        with pytest.raises(RoleConfigError, match="village"):
            manager.validate(config, 5)

    def test_negative_count(self, manager):
        config = RoleConfig(villagers=-1, werewolves=2, seers=0)
        with pytest.raises(RoleConfigError, match="negative"):
            manager.validate(config, 1)


# ── RoleManager.assign_roles ─────────────────────────────────────────────────

class TestAssignRoles:
    def _ids(self, n: int) -> list[str]:
        return [f"p{i}" for i in range(n)]

    def test_assigns_all_players(self, manager):
        ids = self._ids(5)
        config = RoleConfig(villagers=3, werewolves=1, seers=1)
        result = manager.assign_roles(ids, config)
        assert set(result.keys()) == set(ids)

    def test_correct_role_counts(self, manager):
        ids = self._ids(6)
        config = RoleConfig(villagers=4, werewolves=1, seers=1)
        result = manager.assign_roles(ids, config)
        roles = list(result.values())
        assert roles.count(Role.VILLAGER) == 4
        assert roles.count(Role.WEREWOLF) == 1
        assert roles.count(Role.SEER) == 1

    def test_all_roles_are_valid(self, manager):
        ids = self._ids(5)
        config = RoleConfig(villagers=3, werewolves=1, seers=1)
        result = manager.assign_roles(ids, config)
        for role in result.values():
            assert role in list(Role)

    def test_invalid_config_raises(self, manager):
        ids = self._ids(5)
        bad_config = RoleConfig(villagers=0, werewolves=0, seers=0)
        with pytest.raises(RoleConfigError):
            manager.assign_roles(ids, bad_config)

    def test_randomness(self, manager):
        """Run 20 assignments and verify not all identical (statistical)."""
        ids = self._ids(6)
        config = RoleConfig(villagers=4, werewolves=1, seers=1)
        results = [
            tuple(manager.assign_roles(ids, config)[pid] for pid in ids)
            for _ in range(20)
        ]
        assert len(set(results)) > 1, "All 20 assignments were identical — suspiciously unlikely."

    def test_get_wolves(self, manager):
        ids = self._ids(5)
        config = RoleConfig(villagers=3, werewolves=1, seers=1)
        assignment = manager.assign_roles(ids, config)
        wolves = manager.get_wolves(assignment)
        assert len(wolves) == 1
        assert assignment[wolves[0]] in WOLF_TEAM

    def test_get_village(self, manager):
        ids = self._ids(5)
        config = RoleConfig(villagers=3, werewolves=1, seers=1)
        assignment = manager.assign_roles(ids, config)
        village = manager.get_village(assignment)
        assert len(village) == 4
        for pid in village:
            assert assignment[pid] in VILLAGE_TEAM