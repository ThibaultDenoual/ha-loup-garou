"""Tests for services/tts.py"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from custom_components.loup_garou.services.tts import TTSController


@pytest.fixture
def mock_hass():
    hass = MagicMock()
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()
    return hass


class TestTTSController:
    def test_init(self, mock_hass):
        tts = TTSController(mock_hass, media_player_entity="media_player.speaker")
        assert tts._media_player == "media_player.speaker"
        assert tts._language == "fr"
        assert tts._tts_engine == "tts.home_assistant_cloud"

    def test_init_empty_media_player(self, mock_hass):
        tts = TTSController(mock_hass, media_player_entity="")
        assert tts._media_player == ""

    def test_init_custom_tts_engine(self, mock_hass):
        tts = TTSController(mock_hass, media_player_entity="mp", tts_engine="custom.engine")
        assert tts._tts_engine == "custom.engine"


class TestTTSControllerUpdateConfig:
    def test_update_media_player(self, mock_hass):
        tts = TTSController(mock_hass, media_player_entity="old")
        tts.update_config(media_player_entity="new", language="en")
        assert tts._media_player == "new"

    def test_update_language(self, mock_hass):
        tts = TTSController(mock_hass, media_player_entity="mp", language="fr")
        tts.update_config(media_player_entity="mp", language="en")
        assert tts._language == "en"

    def test_update_tts_engine(self, mock_hass):
        tts = TTSController(mock_hass, media_player_entity="mp")
        tts.update_config(media_player_entity="mp", language="fr", tts_engine="custom")
        assert tts._tts_engine == "custom"


class TestTTSControllerSpeak:
    @pytest.mark.asyncio
    async def test_speak_no_media_player(self, mock_hass):
        tts = TTSController(mock_hass, media_player_entity="")
        await tts.async_speak("Hello")
        tts.hass.services.async_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_speak_calls_service(self, mock_hass):
        tts = TTSController(mock_hass, media_player_entity="media_player.speaker", language="fr")
        await tts.async_speak("Hello world")
        tts.hass.services.async_call.assert_called_once()
        call_args = tts.hass.services.async_call.call_args
        assert call_args[0][0] == "tts"
        assert call_args[0][1] == "speak"
        assert call_args[1]["blocking"] is True

    @pytest.mark.asyncio
    async def test_speak_language_mapping_fr(self, mock_hass):
        tts = TTSController(mock_hass, media_player_entity="mp", language="fr")
        await tts.async_speak("test")
        call_args = tts.hass.services.async_call.call_args
        assert call_args[0][2]["language"] == "fr-FR"

    @pytest.mark.asyncio
    async def test_speak_language_mapping_en(self, mock_hass):
        tts = TTSController(mock_hass, media_player_entity="mp", language="en")
        await tts.async_speak("test")
        call_args = tts.hass.services.async_call.call_args
        assert call_args[0][2]["language"] == "en-US"

    @pytest.mark.asyncio
    async def test_speak_includes_message(self, mock_hass):
        tts = TTSController(mock_hass, media_player_entity="mp", language="fr")
        await tts.async_speak("Test message")
        call_args = tts.hass.services.async_call.call_args
        assert "message" in call_args[0][2]
        assert call_args[0][2]["message"] == "Test message"

    @pytest.mark.asyncio
    async def test_speak_service_error_handled(self, mock_hass):
        mock_hass.services.async_call = AsyncMock(side_effect=Exception("Service error"))
        tts = TTSController(mock_hass, media_player_entity="mp", language="fr")
        await tts.async_speak("test")
        mock_hass.services.async_call.assert_called_once()