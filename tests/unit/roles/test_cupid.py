"""Tests for Cupid role."""
import pytest

from loup_garou.game_engine import GameEngine
from loup_garou.roles.impl.villager import Villager
from loup_garou.roles.impl.werewolf import Werewolf
from loup_garou.roles.impl.cupid import Cupid
from tests.unit.conftest import make_engine, make_ctx


async def test_cupid_has_night_action():
    assert Cupid.has_night_action is True


async def test_cupid_priority_is_first():
    from loup_garou.roles.impl.seer import Seer
    assert Cupid.night_priority < Seer.night_priority


async def test_cupid_links_two_lovers_on_night_1():
    engine = make_engine(Villager, Werewolf, Cupid)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "villager", "cupid"])
    state = engine._state
    state.night_number = 1
    alice_id = next(p.id for p in state.players.values() if p.name == "Alice")
    bob_id = next(p.id for p in state.players.values() if p.name == "Bob")

    ctx = make_ctx(state)
    role = engine._roles["cupid"]
    await role.on_night_action(ctx, {"lovers": [alice_id, bob_id]})

    assert state.player_links.get("lovers") == [alice_id, bob_id]


async def test_cupid_does_not_link_after_night_1():
    engine = make_engine(Villager, Werewolf, Cupid)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "villager", "cupid"])
    state = engine._state
    state.night_number = 2
    alice_id = next(p.id for p in state.players.values() if p.name == "Alice")
    bob_id = next(p.id for p in state.players.values() if p.name == "Bob")

    ctx = make_ctx(state)
    role = engine._roles["cupid"]
    await role.on_night_action(ctx, {"lovers": [alice_id, bob_id]})

    assert "lovers" not in state.player_links


async def test_cupid_should_wake_only_on_night_1():
    """should_wake returns True on night 1 and False on subsequent nights."""
    engine = make_engine(Villager, Werewolf, Cupid)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "villager", "cupid"])
    state = engine._state
    role = engine._roles["cupid"]

    state.night_number = 1
    assert role.should_wake(make_ctx(state)) is True

    state.night_number = 2
    assert role.should_wake(make_ctx(state)) is False

    state.night_number = 5
    assert role.should_wake(make_ctx(state)) is False


async def test_cupid_not_woken_on_night_2():
    """Full engine integration: Cupid produces no NIGHT_ROLE_WAKE on night 2."""
    import asyncio

    engine = make_engine(Villager, Werewolf, Cupid)
    await engine.start_game(
        ["Alice", "Bob", "Carol", "Dave"],
        ["villager", "villager", "cupid", "werewolf"],
    )
    state = engine._state
    players = list(state.players.values())
    wolf = next(p for p in players if p.role_id == "werewolf")
    villager = next(p for p in players if p.role_id == "villager")

    wakes: list[str] = []
    engine.on("GameEvent.NIGHT_ROLE_WAKE", lambda d: None)  # placeholder

    from loup_garou.const import GameEvent

    async def record_wake(data):
        wakes.append(data["role"])

    engine.on(GameEvent.NIGHT_ROLE_WAKE, record_wake)

    # Night 1 — cupid should wake
    night1 = asyncio.create_task(engine.begin_night())
    await asyncio.sleep(0)  # let the task start and reach the first await fut

    # Submit cupid action (link two players)
    cupid_players = [p for p in players if p.role_id != "werewolf"]
    await engine.submit_night_action("cupid", {"lovers": [cupid_players[0].id, cupid_players[1].id]})
    await asyncio.sleep(0)

    # Submit wolf action
    await engine.submit_night_action("werewolf", {"target": villager.id})
    await night1

    assert "cupid" in wakes, "Cupid should wake on night 1"

    # Night 2 — cupid must NOT wake
    wakes.clear()
    # Ensure a villager is still alive for wolf to target
    alive_villagers = [p for p in state.players.values() if p.alive and p.role_id != "werewolf"]

    night2 = asyncio.create_task(engine.begin_night())
    await asyncio.sleep(0)

    # Only wolf wakes; submit wolf action
    await engine.submit_night_action("werewolf", {"target": alive_villagers[0].id})
    await night2

    assert "cupid" not in wakes, "Cupid must NOT wake on night 2"


async def test_lover_death_triggers_partner_elimination():
    engine = make_engine(Villager, Werewolf, Cupid)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "villager", "cupid"])
    state = engine._state
    alice_id = next(p.id for p in state.players.values() if p.name == "Alice")
    bob_id = next(p.id for p in state.players.values() if p.name == "Bob")
    state.player_links["lovers"] = [alice_id, bob_id]

    ctx = make_ctx(state)
    role = engine._roles["cupid"]
    decision = await role.on_before_eliminate(ctx, alice_id, "wolf_kill")

    assert bob_id in decision.add_eliminations


async def test_lover_death_no_extra_if_partner_already_dead():
    engine = make_engine(Villager, Werewolf, Cupid)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "villager", "cupid"])
    state = engine._state
    alice_id = next(p.id for p in state.players.values() if p.name == "Alice")
    bob_id = next(p.id for p in state.players.values() if p.name == "Bob")
    state.player_links["lovers"] = [alice_id, bob_id]
    state.players[bob_id].alive = False

    ctx = make_ctx(state)
    role = engine._roles["cupid"]
    decision = await role.on_before_eliminate(ctx, alice_id, "wolf_kill")

    assert decision.add_eliminations == []


async def test_lovers_win_when_only_two_left():
    engine = make_engine(Villager, Werewolf, Cupid)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "villager", "cupid"])
    state = engine._state
    alice_id = next(p.id for p in state.players.values() if p.name == "Alice")
    bob_id = next(p.id for p in state.players.values() if p.name == "Bob")
    carol_id = next(p.id for p in state.players.values() if p.name == "Carol")
    state.player_links["lovers"] = [alice_id, bob_id]
    state.players[carol_id].alive = False

    ctx = make_ctx(state)
    role = engine._roles["cupid"]
    result = await role.check_win(ctx)
    assert result == "lovers"


async def test_lovers_do_not_win_while_others_alive():
    engine = make_engine(Villager, Werewolf, Cupid)
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "villager", "cupid"])
    state = engine._state
    alice_id = next(p.id for p in state.players.values() if p.name == "Alice")
    bob_id = next(p.id for p in state.players.values() if p.name == "Bob")
    state.player_links["lovers"] = [alice_id, bob_id]

    ctx = make_ctx(state)
    role = engine._roles["cupid"]
    result = await role.check_win(ctx)
    assert result is None
