"""Pure game logic — zero HA imports."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

from .const import GameEvent, Phase
from .roles.base import BaseRole, EliminateDecision, RoleContext
from .roles.loader import load_roles

_LOGGER = logging.getLogger(__name__)


@dataclass
class Player:
    id: str
    name: str
    role_id: str
    alive: bool = True

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "role_id": self.role_id, "alive": self.alive}


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
    # Generic mid-chain interrupt (Hunter shot, etc.)
    pending_interrupt_role: str | None = None
    pending_interrupt: Any = None  # asyncio.Future when active


_Handler = Callable[..., Coroutine[Any, Any, None]]


class GameEngine:
    def __init__(self, roles: dict[str, BaseRole] | None = None) -> None:
        self._state = GameState()
        self._roles: dict[str, BaseRole] = roles if roles is not None else load_roles()
        self._listeners: dict[str, list[_Handler]] = {}
        self._pending_action: asyncio.Future[dict] | None = None
        self._pending_action_role: str | None = None

    # ── Event system ──────────────────────────────────────────────────────────

    def on(self, event: GameEvent, handler: _Handler) -> None:
        self._listeners.setdefault(str(event), []).append(handler)

    async def _emit(self, event: GameEvent, data: dict | None = None) -> None:
        payload = data or {}
        for handler in self._listeners.get(str(event), []):
            try:
                await handler(payload)
            except Exception:
                _LOGGER.exception("Error in handler for %s", event)

    # ── Public read API ───────────────────────────────────────────────────────

    def get_public_state(self) -> dict:
        return {
            "phase": self._state.phase,
            "night_number": self._state.night_number,
            "winner": self._state.winner,
            "players": [p.to_dict() for p in self._state.players.values()],
        }

    # ── Game lifecycle ────────────────────────────────────────────────────────

    async def start_game(self, player_names: list[str], role_ids: list[str]) -> None:
        if len(player_names) != len(role_ids):
            raise ValueError("player_names and role_ids must have the same length")

        self._state = GameState()
        for i, (name, role_id) in enumerate(zip(player_names, role_ids)):
            pid = f"p{i}"
            self._state.players[pid] = Player(id=pid, name=name, role_id=role_id)

        ctx = self._make_ctx()
        for role in self._active_roles():
            await role.on_game_start(ctx)

        self._state.phase = Phase.ROLE_REVEAL
        await self._emit(GameEvent.GAME_STARTED, self.get_public_state())
        await self._emit(GameEvent.PHASE_CHANGED, {"phase": Phase.ROLE_REVEAL})

    async def begin_night(self) -> None:
        """Run the full night sequence: wake each role, await action, then resolve."""
        self._state.phase = Phase.NIGHT
        self._state.night_number += 1
        self._state.pending_kills = []
        await self._emit(GameEvent.PHASE_CHANGED, {"phase": Phase.NIGHT})

        ctx = self._make_ctx()
        for role in self._night_roles():
            if not ctx.alive_players_by_role(role.id):
                continue
            if not role.should_wake(ctx):
                continue

            wake_data = {"role": role.id}
            wake_data.update(role.get_wake_data(ctx))
            await self._emit(GameEvent.NIGHT_ROLE_WAKE, wake_data)
            await role.on_night_start(ctx)

            fut: asyncio.Future[dict] = asyncio.get_running_loop().create_future()
            self._pending_action_role = role.id
            self._pending_action = fut
            action = await fut
            self._pending_action = None
            self._pending_action_role = None

            await role.on_night_action(ctx, action)
            await self._emit(GameEvent.NIGHT_ROLE_SLEEP, {"role": role.id})

        await self._resolve_night()

    async def submit_night_action(self, role_id: str, action: dict) -> None:
        if self._pending_action_role == role_id and self._pending_action and not self._pending_action.done():
            self._pending_action.set_result(action)
        else:
            _LOGGER.warning("submit_night_action: no pending action for role %s", role_id)

    async def submit_pending_action(self, role_id: str, action: dict) -> None:
        """Resolve a mid-chain interrupt (e.g. Hunter shot, Witch choice)."""
        fut = self._state.pending_interrupt
        if (
            self._state.pending_interrupt_role == role_id
            and fut is not None
            and not fut.done()
        ):
            fut.set_result(action)
        else:
            _LOGGER.warning("submit_pending_action: no pending interrupt for role %s", role_id)

    def elect_sheriff(self, player_id: str) -> None:
        """Mark a player as sheriff (vote counts double)."""
        for pid in self._state.players:
            self._state.player_flags.setdefault(pid, {}).pop("sheriff", None)
        self._state.player_flags.setdefault(player_id, {})["sheriff"] = True

    async def begin_vote(self) -> None:
        self._state.phase = Phase.VOTE
        await self._emit(GameEvent.PHASE_CHANGED, {"phase": Phase.VOTE})
        await self._emit(GameEvent.VOTE_STARTED, {})

    async def resolve_vote(self, votes: dict[str, str]) -> str | None:
        """votes: {voter_id: target_id}. Returns eliminated player_id or None on tie."""
        ctx = self._make_ctx()
        tally: dict[str, int] = {}

        for voter_id, target_id in votes.items():
            voter = self._state.players.get(voter_id)
            if voter is None or not voter.alive:
                continue
            weight = 2 if ctx.get_flag(voter_id, "sheriff") else 1
            tally[target_id] = tally.get(target_id, 0) + weight

        if not tally:
            await self._emit(GameEvent.VOTE_RESOLVED, {"eliminated": None, "tie": True})
            return None

        max_votes = max(tally.values())
        top = [pid for pid, v in tally.items() if v == max_votes]

        if len(top) > 1:
            scapegoat_id = self._find_scapegoat()
            if scapegoat_id:
                game_over = await self._do_elimination(scapegoat_id, "scapegoat", ctx)
                await self._emit(GameEvent.VOTE_RESOLVED, {"eliminated": scapegoat_id, "tie": True})
                if not game_over:
                    self._state.phase = Phase.DAY
                    await self._emit(GameEvent.PHASE_CHANGED, {"phase": Phase.DAY})
                    await self._emit(GameEvent.DAY_STARTED, {})
                return scapegoat_id
            await self._emit(GameEvent.VOTE_RESOLVED, {"eliminated": None, "tie": True})
            return None

        target_id = top[0]
        game_over = await self._do_elimination(target_id, "village_vote", ctx)
        await self._emit(GameEvent.VOTE_RESOLVED, {"eliminated": target_id, "tie": False})
        if not game_over:
            self._state.phase = Phase.DAY
            await self._emit(GameEvent.PHASE_CHANGED, {"phase": Phase.DAY})
            await self._emit(GameEvent.DAY_STARTED, {"eliminated": [target_id]})
        return target_id

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _make_ctx(self) -> RoleContext:
        return RoleContext(self._state, self._emit)

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
        return None

    async def _end_game(self, winner: str) -> None:
        self._state.phase = Phase.GAME_OVER
        self._state.winner = winner
        await self._emit(GameEvent.PHASE_CHANGED, {"phase": Phase.GAME_OVER})
        await self._emit(GameEvent.GAME_OVER, {"winner": winner})

    async def _do_elimination(self, first_pid: str, cause: str, ctx: RoleContext) -> bool:
        """Run elimination queue starting with first_pid. Returns True if game ended."""
        queue = [first_pid]
        while queue:
            pid = queue.pop(0)
            player = self._state.players.get(pid)
            if player is None or not player.alive:
                continue

            cancelled = False
            extra: list[str] = []
            for role in self._active_roles():
                decision: EliminateDecision = await role.on_before_eliminate(ctx, pid, cause)
                if decision.cancel:
                    cancelled = True
                    break
                extra.extend(decision.add_eliminations)

            if cancelled:
                continue

            for e in extra:
                if e not in queue:
                    queue.append(e)

            player.alive = False
            await self._emit(
                GameEvent.PLAYER_ELIMINATED,
                {"player_id": pid, "name": player.name, "role": player.role_id, "cause": cause},
            )
            for role in self._active_roles():
                await role.on_after_eliminate(ctx, pid, cause)

            winner = await self._check_win(ctx)
            if winner:
                await self._end_game(winner)
                return True

        return False

    async def _resolve_night(self) -> list[str]:
        ctx = self._make_ctx()
        eliminated: list[str] = []

        queue = list(self._state.pending_kills)
        self._state.pending_kills = []

        while queue:
            pid, cause = queue.pop(0)
            player = self._state.players.get(pid)
            if player is None or not player.alive:
                continue

            cancelled = False
            extra: list[str] = []
            for role in self._active_roles():
                decision: EliminateDecision = await role.on_before_eliminate(ctx, pid, cause)
                if decision.cancel:
                    cancelled = True
                    break
                extra.extend(decision.add_eliminations)

            if cancelled:
                continue

            for e in extra:
                if (e, cause) not in queue:
                    queue.append((e, "lover_grief"))

            player.alive = False
            eliminated.append(pid)
            await self._emit(
                GameEvent.PLAYER_ELIMINATED,
                {"player_id": pid, "name": player.name, "role": player.role_id, "cause": cause},
            )
            for role in self._active_roles():
                await role.on_after_eliminate(ctx, pid, cause)

            winner = await self._check_win(ctx)
            if winner:
                await self._emit(GameEvent.NIGHT_RESOLVED, {"eliminated": eliminated})
                await self._end_game(winner)
                return eliminated

        await self._emit(GameEvent.NIGHT_RESOLVED, {"eliminated": eliminated})
        self._state.phase = Phase.DAY
        await self._emit(GameEvent.PHASE_CHANGED, {"phase": Phase.DAY})
        await self._emit(GameEvent.DAY_STARTED, {"eliminated": eliminated})
        return eliminated
