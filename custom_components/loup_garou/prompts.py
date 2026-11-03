"""The one thing the game is waiting for, and what counts as a legal answer."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class IllegalAnswer(ValueError):
    """The answer does not fit the prompt's picks."""


def pick(options: list[str], *counts: int) -> dict:
    """A named choice: which options exist and how many of them may be chosen."""
    return {"options": list(options), "counts": list(counts)}


@dataclass(frozen=True)
class Prompt:
    id: str
    kind: str
    role: str | None = None
    actor: str | None = None   # player who should be holding the phone
    picks: dict[str, dict] = field(default_factory=dict)
    info: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "role": self.role,
            "actor": self.actor,
            "picks": self.picks,
            "info": self.info,
        }

    def validate(self, answer: Any) -> dict:
        """Return the answer as roles read it, or raise IllegalAnswer.

        A pick of at most one option becomes a value or None; any other a list.
        """
        if not isinstance(answer, dict):
            raise IllegalAnswer("answer must be an object")
        unknown = set(answer) - set(self.picks)
        if unknown:
            raise IllegalAnswer(f"unknown picks: {sorted(unknown)}")

        action: dict = {}
        for name, spec in self.picks.items():
            chosen = _as_list(answer.get(name))
            if len(chosen) not in spec["counts"]:
                raise IllegalAnswer(f"wrong number of choices for {name}")
            if len(set(chosen)) != len(chosen) or not set(chosen) <= set(spec["options"]):
                raise IllegalAnswer(f"illegal choice for {name}")
            if max(spec["counts"]) <= 1:
                action[name] = chosen[0] if chosen else None
            else:
                action[name] = chosen
        return action

    def fallback_answer(self) -> dict:
        """The smallest legal answer, for automated players."""
        answer: dict = {}
        for name, spec in self.picks.items():
            answer[name] = spec["options"][:min(spec["counts"])]
        return answer


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        if not all(isinstance(v, str) for v in value):
            raise IllegalAnswer("choices must be strings")
        return value
    if isinstance(value, str):
        return [value]
    raise IllegalAnswer("choices must be strings")
