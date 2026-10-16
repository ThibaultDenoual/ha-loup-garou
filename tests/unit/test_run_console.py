"""Tests for the dev console auto-driver (run_console.py)."""
import asyncio

from loup_garou.const import Phase
from loup_garou.roles.impl.villager import Villager
from loup_garou.roles.impl.werewolf import Werewolf
from loup_garou.roles.impl.witch import Witch

import run_console
from tests.unit.conftest import make_engine


async def test_witch_save_target_is_player_id_not_tuple():
    """The witch auto-save must target the pending kill's player id, not the tuple."""
    engine = make_engine(Villager, Werewolf, Witch)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "werewolf", "witch"])
    engine._state.pending_kills = [("p2", "wolf_kill")]
    alive = {p["id"]: p for p in engine.get_public_state()["players"] if p["alive"]}

    action = run_console._choose_action_for_role(engine, "witch", alive)

    assert action["save_target"] == "p2"


async def test_witch_auto_action_saves_wolf_victim():
    """The full non-interactive night flow must save the wolf's target and poison
    another player (not the one it just saved)."""
    engine = make_engine(Villager, Werewolf, Witch)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "werewolf", "witch"])

    task = asyncio.create_task(engine.begin_night())
    await asyncio.sleep(0.01)
    await run_console._auto_night_actions(engine)
    await task

    wolf_id = next(
        p.id for p in engine._state.players.values() if p.role_id == "werewolf"
    )
    witch_id = next(p.id for p in engine._state.players.values() if p.role_id == "witch")
    villager_id = next(
        p.id for p in engine._state.players.values() if p.role_id == "villager"
    )
    assert not engine._state.players[wolf_id].alive
    assert engine._state.players[villager_id].alive
    assert engine._state.players[witch_id].alive
    assert engine._state.phase == Phase.GAME_OVER
    assert engine._state.winner == "village"