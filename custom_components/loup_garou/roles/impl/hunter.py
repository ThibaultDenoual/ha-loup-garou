"""Hunter role — shoots one player on elimination."""
from ..base import BaseRole, EliminateDecision, RoleContext


class Hunter(BaseRole):
    id = "hunter"
    team = "village"
    night_priority = 99
    has_night_action = False

    async def on_before_eliminate(
        self, ctx: RoleContext, player_id: str, cause: str
    ) -> EliminateDecision:
        player = ctx.get_player(player_id)
        if player is None or player["role_id"] != self.id:
            return EliminateDecision()

        action = await ctx.request_action(self.id, {"player_id": player_id})
        target_id = action.get("target")
        if not target_id:
            return EliminateDecision()
        target = ctx.get_player(target_id)
        if target is None or not target["alive"]:
            return EliminateDecision()
        return EliminateDecision(add_eliminations=[target_id])
