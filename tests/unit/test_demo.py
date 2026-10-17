"""Tests for the scripted demo games — real engine, real roles, no mocks."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from loup_garou.const import GameEvent, Phase
from loup_garou.demo import (
    DEMOS,
    DemoRunner,
    DemoScript,
    DemoStep,
    STEP_NIGHT,
    STEP_VOTE,
    list_demos,
)
from loup_garou.game_engine import GameEngine
from loup_garou.roles.loader import load_roles

LOCALES_DIR = (
    Path(__file__).parent.parent.parent / "custom_components" / "loup_garou" / "locales"
)


def make_engine() -> GameEngine:
    return GameEngine(roles=load_roles())


def variant(key: str, **overrides) -> DemoScript:
    """A copy of the smoke test with selected fields replaced."""
    base = DEMOS["smoke_test"]
    fields = {
        "key": key,
        "players": base.players,
        "night_actions": base.night_actions,
        "interrupt_actions": base.interrupt_actions,
        "steps": base.steps,
    }
    fields.update(overrides)
    return DemoScript(**fields)


class Recorder:
    """Captures the engine event stream so tests can assert the whole script ran."""

    def __init__(self, engine: GameEngine) -> None:
        self.events: list[tuple[str, dict]] = []
        self.winners: list[str] = []
        for event in GameEvent:
            engine.on(event, self._handler(event))
        engine.on(GameEvent.GAME_OVER, self._on_winner)

    def _handler(self, event: GameEvent):
        async def handler(data: dict) -> None:
            self.events.append((str(event), data))
        return handler

    async def _on_winner(self, data: dict) -> None:
        self.winners.append(data["winner"])

    def types(self) -> list[str]:
        return [name for name, _ in self.events]

    def of(self, event: GameEvent) -> list[dict]:
        return [d for name, d in self.events if name == str(event)]

    def wakes(self) -> list[str]:
        return [d["role"] for d in self.of(GameEvent.NIGHT_ROLE_WAKE)]

    def sleeps(self) -> list[str]:
        return [d["role"] for d in self.of(GameEvent.NIGHT_ROLE_SLEEP)]

    def eliminations(self) -> list[tuple[str, str]]:
        return [(d["name"], d["cause"]) for d in self.of(GameEvent.PLAYER_ELIMINATED)]


async def play(script: DemoScript | None = None, **kwargs):
    """Run a demo to completion with no pacing delays."""
    return await play_script(make_engine(), script, **kwargs)


async def play_script(engine: GameEngine, script: DemoScript | None = None, **kwargs):
    script = script or DEMOS["smoke_test"]
    rec = Recorder(engine)
    steps: list[str] = []
    runner = DemoRunner(
        engine,
        script,
        action_delay=0,
        step_delay=0,
        on_step=lambda s: steps.append(s),
        **kwargs,
    )
    await runner.run()
    return engine, rec, steps


# ── The smoke-test preset ────────────────────────────────────────────────────


async def test_smoke_test_ends_with_village_win():
    _, rec, _ = await play()
    assert rec.winners == ["village"]


async def test_smoke_test_walks_every_phase():
    _, rec, _ = await play()
    assert [d["phase"] for d in rec.of(GameEvent.PHASE_CHANGED)] == [
        Phase.ROLE_REVEAL,
        Phase.NIGHT,
        Phase.DAY,
        Phase.VOTE,
        Phase.GAME_OVER,
        Phase.SETUP,
    ]


async def test_smoke_test_wakes_seer_then_werewolf():
    _, rec, _ = await play()
    # The seer wakes twice: once to pick a target, once to acknowledge the result.
    assert rec.wakes() == ["seer", "seer", "werewolf"]
    assert rec.sleeps() == ["seer", "werewolf"]


async def test_smoke_test_seer_learns_the_wolf():
    _, rec, _ = await play()
    results = [d["result"] for d in rec.of(GameEvent.NIGHT_ROLE_WAKE) if "result" in d]
    assert results == [{"player_id": "p1", "role_id": "werewolf"}]


async def test_smoke_test_eliminations_and_causes():
    _, rec, _ = await play()
    assert rec.eliminations() == [("Alice", "wolf_kill"), ("Bob", "village_vote")]


async def test_smoke_test_day_announcement_lists_the_night_death():
    _, rec, _ = await play()
    # Only one day: the vote ends the game, so no second day is announced.
    assert [d["eliminated"] for d in rec.of(GameEvent.DAY_STARTED)] == [["p0"]]


async def test_smoke_test_vote_eliminates_the_wolf():
    _, rec, _ = await play()
    assert [d["eliminated"] for d in rec.of(GameEvent.VOTE_RESOLVED)] == ["p1"]
    assert [d["tie"] for d in rec.of(GameEvent.VOTE_RESOLVED)] == [False]


async def test_smoke_test_ends_in_setup_with_no_winner():
    engine, _, _ = await play()
    state = engine.get_public_state()
    assert state["phase"] == Phase.SETUP
    assert state["winner"] is None
    assert state["players"] == []


async def test_smoke_test_reports_its_steps():
    _, _, steps = await play()
    assert steps == [
        "game_started",
        "night_start",
        "role_action:seer",
        "role_action:seer",
        "role_action:werewolf",
        "vote_cast",
        "finished",
    ]


# ── The other two presets ─────────────────────────────────────────────────────


async def test_wolves_win_uses_a_different_kill_target_each_night():
    _, rec, _ = await play(DEMOS["wolves_win"])
    assert rec.winners == ["wolves"]
    # Alice (night 1) and Carol (night 2) are the two wolf kills; Dave is the vote.
    assert rec.eliminations() == [
        ("Alice", "wolf_kill"),
        ("Dave", "village_vote"),
        ("Carol", "wolf_kill"),
    ]


async def test_wolves_win_step_actions_override_the_script_default():
    """Night 2 retargets the kill, because Alice is already dead by then."""
    script = DEMOS["wolves_win"]
    assert script.night_actions["werewolf"]["target"] == "Alice"
    night_steps = [s for s in script.steps if s.kind == STEP_NIGHT]
    assert night_steps[0].actions is None
    assert night_steps[1].actions == {"werewolf": {"target": "Carol"}}


async def test_wolves_win_seer_wakes_on_both_nights():
    _, rec, _ = await play(DEMOS["wolves_win"])
    # The seer wakes twice per night: once to pick a target, once to ack the result.
    assert rec.wakes() == ["seer", "seer", "werewolf"] * 2


async def test_lovers_win_links_cupid_to_a_player_and_wins():
    """Cupid must be a lover himself — a surviving bystander blocks the win."""
    _, rec, steps = await play(DEMOS["lovers_win"])
    assert rec.winners == ["lovers"]
    assert rec.eliminations() == [
        ("Carol", "wolf_kill"),
        ("Bob", "village_vote"),
    ]
    assert "role_action:cupid" in steps


async def test_lovers_win_cupid_is_one_of_the_lovers():
    """Cupid's check needs *no other* player alive, so he cannot sit it out."""
    assert DEMOS["lovers_win"].night_actions["cupid"]["lovers"] == ["Cupid", "Alice"]
    assert "Cupid" in DEMOS["lovers_win"].names


