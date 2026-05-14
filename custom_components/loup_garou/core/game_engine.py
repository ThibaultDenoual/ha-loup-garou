"""
game_engine.py — Public API entry point for the Werewolf game engine.

This module re-exports the AsyncGameAdapter from adapter.py for backward
compatibility with existing code that imports from this module.
"""

from __future__ import annotations

from .adapter import AsyncGameAdapter

GameEngine = AsyncGameAdapter

__all__ = ["GameEngine", "AsyncGameAdapter"]