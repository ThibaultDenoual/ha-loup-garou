"""Unit tests for Atmosphere — TTS modes, phase delays, event handlers."""
from __future__ import annotations

import sys
from unittest.mock import MagicMock

# Stub homeassistant before importing anything that pulls it in.
# The test environment does not have the full HA package installed.
# Each sub-module must be a *separate* MagicMock so Python's import
# machinery treats them as distinct modules (not attributes of a parent mock).
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

import asyncio
from unittest.mock import AsyncMock, patch  # noqa: E402 (after sys.modules setup)

import pytest

from loup_garou.const import GameEvent, TTS_PHASE_DELAYS
from loup_garou.loup_garou.atmosphere import Atmosphere


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_hass():
    hass = MagicMock()
    hass.services.async_call = AsyncMock()
    return hass


def make_engine_stub():
    engine = MagicMock()
    engine._handlers: dict = {}

    def on(event, handler):
        engine._handlers.setdefault(event, []).append(handler)

    engine.on = on
    engine.get_public_state = MagicMock(return_value={
        "players": [
            {"id": "p0", "name": "Alice", "role_id": "villager", "alive": True},
            {"id": "p1", "name": "Bob",   "role_id": "werewolf", "alive": True},
        ]
    })
    return engine


_LOCALE = {
    "phase.night.start": "La nuit tombe.",
    "phase.day.start_no_death": "Personne n'est mort.",
    "phase.day.start_with_death": "{name} était {article} {role}.",
    "phase.vote.start": "Le vote commence.",
    "phase.vote.tie": "Égalité.",
    "phase.vote.result": "{name} était {article} {role}.",
    "phase.game_over.wolves_win": "Les loups ont gagné.",
    "phase.game_over.village_win": "Le village a gagné.",
    "phase.game_over.lovers_win": "Les amoureux ont gagné.",
    "role.werewolf.wake": "Loups, réveillez-vous.",
    "role.werewolf.sleep": "Loups, dormez.",
    "role.seer.wake": "Voyante, réveillez-vous.",
    "role.seer.sleep": "Voyante, dormez.",
    "role.werewolf.name": "loup-garou",
    "role.villager.name": "villageois",
    "role.seer.name": "voyante",
    "elimination.hunter_shot": "{name} tire sur {target}.",
    "elimination.lover_grief": "{name} meurt de chagrin.",
    "elimination.scapegoat": "{name} était {article} {role}.",
    "article.male": "a",
}


def make_atmosphere(
    *,
    tts_mode="ha",
    speaker="media_player.sonos",
    server=None,
    language="fr",
):
    hass = make_hass()
    engine = make_engine_stub()
    atm = Atmosphere(
        hass=hass,
        engine=engine,
        light_entities=["light.salon"],
        speaker_entity=speaker,
        tts_engine="tts.home_assistant_cloud",
        language=language,
        locale=_LOCALE,
        tts_mode=tts_mode,
        server=server,
    )
    return atm, hass, engine


# ═══════════════════════════════════════════════════════════════════════════════
# TTS_PHASE_DELAYS completeness
# ═══════════════════════════════════════════════════════════════════════════════

def test_tts_phase_delays_has_all_keys():
    expected = {
        "night_start", "role_wake", "role_sleep",
        "day_no_death", "day_with_death",
        "vote_start", "vote_result",
        "elimination_live", "game_over",
    }
    assert set(TTS_PHASE_DELAYS.keys()) == expected


def test_tts_phase_delays_are_positive_floats():
    for key, value in TTS_PHASE_DELAYS.items():
        assert isinstance(value, float), f"{key} is not a float"
        assert value > 0, f"{key} must be > 0"


# ═══════════════════════════════════════════════════════════════════════════════
# speak() — HA mode
# ═══════════════════════════════════════════════════════════════════════════════