async def test_a_lovers_preset_with_a_bystanding_cupid_ends_as_village():
    """Regression guard: Cupid alive and unlinked lets the villager claim the win."""
    script = variant(
        "lovers_win",
        night_actions={
            "cupid": {"lovers": ["Alice", "Carol"]},
            "werewolf": {"target": "Dave"},
        },
        players=(
            ("Bob", "werewolf"),
            ("Cupid", "cupid"),
            ("Alice", "villager"),
            ("Carol", "villager"),
            ("Dave", "villager"),
        ),
        steps=(
            DemoStep(STEP_NIGHT),
            DemoStep(STEP_VOTE, votes={"Alice": "Bob", "Carol": "Bob", "Cupid": "Bob"}),
        ),
    )
    _, rec, _ = await play(script)
    assert rec.winners == ["village"]


# ── Script plumbing ──────────────────────────────────────────────────────────


async def test_names_in_script_are_resolved_to_player_ids():
    engine = make_engine()
    runner = DemoRunner(engine, DEMOS["smoke_test"])
    await engine.start_game(DEMOS["smoke_test"].names, DEMOS["smoke_test"].role_ids)
    # Players are p0..p4 in roster order.
    assert runner._resolve({"target": "Bob"}) == {"target": "p1"}
    assert runner._resolve({"lovers": ["Alice", "Eve"]}) == {"lovers": ["p0", "p4"]}
    assert runner._resolve_votes({"Carol": "Bob"}) == {"p2": "p1"}


