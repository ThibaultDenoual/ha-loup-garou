"""The core's game loop, prompts and rule fixes, with no server or UI."""
from __future__ import annotations

import asyncio

import pytest

from loup_garou.const import GameEvent, Phase
from loup_garou.prompts import IllegalAnswer, Prompt, pick
from loup_garou.roles.impl.cupid import Cupid
from loup_garou.roles.impl.hunter import Hunter
from loup_garou.roles.impl.sheriff import Sheriff
from loup_garou.roles.impl.villager import Villager
from loup_garou.roles.impl.werewolf import Werewolf
from tests.unit.conftest import make_engine


async def next_prompt(engine, kind=None):
    for _ in range(1000):
        prompt = engine.prompt
        if prompt is not None and (kind is None or prompt.kind == kind):
            return prompt
        await asyncio.sleep(0)
    raise AssertionError(f"no {kind} prompt; open: {engine.prompt}")


async def run(engine, names, roles):
    await engine.start_game(names, roles)
    task = asyncio.ensure_future(engine.run_game())
    for _ in names:
        await engine.answer((await next_prompt(engine, "reveal")).id, {})
    return task


def causes(engine):
    return [(d["player_id"], d["cause"]) for d in engine.snapshot()["news"]["deaths"]]


# ── Prompt validation ─────────────────────────────────────────────────────────

def prompt(**picks):
    return Prompt(id="q1", kind="test", picks=picks)


def test_single_pick_reads_as_a_value_and_empty_as_none():
    p = prompt(target=pick(["a", "b"], 0, 1))
    assert p.validate({"target": "a"}) == {"target": "a"}
    assert p.validate({"target": ["a"]}) == {"target": "a"}
    assert p.validate({}) == {"target": None}


def test_multi_pick_reads_as_a_list():
    p = prompt(lovers=pick(["a", "b", "c"], 0, 2))
    assert p.validate({"lovers": ["a", "b"]}) == {"lovers": ["a", "b"]}
    assert p.validate({}) == {"lovers": []}


@pytest.mark.parametrize("answer", [
    "nope", [], {"other": "a"}, {"target": "z"}, {"target": 3}, {"target": [1]},
    {"target": ["a", "b"]},
])
def test_illegal_answers_are_refused(answer):
    with pytest.raises(IllegalAnswer):
        prompt(target=pick(["a", "b"], 0, 1)).validate(answer)


def test_required_pick_cannot_be_left_empty():
    with pytest.raises(IllegalAnswer):
        prompt(target=pick(["a"], 1)).validate({})


def test_one_lover_is_not_a_legal_count():
    with pytest.raises(IllegalAnswer):
        prompt(lovers=pick(["a", "b"], 0, 2)).validate({"lovers": ["a"]})


def test_same_option_twice_is_refused():
    with pytest.raises(IllegalAnswer):
        prompt(lovers=pick(["a", "b"], 0, 2)).validate({"lovers": ["a", "a"]})


def test_fallback_answer_is_legal():
    p = prompt(a=pick(["x", "y"], 1), b=pick(["z"], 0, 1))
    p.validate(p.fallback_answer())


# ── Answers ───────────────────────────────────────────────────────────────────

async def test_answer_results():
    engine = make_engine(Villager, Werewolf)
    await engine.start_game(["A", "B"], ["werewolf", "villager"])
    task = asyncio.ensure_future(engine.ask("t", picks={"x": pick(["a"], 1)}))
    p = await next_prompt(engine)

    assert await engine.answer("q999", {"x": "a"}) == "stale"
    assert await engine.answer(p.id, {"x": "b"}) == "illegal"
    assert engine.prompt is p
    assert await engine.answer(p.id, {"x": "a"}) == "accepted"
    assert await engine.answer(p.id, {"x": "a"}) == "duplicate"
    assert await task == {"x": "a"}
    assert engine.prompt is None


async def test_cancelled_ask_closes_its_prompt():
    engine = make_engine(Villager)
    task = asyncio.ensure_future(engine.ask("t"))
    await next_prompt(engine)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    assert engine.prompt is None


async def test_start_game_refuses_unknown_roles():
    with pytest.raises(ValueError):
        await make_engine(Villager).start_game(["A"], ["dragon"])


# ── Game loop ─────────────────────────────────────────────────────────────────

