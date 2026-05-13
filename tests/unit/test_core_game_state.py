"""
Tests for core_game game_state module.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "custom_components", "loup_garou"))


class TestPlayer:
    """Test Player dataclass."""

    def test_player_creation(self):
        """Can create a player with name and role."""
        from core_game.roles import Villager
        from core_game.game_state import Player
        
        player = Player(name="Alice", role=Villager(None))
        
        assert player.name == "Alice"
        assert player.alive is True
        assert player.silenced is False
        assert player.lover is None

    def test_player_equality(self):
        """Players with same name should be equal."""
        from core_game.roles import Villager
        from core_game.game_state import Player
        
        p1 = Player(name="Alice", role=Villager(None))
        p2 = Player(name="Alice", role=Villager(None))
        
        assert p1 == p2

    def test_player_hash(self):
        """Player name should be hashable."""
        from core_game.roles import Villager
        from core_game.game_state import Player
        
        p = Player(name="Alice", role=Villager(None))
        
        assert hash(p) == hash("Alice")

    def test_player_to_dict(self):
        """Player can serialize to dict."""
        from core_game.roles import Villager
        from core_game.game_state import Player
        
        player = Player(name="Alice", role=Villager(None), alive=True)
        d = player.to_dict()
        
        assert d["name"] == "Alice"
        assert d["role"] == "Villager"
        assert d["alive"] is True
        assert d["silenced"] is False


class TestGameState:
    """Test GameState class."""

    def test_empty_state_creation(self):
        """Can create empty game state."""
        from core_game.game_state import GameState
        
        state = GameState()
        
        assert state.players == []
        assert state.round_number == 0
        assert state.phase == "setup"
        assert state.winner is None

    def test_state_with_players(self):
        """Can create game state with players."""
        from core_game.roles import Villager
        from core_game.game_state import GameState, Player
        
        players = [
            Player(name="Alice", role=Villager(None)),
            Player(name="Bob", role=Villager(None)),
        ]
        state = GameState(players=players)
        
        assert len(state.players) == 2
        assert state.alive_players == players
        assert state.dead_players == []

    def test_alive_players_filter(self):
        """alive_players returns only alive players."""
        from core_game.roles import Villager
        from core_game.game_state import GameState, Player
        
        p1 = Player(name="Alice", role=Villager(None), alive=True)
        p2 = Player(name="Bob", role=Villager(None), alive=False)
        
        state = GameState(players=[p1, p2])
        
        assert len(state.alive_players) == 1
        assert state.alive_players[0].name == "Alice"

    def test_werewolves_property(self):
        """werewolves returns only werewolf team players."""
        from core_game.roles import Villager, Werewolf
        from core_game.game_state import GameState, Player
        
        p1 = Player(name="Alice", role=Werewolf(None))
        p2 = Player(name="Bob", role=Villager(None))
        
        state = GameState(players=[p1, p2])
        
        assert len(state.werewolves) == 1
        assert state.werewolves[0].name == "Alice"

    def test_schedule_death(self):
        """Can schedule a player death."""
        from core_game.roles import Villager
        from core_game.game_state import GameState, Player
        
        player = Player(name="Alice", role=Villager(None))
        state = GameState(players=[player])
        
        state.schedule_death(player, cause="wolf_kill")
        
        assert len(state.pending_deaths) == 1
        assert state.pending_deaths[0][0] == player
        assert state.pending_deaths[0][1] == "wolf_kill"

    def test_reset_night_state(self):
        """reset_night_state clears night-specific data."""
        from core_game.game_state import GameState
        
        state = GameState()
        state.tonight_attacked = ["test"]
        state.tonight_protected = ["test"]
        state.pending_deaths = [("test", "cause")]
        state.tonight_actions = ["test"]
        
        state.reset_night_state()
        
        assert state.tonight_attacked == []
        assert state.tonight_protected == []
        assert state.pending_deaths == []
        assert state.tonight_actions == []

    def test_link_lovers(self):
        """Can link two players as lovers."""
        from core_game.roles import Villager
        from core_game.game_state import GameState, Player
        
        p1 = Player(name="Alice", role=Villager(None))
        p2 = Player(name="Bob", role=Villager(None))
        
        state = GameState(players=[p1, p2])
        state.link_lovers(p1, p2)
        
        assert p1.lover == p2
        assert p2.lover == p1

    def test_declare_solo_winner(self):
        """Can declare a solo winner."""
        from core_game.roles import Villager
        from core_game.game_state import GameState, Player
        
        player = Player(name="Alice", role=Villager(None))
        state = GameState(players=[player])
        
        state.declare_solo_winner(player)
        
        assert state.winner == "Alice"
        assert state.solo_winner == player

    def test_is_game_over(self):
        """is_game_over returns True when winner is set."""
        from core_game.game_state import GameState
        
        state = GameState()
        assert state.is_game_over() is False
        
        state.winner = "village"
        assert state.is_game_over() is True


class TestGameStateSerialization:
    """Test game state serialization."""

    def test_to_dict(self):
        """GameState can serialize to dict."""
        from core_game.roles import Villager
        from core_game.game_state import GameState, Player
        
        player = Player(name="Alice", role=Villager(None))
        state = GameState(players=[player], round_number=1)
        
        d = state.to_dict()
        
        assert "players" in d
        assert "round_number" in d
        assert "phase" in d

    def test_from_dict(self):
        """GameState can deserialize from dict."""
        from core_game.roles import ROLE_REGISTRY
        from core_game.game_state import GameState
        
        data = {
            "players": [
                {"name": "Alice", "role": "Villager", "alive": True, "silenced": False}
            ],
            "round_number": 1,
            "phase": "day",
            "winner": None,
            "event_log": []
        }
        
        state = GameState.from_dict(data, ROLE_REGISTRY)
        
        assert len(state.players) == 1
        assert state.players[0].name == "Alice"
        assert state.round_number == 1
        assert state.phase == "day"