async def test_speak_ha_mode_calls_tts_service():
    atm, hass, _ = make_atmosphere(tts_mode="ha")
    with patch("loup_garou.loup_garou.atmosphere.asyncio.sleep", new_callable=AsyncMock):
        await atm.speak("Bonjour", delay_key="role_wake")
    hass.services.async_call.assert_awaited_once()
    call_args = hass.services.async_call.call_args[0]
    assert call_args[0] == "tts"
    assert call_args[1] == "speak"
    assert call_args[2]["message"] == "Bonjour"


async def test_speak_ha_mode_sleeps_for_delay_key():
    atm, _, _ = make_atmosphere(tts_mode="ha")
    sleep_calls = []
    async def fake_sleep(seconds):
        sleep_calls.append(seconds)
    with patch("loup_garou.loup_garou.atmosphere.asyncio.sleep", fake_sleep):
        await atm.speak("Hello", delay_key="night_start")
    assert sleep_calls == [TTS_PHASE_DELAYS["night_start"]]


async def test_speak_ha_mode_unknown_delay_key_uses_default():
    atm, _, _ = make_atmosphere(tts_mode="ha")
    sleep_calls = []
    async def fake_sleep(seconds):
        sleep_calls.append(seconds)
    with patch("loup_garou.loup_garou.atmosphere.asyncio.sleep", fake_sleep):
        await atm.speak("Hello", delay_key="nonexistent_key")
    assert sleep_calls == [2.5]


async def test_speak_ha_mode_each_delay_key_uses_correct_duration():
    for key, expected_delay in TTS_PHASE_DELAYS.items():
        atm, _, _ = make_atmosphere(tts_mode="ha")
        sleep_calls = []
        async def fake_sleep(s, _key=key):
            sleep_calls.append(s)
        with patch("loup_garou.loup_garou.atmosphere.asyncio.sleep", fake_sleep):
            await atm.speak("x", delay_key=key)
        assert sleep_calls == [expected_delay], f"Wrong delay for key={key!r}"


async def test_speak_ha_mode_empty_text_skips():
    atm, hass, _ = make_atmosphere(tts_mode="ha")
    await atm.speak("", delay_key="role_wake")
    hass.services.async_call.assert_not_awaited()


async def test_speak_ha_mode_no_speaker_skips():
    atm, hass, _ = make_atmosphere(tts_mode="ha", speaker="")
    await atm.speak("Hello", delay_key="role_wake")
    hass.services.async_call.assert_not_awaited()


async def test_speak_ha_mode_service_error_does_not_raise():
    atm, hass, _ = make_atmosphere(tts_mode="ha")
    hass.services.async_call = AsyncMock(side_effect=Exception("TTS broken"))
    with patch("loup_garou.loup_garou.atmosphere.asyncio.sleep", new_callable=AsyncMock):
        await atm.speak("Broken", delay_key="role_wake")


async def test_speak_ha_mode_passes_language_to_service():
    atm, hass, _ = make_atmosphere(tts_mode="ha", language="en")
    with patch("loup_garou.loup_garou.atmosphere.asyncio.sleep", new_callable=AsyncMock):
        await atm.speak("Good night", delay_key="night_start")
    call_data = hass.services.async_call.call_args[0][2]
    assert call_data["language"] == "en"


# ═══════════════════════════════════════════════════════════════════════════════
# speak() — browser mode
# ═══════════════════════════════════════════════════════════════════════════════

async def test_speak_browser_mode_calls_server_narrate():
    server = MagicMock()
    server.narrate = AsyncMock()
    atm, hass, _ = make_atmosphere(tts_mode="browser", server=server)
    await atm.speak("Good night", delay_key="night_start")
    server.narrate.assert_awaited_once_with("Good night", "fr", audio_url=None)
    hass.services.async_call.assert_not_awaited()


async def test_speak_browser_mode_no_server_is_silent():
    atm, hass, _ = make_atmosphere(tts_mode="browser", server=None)
    await atm.speak("Good night", delay_key="night_start")
    hass.services.async_call.assert_not_awaited()


