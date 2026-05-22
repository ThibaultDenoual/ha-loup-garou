"""Elder role — survives the first wolf kill."""
from ..base import BaseRole, EliminateDecision, RoleContext


class Elder(BaseRole):
    id = "elder"
    team = "village"
    night_priority = 99
    has_night_action = False

    async def on_game_start(self, ctx: RoleContext) -> None:
        for p in ctx.alive_players:
            if p["role_id"] == self.id:
                ctx.set_flag(p["id"], "elder_first_life", True)

    async def on_before_eliminate(
        self, ctx: RoleContext, player_id: str, cause: str
    ) -> EliminateDecision:
        player = ctx.get_player(player_id)
        if player is None or player["role_id"] != self.id:
            return EliminateDecision()
        if cause == "wolf_kill" and ctx.get_flag(player_id, "elder_first_life"):
            ctx.set_flag(player_id, "elder_first_life", False)
            return EliminateDecision(cancel=True)
        return EliminateDecision()
