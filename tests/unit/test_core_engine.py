"""
Tests for core_game engine module.
"""

from __future__ import annotations

import pytest

from core_game.roles import PRESETS


class MockIO:
    """Mock IO for testing game engine."""

    def __init__(self):
        self.messages = []
        self.private_messages = {}
        self.choices = {}
        self.yes_no_answers = {}
        self.vote_tally = {}
        self.paused = False

    def announce(self, message: str) -> None:
        self.messages.append(("announce", message))

    def private(self, player, message: str) -> None:
        self.private_messages[player.name] = message

    def choose_target(self, actor, candidates, prompt):
        key = (actor.name, prompt)
        if key in self.choices:
            choice_name = self.choices[key]
            for c in candidates:
                if c.name == choice_name:
                    return c
        if candidates:
            return candidates[0]
        return None

    def choose_multiple(self, actor, candidates, prompt, min_choices=1, max_choices=1):
        key = (actor.name, prompt)
        if key in self.choices:
            choice_names = self.choices[key]
            return [c for c in candidates if c.name in choice_names]
        return candidates[:1] if candidates else []

    def yes_no(self, actor, prompt):
        key = (actor.name, prompt)
        return self.yes_no_answers.get(key, False)

    def get_votes(self, voters, candidates):
        return self.vote_tally

    def pause(self, prompt=""):
        self.paused = True

    def separator(self, title=""):
        self.messages.append(("separator", title))


class TestEngineInitialization:
    """Test engine initialization."""

    def test_engine_requires_transitions(self):
        """Engine module should import successfully with transitions installed."""
        from core_game.engine import GameEngine
        assert GameEngine is not None

    def test_engine_creation_basic(self):
        """Can create engine with basic parameters."""
        from core_game.engine import GameEngine
        from core_game import Player, ROLE_REGISTRY

        io = MockIO()
        engine = GameEngine(
            player_names=["Alice", "Bob", "Charlie", "Dave", "Eve", "Frank"],
            role_names=PRESETS["small"],
            io=io,
            seed=42,
        )

        assert len(engine.state.players) == 6
        assert engine._fsm_state == "setup"

    def test_engine_role_assignment(self):
        """Engine assigns correct number of each role."""
        from core_game.engine import GameEngine
        from core_game import ROLE_REGISTRY

        io = MockIO()
        engine = GameEngine(
            player_names=["Alice", "Bob", "Charlie", "Dave", "Eve", "Frank"],
            role_names=PRESETS["small"],
            io=io,
            seed=42,
        )

        roles = [p.role.name for p in engine.state.players]
        assert roles.count("Werewolf") == 1
        assert roles.count("Seer") == 1
        assert roles.count("Doctor") == 1
        assert roles.count("Villager") == 3

    def test_engine_role_shuffle(self):
        """Engine shuffles roles for randomness."""
        from core_game.engine import GameEngine

        io1 = MockIO()
        io2 = MockIO()

        names = ["A", "B", "C", "D", "E", "F"]

        e1 = GameEngine(names, role_names=PRESETS["small"], io=io1, seed=1)
        e2 = GameEngine(names, role_names=PRESETS["small"], io=io2, seed=2)

        r1 = [p.role.name for p in e1.state.players]
        r2 = [p.role.name for p in e2.state.players]

        assert r1 != r2

    def test_engine_explicit_roles(self):
        """Can specify explicit role names."""
        from core_game.engine import GameEngine
        from core_game import ROLE_REGISTRY

        io = MockIO()
        roles = ["Werewolf", "Seer", "Villager", "Villager", "Villager"]
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E"],
            role_names=roles,
            io=io,
        )

        role_names = [p.role.name for p in engine.state.players]
        assert sorted(role_names) == sorted(roles)

    def test_engine_role_count_mismatch_raises(self):
        """Engine raises if role count doesn't match player count."""
        from core_game.engine import GameEngine

        io = MockIO()
        roles = ["Werewolf", "Seer"]

        with pytest.raises(ValueError, match="must match player count"):
            GameEngine(
                player_names=["A", "B", "C", "D", "E"],
                role_names=roles,
                io=io,
            )

    def test_engine_requires_explicit_role_names(self):
        """Engine requires explicit role_names, no auto-preset selection."""
        from core_game.engine import GameEngine
        import pytest

        io = MockIO()
        with pytest.raises(TypeError):
            GameEngine(
                player_names=["A", "B", "C", "D", "E", "F"],
                io=io,
            )

    def test_engine_player_links(self):
        """Players have their role.player reference set."""
        from core_game.engine import GameEngine

        io = MockIO()
        engine = GameEngine(
            player_names=["Alice", "Bob", "Charlie", "Dave", "Eve", "Frank"],
            role_names=PRESETS["small"],
            io=io,
        )

        for p in engine.state.players:
            assert p.role.player is p


