"""Villager role — baseline village team, no night action."""
from ..base import BaseRole, EliminateDecision, RoleContext


class Villager(BaseRole):
    id = "villager"
    team = "village"
    night_priority = 99
    has_night_action = False

    async def check_win(self, ctx: RoleContext) -> str | None:
        alive = ctx.alive_players
        wolves_alive = any(p["role_id"] in ("werewolf", "alpha_wolf") for p in alive)
        if not wolves_alive and alive:
            return "village"
        return None