async def test_prompt_opens_only_after_every_wake_handler_finished():
    engine = make_engine(Villager, Werewolf)
    seen = []

    async def slow_narration(_data):
        await asyncio.sleep(0.01)
        seen.append(engine.prompt)

    engine.on(GameEvent.NIGHT_ROLE_WAKE, slow_narration)
    task = await run(engine, ["W", "A", "B", "C"], ["werewolf", "villager", "villager", "villager"])
    await next_prompt(engine, "night_action")
    assert seen == [None]
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


async def test_snapshot_is_published_before_the_phase_is_narrated():
    engine = make_engine(Villager, Werewolf)
    phases = []

    async def on_state(state): phases.append(("state", state["phase"]))
    async def on_phase(data): phases.append(("event", data["phase"]))

    engine.on(GameEvent.STATE_CHANGED, on_state)
    engine.on(GameEvent.PHASE_CHANGED, on_phase)
    await engine.begin_vote()
    assert phases == [("state", Phase.VOTE), ("event", Phase.VOTE)]


async def test_whole_game_ends_with_a_new_game_prompt_then_setup():
    engine = make_engine(Villager, Werewolf)
    task = await run(engine, ["W", "A", "B"], ["werewolf", "villager", "villager"])
    await engine.answer((await next_prompt(engine, "night_action")).id, {"target": "p1"})
    p = await next_prompt(engine, "new_game")
    assert engine.snapshot()["winner"] == "wolves"
    await engine.answer(p.id, {})
    await task
    assert engine.snapshot()["phase"] == Phase.SETUP


async def test_a_ballot_for_a_dead_player_does_not_count():
    engine = make_engine(Villager, Werewolf)
    await engine.start_game(["W", "A", "B", "C"], ["werewolf", "villager", "villager", "villager"])
    engine._state.players["p1"].alive = False
    assert await engine.resolve_vote({"p2": "p1"}) is None
    assert engine.snapshot()["news"]["tie"] is True


async def test_sheriff_is_elected_only_once():
    engine = make_engine(Villager, Werewolf, Sheriff)
    task = await run(engine, ["W", "S", "A", "B", "C"],
                     ["werewolf", "sheriff", "villager", "villager", "villager"])
    await engine.answer((await next_prompt(engine, "night_action")).id, {})
    await engine.answer((await next_prompt(engine, "sheriff_election")).id, {"target": "p2"})
    await engine.answer((await next_prompt(engine, "day_choice")).id, {"next": "night"})
    await engine.answer((await next_prompt(engine, "night_action")).id, {})
    assert (await next_prompt(engine, "day_choice")).kind == "day_choice"
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


# ── Causes of death ───────────────────────────────────────────────────────────

async def test_lover_of_a_voted_out_player_dies_of_grief():
    engine = make_engine(Villager, Werewolf, Cupid)
    await engine.start_game(["W", "L1", "L2", "A", "B", "C"],
                            ["werewolf", "cupid", "villager", "villager", "villager", "villager"])
    engine._make_ctx().add_link("lovers", ["p1", "p2"])
    await engine.resolve_vote({"p0": "p1", "p3": "p1"})
    assert causes(engine) == [("p1", "village_vote"), ("p2", "lover_grief")]


async def test_lover_of_a_wolf_victim_dies_of_grief():
    engine = make_engine(Villager, Werewolf, Cupid)
    await engine.start_game(["W", "L1", "L2", "A", "B", "C"],
                            ["werewolf", "cupid", "villager", "villager", "villager", "villager"])
    ctx = engine._make_ctx()
    ctx.add_link("lovers", ["p1", "p2"])
    ctx.add_pending_kill("p1", "wolf_kill")
    await engine._resolve_night()
    assert causes(engine) == [("p1", "wolf_kill"), ("p2", "lover_grief")]


async def test_hunter_target_at_night_dies_of_the_shot():
    engine = make_engine(Villager, Werewolf, Hunter)
    await engine.start_game(["W", "H", "A", "B", "C"],
                            ["werewolf", "hunter", "villager", "villager", "villager"])
    engine._make_ctx().add_pending_kill("p1", "wolf_kill")
    task = asyncio.ensure_future(engine._resolve_night())
    await engine.answer((await next_prompt(engine, "hunter_shot")).id, {"target": "p2"})
    await task
    assert causes(engine) == [("p1", "wolf_kill"), ("p2", "hunter_shot")]
