"""Whole games over the real WebSocket view, with narration and lights going to HA services."""
from __future__ import annotations

import asyncio

import pytest
from pytest_homeassistant_custom_component.common import async_mock_service

from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import entity_registry as er

from .conftest import DOMAIN

SPEAKER = "media_player.salon"
LIGHT = "light.salon"
TTS_ENGINE = "tts.google_translate_say"


class _NoSleepAsyncio:
    """asyncio for the atmosphere module only, with its pacing sleeps cut to zero."""

    def __getattr__(self, name):
        return getattr(asyncio, name)

    @staticmethod
    async def sleep(delay, result=None):
        return await asyncio.sleep(0, result)


@pytest.fixture
def entry_data() -> dict:
    return {
        "audio_source": "tts",
        "audio_output": "ha",
        "speaker_entity": SPEAKER,
        "light_entities": [LIGHT],
        "tts_engine": TTS_ENGINE,
        "language": "fr",
    }


@pytest.fixture(autouse=True)
def no_narration_pauses(monkeypatch):
    monkeypatch.setattr(
        "custom_components.loup_garou.loup_garou.atmosphere.asyncio", _NoSleepAsyncio()
    )


@pytest.fixture
def fast_demo(hass: HomeAssistant, setup_entry):
    server = hass.data[DOMAIN][setup_entry.entry_id]["server"]
    server._demo_action_delay = 0
    server._demo_step_delay = 0
    return server


async def _receive_until(ws, msg_type: str, limit: int = 500) -> list[dict]:
    seen = []
    for _ in range(limit):
        msg = await ws.receive_json(timeout=5)
        seen.append(msg)
        if msg.get("type") == msg_type:
            return seen
    raise AssertionError(f"no {msg_type!r} in {len(seen)} messages")


async def test_demo_game_drives_ha_tts_and_lights(
    hass: HomeAssistant, fast_demo, hass_client
) -> None:
    tts_calls = async_mock_service(hass, "tts", "speak")
    light_calls = async_mock_service(hass, "light", "turn_on")
    client = await hass_client()

    async with client.ws_connect("/loup_garou/ws") as ws:
        await ws.send_json({"cmd": "run_demo", "data": {"preset": "smoke_test"}})
        msgs = await _receive_until(ws, "demo_finished")
    await hass.async_block_till_done()

    assert not [m for m in msgs if m["type"] in ("error", "demo_error")]
    # The demo resets the engine once it is done, so look for the game-over state.
    winners = {m["state"]["winner"] for m in msgs if m["type"] == "state"} - {None}
    assert winners == {"village"}

    assert tts_calls, "no narration reached tts.speak"
    for call in tts_calls:
        assert call.data["entity_id"] == TTS_ENGINE
        assert call.data["media_player_entity_id"] == SPEAKER
        assert call.data["language"] == "fr"
        assert call.data["message"]

    assert light_calls, "no light scene reached light.turn_on"
    assert {call.data["entity_id"] for call in light_calls} == {LIGHT}


async def test_save_config_persists_to_the_config_entry(
    hass: HomeAssistant, setup_entry, hass_client
) -> None:
    client = await hass_client()

    async with client.ws_connect("/loup_garou/ws") as ws:
        await ws.send_json({
            "cmd": "save_config",
            "data": {"light_entities": ["light.cuisine"], "language": "en"},
        })
        msgs = await _receive_until(ws, "config")

    assert msgs[-1]["config"]["light_entities"] == ["light.cuisine"]
    assert setup_entry.data["light_entities"] == ["light.cuisine"]
    assert setup_entry.data["language"] == "en"
    assert setup_entry.data["speaker_entity"] == SPEAKER


async def test_get_entities_reads_real_states_and_registries(
    hass: HomeAssistant, setup_entry, hass_client
) -> None:
    area = ar.async_get(hass).async_create("Salon")
    er.async_get(hass).async_get_or_create(
        "light", "test", "salon-1", suggested_object_id="salon"
    )
    er.async_get(hass).async_update_entity(LIGHT, area_id=area.id)
    hass.states.async_set(LIGHT, "on", {"friendly_name": "Lampe du salon"})
    hass.states.async_set("light.cave", "off")
    hass.states.async_set(SPEAKER, "idle")
    client = await hass_client()

    async with client.ws_connect("/loup_garou/ws") as ws:
        await ws.send_json({"cmd": "get_entities"})
        msgs = await _receive_until(ws, "entities")

    data = msgs[-1]["data"]
    assert data["speakers"] == [SPEAKER]
    lights = {light["entity_id"]: light for light in data["lights"]}
    assert lights[LIGHT] == {
        "entity_id": LIGHT, "name": "Lampe du salon", "area": "Salon", "state": "on",
    }
    assert lights["light.cave"] == {
        "entity_id": "light.cave", "name": "light.cave", "area": None, "state": "off",
    }
