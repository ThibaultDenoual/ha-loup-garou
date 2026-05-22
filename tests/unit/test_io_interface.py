"""Tests for core_game/io_interface.py"""
from __future__ import annotations

import pytest
from abc import ABC

from custom_components.loup_garou.core_game.io_interface import IOInterface, ConsoleIO


class TestIOInterface:
    def test_is_abstract(self):
        assert issubclass(IOInterface, ABC)

    def test_class_has_abstract_methods(self):
        methods = ["announce", "private", "choose_target", "choose_multiple",
                   "yes_no", "get_votes", "pause", "separator"]
        for m in methods:
            assert hasattr(IOInterface, m)


class TestConsoleIOAnnounce:
    def test_announce_prints_message(self, capsys):
        io = ConsoleIO()
        io.announce("Hello World")
        captured = capsys.readouterr()
        assert "Hello World" in captured.out


class TestConsoleIOSeparator:
    def test_separator_with_title(self, capsys):
        io = ConsoleIO()
        io.separator("Test Title")
        captured = capsys.readouterr()
        assert "Test Title" in captured.out

    def test_separator_without_title(self, capsys):
        io = ConsoleIO()
        io.separator("")
        captured = capsys.readouterr()
        assert captured.out  # prints dashes