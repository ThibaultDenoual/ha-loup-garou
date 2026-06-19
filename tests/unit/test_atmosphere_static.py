"""Unit tests for Atmosphere static TTS mode.

Verifies that:
- Static locale keys resolve to an audio_url in the narrate() call.
- Dynamic messages (player names, roles) call narrate() without audio_url.
- browser and ha modes are unaffected (no audio_url injected).
"""
from __future__ import annotations

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

from unittest.mock import AsyncMock, call, patch  # noqa: E402

import pytest  # noqa: E402

from loup_garou.const import STATIC_AUDIO_MAP  # noqa: E402
from loup_garou.loup_garou.atmosphere import Atmosphere  # noqa: E402
from loup_garou.narration import NarrationMessage  # noqa: E402

_SLEEP = "loup_garou.loup_garou.atmosphere.asyncio.sleep"


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_server_mock():
    server = MagicMock()
    server.narrate = AsyncMock()
    return server


def make_atmosphere(audio_source: str, audio_output: str = "browser", lang: str = "fr") -> tuple:
    hass = MagicMock()
    hass.services.async_call = AsyncMock()
    engine = MagicMock()
    engine.on = MagicMock()
    server = make_server_mock()
    locale = {k: f"text for {k}" for k in STATIC_AUDIO_MAP}
    locale["phase.day.start_with_death"] = "{name} a été dévoré. C'était {article} {role}."
    locale["phase.vote.result"] = "{name} éliminé. C'était {article} {role}."
    locale["ui.misc.plain"] = "Texte simple"
    atm = Atmosphere(
        hass=hass,
        engine=engine,
        light_entities=[],
        speaker_entity="media_player.test",
        tts_engine="tts.test",
        language=lang,
        locale=locale,
        audio_source=audio_source,
        audio_output=audio_output,
        server=server,
    )
    return atm, server


# ═══════════════════════════════════════════════════════════════════════════════
# Static mode — static locale keys
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("locale_key,stem", list(STATIC_AUDIO_MAP.items()))
async def test_static_mode_sends_audio_url_for_static_key(locale_key, stem):
    atm, server = make_atmosphere("static", lang="fr")
    await atm.speak(atm._narrate(locale_key, delay_key="role_wake"))
    server.narrate.assert_awaited_once()
    msg = server.narrate.call_args[0][0]
    assert msg.audio_url == f"/loup_garou/audio/fr/{stem}.mp3"


async def test_static_mode_audio_url_uses_language():
    atm, server = make_atmosphere("static", lang="en")
    await atm.speak(atm._narrate("phase.night.start", delay_key="night_start"))
    msg = server.narrate.call_args[0][0]
    assert msg.audio_url == "/loup_garou/audio/en/night_start.mp3"


# ═══════════════════════════════════════════════════════════════════════════════
# Static mode — dynamic messages (no pre-recorded file)
# ═══════════════════════════════════════════════════════════════════════════════

async def test_static_mode_no_audio_url_for_parameterized_key():
    """Parameterized messages interpolate at runtime, so they never get a static MP3."""
    atm, server = make_atmosphere("static")
    await atm.speak(atm._narrate(
        "phase.day.start_with_death",
        delay_key="day_with_death",
        name="Alice", article="un", role="Loup",
    ))
    server.narrate.assert_awaited_once()
    msg = server.narrate.call_args[0][0]
    assert msg.audio_url is None
    assert "Alice" in msg.text


async def test_static_mode_no_audio_url_for_non_static_key():
    """A fixed-text key absent from STATIC_AUDIO_MAP resolves text but no audio."""
    atm, server = make_atmosphere("static")
    await atm.speak(atm._narrate("ui.misc.plain", delay_key="role_wake"))
    server.narrate.assert_awaited_once()
    msg = server.narrate.call_args[0][0]
    assert msg.audio_url is None
    assert msg.text == "Texte simple"