async def test_unknown_player_names_are_left_alone():
    engine = make_engine()
    runner = DemoRunner(engine, DEMOS["smoke_test"])
    await engine.start_game(DEMOS["smoke_test"].names, DEMOS["smoke_test"].role_ids)
    assert runner._resolve({"target": "Nobody"}) == {"target": "Nobody"}
    assert runner._resolve_votes({"Ghost": "Bob"}) == {}
    assert runner._resolve_votes({"Carol": "Ghost"}) == {}


async def test_non_string_action_values_pass_through():
    engine = make_engine()
    runner = DemoRunner(engine, DEMOS["smoke_test"])
    await engine.start_game(DEMOS["smoke_test"].names, DEMOS["smoke_test"].role_ids)
    assert runner._resolve({"count": 2, "ok": True, "none": None}) == {
        "count": 2,
        "ok": True,
        "none": None,
    }


async def test_wake_for_a_role_nothing_is_waiting_on_is_ignored(caplog):
    engine = make_engine()
    runner = DemoRunner(engine, DEMOS["smoke_test"], action_delay=0, step_delay=0)
    engine.on(GameEvent.NIGHT_ROLE_WAKE, runner._on_night_role_wake)
    await engine._emit(GameEvent.NIGHT_ROLE_WAKE, {"role": "elder"})
    await asyncio.sleep(0.01)
    assert "nothing pending for role elder" in caplog.text


async def test_unknown_step_kind_is_skipped():
    _, rec, _ = await play(variant("bogus", steps=(DemoStep("teleport"),)))
    assert str(GameEvent.NIGHT_ROLE_WAKE) not in rec.types()


async def test_role_without_a_scripted_action_gets_an_empty_one():
    """An unanswered role must not stall the night."""
    _, rec, _ = await play(
        variant("partial", night_actions={}, steps=(DemoStep(STEP_NIGHT),))
    )
    assert rec.wakes() == ["seer", "werewolf"]
    assert rec.eliminations() == []
    assert rec.of(GameEvent.NIGHT_RESOLVED)[0]["eliminated"] == []


async def test_script_with_no_steps_only_deals_roles():
    _, rec, _ = await play(variant("roles_only", steps=()))
    assert rec.of(GameEvent.GAME_STARTED)
    assert rec.winners == []


async def test_on_step_may_be_a_coroutine():
    engine = make_engine()
    seen: list[str] = []

    async def on_step(step: str) -> None:
        seen.append(step)

    runner = DemoRunner(
        engine,
        variant("async_cb"),
        action_delay=0,
        step_delay=0,
        on_step=on_step,
    )
    await runner.run()
    assert seen[0] == "game_started"
    assert seen[-1] == "finished"


# ── Cancellation ─────────────────────────────────────────────────────────────


async def test_cancel_stops_the_demo_and_resets_the_engine():
    engine = make_engine()
    rec = Recorder(engine)
    runner = DemoRunner(engine, DEMOS["smoke_test"], action_delay=0.05, step_delay=30)
    task = asyncio.create_task(runner.run())
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert engine.get_public_state()["phase"] == Phase.SETUP
    assert rec.winners == []


async def test_off_removes_a_handler():
    engine = make_engine()
    calls: list[dict] = []

    async def handler(data: dict) -> None:
        calls.append(data)

    engine.on(GameEvent.PHASE_CHANGED, handler)
    await engine.start_game(["A"], ["villager"])
    assert len(calls) == 1

    calls.clear()
    engine.off(GameEvent.PHASE_CHANGED, handler)
    await engine._emit(GameEvent.PHASE_CHANGED, {"phase": Phase.NIGHT})
    assert calls == []

    # Removing a handler that was never registered is a no-op.
    engine.off(GameEvent.PHASE_CHANGED, handler)
    engine.off(GameEvent.VOTE_STARTED, handler)


async def test_cancel_detaches_the_wake_listener():
    """A cancelled demo must not keep answering role wakes."""
    engine = make_engine()
    runner = DemoRunner(engine, DEMOS["smoke_test"], action_delay=0.05, step_delay=30)
    task = asyncio.create_task(runner.run())
    await asyncio.sleep(0.05)
    runner.cancel()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # A fresh demo over the same engine still plays cleanly, so the cancelled
    # runner left no listener behind to double-answer the seer.
    _, rec, _ = await play_script(engine, DEMOS["smoke_test"])
    assert rec.wakes() == ["seer", "seer", "werewolf"]
    assert rec.winners == ["village"]


# ── Preset registry ──────────────────────────────────────────────────────────


