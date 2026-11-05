"""Minion role — wins with the wolves, no night action, unknown to the wolves.

The Minion doesn't know who the wolves are either: finding them is played at
the table, not in the app.
"""
from ..base import BaseRole, EliminateDecision, RoleContext


class Minion(BaseRole):
    id = "minion"
    team = "wolves"
    night_priority = 99
    has_night_action = False

    async def check_win(self, ctx: RoleContext) -> str | None:
        alive = ctx.alive_players
        wolves = [p for p in alive if p["role_id"] in ("werewolf", "alpha_wolf")]
        villagers = [p for p in alive if p["role_id"] not in ("werewolf", "alpha_wolf", "minion")]
        if wolves and len(wolves) >= len(villagers):
            return "wolves"
        return None
