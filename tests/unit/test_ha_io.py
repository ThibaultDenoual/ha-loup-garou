"""Tests for core_game/io_adapters/ha_io.py"""
from __future__ import annotations

import pytest

from custom_components.loup_garou.core_game.io_adapters.ha_io import (
    HomeAssistantIO,
    MockIO,
    IOOperation,
    AnnounceOp,
    PrivateOp,
    ChooseTargetOp,
    ChooseMultipleOp,
    YesNoOp,
    GetVotesOp,
    PauseOp,
    SeparatorOp,
    SyncToAsyncIOBridge,
)


class TestIOOperation:
    def test_io_operation_base(self):
        op = IOOperation()
        assert op is not None


class TestAnnounceOp:
    def test_announce_op_fields(self):
        op = AnnounceOp(message="test")
        assert op.message == "test"


class TestPrivateOp:
    def test_private_op_fields(self):
        mock_player = type("MockPlayer", (), {"name": "Alice"})()
        op = PrivateOp(player=mock_player, message="hello")
        assert op.player.name == "Alice"
        assert op.message == "hello"


class TestChooseTargetOp:
    def test_choose_target_op_defaults(self):
        op = ChooseTargetOp()
        assert op.result is None
        assert op.completed is False


class TestChooseMultipleOp:
    def test_choose_multiple_op_defaults(self):
        op = ChooseMultipleOp()
        assert op.min_choices == 1
        assert op.max_choices == 1
        assert op.result == []


class TestYesNoOp:
    def test_yes_no_op_defaults(self):
        op = YesNoOp()
        assert op.result is None
        assert op.completed is False


class TestGetVotesOp:
    def test_get_votes_op_defaults(self):
        op = GetVotesOp()
        assert op.result == {}


class TestPauseOp:
    def test_pause_op(self):
        op = PauseOp(prompt="wait")
        assert op.prompt == "wait"


class TestSeparatorOp:
    def test_separator_op(self):
        op = SeparatorOp(title="Night")
        assert op.title == "Night"


class TestHomeAssistantIO:
    def test_init(self):
        io = HomeAssistantIO()
        assert io.pending_operations == []
        assert io._current_choice_op is None

    def test_announce(self):
        io = HomeAssistantIO()
        io.announce("Hello")
        assert len(io.pending_operations) == 1
        assert isinstance(io.pending_operations[0], AnnounceOp)
        assert io.pending_operations[0].message == "Hello"

    def test_private(self):
        io = HomeAssistantIO()
        mock_player = type("MockPlayer", (), {"name": "Bob"})()
        io.private(mock_player, "Secret")
        assert len(io.pending_operations) == 1
        assert isinstance(io.pending_operations[0], PrivateOp)

    def test_choose_target(self):
        io = HomeAssistantIO()
        mock_actor = type("MockPlayer", (), {"name": "Actor"})()
        mock_candidates = [type("MockP", (), {"name": "A"})(), type("MockP", (), {"name": "B"})()]
        result = io.choose_target(mock_actor, mock_candidates, "Choose")
        assert result.name == "A"
        assert len(io.pending_operations) == 1

    def test_choose_target_empty_candidates(self):
        io = HomeAssistantIO()
        mock_actor = type("MockPlayer", (), {"name": "Actor"})()
        result = io.choose_target(mock_actor, [], "Choose")
        assert result is None

    def test_choose_multiple(self):
        io = HomeAssistantIO()
        mock_actor = type("MockPlayer", (), {"name": "Actor"})()
        mock_candidates = [type("MockP", (), {"name": "A"})()]
        result = io.choose_multiple(mock_actor, mock_candidates, "Pick", min_choices=1, max_choices=2)
        assert len(result) == 1

    def test_yes_no(self):
        io = HomeAssistantIO()
        mock_actor = type("MockPlayer", (), {"name": "Actor"})()
        result = io.yes_no(mock_actor, "Continue?")
        assert result is False
        assert len(io.pending_operations) == 1

    def test_get_votes(self):
        io = HomeAssistantIO()
        mock_voters = []
        mock_candidates = []
        result = io.get_votes(mock_voters, mock_candidates)
        assert result == {}
        assert len(io.pending_operations) == 1

    def test_pause(self):
        io = HomeAssistantIO()
        io.pause("wait")
        assert len(io.pending_operations) == 1

    def test_separator(self):
        io = HomeAssistantIO()
        io.separator("Day")
        assert len(io.pending_operations) == 1

    def test_get_pending_clears(self):
        io = HomeAssistantIO()
        io.announce("A")
        io.announce("B")
        ops = io.get_pending()
        assert len(ops) == 2
        assert len(io.pending_operations) == 0

    def test_clear(self):
        io = HomeAssistantIO()
        io.announce("A")
        io.clear()
        assert len(io.pending_operations) == 0


class TestSyncToAsyncIOBridge:
    def test_init(self):
        ha_io = HomeAssistantIO()
        bridge = SyncToAsyncIOBridge(ha_io)
        assert bridge._ha_io is ha_io

    def test_process_pending(self):
        ha_io = HomeAssistantIO()
        ha_io.announce("test")
        bridge = SyncToAsyncIOBridge(ha_io)
        ops = bridge.process_pending()
        assert len(ops) == 1

    def test_resolve_choice(self):
        ha_io = HomeAssistantIO()
        mock_target = type("MockP", (), {"name": "X"})()
        op = ChooseTargetOp(result=None, completed=False)
        bridge = SyncToAsyncIOBridge(ha_io)
        bridge.resolve_choice(op, mock_target)
        assert op.result == mock_target
        assert op.completed is True

    def test_resolve_choice_calls_callback(self):
        ha_io = HomeAssistantIO()
        callback = type("MockCB", (), {"called": False, "__call__": lambda s, o: setattr(s, "called", True)})()
        bridge = SyncToAsyncIOBridge(ha_io, on_choice_callback=callback)
        op = ChooseTargetOp()
        bridge.resolve_choice(op, None)
        assert callback.called is True


class TestMockIO:
    def test_init(self):
        io = MockIO()
        assert io.announced == []
        assert io.choices == []

    def test_announce(self):
        io = MockIO()
        io.announce("hello")
        assert "hello" in io.announced

    def test_private(self):
        io = MockIO()
        mock_player = type("MockP", (), {"name": "P"})()
        io.private(mock_player, "secret")
        assert len(io.private_messages) == 1

    def test_choose_target(self):
        io = MockIO()
        actor = type("MockP", (), {"name": "A"})()
        candidates = [type("MockP", (), {"name": "B"})()]
        result = io.choose_target(actor, candidates, "prompt")
        assert result.name == "B"

    def test_choose_multiple(self):
        io = MockIO()
        actor = type("MockP", (), {"name": "A"})()
        candidates = [type("MockP", (), {"name": "B"})()]
        result = io.choose_multiple(actor, candidates, "prompt", min_choices=1, max_choices=1)
        assert len(result) == 1

    def test_yes_no_true(self):
        io = MockIO()
        actor = type("MockP", (), {"name": "A"})()
        result = io.yes_no(actor, "OK?")
        assert result is True

    def test_get_votes(self):
        io = MockIO()
        voters = []
        candidates = [type("MockP", (), {"name": "A"})()]
        result = io.get_votes(voters, candidates)
        assert result == {candidates[0]: 0}

    def test_get_votes_empty(self):
        io = MockIO()
        result = io.get_votes([], [])
        assert result == {}

    def test_pause(self):
        io = MockIO()
        io.pause("wait")

    def test_separator(self):
        io = MockIO()
        io.separator("title")