# ═══════════════════════════════════════════════════════════════════════════════
# Browser mode — never sends audio_url
# ═══════════════════════════════════════════════════════════════════════════════

async def test_browser_mode_never_sends_audio_url():
    atm, server = make_atmosphere("tts", "browser")
    await atm.speak(atm._narrate("phase.night.start", delay_key="night_start"))
    server.narrate.assert_awaited_once()
    msg = server.narrate.call_args[0][0]
    assert msg.audio_url is None


# ═══════════════════════════════════════════════════════════════════════════════
# HA mode — does not call server.narrate at all
# ═══════════════════════════════════════════════════════════════════════════════

async def test_ha_mode_does_not_call_server_narrate():
    atm, server = make_atmosphere("tts", "ha")
    with MagicMock() as _sleep_patch:
        import asyncio as _aio
        orig_sleep = _aio.sleep
        _aio.sleep = AsyncMock()
        try:
            await atm.speak(atm._narrate("phase.night.start", delay_key="night_start"))
        finally:
            _aio.sleep = orig_sleep
    server.narrate.assert_not_awaited()


# ═══════════════════════════════════════════════════════════════════════════════
# Integration: atmosphere event handlers route static keys correctly
# ═══════════════════════════════════════════════════════════════════════════════

async def test_on_phase_changed_night_sends_audio_url():
    atm, server = make_atmosphere("static")
    with patch(_SLEEP, new_callable=AsyncMock):
        await atm._on_phase_changed({"phase": "night"})
    server.narrate.assert_awaited_once()
    msg = server.narrate.call_args[0][0]
    assert msg.audio_url == "/loup_garou/audio/fr/night_start.mp3"


async def test_on_vote_started_sends_audio_url():
    atm, server = make_atmosphere("static")
    await atm._on_vote_started({})
    server.narrate.assert_awaited_once()
    msg = server.narrate.call_args[0][0]
    assert msg.audio_url == "/loup_garou/audio/fr/vote_start.mp3"


async def test_on_role_wake_sends_audio_url_for_werewolf():
    atm, server = make_atmosphere("static")
    with patch(_SLEEP, new_callable=AsyncMock):
        await atm._on_role_wake({"role": "werewolf"})
    server.narrate.assert_awaited_once()
    msg = server.narrate.call_args[0][0]
    assert msg.audio_url == "/loup_garou/audio/fr/role_werewolf_wake.mp3"


async def test_on_role_sleep_sends_audio_url_for_seer():
    atm, server = make_atmosphere("static")
    with patch(_SLEEP, new_callable=AsyncMock):
        await atm._on_role_sleep({"role": "seer"})
    server.narrate.assert_awaited_once()
    msg = server.narrate.call_args[0][0]
    assert msg.audio_url == "/loup_garou/audio/fr/role_seer_sleep.mp3"


async def test_on_game_over_wolves_win_sends_audio_url():
    atm, server = make_atmosphere("static")
    with patch(_SLEEP, new_callable=AsyncMock):
        await atm._on_game_over({"winner": "wolves"})
    server.narrate.assert_awaited_once()
    msg = server.narrate.call_args[0][0]
    assert msg.audio_url == "/loup_garou/audio/fr/game_over_wolves.mp3"


async def test_on_day_started_death_prelude_sends_audio_url():
    """prelude_death is a parameterless key — it gets a static audio_url."""
    atm, server = make_atmosphere("static")
    atm._engine.get_public_state.return_value = {
        "players": [{"id": "p0", "name": "Alice", "role_id": "werewolf", "alive": False}]
    }
    with patch(_SLEEP, new_callable=AsyncMock):
        await atm._on_day_started({"eliminated": ["p0"]})
    # First call is the prelude, second is the per-victim announcement
    assert server.narrate.await_count == 2
    prelude_msg = server.narrate.call_args_list[0][0][0]
    assert prelude_msg.audio_url == "/loup_garou/audio/fr/day_prelude_death.mp3"
