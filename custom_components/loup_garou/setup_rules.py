"""Rules a new game's players must follow — zero HA imports.

They mirror the setup screen (`www/game/js/views/setup.js`), so a client that
skips the browser checks still cannot start a game the UI would refuse. Each
reason matches a `ui.setup.hint.<reason>` locale key.
"""
from __future__ import annotations

import re

MIN_PLAYERS = 3
MAX_NAME = 20
_BAD_CHARS = re.compile(r"[{}]")


class InvalidSetup(ValueError):
    """The players can't start a game; `reason` says why."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"invalid setup: {reason}")
        self.reason = reason


def check_players(names: list) -> list[str]:
    """Return the trimmed names, or raise InvalidSetup for the first broken rule."""
    if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
        raise TypeError("players must be a list of names")
    names = [n.strip() for n in names]
    if len(names) < MIN_PLAYERS:
        raise InvalidSetup("need_players")
    if any(not n for n in names):
        raise InvalidSetup("empty_name")
    if any(len(n) > MAX_NAME for n in names):
        raise InvalidSetup("long_name")
    if any(_BAD_CHARS.search(n) for n in names):
        raise InvalidSetup("bad_chars")
    if len({n.casefold() for n in names}) != len(names):
        raise InvalidSetup("duplicate")
    return names
