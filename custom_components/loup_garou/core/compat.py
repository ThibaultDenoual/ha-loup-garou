"""
compat.py — Compatibility shim between existing engine and core_game.

This module provides utilities for migrating from the current implementation
to the new core_game module. It is optional and the existing implementation
remains the default.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..core.adapter import AsyncGameAdapter


def create_core_game_adapter(
    hass: "HomeAssistant",
    config_entry_id: str,
) -> "AsyncGameAdapter":
    """
    Create a new-style game adapter using core_game.
    
    This can be used as an alternative to the existing GameEngine.
    Currently returns NotImplementedError - needs transitions package.
    
    Args:
        hass: Home Assistant instance
        config_entry_id: Configuration entry ID
        
    Returns:
        AsyncGameAdapter instance
        
    Raises:
        NotImplementedError: If transitions package not available
    """
    try:
        from ..core.adapter import AsyncGameAdapter as Adapter
        return Adapter(hass, config_entry_id)
    except ImportError as e:
        raise NotImplementedError(
            "core_game adapter requires the 'transitions' package. "
            "Install with: pip install transitions"
        ) from e


def is_core_game_available() -> bool:
    """Check if core_game can be loaded."""
    try:
        from ..core_game import GameEngine
        return True
    except ImportError:
        return False


USE_CORE_GAME = False  # Set to True to enable core_game migration