"""Tests for services/lights.py"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.loup_garou.services.lights import LightController


@pytest.fixture
def mock_hass():
    hass = MagicMock()
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()
    return hass


class TestLightController:
    def test_init(self, mock_hass):
        lc = LightController(mock_hass, ["light.1", "light.2"])
        assert lc._lights == ["light.1", "light.2"]
        assert lc._hass is mock_hass

    def test_init_empty_lights(self, mock_hass):
        lc = LightController(mock_hass, [])
        assert lc._lights == []

    def test_update_entities(self, mock_hass):
        lc = LightController(mock_hass, ["light.1"])
        lc.update_entities(["light.1", "light.2"])
        assert lc._lights == ["light.1", "light.2"]


class TestLightControllerSetScene:
    @pytest.mark.asyncio
    async def test_set_scene_unknown_key_warns(self, mock_hass):
        lc = LightController(mock_hass, ["light.1"])
        lc._hass.services.async_call = AsyncMock()
        await lc.async_set_scene("nonexistent_scene")
        lc._hass.services.async_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_scene_no_lights_skips(self, mock_hass):
        lc = LightController(mock_hass, [])
        await lc.async_set_scene("day")
        lc._hass.services.async_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_scene_basic_apply(self, mock_hass):
        lc = LightController(mock_hass, ["light.1"])
        await lc.async_set_scene("day")
        lc._hass.services.async_call.assert_called_once()
        call_kwargs = lc._hass.services.async_call.call_args
        assert call_kwargs[0][0] == "light"
        assert call_kwargs[0][1] == "turn_on"
        assert call_kwargs[1]["blocking"] is False

    @pytest.mark.asyncio
    async def test_set_scene_night(self, mock_hass):
        lc = LightController(mock_hass, ["light.1"])
        await lc.async_set_scene("night")
        lc._hass.services.async_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_scene_wolf_wake(self, mock_hass):
        lc = LightController(mock_hass, ["light.1"])
        await lc.async_set_scene("wolf_wake")
        lc._hass.services.async_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_scene_seer_wake(self, mock_hass):
        lc = LightController(mock_hass, ["light.1"])
        await lc.async_set_scene("seer_wake")
        lc._hass.services.async_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_scene_death(self, mock_hass):
        lc = LightController(mock_hass, ["light.1"])
        from unittest.mock import patch
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await lc.async_set_scene("death")
        assert mock_hass.services.async_call.called

    @pytest.mark.asyncio
    async def test_set_scene_village_win(self, mock_hass):
        lc = LightController(mock_hass, ["light.1"])
        await lc.async_set_scene("village_win")
        mock_hass.services.async_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_scene_wolves_win(self, mock_hass):
        lc = LightController(mock_hass, ["light.1"])
        from unittest.mock import patch
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await lc.async_set_scene("wolves_win")
        assert mock_hass.services.async_call.called


class TestLightControllerFlash:
    @pytest.mark.asyncio
    async def test_flash_then_hold(self, mock_hass):
        lc = LightController(mock_hass, ["light.1"])
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_sleep.side_effect = [None, None]
            await lc.async_set_scene("death")
        calls = lc._hass.services.async_call.call_args_list
        assert len(calls) >= 2

    @pytest.mark.asyncio
    async def test_strobe_then_hold(self, mock_hass):
        lc = LightController(mock_hass, ["light.1"])
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_sleep.side_effect = [None, None, None, None, None, None]
            await lc.async_set_scene("wolves_win")
        calls = lc._hass.services.async_call.call_args_list
        assert len(calls) >= 4