"""Public roles: the trade every villager is known by — zero HA imports.

Each player gets one when the game starts, on top of their secret role. The
narrator names players by it ("the victim is… the Baker"), so every line can
be pre-recorded: player names never need to be spoken.

Past ten players, the trades repeat as apprentices ("the Baker's apprentice"),
which caps a game at twenty players. Locale keys: `public.<id>.name` for the
screen and `public.<id>.spoken` (with its article) for the narration.
"""
from __future__ import annotations

import random

TRADES: tuple[str, ...] = (
    "baker", "blacksmith", "miller", "shepherd", "innkeeper",
    "weaver", "fisher", "woodcutter", "herbalist", "potter",
)
APPRENTICE = "_apprentice"
MAX_PLAYERS = 2 * len(TRADES)

ALL: tuple[str, ...] = TRADES + tuple(t + APPRENTICE for t in TRADES)


def deal(count: int, rng: random.Random | None = None) -> list[str]:
    """One distinct public role per player, in random order.

    Apprentices only appear past ten players, and only for trades in play.
    """
    if not 0 <= count <= MAX_PLAYERS:
        raise ValueError(f"public roles cover 0 to {MAX_PLAYERS} players, not {count}")
    rng = rng or random.Random()
    trades = rng.sample(TRADES, len(TRADES))
    roles = trades[:count] + [t + APPRENTICE for t in trades[: max(0, count - len(TRADES))]]
    rng.shuffle(roles)
    return roles
