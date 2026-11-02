"""Sheriff role — elected; vote counts double."""
from ...prompts import pick
from ..base import BaseRole, EliminateDecision, RoleContext


class Sheriff(BaseRole):
    id = "sheriff"
    team = "village"
    night_priority = 99
    has_night_action = False
    # Double-vote weight is applied in engine.resolve_vote().

    async def on_day_start(self, ctx: RoleContext) -> None:
        """The village elects its sheriff, once, on the first day."""
        if any(ctx.get_flag(p["id"], "sheriff") for p in ctx.all_players):
            return
        options = [p["id"] for p in ctx.alive_players]
        answer = await ctx.ask(
            "sheriff_election", role=self.id, picks={"target": pick(options, 1)}
        )
        ctx.set_flag(answer["target"], "sheriff", True)
