"""Scripted demo games — drive the real engine so the ambience setup can be checked.

No `homeassistant` imports: the runner only calls the public GameEngine API and
lets the engine emit its real events, so lights and TTS behave exactly as they
do in a real game. Nothing here is mocked.

A preset is a declarative timeline: a roster, the action each role submits on
its night turn, and the sequence of phases to walk through. Player names in the
script are resolved to engine player ids at run time, so presets stay readable.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from .const import GameEvent
from .game_engine import GameEngine

_LOGGER = logging.getLogger(__name__)

STEP_NIGHT = "night"
STEP_VOTE = "vote"

StepCallback = Callable[[str], Awaitable[None] | None]


@dataclass(frozen=True)
class DemoStep:
    """One scripted phase of the demo timeline."""

    kind: str
    # voter name -> target name, only used by STEP_VOTE
    votes: dict[str, str] = field(default_factory=dict)
    # role id -> action for this night only, overriding the script-wide defaults.
    # Needed whenever a role must pick a different target on a later night: the
    # engine silently ignores an action aimed at an already-dead player.
    actions: dict[str, dict] | None = None


@dataclass(frozen=True)
class DemoScript:
    """A complete, deterministic fake game."""

    key: str
    players: tuple[tuple[str, str], ...]
    # role id -> action submitted on that role's night turn (names resolved to ids)
    night_actions: dict[str, dict] = field(default_factory=dict)
    # role id -> action submitted when that role's mid-chain interrupt fires
    interrupt_actions: dict[str, dict] = field(default_factory=dict)
    steps: tuple[DemoStep, ...] = ()

    @property
    def names(self) -> list[str]:
        return [name for name, _ in self.players]

    @property
    def role_ids(self) -> list[str]:
        return [role_id for _, role_id in self.players]


# ── Presets ───────────────────────────────────────────────────────────────────

# Preset 1 — smoke test: one night, one vote, village wins. Exercises night
# narration, the seer and werewolf wake/sleep scenes, the day announcement with
# a death, the vote, and the village-win ending.
SMOKE_TEST = DemoScript(
    key="smoke_test",
    players=(
        ("Alice", "villager"),
        ("Bob", "werewolf"),
        ("Carol", "villager"),
        ("Dave", "villager"),
        ("Eve", "seer"),
    ),
    night_actions={
        "seer": {"target": "Bob"},
        "werewolf": {"target": "Alice"},
    },
    # The seer wakes twice per night: once to pick a target, once to acknowledge
    # the revealed result. An empty action is the acknowledgement.
    interrupt_actions={"seer": {}},
    steps=(
        DemoStep(STEP_NIGHT),
        DemoStep(
            STEP_VOTE,
            votes={"Carol": "Bob", "Dave": "Bob", "Eve": "Bob"},
        ),
    ),
)

# Preset 2 — wolves win on parity: the seer finds the wolf but the village keeps
# voting the wrong way. Two nights so the seer wakes twice, then the night kill
# itself tips wolves >= villagers and ends the game before a second vote.
WOLVES_WIN = DemoScript(
    key="wolves_win",
    players=(
        ("Bob", "werewolf"),
        ("Eve", "seer"),
        ("Alice", "villager"),
        ("Carol", "villager"),
        ("Dave", "villager"),
    ),
    night_actions={
        "seer": {"target": "Bob"},
        "werewolf": {"target": "Alice"},
    },
    interrupt_actions={"seer": {}},
    steps=(
        DemoStep(STEP_NIGHT),
        DemoStep(STEP_VOTE, votes={"Carol": "Dave", "Eve": "Dave", "Alice": "Dave"}),
        # Alice is dead by now, so the second kill needs its own target.
        DemoStep(STEP_NIGHT, actions={"werewolf": {"target": "Carol"}}),
    ),
)

# Preset 3 — lovers win. Cupid links *himself* with Alice on night 1, the wolf
# eats the spare villager, and the village votes the wolf out. Only Cupid and
# Alice are left alive, which is Cupid's win condition.
#
# Cupid has to be one of the two lovers: his check requires that no *other*
# player is alive, so as long as he survives as a bystander he blocks the win and
# the villager role claims it instead.
LOVERS_WIN = DemoScript(
    key="lovers_win",
    players=(
        ("Bob", "werewolf"),
        ("Cupid", "cupid"),
        ("Alice", "villager"),
        ("Carol", "villager"),
    ),
    night_actions={
        "cupid": {"lovers": ["Cupid", "Alice"]},
        "werewolf": {"target": "Carol"},
    },
    steps=(
        DemoStep(STEP_NIGHT),
        DemoStep(STEP_VOTE, votes={"Alice": "Bob", "Cupid": "Bob"}),
    ),
)

DEMOS: dict[str, DemoScript] = {
    s.key: s for s in (SMOKE_TEST, WOLVES_WIN, LOVERS_WIN)
}


def list_demos() -> list[dict]:
    """Preset descriptors for the config UI."""
    return [{"key": s.key, "label_key": f"demo.preset.{s.key}"} for s in DEMOS.values()]


# ── Runner ────────────────────────────────────────────────────────────────────


class DemoRunner:
    """Replays a DemoScript against a real GameEngine."""

    def __init__(
        self,
        engine: GameEngine,
        script: DemoScript,
        *,
        action_delay: float = 1.5,
        step_delay: float = 1.0,
        on_step: StepCallback | None = None,
    ) -> None:
        self._engine = engine
        self._script = script
        self._action_delay = action_delay
        self._step_delay = step_delay
        self._on_step = on_step
        self._responders: set[asyncio.Task] = set()
        # Script-wide night actions, narrowed per night by DemoStep.actions.
        self._night_actions = script.night_actions

    @property
    def key(self) -> str:
        return self._script.key

    async def run(self) -> None:
        """Play the script to its end, then reset the engine to the setup phase."""
        self._engine.on(GameEvent.NIGHT_ROLE_WAKE, self._on_night_role_wake)
        try:
            await self._engine.start_game(self._script.names, self._script.role_ids)
            await self._notify("game_started")
            await asyncio.sleep(self._step_delay)

            for step in self._script.steps:
                if step.kind == STEP_NIGHT:
                    if step.actions is not None:
                        self._night_actions = {**self._script.night_actions, **step.actions}
                    await self._notify("night_start")
                    await self._engine.begin_night()
                elif step.kind == STEP_VOTE:
                    await self._engine.begin_vote()
                    await asyncio.sleep(self._step_delay)
                    await self._notify("vote_cast")
                    await self._engine.resolve_vote(self._resolve_votes(step.votes))
                else:
                    _LOGGER.warning("Unknown demo step: %s", step.kind)
                await asyncio.sleep(self._step_delay)

            await self._notify("finished")
        finally:
            self._engine.off(GameEvent.NIGHT_ROLE_WAKE, self._on_night_role_wake)
            self._cancel_responders()
            with contextlib.suppress(asyncio.CancelledError):
                await self._engine.reset()

    def cancel(self) -> None:
        """Stop answering role wakes without waiting for run() to unwind."""
        self._engine.off(GameEvent.NIGHT_ROLE_WAKE, self._on_night_role_wake)
        self._cancel_responders()

    # ── Internals ─────────────────────────────────────────────────────────────

    def _cancel_responders(self) -> None:
        for task in self._responders:
            task.cancel()
        self._responders.clear()

    async def _on_night_role_wake(self, data: dict) -> None:
        """Answer a role's wake with its scripted action.

        The engine emits NIGHT_ROLE_WAKE *before* it creates the future it blocks
        on for a night action (interrupts set theirs up first), so the reply has
        to be deferred to its own task — replying inline would be dropped.
        """
        role_id = str(data.get("role", ""))
        task = asyncio.create_task(self._respond(role_id))
        self._responders.add(task)
        task.add_done_callback(self._responders.discard)

    async def _respond(self, role_id: str) -> None:
        if self._action_delay:
            await asyncio.sleep(self._action_delay)

        # A role can wake twice in one night (target, then result). pending_action_role
        # is only set after the wake event returns, pending_interrupt_role before it.
        if self._engine.pending_interrupt_role == role_id:
            action = self._script.interrupt_actions.get(role_id, {})
            await self._notify("role_action", role_id)
            await self._engine.submit_pending_action(role_id, self._resolve(action))
        elif self._engine.pending_action_role == role_id:
            action = self._night_actions.get(role_id, {})
            await self._notify("role_action", role_id)
            await self._engine.submit_night_action(role_id, self._resolve(action))
        else:
            _LOGGER.warning("Demo: nothing pending for role %s, skipping reply", role_id)

    def _resolve_votes(self, votes: dict[str, str]) -> dict[str, str]:
        ids = self._name_to_id()
        resolved: dict[str, str] = {}
        for voter, target in votes.items():
            if voter not in ids:
                _LOGGER.warning("Demo: unknown voter %r", voter)
                continue
            if target not in ids:
                _LOGGER.warning("Demo: unknown vote target %r", target)
                continue
            resolved[ids[voter]] = ids[target]
        return resolved

    def _resolve(self, action: dict) -> dict:
        """Swap player names for engine player ids, recursively."""
        ids = self._name_to_id()
        return self._walk(action, ids)

    def _walk(self, value: Any, ids: dict[str, str]) -> Any:
        if isinstance(value, str):
            return ids.get(value, value)
        if isinstance(value, list):
            return [self._walk(v, ids) for v in value]
        if isinstance(value, dict):
            return {k: self._walk(v, ids) for k, v in value.items()}
        return value

    def _name_to_id(self) -> dict[str, str]:
        return {p["name"]: p["id"] for p in self._engine.get_public_state()["players"]}

    async def _notify(self, step: str, role_id: str | None = None) -> None:
        if self._on_step is None:
            return
        result = self._on_step(step) if role_id is None else self._on_step(f"{step}:{role_id}")
        if asyncio.iscoroutine(result):
            await result