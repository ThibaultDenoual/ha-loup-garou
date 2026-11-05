"""Narration on a HA speaker waits for the speaker itself, not for a fixed delay (#57)."""
from __future__ import annotations

import asyncio
import logging
from unittest.mock import MagicMock

import pytest

from homeassistant.core import HomeAssistant, ServiceCall

from custom_components.loup_garou.const import TTS_PHASE_DELAYS
from custom_components.loup_garou.loup_garou import atmosphere as atmosphere_module
from custom_components.loup_garou.loup_garou.atmosphere import Atmosphere
from custom_components.loup_garou.narration import NarrationMessage

SPEAKER = "media_player.salon"
LINE = NarrationMessage(text="La nuit tombe.", lang="fr", delay_key="night_start")


class _RecordingAsyncio:
    """asyncio for the atmosphere module, with sleeps recorded and cut to zero."""

    def __init__(self) -> None:
        self.sleeps: list[float] = []

    def __getattr__(self, name):
        return getattr(asyncio, name)

    async def sleep(self, delay, result=None):
        self.sleeps.append(delay)
        return await asyncio.sleep(0, result)


@pytest.fixture
def clock(monkeypatch) -> _RecordingAsyncio:
    fake = _RecordingAsyncio()
    monkeypatch.setattr(atmosphere_module, "asyncio", fake)
    monkeypatch.setattr(atmosphere_module, "SPEAKER_START_TIMEOUT", 0.2)
    monkeypatch.setattr(atmosphere_module, "SPEAKER_MAX_LINE", 0.2)
    return fake


@pytest.fixture
def calls(hass: HomeAssistant) -> list[ServiceCall]:
    """tts.speak and media_player.play_media, which do nothing to the speaker by themselves."""
    seen: list[ServiceCall] = []

    async def _record(call: ServiceCall) -> None:
        seen.append(call)

    hass.services.async_register("tts", "speak", _record)
    hass.services.async_register("media_player", "play_media", _record)
    return seen


def make_atmosphere(hass: HomeAssistant, audio_source: str = "tts") -> Atmosphere:
    return Atmosphere(
        hass, MagicMock(), [], SPEAKER, "tts.google_translate_say", "fr",
        audio_source=audio_source, audio_output="ha",
    )


async def _until(condition) -> None:
    for _ in range(200):
        if condition():
            return
        await asyncio.sleep(0)
    raise AssertionError("condition never met")


@pytest.mark.parametrize("audio_source", ["tts", "static"])
async def test_the_next_line_waits_until_the_speaker_stops(
    hass: HomeAssistant, clock, calls, audio_source
) -> None:
    hass.config.internal_url = "http://ha.local:8123"
    hass.states.async_set(SPEAKER, "idle")
    atm = make_atmosphere(hass, audio_source)
    msg = atm._narrate("phase.night.start", delay_key="night_start")

    task = asyncio.create_task(atm.speak(msg))
    await _until(lambda: calls)
    hass.states.async_set(SPEAKER, "playing")
    await hass.async_block_till_done()
    await asyncio.sleep(0)
    assert not task.done(), "moved on while the speaker was still playing"

    hass.states.async_set(SPEAKER, "idle")
    await asyncio.wait_for(task, 1)
    # Only the short breath between lines, not the fixed delay or clip length.
    assert clock.sleeps == [atmosphere_module.SPEAKER_GAP]


async def test_a_speaker_that_never_plays_falls_back_to_fixed_delays(
    hass: HomeAssistant, clock, calls, caplog
) -> None:
    hass.states.async_set(SPEAKER, "idle")
    atm = make_atmosphere(hass)

    with caplog.at_level(logging.WARNING):
        await asyncio.wait_for(atm.speak(LINE), 2)
    assert "did not start playing" in caplog.text

    # From now on, no more waiting for a speaker that doesn't report "playing".
    await asyncio.wait_for(atm.speak(LINE), 1)
    assert clock.sleeps == [TTS_PHASE_DELAYS["night_start"]]


async def test_a_speaker_that_worked_once_keeps_being_watched(
    hass: HomeAssistant, clock, calls
) -> None:
    hass.states.async_set(SPEAKER, "idle")
    atm = make_atmosphere(hass)
    atm._speaker_reports_state = True

    await asyncio.wait_for(atm.speak(LINE), 2)  # this one line never plays
    assert atm._speaker_reports_state is True
    assert clock.sleeps == []


async def test_a_busy_or_unknown_speaker_gets_the_fixed_delay(
    hass: HomeAssistant, clock, calls
) -> None:
    atm = make_atmosphere(hass)
    await atm.speak(LINE)  # no state at all
    hass.states.async_set(SPEAKER, "playing")
    await atm.speak(LINE)  # already playing something else
    assert clock.sleeps == [TTS_PHASE_DELAYS["night_start"]] * 2


async def test_a_speaker_stuck_on_playing_cannot_hold_the_game(
    hass: HomeAssistant, clock, calls, caplog
) -> None:
    hass.states.async_set(SPEAKER, "idle")
    atm = make_atmosphere(hass)

    task = asyncio.create_task(atm.speak(LINE))
    await _until(lambda: calls)
    hass.states.async_set(SPEAKER, "playing")
    with caplog.at_level(logging.WARNING):
        await asyncio.wait_for(task, 2)
    assert "still playing" in caplog.text


async def test_a_new_speaker_is_watched_again(hass: HomeAssistant, clock) -> None:
    atm = make_atmosphere(hass)
    atm._speaker_reports_state = False
    atm.update_config({"speaker_entity": "media_player.cuisine"})
    assert atm._speaker_reports_state is None
