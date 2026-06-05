"""Hunter role — shoots one player on elimination."""
from ...const import GameEvent
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

        # Emit HUNTER_SHOT before the target enters the elimination queue so
        # atmosphere and the UI can announce "hunter dragged target down" with
        # both names, before the generic PLAYER_ELIMINATED event fires for the target.
        await ctx.emit(GameEvent.HUNTER_SHOT, {
            "hunter_id": player_id,
            "hunter_name": player["name"],
            "target_id": target_id,
            "target_name": target["name"],
            "target_role": target["role_id"],
        })

        return EliminateDecision(add_eliminations=[target_id])
