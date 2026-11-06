"""Pure game logic — zero HA imports.

run_game() drives a whole game. It only ever waits on people through ask(), so
the open prompt is always the one thing the game can accept.
"""
from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable, Coroutine

from .const import GameEvent, Phase
from . import public_roles
from .prompts import IllegalAnswer, Prompt, pick
from .roles.base import BaseRole, EliminateDecision, RoleContext
from .roles.loader import load_roles

_LOGGER = logging.getLogger(__name__)

PROMPT_REVEAL = "reveal"
PROMPT_NIGHT_ACTION = "night_action"
PROMPT_DAY_CHOICE = "day_choice"
PROMPT_BALLOT = "ballot"
PROMPT_NEW_GAME = "new_game"

NEXT_VOTE = "vote"
NEXT_NIGHT = "night"


class AnswerResult(StrEnum):
    ACCEPTED = "accepted"
    DUPLICATE = "duplicate"
    STALE = "stale"
    ILLEGAL = "illegal"


@dataclass
class Player:
    id: str
    name: str
    role_id: str
    alive: bool = True
    # The trade the village knows them by (public_roles.py); not a secret.
    public_role: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "role_id": self.role_id,
            "alive": self.alive, "public_role": self.public_role,
        }


def _empty_news(source: str = "night") -> dict:
    return {"source": source, "deaths": [], "tie": False}


@dataclass
class GameState:
    players: dict[str, Player] = field(default_factory=dict)
    phase: Phase = Phase.SETUP
    night_number: int = 0
    # Each entry: (player_id, cause)
    pending_kills: list[tuple[str, str]] = field(default_factory=list)
    player_flags: dict[str, dict] = field(default_factory=dict)
    player_links: dict[str, list[str]] = field(default_factory=dict)
    winner: str | None = None
    # What the village last learned: the deaths of a night or a vote.
    news: dict = field(default_factory=_empty_news)


_Handler = Callable[..., Coroutine[Any, Any, None]]


