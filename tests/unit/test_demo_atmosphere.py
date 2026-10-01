"""The demo presets must exercise the real atmosphere pipeline.

Real engine, real roles, real Atmosphere. Only the HA service calls are mocked —
that is the whole point of the feature: prove lights and TTS fire for every phase.
"""
from __future__ import annotations

import asyncio
import sys
from unittest.mock import MagicMock

for _mod in [
    "homeassistant",
    "homeassistant.core",
    "homeassistant.config_entries",
    "homeassistant.helpers",
    "homeassistant.helpers.entity",
    "homeassistant.components",
    "homeassistant.components.frontend",
    "homeassistant.components.http",
]:
    sys.modules.setdefault(_mod, MagicMock())

from unittest.mock import AsyncMock  # noqa: E402

import pytest  # noqa: E402

from loup_garou.const import LIGHT_SCENES  # noqa: E402
from loup_garou.demo import DEMOS, DemoRunner  # noqa: E402
from loup_garou.game_engine import GameEngine  # noqa: E402
from loup_garou.loup_garou.atmosphere import Atmosphere  # noqa: E402
from loup_garou.roles.loader import load_roles  # noqa: E402

LIGHTS = ["light.living_room", "light.hallway"]

# Scenes the smoke test is meant to prove. The "death" flash is absent on purpose:
# the atmosphere only flashes it for lover grief, scapegoat and hunter shots, which
# the later presets cover — a plain wolf kill or village vote does not.
EXPECTED_SCENES = ("night", "seer_wake", "wolf_wake", "day", "village_win")


@pytest.fixture(autouse=True)
def no_ambience_pauses(monkeypatch):
    """Atmosphere paces itself with real sleeps; tests only care about what fires."""
    real_sleep = asyncio.sleep

    async def instant(delay):
        # Still yield, so fire-and-forget light tasks get a chance to run.
        await real_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", instant)


def build():
    """A real engine + real atmosphere, with only the HA calls faked out."""
    hass = MagicMock()
    hass.services.async_call = AsyncMock()

    engine = GameEngine(roles=load_roles())
    spoken: list[str] = []
    atmosphere = Atmosphere(
        hass=hass,
        engine=engine,
        light_entities=LIGHTS,
        speaker_entity="media_player.living_room",
        tts_engine="tts.home_assistant_cloud",
        language="fr",
        audio_source="tts",
        audio_output="ha",
    )
    atmosphere.wire_events()

    async def record(msg) -> None:
        spoken.append(msg.text)

    atmosphere.speak = record
    return engine, atmosphere, hass, spoken


def light_scenes(hass) -> list[str]:
    """The scene key behind each light.turn_on call, in order.

    Scenes are matched on colour *and* brightness: "wolf_wake" and "death" share
    an RGB value and differ only in brightness.
    """
    by_look = {
        (tuple(v["rgb_color"]), v["brightness"]): k for k, v in LIGHT_SCENES.items()
    }
    scenes = []
    for call in hass.services.async_call.await_args_list:
        if call.args[:2] != ("light", "turn_on"):
            continue
        data = call.args[2]
        look = (tuple(data["rgb_color"]), data["brightness"])
        if look in by_look:
            scenes.append(by_look[look])
    return scenes


async def play(preset="smoke_test"):
    engine, _, hass, spoken = build()
    runner = DemoRunner(engine, DEMOS[preset], action_delay=0, step_delay=0)
    await runner.run()
    return engine, hass, spoken


async def test_demo_lights_every_expected_scene():
    _, hass, _ = await play()
    scenes = light_scenes(hass)
    for expected in EXPECTED_SCENES:
        assert expected in scenes, f"{expected} never lit (got {scenes})"


async def test_demo_lights_reach_both_configured_lights():
    _, hass, _ = await play()
    turned_on = [
        call for call in hass.services.async_call.await_args_list
        if call.args[:2] == ("light", "turn_on")
    ]
    assert turned_on
    for call in turned_on:
        assert call.args[2]["entity_id"] in LIGHTS


async def test_demo_narrates_every_phase_and_role():
    _, _, spoken = await play()
    joined = "\n".join(spoken)
    for fragment in (
        "La nuit tombe",     # phase.night.start
        "Voyante",           # role.seer.wake
        "Loups-garous",      # role.werewolf.wake
        "L'aube se lève",    # phase.day.prelude_death
        "Alice",             # night death announcement
        "Il est temps de voter",
    ):
        assert fragment in joined, f"never narrated {fragment!r}:\n{joined}"


async def test_demo_narrates_the_victory():
    _, _, spoken = await play()
    assert any("gagné" in text for text in spoken), spoken


async def test_demo_ends_in_setup():
    engine, _, _ = await play()
    assert engine.get_public_state()["phase"] == "setup"