def test_demo_presets_are_listed_for_the_ui():
    assert list_demos() == [
        {"key": "smoke_test", "label_key": "demo.preset.smoke_test"},
        {"key": "wolves_win", "label_key": "demo.preset.wolves_win"},
        {"key": "lovers_win", "label_key": "demo.preset.lovers_win"},
    ]


# Each preset exists to show one ending, so pin which ending it reaches.
EXPECTED_WINNER = {
    "smoke_test": "village",
    "wolves_win": "wolves",
    "lovers_win": "lovers",
}


@pytest.mark.parametrize("preset", sorted(DEMOS))
def test_every_preset_is_well_formed(preset):
    script = DEMOS[preset]
    assert script.key == preset
    assert len(script.names) == len(script.role_ids)
    assert len(set(script.names)) == len(script.names), "player names must be unique"
    assert script.steps, "a preset needs at least one step"
    for step in script.steps:
        assert step.kind in (STEP_NIGHT, STEP_VOTE)
        if step.kind == STEP_VOTE:
            assert step.votes, "a vote step needs votes"
            assert set(step.votes) <= set(script.names)
            assert set(step.votes.values()) <= set(script.names)


@pytest.mark.parametrize("preset", sorted(DEMOS))
def test_every_preset_reaches_a_winner(preset):
    """Every preset must be a complete game, not a truncated one."""
    _, rec, _ = asyncio.run(play(DEMOS[preset]))
    assert rec.winners, f"preset {preset} never reached a win condition"


@pytest.mark.parametrize("preset", sorted(DEMOS))
def test_every_preset_reaches_its_intended_ending(preset):
    """A preset that quietly ends the wrong way is not validating what it claims."""
    _, rec, _ = asyncio.run(play(DEMOS[preset]))
    assert rec.winners == [EXPECTED_WINNER[preset]]


def test_all_three_win_conditions_have_a_preset():
    """Guards the goal of demo mode: one runnable game per win condition."""
    assert set(EXPECTED_WINNER.values()) == {"village", "wolves", "lovers"}
    assert set(EXPECTED_WINNER) == set(DEMOS)


@pytest.mark.parametrize("preset", sorted(DEMOS))
def test_every_preset_uses_only_real_roles(preset):
    assert set(DEMOS[preset].role_ids) <= set(load_roles())


# ── Locale coverage ──────────────────────────────────────────────────────────


def read_locale(lang: str) -> dict:
    with open(LOCALES_DIR / f"{lang}.json") as f:
        return json.load(f)


@pytest.mark.parametrize("lang", ["fr", "en"])
@pytest.mark.parametrize("preset", sorted(DEMOS))
def test_preset_label_is_localised(lang, preset):
    assert read_locale(lang).get(f"demo.preset.{preset}")


@pytest.mark.parametrize("lang", ["fr", "en"])
def test_demo_ui_strings_are_localised(lang):
    locale = read_locale(lang)
    for key in (
        "demo.title",
        "demo.hint",
        "demo.preset_label",
        "demo.run",
        "demo.stop",
        "demo.running",
        "demo.finished",
        "demo.stopped",
        "demo.failed",
        "demo.rejected.game_in_progress",
        "demo.rejected.already_running",
        "demo.rejected.unknown_preset",
    ):
        assert locale.get(key), f"Missing {key} in {lang}"


@pytest.mark.parametrize("lang", ["fr", "en"])
def test_every_emitted_step_has_a_label(lang):
    """The runner emits these step names, so each needs a locale string."""
    locale = read_locale(lang)
    for step in ("game_started", "night_start", "vote_cast"):
        assert locale.get(f"demo.step.{step}"), step
    for script in DEMOS.values():
        for role_id in script.night_actions:
            assert locale.get(f"demo.step.role_action:{role_id}"), role_id


@pytest.mark.parametrize("lang", ["fr", "en"])
def test_launcher_references_only_existing_locale_keys(lang):
    """Every demo.* key the launcher asks for must resolve."""
    locale = read_locale(lang)
    html = (
        Path(__file__).parent.parent.parent
        / "custom_components" / "loup_garou" / "www" / "game" / "launcher.html"
    ).read_text()
    assert "demo.step.${msg.data.step}" in html
    assert "demo.rejected.${msg.data.reason}" in html
    for role_id in ("seer", "werewolf", "witch", "cupid", "alpha_wolf", "hunter"):
        assert locale.get(f"demo.step.role_action:{role_id}"), role_id