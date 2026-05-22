"""Base role interface — every role implements BaseRole."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Coroutine

if TYPE_CHECKING:
    from ..game_engine import GameState


@dataclass
class EliminateDecision:
    cancel: bool = False
    add_eliminations: list[str] = field(default_factory=list)


class RoleContext:
    """Read+write facade over GameState. Roles must only interact with state through this."""

    def __init__(
        self,
        state: "GameState",
        emit: Callable[..., Coroutine[Any, Any, None]],
    ) -> None:
        self._state = state
        self.emit = emit

    # ── Read ──────────────────────────────────────────────────────────────────

    @property
    def alive_players(self) -> list[dict]:
        return [p.to_dict() for p in self._state.players.values() if p.alive]

    @property
    def all_players(self) -> list[dict]:
        return [p.to_dict() for p in self._state.players.values()]

    @property
    def night_number(self) -> int:
        return self._state.night_number

    @property
    def pending_kills(self) -> list[str]:
        """Player IDs marked for death this night (wolves' choices so far)."""
        return [pid for pid, _ in self._state.pending_kills]

    def get_player(self, player_id: str) -> dict | None:
        p = self._state.players.get(player_id)
        return p.to_dict() if p else None

    def get_flag(self, player_id: str, key: str, default: Any = None) -> Any:
        return self._state.player_flags.get(player_id, {}).get(key, default)

    def get_link(self, link_type: str, player_id: str) -> list[str]:
        """Return other player IDs linked to this player under link_type."""
        group = self._state.player_links.get(link_type, [])
        if player_id in group:
            return [pid for pid in group if pid != player_id]
        return []

    def alive_players_by_role(self, role_id: str) -> list[dict]:
        return [
            p.to_dict()
            for p in self._state.players.values()
            if p.alive and p.role_id == role_id
        ]

    # ── Write ─────────────────────────────────────────────────────────────────

    def set_flag(self, player_id: str, key: str, value: Any) -> None:
        self._state.player_flags.setdefault(player_id, {})[key] = value

    def add_pending_kill(self, player_id: str, cause: str = "wolf_kill") -> None:
        if player_id not in self.pending_kills:
            self._state.pending_kills.append((player_id, cause))

    def remove_pending_kill(self, player_id: str) -> None:
        self._state.pending_kills = [
            (pid, c) for pid, c in self._state.pending_kills if pid != player_id
        ]

    def add_link(self, link_type: str, player_ids: list[str]) -> None:
        self._state.player_links[link_type] = list(player_ids)

    def change_role(self, player_id: str, new_role_id: str) -> None:
        p = self._state.players.get(player_id)
        if p:
            p.role_id = new_role_id

    async def request_action(self, role_id: str, event_data: dict) -> dict:
        """Pause the elimination chain, emit event, await external UI input."""
        from ..const import GameEvent
        loop = asyncio.get_event_loop()
        fut: asyncio.Future[dict] = loop.create_future()
        self._state.pending_interrupt_role = role_id
        self._state.pending_interrupt = fut
        await self.emit(GameEvent.NIGHT_ROLE_WAKE, {"role": role_id, **event_data})
        result = await fut
        self._state.pending_interrupt_role = None
        self._state.pending_interrupt = None
        return result


class BaseRole:
    """Interface every role must implement."""

    id: str = ""
    team: str = "village"
    night_priority: int = 99
    has_night_action: bool = False

    # ── Hooks ─────────────────────────────────────────────────────────────────

    async def on_game_start(self, ctx: RoleContext) -> None:
        pass

    async def on_night_start(self, ctx: RoleContext) -> None:
        pass

    async def on_night_action(self, ctx: RoleContext, action: dict) -> None:
        pass

    async def on_before_eliminate(
        self, ctx: RoleContext, player_id: str, cause: str
    ) -> EliminateDecision:
        return EliminateDecision()

    async def on_after_eliminate(
        self, ctx: RoleContext, player_id: str, cause: str
    ) -> None:
        pass

    async def check_win(self, ctx: RoleContext) -> str | None:
        return None

    def get_public_state(self, ctx: RoleContext) -> dict:
        return {}

    def get_wake_data(self, ctx: RoleContext) -> dict:
        """Extra data to include in NIGHT_ROLE_WAKE payload. Roles override this."""
        return {}
