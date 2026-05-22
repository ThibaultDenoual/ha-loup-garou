"""Cupid role — links two lovers on night 1; they die together."""
from ..base import BaseRole, EliminateDecision, RoleContext


class Cupid(BaseRole):
    id = "cupid"
    team = "village"
    night_priority = 5  # First role to act each game (night 1 only)
    has_night_action = True

    def should_wake(self, ctx: RoleContext) -> bool:
        return ctx.night_number == 1

    async def on_night_action(self, ctx: RoleContext, action: dict) -> None:
        if ctx.night_number != 1:
            return
        lovers = action.get("lovers", [])
        if len(lovers) == 2:
            ctx.add_link("lovers", lovers)

    async def on_before_eliminate(
        self, ctx: RoleContext, player_id: str, cause: str
    ) -> EliminateDecision:
        linked = ctx.get_link("lovers", player_id)
        extra = [pid for pid in linked if ctx.get_player(pid) and ctx.get_player(pid)["alive"]]
        if extra:
            return EliminateDecision(add_eliminations=extra)
        return EliminateDecision()

    async def check_win(self, ctx: RoleContext) -> str | None:
        lovers_link = ctx._state.player_links.get("lovers", [])
        if len(lovers_link) != 2:
            return None
        a_id, b_id = lovers_link
        a = ctx.get_player(a_id)
        b = ctx.get_player(b_id)
        if a is None or b is None:
            return None
        if a["alive"] and b["alive"]:
            alive = ctx.alive_players
            non_lovers_alive = [p for p in alive if p["id"] not in (a_id, b_id)]
            if not non_lovers_alive:
                return "lovers"
        return None