class TestEngineFSM:
    """Test engine Finite State Machine transitions."""

    def test_initial_state(self):
        """Engine starts in 'setup' state."""
        from core_game.engine import GameEngine

        io = MockIO()
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_names=PRESETS["small"],
            io=io,
        )

        assert engine._fsm_state == "setup"

    def test_begin_game_exists_and_callable(self):
        """begin_game trigger exists and can be called."""
        from core_game.engine import GameEngine

        io = MockIO()
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_names=PRESETS["small"],
            io=io,
        )

        assert hasattr(engine, 'begin_game')
        assert callable(engine.begin_game)

        engine.begin_game()

        assert engine._fsm_state == "night_start"

    def test_start_night_exists_and_callable(self):
        """start_night trigger exists and can be called."""
        from core_game.engine import GameEngine

        io = MockIO()
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_names=PRESETS["small"],
            io=io,
        )

        engine.begin_game()
        engine.start_night()

        assert engine._fsm_state == "night_actions"

    def test_resolve_exists_and_callable(self):
        """resolve trigger exists and can be called."""
        from core_game.engine import GameEngine

        io = MockIO()
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_names=PRESETS["small"],
            io=io,
        )

        engine.begin_game()
        engine.start_night()
        engine.resolve()

        assert engine._fsm_state == "resolve_night"

    def test_dawn_exists_and_callable(self):
        """dawn trigger exists and can be called."""
        from core_game.engine import GameEngine

        io = MockIO()
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_names=PRESETS["small"],
            io=io,
        )

        engine.begin_game()
        engine.start_night()
        engine.resolve()
        engine.dawn()

        assert engine._fsm_state == "day_start"

    def test_open_day_exists_and_callable(self):
        """open_day trigger exists and can be called."""
        from core_game.engine import GameEngine

        io = MockIO()
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_names=PRESETS["small"],
            io=io,
        )

        engine.begin_game()
        engine.start_night()
        engine.resolve()
        engine.dawn()
        engine.open_day()

        assert engine._fsm_state == "discussion"

    def test_call_vote_exists_and_callable(self):
        """call_vote trigger exists and can be called."""
        from core_game.engine import GameEngine

        io = MockIO()
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_names=PRESETS["small"],
            io=io,
        )

        engine.begin_game()
        engine.start_night()
        engine.resolve()
        engine.dawn()
        engine.open_day()
        engine.call_vote()

        assert engine._fsm_state == "vote"

    def test_tally_exists_and_callable(self):
        """tally trigger exists and can be called."""
        from core_game.engine import GameEngine

        io = MockIO()
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_names=PRESETS["small"],
            io=io,
        )

        engine.begin_game()
        engine.start_night()
        engine.resolve()
        engine.dawn()
        engine.open_day()
        engine.call_vote()
        engine.tally()

        assert engine._fsm_state == "resolve_day"


class TestEngineGuards:
    """Test FSM guard conditions."""

    def test_game_continues_when_game_not_over(self):
        """game_continues returns True when no winner."""
        from core_game.engine import GameEngine

        io = MockIO()
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_names=PRESETS["small"],
            io=io,
        )

        assert engine.game_continues() is True

    def test_game_is_over_when_winner_set(self):
        """game_is_over returns True when winner is set."""
        from core_game.engine import GameEngine

        io = MockIO()
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_names=PRESETS["small"],
            io=io,
        )
        engine.state.winner = "village"

        assert engine.game_is_over() is True

    def test_next_round_fails_when_game_over(self):
        """next_round doesn't transition when game is over."""
        from core_game.engine import GameEngine

        io = MockIO()
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_names=PRESETS["small"],
            io=io,
        )

        engine.begin_game()
        engine.state.winner = "village"

        original_state = engine._fsm_state
        engine.next_round()

        assert engine._fsm_state == original_state


