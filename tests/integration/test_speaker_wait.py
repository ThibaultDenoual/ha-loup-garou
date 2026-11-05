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


# ── #56: what "Test the narration" reports, and what the speaker is sent ─────

ANNOUNCE = 1048576  # MediaPlayerEntityFeature.MEDIA_ANNOUNCE


async def _play_one_line(hass: HomeAssistant, atm: Atmosphere, calls) -> str:
    """Run the narration test while the speaker plays the line."""
    task = asyncio.create_task(atm.test_speaker())
    await _until(lambda: calls)
    hass.states.async_set(SPEAKER, "playing")
    await hass.async_block_till_done()
    hass.states.async_set(SPEAKER, "idle")
    return await asyncio.wait_for(task, 2)


async def test_the_test_reports_a_played_line(hass: HomeAssistant, clock, calls) -> None:
    hass.states.async_set(SPEAKER, "idle")
    assert await _play_one_line(hass, make_atmosphere(hass), calls) == "played"


async def test_the_test_watches_a_speaker_that_failed_before(
    hass: HomeAssistant, clock, calls
) -> None:
    hass.states.async_set(SPEAKER, "idle")
    atm = make_atmosphere(hass)
    atm._speaker_reports_state = False
    assert await _play_one_line(hass, atm, calls) == "played"


async def test_the_test_reports_a_silent_speaker(hass: HomeAssistant, clock, calls) -> None:
    hass.states.async_set(SPEAKER, "idle")
    assert await make_atmosphere(hass).test_speaker() == "not_started"


async def test_the_test_reports_a_speaker_without_state(hass: HomeAssistant, clock, calls) -> None:
    assert await make_atmosphere(hass).test_speaker() == "sent"


async def test_the_test_reports_a_refused_call(hass: HomeAssistant, clock, caplog) -> None:
    async def _refuse(call: ServiceCall) -> None:
        raise RuntimeError("Entity tts.missing not found")

    hass.services.async_register("tts", "speak", _refuse)
    hass.states.async_set(SPEAKER, "idle")
    with caplog.at_level(logging.ERROR):
        assert await make_atmosphere(hass).test_speaker() == "refused"
    assert "refused tts.speak on media_player.salon" in caplog.text


async def test_the_test_reports_no_speaker(hass: HomeAssistant, clock) -> None:
    atm = make_atmosphere(hass)
    atm.update_config({"speaker_entity": ""})
    assert await atm.test_speaker() == "no_speaker"


async def test_a_clip_without_any_ha_address_reports_no_url(
    hass: HomeAssistant, clock, calls
) -> None:
    hass.config.internal_url = None
    hass.config.external_url = None
    hass.states.async_set(SPEAKER, "idle")
    assert await make_atmosphere(hass, "static").test_speaker() == "no_url"
    assert calls == []


@pytest.mark.parametrize("features, announce", [(ANNOUNCE, True), (0, None)])
async def test_clips_are_announcements_when_the_speaker_supports_it(
    hass: HomeAssistant, clock, calls, features, announce
) -> None:
    hass.config.internal_url = "http://192.168.1.10:8123"
    hass.states.async_set(SPEAKER, "idle", {"supported_features": features})
    await _play_one_line(hass, make_atmosphere(hass, "static"), calls)

    data = calls[0].data
    assert data["media_content_id"] == "http://192.168.1.10:8123/loup_garou/audio/fr/night_start.mp3"
    assert data.get("announce") is announce
