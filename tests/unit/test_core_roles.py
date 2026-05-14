"""
Tests for core_game roles module.
"""

import pytest


class TestRoleRegistry:
    """Test role registry contains expected roles."""

    def test_all_village_roles_exist(self):
        """Verify all village roles are registered."""
        from core_game import ROLE_REGISTRY
        
        expected_village = ["Villager", "Seer", "Doctor", "Bodyguard", "Hunter", "Witch", "Cupid"]
        for role in expected_village:
            assert role in ROLE_REGISTRY, f"Missing village role: {role}"

    def test_all_werewolf_roles_exist(self):
        """Verify werewolf roles are registered."""
        from core_game import ROLE_REGISTRY
        
        expected_wolves = ["Werewolf", "Alpha Wolf", "Minion"]
        for role in expected_wolves:
            assert role in ROLE_REGISTRY, f"Missing werewolf role: {role}"

    def test_all_solo_roles_exist(self):
        """Verify solo roles are registered."""
        from core_game import ROLE_REGISTRY
        
        assert "Serial Killer" in ROLE_REGISTRY
        assert "Jester" in ROLE_REGISTRY

    def test_role_has_expected_properties(self):
        """Verify roles have correct default properties."""
        from core_game import Villager, Werewolf, Seer, SerialKiller
        
        assert Villager.team == "village"
        assert Villager.has_night_action is False
        
        assert Werewolf.team == "werewolf"
        assert Werewolf.has_night_action is True
        assert Werewolf.night_priority == 30
        
        assert Seer.team == "village"
        assert Seer.has_night_action is True
        assert Seer.night_priority == 10
        
        assert SerialKiller.team == "solo"
        assert SerialKiller.has_night_action is True


class TestPresets:
    """Test role presets."""

    def test_small_preset_player_count(self):
        """Small preset should have 6 players."""
        from core_game import PRESETS
        
        assert len(PRESETS["small"]) == 6

    def test_medium_preset_player_count(self):
        """Medium preset should have 9 players."""
        from core_game import PRESETS
        
        assert len(PRESETS["medium"]) == 9

    def test_large_preset_player_count(self):
        """Large preset should have 13 players."""
        from core_game import PRESETS
        
        assert len(PRESETS["large"]) == 13

    def test_chaos_preset_has_werewolf_and_serial_killer(self):
        """Chaos preset should include both werewolf and serial killer."""
        from core_game import PRESETS
        
        roles = PRESETS["chaos"]
        assert "Werewolf" in roles
        assert "Serial Killer" in roles
        assert "Jester" in roles

    def test_preset_contains_valid_role_names(self):
        """All roles in presets should be in registry."""
        from core_game import ROLE_REGISTRY, PRESETS
        
        for preset_name, role_names in PRESETS.items():
            for role in role_names:
                assert role in ROLE_REGISTRY, f"Invalid role {role} in preset {preset_name}"


class TestRoleInstantiation:
    """Test role can be instantiated with a player."""

    def test_villager_instantiation(self):
        """Can create a Villager with a player."""
        from core_game.roles import Villager
        from core_game.game_state import Player
        
        player = Player(name="Alice", role=Villager(None))
        assert player.role.name == "Villager"
        assert player.role.team == "village"

    def test_role_key_property(self):
        """Role key should be accessible."""
        from core_game.roles import Seer, Werewolf
        
        assert Seer.role_key == "Seer"
        assert Werewolf.role_key == "Werewolf"