"""Seer role — investigates one player per night."""
from ..base import BaseRole, EliminateDecision, RoleContext


class Seer(BaseRole):
    id = "seer"
    team = "village"
    night_priority = 10
    has_night_action = True

    async def on_night_action(self, ctx: RoleContext, action: dict) -> None:
        target_id = action.get("target")
        if not target_id:
            return
        target = ctx.get_player(target_id)
        if target is None or not target["alive"]:
            return
        # Show result and wait for the seer to acknowledge before sleeping.
        # This ensures the result stays visible until the seer taps confirm.
        await ctx.request_action(
            self.id,
            {"result": {"player_id": target_id, "role_id": target["role_id"]}},
        )
