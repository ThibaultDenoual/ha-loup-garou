"""
core_game — Standalone, HA-agnostic Werewolf game engine.

This module contains the pure game logic separated from Home Assistant.
It can be used independently for testing or future non-HA deployments.

Exports:
    GameEngine - Main game orchestrator (requires transitions package)
    GameState  - Game state container
    Player     - Player data class
    Role       - Base role class
    IOInterface - Abstract IO interface
    ConsoleIO  - CLI implementation
    GameEvents - Abstract events for external systems
    ROLE_REGISTRY - Map of role name -> role class
    PRESETS    - Predefined role configurations
"""

from .game_state import GameState, Player
from .io_interface import IOInterface, ConsoleIO
from .roles import (
    Role,
    NightAction,
    ROLE_REGISTRY,
    PRESETS,
    Villager,
    Seer, 
    Doctor,
    Bodyguard,
    Hunter,
    Witch,
    Cupid,
    Werewolf,
    AlphaWolf,
    Minion,
    SerialKiller,
    Jester,
    WerewolfPackCoordinator,
)

# Lazy-load engine (requires transitions package)
GameEngine = None
GameEvents = None

def _load_engine():
    global GameEngine, GameEvents
    if GameEngine is None:
        try:
            from .engine import GameEngine as _GE, GameEvents as _GTE
            GameEngine = _GE
            GameEvents = _GTE
        except ImportError:
            pass

def __getattr__(name):
    if name in ("GameEngine", "GameEvents"):
        _load_engine()
        return globals().get(name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "GameEngine",
    "GameState",
    "Player",
    "Role",
    "NightAction",
    "IOInterface",
    "ConsoleIO",
    "GameEvents",
    "ROLE_REGISTRY",
    "PRESETS",
    "WerewolfPackCoordinator",
    # Roles
    "Villager",
    "Seer", 
    "Doctor",
    "Bodyguard",
    "Hunter",
    "Witch",
    "Cupid",
    "Werewolf",
    "AlphaWolf",
    "Minion",
    "SerialKiller",
    "Jester",
]

__version__ = "1.0.0"