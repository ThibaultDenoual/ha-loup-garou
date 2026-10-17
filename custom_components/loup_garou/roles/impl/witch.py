"""Witch role — save potion + poison potion, once each."""
from ..base import BaseRole, EliminateDecision, RoleContext
from ...const import GameEvent


class Witch(BaseRole):
    id = "witch"
    team = "village"
    night_priority = 60  # After wolves (50) so she can see the victim
    has_night_action = True

    async def on_game_start(self, ctx: RoleContext) -> None:
        for p in ctx.alive_players:
            if p["role_id"] == self.id:
                ctx.set_flag(p["id"], "witch_save_used", False)
                ctx.set_flag(p["id"], "witch_poison_used", False)

    def get_wake_data(self, ctx: RoleContext) -> dict:
        witch_players = ctx.alive_players_by_role(self.id)
        witch_id = witch_players[0]["id"] if witch_players else None
        pending_kills = []
        for player_id, cause in ctx.pending_kills_full():
            player = ctx.get_player(player_id)
            elder_is_protected = (
                cause == "wolf_kill"
                and player is not None
                and player["role_id"] == "elder"
                and ctx.get_flag(player_id, "elder_first_life", False)
            )
            if not elder_is_protected:
                pending_kills.append({"player_id": player_id, "cause": cause})
        return {
            "pending_kills": pending_kills,
            "save_used": ctx.get_flag(witch_id, "witch_save_used", False) if witch_id else True,
            "poison_used": ctx.get_flag(witch_id, "witch_poison_used", False) if witch_id else True,
        }

    async def on_night_action(self, ctx: RoleContext, action: dict) -> None:
        witch_id = action.get("player_id")
        if witch_id is None:
            witch_players = ctx.alive_players_by_role(self.id)
            if not witch_players:
                return
            witch_id = witch_players[0]["id"]

        save_target = action.get("save_target")
        poison_target = action.get("poison_target")

        if save_target and not ctx.get_flag(witch_id, "witch_save_used"):
            player = ctx.get_player(save_target)
            is_protected_elder = (
                player is not None
                and player["role_id"] == "elder"
                and ctx.get_flag(save_target, "elder_first_life", False)
            )
            is_pending_wolf_victim = any(
                pid == save_target and cause == "wolf_kill"
                for pid, cause in ctx.pending_kills_full()
            )
            if is_pending_wolf_victim and not is_protected_elder:
                ctx.remove_pending_kill(save_target)
                ctx.set_flag(witch_id, "witch_save_used", True)

        if poison_target and not ctx.get_flag(witch_id, "witch_poison_used"):
            target = ctx.get_player(poison_target)
            if target and target["alive"]:
                ctx.add_pending_kill(poison_target, "witch_poison")
                ctx.set_flag(witch_id, "witch_poison_used", True)
