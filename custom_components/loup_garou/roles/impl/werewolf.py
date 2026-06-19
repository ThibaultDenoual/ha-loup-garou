"""Werewolf role — kills one player per night."""
from ..base import BaseRole, EliminateDecision, RoleContext


class Werewolf(BaseRole):
    id = "werewolf"
    team = "wolves"
    night_priority = 50
    has_night_action = True

    async def on_night_action(self, ctx: RoleContext, action: dict) -> None:
        target_id = action.get("target")
        wolf_role_ids = {"werewolf", "alpha_wolf"}
        if target_id and any(
            p["id"] == target_id and p["alive"] and p["role_id"] not in wolf_role_ids
            for p in ctx.alive_players
        ):
            ctx.add_pending_kill(target_id, "wolf_kill")

    async def check_win(self, ctx: RoleContext) -> str | None:
        alive = ctx.alive_players
        wolves = [p for p in alive if p["role_id"] in ("werewolf", "alpha_wolf")]
        villagers = [p for p in alive if p["role_id"] not in ("werewolf", "alpha_wolf", "minion")]
        if wolves and len(wolves) >= len(villagers):
            return "wolves"
        return None