class TestEngineWinConditions:
    """Test win condition detection."""

    def test_village_wins_when_no_werewolves(self):
        """Village wins when all werewolves eliminated."""
        from core_game.engine import GameEngine

        io = MockIO()
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E"],
            role_names=["Villager", "Villager", "Villager", "Villager", "Seer"],
            io=io,
        )

        for p in engine.state.players:
            if p.role.name == "Seer":
                p.alive = False

        engine.state.check_win_conditions()

        assert engine.state.winner == "village"

    def test_werewolves_win_when_equal_count(self):
        """Werewolves win when count equals village count."""
        from core_game.engine import GameEngine

        io = MockIO()
        engine = GameEngine(
            player_names=["Wolf1", "Wolf2", "Vill"],
            role_names=["Werewolf", "Werewolf", "Villager"],
            io=io,
        )

        engine.state.players[2].alive = False

        engine.state.check_win_conditions()

        assert engine.state.winner == "werewolf"

    def test_no_winner_when_balanced(self):
        """No winner when werewolves exist but are outnumbered."""
        from core_game.engine import GameEngine

        io = MockIO()
        engine = GameEngine(
            player_names=["Wolf", "V1", "V2", "V3"],
            role_names=["Werewolf", "Villager", "Villager", "Villager"],
            io=io,
        )

        engine.state.check_win_conditions()

        assert engine.state.winner is None


class TestEngineDeath:
    """Test player death mechanics."""

    def test_kill_player_marks_dead(self):
        """_kill_player marks player as not alive."""
        from core_game.engine import GameEngine

        io = MockIO()
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_names=PRESETS["small"],
            io=io,
        )

        player = engine.state.players[0]
        engine._kill_player(player, cause="test")

        assert player.alive is False

    def test_kill_player_already_dead_ignores(self):
        """_kill_player ignores already dead player."""
        from core_game.engine import GameEngine

        io = MockIO()
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_names=PRESETS["small"],
            io=io,
        )

        player = engine.state.players[0]
        player.alive = False

        original_state = engine._fsm_state
        engine._kill_player(player, cause="test")

        assert engine._fsm_state == original_state

    def test_lover_dies_with_partner(self):
        """When a lover dies, their partner dies too."""
        from core_game.engine import GameEngine

        io = MockIO()
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_names=PRESETS["small"],
            io=io,
        )

        p1 = engine.state.players[0]
        p2 = engine.state.players[1]
        engine.state.link_lovers(p1, p2)

        engine._kill_player(p1, cause="vote")

        assert p1.alive is False
        assert p2.alive is False

    def test_log_on_death(self):
        """Death is logged to event log."""
        from core_game.engine import GameEngine

        io = MockIO()
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_names=PRESETS["small"],
            io=io,
        )
        engine.state.round_number = 1
        engine.state.phase = "resolve_night"

        player = engine.state.players[0]
        engine._kill_player(player, cause="wolf_kill")

        assert any("died from wolf_kill" in log for log in engine.state.event_log)


class TestGameEvents:
    """Test GameEvents callbacks."""

    def test_events_on_night_resolved(self):
        """on_night_resolved is called when night actions complete."""
        from core_game.engine import GameEngine
        from unittest.mock import MagicMock

        events = MagicMock()

        io = MockIO()
        io.vote_tally = {}

        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_names=PRESETS["small"],
            io=io,
            events=events,
        )

        engine.state.winner = "village"

        events.on_night_resolved.assert_not_called()

    def test_events_on_player_eliminated(self):
        """on_player_eliminated is called when player dies."""
        from core_game.engine import GameEngine
        from unittest.mock import MagicMock

        events = MagicMock()

        io = MockIO()
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_names=PRESETS["small"],
            io=io,
            events=events,
        )

        player = engine.state.players[0]
        engine._kill_player(player, cause="test")

        events.on_player_eliminated.assert_called_with(player, "test")

    def test_events_on_game_over(self):
        """on_game_over is called when game ends."""
        from core_game.engine import GameEngine
        from unittest.mock import MagicMock

        events = MagicMock()

        io = MockIO()
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_names=PRESETS["small"],
            io=io,
            events=events,
        )

        engine.state.winner = "village"
        engine._game_over_phase()

        events.on_game_over.assert_called_with("village")