async def test_speak_browser_mode_empty_text_skips_narrate():
    server = MagicMock()
    server.narrate = AsyncMock()
    atm, _, _ = make_atmosphere(tts_mode="browser", server=server)
    await atm.speak("", delay_key="role_wake")
    server.narrate.assert_not_awaited()


async def test_speak_browser_mode_does_not_sleep():
    server = MagicMock()
    server.narrate = AsyncMock()
    atm, _, _ = make_atmosphere(tts_mode="browser", server=server)
    sleep_calls = []
    async def fake_sleep(s):
        sleep_calls.append(s)
    with patch("loup_garou.loup_garou.atmosphere.asyncio.sleep", fake_sleep):
        await atm.speak("Hello", delay_key="night_start")
    assert sleep_calls == []


async def test_speak_browser_mode_passes_language():
    server = MagicMock()
    server.narrate = AsyncMock()
    atm, _, _ = make_atmosphere(tts_mode="browser", server=server, language="en")
    await atm.speak("Good night", delay_key="night_start")
    server.narrate.assert_awaited_once_with("Good night", "en", audio_url=None)


# ═══════════════════════════════════════════════════════════════════════════════
# Locale helpers
# ═══════════════════════════════════════════════════════════════════════════════

def test_t_returns_locale_string():
    atm, _, _ = make_atmosphere()
    assert atm.t("phase.night.start") == "La nuit tombe."


def test_t_returns_empty_for_missing_key():
    atm, _, _ = make_atmosphere()
    assert atm.t("this.key.does.not.exist") == ""


def test_t_substitutes_template_variables():
    atm, _, _ = make_atmosphere()
    result = atm.t("phase.day.start_with_death", name="Alice", article="un", role="villageois")
    assert "Alice" in result
    assert "villageois" in result


def test_article_masculine_for_werewolf():
    atm, _, _ = make_atmosphere(language="fr")
    assert atm._article("werewolf") == "un"


def test_article_feminine_for_seer():
    atm, _, _ = make_atmosphere(language="fr")
    assert atm._article("seer") == "une"


def test_article_feminine_for_witch():
    atm, _, _ = make_atmosphere(language="fr")
    assert atm._article("witch") == "une"


def test_article_feminine_for_little_girl():
    atm, _, _ = make_atmosphere(language="fr")
    assert atm._article("little_girl") == "une"


# ═══════════════════════════════════════════════════════════════════════════════
# wire_events registers handlers
# ═══════════════════════════════════════════════════════════════════════════════

def test_wire_events_registers_all_expected_events():
    atm, _, engine = make_atmosphere()
    atm.wire_events()
    registered = set(engine._handlers.keys())
    assert GameEvent.PHASE_CHANGED in registered
    assert GameEvent.NIGHT_ROLE_WAKE in registered
    assert GameEvent.NIGHT_ROLE_SLEEP in registered
    assert GameEvent.DAY_STARTED in registered
    assert GameEvent.VOTE_STARTED in registered
    assert GameEvent.VOTE_RESOLVED in registered
    assert GameEvent.PLAYER_ELIMINATED in registered
    assert GameEvent.GAME_OVER in registered


# ═══════════════════════════════════════════════════════════════════════════════
# Event handlers — speak() called with correct delay_key
# ═══════════════════════════════════════════════════════════════════════════════

async def test_on_phase_changed_night_narrates():
    server = MagicMock()
    server.narrate = AsyncMock()
    atm, _, _ = make_atmosphere(tts_mode="browser", server=server)
    with patch.object(atm, "_set_lights", new_callable=AsyncMock):
        await atm._on_phase_changed({"phase": "night"})
    server.narrate.assert_awaited_once()


