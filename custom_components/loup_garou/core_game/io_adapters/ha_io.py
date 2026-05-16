"""
io_adapters/ha_io.py — Home Assistant IO implementation.

This IO implementation records all operations for the adapter to process
asynchronously via WebSocket. It doesn't block - it stores pending operations
that the adapter will handle.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..game_state import Player

from ..io_interface import IOInterface


@dataclass
class IOOperation:
    """Base class for IO operations to be processed by the adapter."""
    pass


@dataclass
class AnnounceOp(IOOperation):
    message: str = ""


@dataclass
class PrivateOp(IOOperation):
    player: "Player" = None
    message: str = ""


@dataclass
class ChooseTargetOp(IOOperation):
    actor: "Player" = None
    candidates: list["Player"] = field(default_factory=list)
    prompt: str = ""
    result: Optional["Player"] = None
    completed: bool = False


@dataclass
class ChooseMultipleOp(IOOperation):
    actor: "Player" = None
    candidates: list["Player"] = field(default_factory=list)
    prompt: str = ""
    min_choices: int = 1
    max_choices: int = 1
    result: list["Player"] = field(default_factory=list)
    completed: bool = False


@dataclass
class YesNoOp(IOOperation):
    actor: "Player" = None
    prompt: str = ""
    result: Optional[bool] = None
    completed: bool = False


@dataclass
class GetVotesOp(IOOperation):
    voters: list["Player"] = field(default_factory=list)
    candidates: list["Player"] = field(default_factory=list)
    result: dict = field(default_factory=dict)
    completed: bool = False


@dataclass
class PauseOp(IOOperation):
    prompt: str = ""


@dataclass
class SeparatorOp(IOOperation):
    title: str = ""


class HomeAssistantIO(IOInterface):
    """
    HA-compatible IO implementation.

    Instead of blocking, all operations are recorded and can be processed
    asynchronously by the adapter through WebSocket.
    """

    def __init__(self, tts_controller=None, light_controller=None, hass=None):
        self.pending_operations: list[IOOperation] = []
        self._current_choice_op: Optional[ChooseTargetOp] = None
        self._tts = tts_controller
        self._lights = light_controller
        self._hass = hass

    def set_controllers(self, tts_controller, light_controller) -> None:
        """Set or update TTS and Light controllers after initialization."""
        self._tts = tts_controller
        self._lights = light_controller

    def set_hass(self, hass) -> None:
        """Set the Home Assistant instance for async scheduling."""
        self._hass = hass

    def announce(self, message: str) -> None:
        self.pending_operations.append(AnnounceOp(message=message))

    def private(self, player: "Player", message: str) -> None:
        self.pending_operations.append(PrivateOp(player=player, message=message))

    def choose_target(
        self, actor: "Player", candidates: list["Player"], prompt: str
    ) -> "Player":
        op = ChooseTargetOp(actor=actor, candidates=candidates, prompt=prompt)
        self.pending_operations.append(op)
        return candidates[0] if candidates else None

    def choose_multiple(
        self, actor: "Player", candidates: list["Player"],
        prompt: str, min_choices: int = 1, max_choices: int = 1
    ) -> list["Player"]:
        op = ChooseMultipleOp(
            actor=actor, candidates=candidates, prompt=prompt,
            min_choices=min_choices, max_choices=max_choices
        )
        self.pending_operations.append(op)
        return candidates[:min_choices] if candidates else []

    def yes_no(self, actor: "Player", prompt: str) -> bool:
        op = YesNoOp(actor=actor, prompt=prompt)
        self.pending_operations.append(op)
        return False

    def get_votes(self, voters: list["Player"], candidates: list["Player"]) -> dict["Player", int]:
        op = GetVotesOp(voters=voters, candidates=candidates)
        self.pending_operations.append(op)
        return {}

    def pause(self, prompt: str = "") -> None:
        self.pending_operations.append(PauseOp(prompt=prompt))

    def separator(self, title: str = "") -> None:
        self.pending_operations.append(SeparatorOp(title=title))

    def speak(self, message: str) -> None:
        if self._tts and self._hass:
            self._hass.async_create_task(self._tts.async_speak(message))

    def set_scene(self, scene_key: str) -> None:
        if self._lights and self._hass:
            self._hass.async_create_task(self._lights.async_set_scene(scene_key))

    def get_pending(self) -> list[IOOperation]:
        """Return and clear all pending operations."""
        ops = self.pending_operations.copy()
        self.pending_operations.clear()
        return ops

    def clear(self) -> None:
        """Clear all pending operations."""
        self.pending_operations.clear()


class SyncToAsyncIOBridge:
    """
    Bridge that allows the sync game engine to work with async HA code.

    For simple operations (announce, private, separator), it processes them
    immediately. For choice operations, it returns default values that the
    adapter will override when the actual async response comes back.
    """

    def __init__(self, ha_io: HomeAssistantIO, on_choice_callback=None):
        self._ha_io = ha_io
        self._on_choice = on_choice_callback

    def process_pending(self) -> list[IOOperation]:
        """Get pending operations from the IO and process them."""
        return self._ha_io.get_pending()

    def resolve_choice(self, op: ChooseTargetOp, target: "Player") -> None:
        """Resolve a pending choice operation."""
        op.result = target
        op.completed = True
        if self._on_choice:
            self._on_choice(op)


class MockIO(IOInterface):
    """
    Minimal mock IO for testing without HA dependencies.
    """

    def __init__(self):
        self.announced: list[str] = []
        self.private_messages: list[tuple] = []
        self.choices: list = []

    def announce(self, message: str) -> None:
        self.announced.append(message)

    def private(self, player: "Player", message: str) -> None:
        self.private_messages.append((player, message))

    def choose_target(self, actor: "Player", candidates: list["Player"], prompt: str) -> "Player":
        return candidates[0] if candidates else None

    def choose_multiple(self, actor: "Player", candidates: list["Player"],
                        prompt: str, min_choices: int = 1, max_choices: int = 1) -> list["Player"]:
        return candidates[:min_choices] if candidates else []

    def yes_no(self, actor: "Player", prompt: str) -> bool:
        return True

    def get_votes(self, voters: list["Player"], candidates: list["Player"]) -> dict["Player", int]:
        return {candidates[0]: len(voters)} if candidates else {}

    def pause(self, prompt: str = "") -> None:
        pass

    def separator(self, title: str = "") -> None:
        pass

    def speak(self, message: str) -> None:
        pass

    def set_scene(self, scene_key: str) -> None:
        pass