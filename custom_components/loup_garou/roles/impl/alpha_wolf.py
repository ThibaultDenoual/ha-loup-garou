"""Alpha Wolf role — converts one villager per game (night action)."""
from ..base import BaseRole, EliminateDecision, RoleContext


class AlphaWolf(BaseRole):
    id = "alpha_wolf"
    team = "wolves"
    night_priority = 50  # Acts with the wolves
    has_night_action = True

    async def on_game_start(self, ctx: RoleContext) -> None:
        for p in ctx.alive_players:
            if p["role_id"] == self.id:
                ctx.set_flag(p["id"], "alpha_conversion_used", False)

    async def on_night_action(self, ctx: RoleContext, action: dict) -> None:
        alphas = ctx.alive_players_by_role("alpha_wolf")
        wolf_id = alphas[0]["id"] if alphas else None
        if wolf_id and ctx.get_flag(wolf_id, "alpha_conversion_used"):
            return  # Already used

        convert_target = action.get("convert_target")
        if not convert_target:
            return

        target = ctx.get_player(convert_target)
        if target is None or not target["alive"]:
            return
        if target["role_id"] in ("werewolf", "alpha_wolf"):
            return  # Can't convert a wolf

        ctx.change_role(convert_target, "werewolf")
        ctx.set_flag(wolf_id, "alpha_conversion_used", True)

    async def check_win(self, ctx: RoleContext) -> str | None:
        alive = ctx.alive_players
        wolves = [p for p in alive if p["role_id"] in ("werewolf", "alpha_wolf")]
        villagers = [p for p in alive if p["role_id"] not in ("werewolf", "alpha_wolf", "minion")]
        if wolves and len(wolves) >= len(villagers):
            return "wolves"
        return None
