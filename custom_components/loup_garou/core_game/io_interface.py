"""
io_interface.py — All user input / output abstraction.

The game engine never calls print() or input() directly.
Swap ConsoleIO for a GUI/web adapter without touching game logic.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .game_state import Player


# ─────────────────────────────────────────────
#  Abstract base
# ─────────────────────────────────────────────

class IOInterface(ABC):
    """Abstract interface for all game input/output."""

    @abstractmethod
    def announce(self, message: str) -> None:
        """Broadcast a message to all players."""

    @abstractmethod
    def private(self, player: "Player", message: str) -> None:
        """Send a message only the given player should see."""

    @abstractmethod
    def choose_target(
        self, actor: "Player", candidates: list["Player"], prompt: str
    ) -> "Player":
        """Ask actor to pick one player from candidates."""

    @abstractmethod
    def choose_multiple(
        self, actor: "Player", candidates: list["Player"],
        prompt: str, min_choices: int = 1, max_choices: int = 1
    ) -> list["Player"]:
        """Ask actor to pick between min and max players."""

    @abstractmethod
    def yes_no(self, actor: "Player", prompt: str) -> bool:
        """Ask actor a yes/no question."""

    @abstractmethod
    def get_votes(self, voters: list["Player"], candidates: list["Player"]) -> dict["Player", int]:
        """Collect elimination votes; returns {candidate: vote_count}."""

    @abstractmethod
    def pause(self, prompt: str = "") -> None:
        """Pause for the player to read; no-op in automated modes."""

    @abstractmethod
    def separator(self, title: str = "") -> None:
        """Print a visual separator with optional title."""


# ─────────────────────────────────────────────
#  Console (CLI) implementation
# ─────────────────────────────────────────────

class ConsoleIO(IOInterface):
    """Terminal implementation for local testing/development."""

    def announce(self, message: str) -> None:
        print(f"\n{message}")

    def private(self, player: "Player", message: str) -> None:
        print(f"\n  [Private → {player.name}] {message}")
        self.pause(f"  (Press Enter when {player.name} has read this...)")

    def _press_enter(self, prompt: str = "  (Press Enter to continue...)"):
        input(prompt)

    def choose_target(
        self, actor: "Player", candidates: list["Player"], prompt: str
    ) -> "Player":
        return self.choose_multiple(actor, candidates, prompt, 1, 1)[0]

    def choose_multiple(
        self, actor: "Player", candidates: list["Player"],
        prompt: str, min_choices: int = 1, max_choices: int = 1
    ) -> list["Player"]:
        while True:
            print(f"\n  {prompt}")
            for i, p in enumerate(candidates, 1):
                print(f"    {i}. {p.name}")
            raw = input(
                f"  Enter number{'s' if max_choices > 1 else ''} "
                f"(1-{len(candidates)}): "
            ).strip()
            try:
                indices = [int(x) - 1 for x in raw.replace(",", " ").split()]
                if not (min_choices <= len(indices) <= max_choices):
                    raise ValueError
                chosen = [candidates[i] for i in indices]
                if len(set(chosen)) != len(chosen):
                    raise ValueError
                return chosen
            except (ValueError, IndexError):
                print(f"  ⚠️  Invalid choice. Pick {min_choices}–{max_choices} number(s).")

    def yes_no(self, actor: "Player", prompt: str) -> bool:
        while True:
            ans = input(f"\n  {prompt} [y/n]: ").strip().lower()
            if ans in ("y", "yes"):
                return True
            if ans in ("n", "no"):
                return False
            print("  ⚠️  Please enter y or n.")

    def get_votes(
        self, voters: list["Player"], candidates: list["Player"]
    ) -> dict["Player", int]:
        tally: dict["Player", int] = {p: 0 for p in candidates}
        print(f"\n  VILLAGE VOTE — Choose someone to eliminate (or 0 to abstain):")
        for i, c in enumerate(candidates, 1):
            print(f"    {i}. {c.name}")

        for voter in voters:
            if voter.silenced:
                print(f"  🔇 {voter.name} is silenced and cannot vote.")
                continue
            while True:
                try:
                    choice = int(input(f"  {voter.name}'s vote (0 to abstain): ").strip())
                    if choice == 0:
                        break
                    if 1 <= choice <= len(candidates):
                        tally[candidates[choice - 1]] += 1
                        break
                    print("  ⚠️  Invalid choice.")
                except ValueError:
                    print("  ⚠️  Enter a number.")
        return tally

    def pause(self, prompt: str = "") -> None:
        input(prompt or "  (Press Enter to continue...)")

    def separator(self, title: str = "") -> None:
        if title:
            pad = max(0, (58 - len(title) - 2) // 2)
            line = "━" * pad + f" {title} " + "━" * pad
            print(f"\n{line[:58]}")
        else:
            print(f"\n{'━' * 58}")