class GameEngine:
    def __init__(
        self, roles: dict[str, BaseRole] | None = None, *, rng: random.Random | None = None,
    ) -> None:
        self._rng = rng or random.Random()
        self._state = GameState()
        self._roles: dict[str, BaseRole] = roles if roles is not None else load_roles()
        self._listeners: dict[str, list[_Handler]] = {}
        self._prompt: Prompt | None = None
        self._prompt_future: asyncio.Future[dict] | None = None
        self._prompt_count = 0
        self._last_answered: str | None = None
        self._revision = 0

    # ── Event system ──────────────────────────────────────────────────────────

    def on(self, event: GameEvent, handler: _Handler) -> None:
        self._listeners.setdefault(str(event), []).append(handler)

    def off(self, event: GameEvent, handler: _Handler) -> None:
        """Remove a previously registered handler. Safe to call if not registered."""
        handlers = self._listeners.get(str(event))
        if handlers and handler in handlers:
            handlers.remove(handler)

    async def _emit(self, event: GameEvent, data: dict | None = None) -> None:
        payload = data or {}
        for handler in list(self._listeners.get(str(event), [])):
            try:
                await handler(payload)
            except Exception:
                _LOGGER.exception("Error in handler for %s", event)

    async def _publish(self) -> None:
        """Tell the clients what changed, before anything narrates it."""
        self._revision += 1
        await self._emit(GameEvent.STATE_CHANGED, self.snapshot())

    # ── Public read API ───────────────────────────────────────────────────────

    def get_public_state(self) -> dict:
        """The full table, roles included: for the server side only (see snapshot)."""
        return {
            "phase": self._state.phase,
            "night_number": self._state.night_number,
            "winner": self._state.winner,
            "players": [p.to_dict() for p in self._state.players.values()],
        }

    def snapshot(self) -> dict:
        """Everything a client needs to render the game, without secret roles."""
        game_over = self._state.phase == Phase.GAME_OVER
        players = []
        for p in self._state.players.values():
            entry: dict = {
                "id": p.id, "name": p.name, "alive": p.alive, "public_role": p.public_role,
            }
            if game_over or not p.alive:
                entry["role_id"] = p.role_id
            if self._state.player_flags.get(p.id, {}).get("sheriff"):
                entry["sheriff"] = True
            players.append(entry)
        return {
            "rev": self._revision,
            "phase": self._state.phase,
            "night": self._state.night_number,
            "winner": self._state.winner,
            "players": players,
            "news": self._state.news,
            "prompt": self._prompt.to_dict() if self._prompt else None,
        }

    @property
    def prompt(self) -> Prompt | None:
        """What the game is waiting for, or None."""
        return self._prompt

    # ── Prompts ───────────────────────────────────────────────────────────────

    async def ask(
        self,
        kind: str,
        *,
        role: str | None = None,
        actor: str | None = None,
        picks: dict | None = None,
        info: dict | None = None,
    ) -> dict:
        """Open a prompt and wait for its answer. This is the game's only wait on people."""
        self._prompt_count += 1
        prompt = Prompt(
            id=f"q{self._prompt_count}", kind=kind, role=role, actor=actor,
            picks=picks or {}, info=info or {},
        )
        future: asyncio.Future[dict] = asyncio.get_running_loop().create_future()
        self._prompt = prompt
        self._prompt_future = future
        await self._publish()
        await self._emit(GameEvent.PROMPT_OPENED, prompt.to_dict())
        try:
            return await future
        finally:
            if self._prompt is prompt:
                self._prompt = None
                self._prompt_future = None

    async def answer(self, prompt_id: str, answer: Any) -> AnswerResult:
        prompt = self._prompt
        if prompt is None or prompt.id != prompt_id:
            if prompt_id == self._last_answered:
                return AnswerResult.DUPLICATE
            _LOGGER.info("Answer to prompt %s, which is not open", prompt_id)
            return AnswerResult.STALE
        try:
            action = prompt.validate(answer)
        except IllegalAnswer as exc:
            _LOGGER.info("Illegal answer to %s: %s", prompt.kind, exc)
            return AnswerResult.ILLEGAL

        future = self._prompt_future
        self._prompt = None
        self._prompt_future = None
        self._last_answered = prompt_id
        future.set_result(action)
        await self._publish()
        return AnswerResult.ACCEPTED

    # ── Game lifecycle ────────────────────────────────────────────────────────

    async def reset(self) -> None:
        """Discard any game in progress and return to the setup phase."""
        self._prompt = None
        self._prompt_future = None
        self._state = GameState()
        await self._publish()
        await self._emit(GameEvent.PHASE_CHANGED, {"phase": Phase.SETUP})

    async def start_game(self, player_names: list[str], role_ids: list[str]) -> None:
        """Deal the roles. run_game() then plays the game."""
        if len(player_names) != len(role_ids):
            raise ValueError("player_names and role_ids must have the same length")
        unknown = set(role_ids) - set(self._roles)
        if unknown:
            raise ValueError(f"unknown roles: {sorted(unknown)}")

        self._prompt = None
        self._prompt_future = None
        self._state = GameState()
        trades = public_roles.deal(len(player_names), self._rng)
        for i, (name, role_id, trade) in enumerate(zip(player_names, role_ids, trades)):
            pid = f"p{i}"
            self._state.players[pid] = Player(
                id=pid, name=name, role_id=role_id, public_role=trade,
            )

        ctx = self._make_ctx()
        for role in self._active_roles():
            await role.on_game_start(ctx)

        self._state.phase = Phase.ROLE_REVEAL
        await self._publish()
        await self._emit(GameEvent.GAME_STARTED, self.get_public_state())
        await self._emit(GameEvent.PHASE_CHANGED, {"phase": Phase.ROLE_REVEAL})

    async def run_game(self) -> None:
        """Play a dealt game from the reveal to the new-game prompt."""
        await self.play_reveal()
        while self._state.phase != Phase.GAME_OVER:
            await self.begin_night()
            if self._state.phase != Phase.GAME_OVER:
                await self._play_day()
        await self.ask(PROMPT_NEW_GAME)
        await self.reset()

    async def play_reveal(self) -> None:
        players = list(self._state.players.values())
        for done, player in enumerate(players, start=1):
            await self.ask(
                PROMPT_REVEAL,
                actor=player.id,
                info={"role_id": player.role_id, "done": done, "total": len(players)},
            )

    async def _play_day(self) -> None:
        ctx = self._make_ctx()
        for role in self._active_roles():
            await role.on_day_start(ctx)

        answer = await self.ask(
            PROMPT_DAY_CHOICE, picks={"next": pick([NEXT_VOTE, NEXT_NIGHT], 1)}
        )
        if answer["next"] != NEXT_VOTE:
            return

        await self.begin_vote()
        await self.resolve_vote(await self.collect_ballots())
        if self._state.phase != Phase.GAME_OVER:
            # One vote a day: the village reads the verdict, then night falls.
            await self.ask(PROMPT_DAY_CHOICE, picks={"next": pick([NEXT_NIGHT], 1)})

    async def collect_ballots(self, *, allow_abstain: bool = False) -> dict[str, str]:
        voters = [p for p in self._state.players.values() if p.alive]
        counts = (0, 1) if allow_abstain else (1,)
        votes: dict[str, str] = {}
        for done, voter in enumerate(voters):
            targets = [p.id for p in voters if p.id != voter.id]
            answer = await self.ask(
                PROMPT_BALLOT,
                actor=voter.id,
                picks={"target": pick(targets, *counts)},
                info={"done": done, "total": len(voters)},
            )
            if answer["target"]:
                votes[voter.id] = answer["target"]
        return votes

    async def begin_night(self) -> None:
        """Run the full night sequence: wake each role, ask it, then resolve."""
        self._state.night_number += 1
        self._state.pending_kills = []
        self._state.news = _empty_news()
        await self._enter(Phase.NIGHT)

        ctx = self._make_ctx()
        for role in self._night_roles():
            if not ctx.alive_players_by_role(role.id):
                continue
            if not role.should_wake(ctx):
                continue

            # Handlers narrate the wake here: the prompt opens once they finish.
            await self._emit(GameEvent.NIGHT_ROLE_WAKE, {"role": role.id})
            await role.on_night_start(ctx)
            action = await self.ask(PROMPT_NIGHT_ACTION, role=role.id, **role.night_prompt(ctx))
            await role.on_night_action(ctx, action)
            await self._emit(GameEvent.NIGHT_ROLE_SLEEP, {"role": role.id})

        await self._resolve_night()

    def elect_sheriff(self, player_id: str) -> None:
        """Mark a player as sheriff (vote counts double)."""
        for pid in self._state.players:
            self._state.player_flags.setdefault(pid, {}).pop("sheriff", None)
        self._state.player_flags.setdefault(player_id, {})["sheriff"] = True

    async def begin_vote(self) -> None:
        await self._enter(Phase.VOTE)
        await self._emit(GameEvent.VOTE_STARTED, {})

    async def resolve_vote(self, votes: dict[str, str]) -> str | None:
        """votes: {voter_id: target_id}. Returns eliminated player_id or None on tie."""
        ctx = self._make_ctx()
        self._state.news = _empty_news("vote")
        tally: dict[str, int] = {}

        for voter_id, target_id in votes.items():
            voter = self._state.players.get(voter_id)
            target = self._state.players.get(target_id)
            if voter is None or not voter.alive or target is None or not target.alive:
                continue
            weight = 2 if ctx.get_flag(voter_id, "sheriff") else 1
            tally[target_id] = tally.get(target_id, 0) + weight

        top_votes = max(tally.values(), default=0)
        top = [pid for pid, v in tally.items() if v == top_votes]
        tie = len(top) != 1
        self._state.news["tie"] = tie

        if tie:
            target_id, cause = self._find_scapegoat(), "scapegoat"
        else:
            target_id, cause = top[0], "village_vote"

        await self._emit(GameEvent.VOTE_RESOLVED, {"eliminated": target_id, "tie": tie})
        if target_id is None:
            await self._start_day(after="vote")
            return None

        eliminated = await self._eliminate([(target_id, cause)])
        if not await self._finish_if_won(ctx, eliminated):
            await self._start_day(eliminated, after="vote")
        return target_id

    async def _enter(self, phase: Phase) -> None:
        self._state.phase = phase
        await self._publish()
        await self._emit(GameEvent.PHASE_CHANGED, {"phase": phase})

    async def _start_day(
        self, eliminated: list[str] | None = None, *, after: str = "night"
    ) -> None:
        """Enter the day. `after` says whether a night or a vote led here."""
        await self._enter(Phase.DAY)
        await self._emit(
            GameEvent.DAY_STARTED, {"eliminated": eliminated or [], "after": after}
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _make_ctx(self) -> RoleContext:
        return RoleContext(self._state, self._emit, self.ask)

    def _active_roles(self) -> list[BaseRole]:
        present = {p.role_id for p in self._state.players.values()}
        return sorted(
            [r for r in self._roles.values() if r.id in present],
            key=lambda r: r.night_priority,
        )

    def _night_roles(self) -> list[BaseRole]:
        return [r for r in self._active_roles() if r.has_night_action]

    def _find_scapegoat(self) -> str | None:
        for p in self._state.players.values():
            if p.alive and p.role_id == "scapegoat":
                return p.id
        return None

    async def _check_win(self, ctx: RoleContext) -> str | None:
        for role in self._active_roles():
            result = await role.check_win(ctx)
            if result is not None:
                return result
        # The village wins whichever roles are in play: no role may have to be
        # present for the game to end.
        alive = ctx.alive_players
        if alive and not any(self._is_wolf(p["role_id"]) for p in alive):
            return "village"
        return None

    def _is_wolf(self, role_id: str) -> bool:
        role = self._roles.get(role_id)
        return role is not None and role.is_wolf

    async def _end_game(self, winner: str) -> None:
        self._state.winner = winner
        await self._enter(Phase.GAME_OVER)
        await self._emit(GameEvent.GAME_OVER, {"winner": winner})

    async def _finish_if_won(self, ctx: RoleContext, eliminated: list[str]) -> bool:
        if not eliminated:
            return False
        winner = await self._check_win(ctx)
        if winner is None and not ctx.alive_players:
            winner = "village"
        if winner:
            await self._end_game(winner)
            return True
        return False

    async def _eliminate(self, kills: list[tuple[str, str]]) -> list[str]:
        """Kill these (player_id, cause) pairs and everyone they drag along."""
        ctx = self._make_ctx()
        queue = list(kills)
        eliminated: list[str] = []

        while queue:
            pid, cause = queue.pop(0)
            player = self._state.players.get(pid)
            if player is None or not player.alive:
                continue

            decisions: list[EliminateDecision] = []
            for role in self._active_roles():
                decision: EliminateDecision = await role.on_before_eliminate(ctx, pid, cause)
                if decision.cancel:
                    decisions = []
                    break
                decisions.append(decision)
            if not decisions:
                continue

            for decision in decisions:
                for extra in decision.add_eliminations:
                    if all(extra != queued for queued, _ in queue):
                        queue.append((extra, decision.cause or cause))

            player.alive = False
            eliminated.append(pid)
            self._state.news["deaths"].append(
                {"player_id": pid, "name": player.name, "role": player.role_id, "cause": cause}
            )
            await self._publish()
            await self._emit(
                GameEvent.PLAYER_ELIMINATED,
                {"player_id": pid, "name": player.name, "role": player.role_id, "cause": cause},
            )
            for role in self._active_roles():
                await role.on_after_eliminate(ctx, pid, cause)

        return eliminated

    async def _resolve_night(self) -> list[str]:
        ctx = self._make_ctx()
        kills = list(self._state.pending_kills)
        self._state.pending_kills = []

        eliminated = await self._eliminate(kills)
        await self._emit(GameEvent.NIGHT_RESOLVED, {"eliminated": eliminated})

        if not await self._finish_if_won(ctx, eliminated):
            await self._start_day(eliminated)
        return eliminated
