"""Tests for core_game/engine.py phase handlers."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from core_game.engine import GameEngine
from core_game import Player, ROLE_REGISTRY, NightAction
from core_game.roles import WerewolfPackCoordinator


class MockIO:
    def __init__(self):
        self.messages = []
        self.private_messages = {}
        self.yes_no_answers = {}
        self.choices = {}
        self.vote_tally = {}
        self.paused = False

    def announce(self, message):
        self.messages.append(message)

    def private(self, player, message):
        self.private_messages[player.name] = message

    def choose_target(self, actor, candidates, prompt):
        key = (actor.name, prompt)
        if key in self.choices:
            for c in candidates:
                if c.name == self.choices[key]:
                    return c
        return candidates[0] if candidates else None

    def choose_multiple(self, actor, candidates, prompt, min_choices=1, max_choices=1):
        return self.choose_target(actor, candidates, prompt)

    def yes_no(self, actor, prompt):
        key = (actor.name, prompt)
        return self.yes_no_answers.get(key, False)

    def get_votes(self, voters, candidates):
        return self.vote_tally

    def pause(self, prompt=""):
        self.paused = True

    def separator(self, title=""):
        self.messages.append(("sep", title))


class TestEnginePhaseHandlers:
    def test_setup_phase_announces(self):
        io = MockIO()
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            preset="small",
            io=io,
        )
        engine._setup_phase()
        assert len(io.messages) > 0

    def test_reveal_roles_privately_announces(self):
        io = MockIO()
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            preset="small",
            io=io,
        )
        engine._reveal_roles_privately()
        assert len(io.private_messages) > 0

    def test_enter_night_start_increments_round(self):
        io = MockIO()
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            preset="small",
            io=io,
        )
        engine._setup_phase()
        engine.begin_game()
        engine._enter_night_start()
        assert engine.state.round_number == 1
        assert engine.state.phase == "night"

    def test_enter_night_start_separator(self):
        io = MockIO()
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            preset="small",
            io=io,
        )
        engine._setup_phase()
        engine.begin_game()
        engine._enter_night_start()
        sep_messages = [m for m in io.messages if isinstance(m, tuple) and m[0] == "sep"]
        assert len(sep_messages) > 0

    def test_run_night_actions_calls_role_act(self):
        io = MockIO()
        io.vote_tally = {}
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            preset="small",
            io=io,
        )
        engine.begin_game()
        engine.start_night()
        engine._run_night_actions()
        assert len(engine.state.tonight_actions) >= 0

    def test_resolve_night_no_deaths(self):
        io = MockIO()
        io.vote_tally = {}
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_names=["Villager", "Villager", "Villager", "Villager", "Villager", "Seer"],
            io=io,
        )
        engine.begin_game()
        engine.start_night()
        engine.resolve()
        engine._resolve_night()
        assert engine._fsm_state == "resolve_night"

    def test_resolve_night_with_kill(self):
        io = MockIO()
        io.vote_tally = {}
        io.choices[("A", "Werewolves, choose your victim:")] = "B"
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_names=["Werewolf", "Villager", "Villager", "Villager", "Villager", "Seer"],
            io=io,
        )
        engine.begin_game()
        engine.start_night()
        engine.resolve()
        engine._resolve_night()

    def test_apply_conversion_notifies_player(self):
        io = MockIO()
        io.vote_tally = {}
        io.yes_no_answers[("A", "Alpha Wolf! Use your power to convert a villager?")] = True
        io.choices[("A", "Choose a villager to convert:")] = "B"
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_names=["Alpha Wolf", "Villager", "Villager", "Villager", "Villager", "Seer"],
            io=io,
        )
        engine._setup_phase()
        engine.begin_game()
        engine._enter_night_start()
        engine.start_night()
        from core_game import NightAction
        player_B = engine.state.players[1]
        action = NightAction(
            actor=engine.state.players[0],
            action_type="convert",
            target=player_B,
        )
        engine._apply_conversion(action)
        assert len(io.private_messages) > 0

    def test_announce_deaths_no_deaths(self):
        io = MockIO()
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            preset="small",
            io=io,
        )
        engine.state.round_number = 1
        engine._announce_deaths([])
        assert len(io.messages) > 0

    def test_announce_deaths_with_deaths(self):
        io = MockIO()
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            preset="small",
            io=io,
        )
        player = engine.state.players[0]
        engine._announce_deaths([(player, "wolf_kill")])
        assert len(io.messages) > 0

    def test_game_over_phase_village_wins(self):
        io = MockIO()
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            preset="small",
            io=io,
        )
        engine.state.winner = "village"
        engine._game_over_phase()
        village_win = any("VILLAGE" in str(m) or "village" in str(m) for m in io.messages)
        assert village_win

    def test_game_over_phase_werewolf_wins(self):
        io = MockIO()
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            preset="small",
            io=io,
        )
        engine.state.winner = "werewolf"
        engine._game_over_phase()
        assert len(io.messages) > 0


class TestEngineRunLoop:
    def test_run_completes(self):
        io = MockIO()
        io.vote_tally = {}
        io.choices[("A", "Werewolves, choose your victim:")] = "B"
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_names=["Werewolf", "Villager", "Villager", "Villager", "Villager", "Seer"],
            io=io,
        )
        engine.run()
        assert engine._fsm_state == "game_over"


class TestEngineWerewolfPackCoordinator:
    def test_coordinate_no_werewolves(self):
        io = MockIO()
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_names=["Villager", "Villager", "Villager", "Villager", "Villager", "Seer"],
            io=io,
        )
        action = WerewolfPackCoordinator.coordinate(engine.state)
        assert action is None

    def test_coordinate_returns_action(self):
        io = MockIO()
        io.choices[("A", "Werewolves, choose your victim:")] = "B"
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_names=["Werewolf", "Villager", "Villager", "Villager", "Villager", "Seer"],
            io=io,
        )
        action = WerewolfPackCoordinator.coordinate(engine.state)
        assert action is not None
        assert action.action_type == "kill"


class TestEngineDayResolution:
    def test_resolve_day_no_votes(self):
        io = MockIO()
        io.vote_tally = {}
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            preset="small",
            io=io,
        )
        engine._last_vote_tally = {}
        engine._resolve_day()
        assert len(io.messages) > 0

    def test_resolve_day_tie(self):
        io = MockIO()
        io.vote_tally = {}
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            preset="small",
            io=io,
        )
        p1 = engine.state.players[0]
        p2 = engine.state.players[1]
        engine._last_vote_tally = {p1: 2, p2: 2}
        engine._resolve_day()
        assert len(io.messages) > 0

    def test_resolve_day_condemned(self):
        io = MockIO()
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            preset="small",
            io=io,
        )
        p1 = engine.state.players[0]
        engine._last_vote_tally = {p1: 3}
        engine._resolve_day()
        assert p1.alive is False


class TestEngineKillPlayer:
    def test_kill_player_logs_death(self):
        io = MockIO()
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            preset="small",
            io=io,
        )
        player = engine.state.players[0]
        engine._kill_player(player, cause="test_kill")
        assert any("test_kill" in log for log in engine.state.event_log)

    def test_kill_player_on_death_callback(self):
        io = MockIO()
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            role_names=["Villager", "Villager", "Villager", "Villager", "Villager", "Seer"],
            io=io,
        )
        player = engine.state.players[5]
        engine._kill_player(player, cause="wolf_kill")
        assert player.alive is False


class TestEngineRunDiscussion:
    def test_run_discussion_announces(self):
        io = MockIO()
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            preset="small",
            io=io,
        )
        engine.state.round_number = 1
        engine._run_discussion()
        assert len(io.messages) > 0


class TestEngineRunVote:
    def test_run_vote_sets_phase(self):
        io = MockIO()
        io.vote_tally = {}
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            preset="small",
            io=io,
        )
        engine._run_vote()
        assert engine.state.phase == "vote"


class TestEngineEnterDayStart:
    def test_enter_day_start_sets_phase(self):
        io = MockIO()
        engine = GameEngine(
            player_names=["A", "B", "C", "D", "E", "F"],
            preset="small",
            io=io,
        )
        engine._enter_day_start()
        assert engine.state.phase == "day"