async def test_on_phase_changed_day_phase_skips_tts():
    """Day phase is handled by the dedicated day_started event, not phase_changed."""
    server = MagicMock()
    server.narrate = AsyncMock()
    atm, _, _ = make_atmosphere(tts_mode="browser", server=server)
    await atm._on_phase_changed({"phase": "day"})
    server.narrate.assert_not_awaited()


async def test_on_role_wake_narrates():
    server = MagicMock()
    server.narrate = AsyncMock()
    atm, _, _ = make_atmosphere(tts_mode="browser", server=server)
    with patch.object(atm, "_set_lights", new_callable=AsyncMock):
        await atm._on_role_wake({"role": "werewolf"})
    server.narrate.assert_awaited_once()


async def test_on_role_wake_with_result_skips_tts():
    """Seer investigation result is read on-screen; no narration."""
    server = MagicMock()
    server.narrate = AsyncMock()
    atm, _, _ = make_atmosphere(tts_mode="browser", server=server)
    await atm._on_role_wake({"role": "seer", "result": {"player_id": "p1", "role_id": "werewolf"}})
    server.narrate.assert_not_awaited()


async def test_on_role_sleep_narrates():
    server = MagicMock()
    server.narrate = AsyncMock()
    atm, _, _ = make_atmosphere(tts_mode="browser", server=server)
    with patch.object(atm, "_set_lights", new_callable=AsyncMock):
        await atm._on_role_sleep({"role": "werewolf"})
    server.narrate.assert_awaited_once()


async def test_on_day_started_no_deaths_narrates_once():
    server = MagicMock()
    server.narrate = AsyncMock()
    atm, _, _ = make_atmosphere(tts_mode="browser", server=server)
    with patch.object(atm, "_set_lights", new_callable=AsyncMock):
        await atm._on_day_started({"eliminated": []})
    assert server.narrate.await_count == 1


async def test_on_day_started_with_death_narrates_per_victim():
    server = MagicMock()
    server.narrate = AsyncMock()
    atm, _, engine = make_atmosphere(tts_mode="browser", server=server)
    engine.get_public_state.return_value = {
        "players": [
            {"id": "p0", "name": "Alice", "role_id": "villager", "alive": False},
            {"id": "p1", "name": "Bob",   "role_id": "villager", "alive": False},
            {"id": "p2", "name": "Carol", "role_id": "werewolf", "alive": True},
        ]
    }
    with patch.object(atm, "_set_lights", new_callable=AsyncMock):
        await atm._on_day_started({"eliminated": ["p0", "p1"]})
    assert server.narrate.await_count == 2


async def test_on_vote_started_narrates():
    server = MagicMock()
    server.narrate = AsyncMock()
    atm, _, _ = make_atmosphere(tts_mode="browser", server=server)
    await atm._on_vote_started({})
    server.narrate.assert_awaited_once()


async def test_on_vote_resolved_tie_narrates():
    server = MagicMock()
    server.narrate = AsyncMock()
    atm, _, _ = make_atmosphere(tts_mode="browser", server=server)
    await atm._on_vote_resolved({"eliminated": None, "tie": True})
    server.narrate.assert_awaited_once()


async def test_on_vote_resolved_with_elimination_narrates():
    server = MagicMock()
    server.narrate = AsyncMock()
    atm, _, engine = make_atmosphere(tts_mode="browser", server=server)
    engine.get_public_state.return_value = {
        "players": [
            {"id": "p0", "name": "Alice", "role_id": "werewolf", "alive": False},
        ]
    }
    await atm._on_vote_resolved({"eliminated": "p0", "tie": False})
    server.narrate.assert_awaited_once()


async def test_on_game_over_wolves_win_narrates():
    server = MagicMock()
    server.narrate = AsyncMock()
    atm, _, _ = make_atmosphere(tts_mode="browser", server=server)
    with patch.object(atm, "_set_lights", new_callable=AsyncMock):
        await atm._on_game_over({"winner": "wolves"})
    server.narrate.assert_awaited_once()


async def test_on_game_over_village_win_narrates():
    server = MagicMock()
    server.narrate = AsyncMock()
    atm, _, _ = make_atmosphere(tts_mode="browser", server=server)
    with patch.object(atm, "_set_lights", new_callable=AsyncMock):
        await atm._on_game_over({"winner": "village"})
    server.narrate.assert_awaited_once()


async def test_on_hunter_shot_narrates_with_both_names():
    """HUNTER_SHOT event (not PLAYER_ELIMINATED) triggers TTS with hunter + target names (fixes #8)."""
    server = MagicMock()
    server.narrate = AsyncMock()
    atm, _, _ = make_atmosphere(tts_mode="browser", server=server)
    with patch.object(atm, "_set_lights", new_callable=AsyncMock):
        await atm._on_hunter_shot({
            "hunter_name": "Alice",
            "target_name": "Bob",
            "hunter_id": "p0",
            "target_id": "p1",
            "target_role": "villager",
        })
    server.narrate.assert_awaited_once()
    # Verify both names appear in the narrated text
    narrated_text = server.narrate.call_args[0][0]
    assert "Alice" in narrated_text
    assert "Bob" in narrated_text


async def test_on_player_eliminated_hunter_cause_is_silent():
    """PLAYER_ELIMINATED with hunter-related cause should NOT trigger duplicate TTS (handled by HUNTER_SHOT event)."""
    server = MagicMock()
    server.narrate = AsyncMock()
    atm, _, _ = make_atmosphere(tts_mode="browser", server=server)
    # The target's PLAYER_ELIMINATED fires with the original cause (e.g. village_vote),
    # not "hunter_shot", so no special handling is needed here.
    await atm._on_player_eliminated({"cause": "village_vote", "name": "Bob", "role": "villager"})
    server.narrate.assert_not_awaited()


async def test_on_player_eliminated_lover_grief_narrates():
    server = MagicMock()
    server.narrate = AsyncMock()
    atm, _, _ = make_atmosphere(tts_mode="browser", server=server)
    with patch.object(atm, "_set_lights", new_callable=AsyncMock):
        await atm._on_player_eliminated({"cause": "lover_grief", "name": "Bob"})
    server.narrate.assert_awaited_once()


async def test_on_player_eliminated_wolf_kill_is_silent():
    """Wolf kills are announced at day start, not immediately."""
    server = MagicMock()
    server.narrate = AsyncMock()
    atm, _, _ = make_atmosphere(tts_mode="browser", server=server)
    await atm._on_player_eliminated({"cause": "wolf_kill", "name": "Alice"})
    server.narrate.assert_not_awaited()


# ═══════════════════════════════════════════════════════════════════════════════
# _set_lights — HA service calls
# ═══════════════════════════════════════════════════════════════════════════════

async def test_set_lights_calls_ha_service_for_each_light():
    atm, hass, _ = make_atmosphere()
    atm._lights = ["light.a", "light.b"]
    await atm._set_lights("night")
    assert hass.services.async_call.await_count == 2


async def test_set_lights_unknown_scene_is_noop():
    atm, hass, _ = make_atmosphere()
    await atm._set_lights("this_scene_does_not_exist")
    hass.services.async_call.assert_not_awaited()


async def test_set_lights_no_lights_configured_is_noop():
    atm, hass, _ = make_atmosphere()
    atm._lights = []
    await atm._set_lights("night")
    hass.services.async_call.assert_not_awaited()


async def test_set_lights_strips_flash_and_strobe_keys():
    atm, hass, _ = make_atmosphere()
    await atm._set_lights("death")  # death scene has flash=True
    call_data = hass.services.async_call.call_args[0][2]
    assert "flash" not in call_data
    assert "strobe" not in call_data


async def test_set_lights_service_error_does_not_raise():
    atm, hass, _ = make_atmosphere()
    hass.services.async_call = AsyncMock(side_effect=Exception("light broken"))
    await atm._set_lights("night")
