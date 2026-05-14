"""Tests for config_flow.py"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from custom_components.loup_garou.config_flow import (
    LoupGarouConfigFlow,
    LoupGarouOptionsFlow,
    STEP_USER_DATA_SCHEMA,
)


@pytest.fixture
def mock_hass():
    hass = MagicMock()
    hass.data = {}
    return hass


class TestStepUserDataSchema:
    def test_schema_has_required_speaker(self):
        from voluptuous import Invalid
        with pytest.raises(Invalid):
            STEP_USER_DATA_SCHEMA({})

    def test_schema_accepts_valid_input(self):
        data = STEP_USER_DATA_SCHEMA({
            "speaker_entity": "media_player.speaker",
            "light_entities": "light.1, light.2",
            "language": "fr",
        })
        assert data["speaker_entity"] == "media_player.speaker"
        assert data["light_entities"] == "light.1, light.2"
        assert data["language"] == "fr"

    def test_schema_defaults_language(self):
        data = STEP_USER_DATA_SCHEMA({
            "speaker_entity": "media_player.speaker",
        })
        assert data["language"] == "fr"

    def test_schema_defaults_lights(self):
        data = STEP_USER_DATA_SCHEMA({
            "speaker_entity": "media_player.speaker",
        })
        assert data["light_entities"] == ""


class TestLoupGarouConfigFlow:
    def test_version(self):
        assert LoupGarouConfigFlow.VERSION == 1


    @pytest.mark.asyncio
    async def test_async_step_user_aborts_single_instance(self, mock_hass):
        flow = LoupGarouConfigFlow()
        flow.hass = mock_hass
        flow._async_current_entries = MagicMock(return_value=["existing_entry"])

        result = await flow.async_step_user(user_input=None)

        assert result["type"] == "abort"
        assert result["reason"] == "single_instance_allowed"

    @pytest.mark.asyncio
    async def test_async_step_user_shows_form(self, mock_hass):
        flow = LoupGarouConfigFlow()
        flow.hass = mock_hass
        flow._async_current_entries = MagicMock(return_value=[])

        result = await flow.async_step_user(user_input=None)

        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert "data_schema" in result

    @pytest.mark.asyncio
    async def test_async_step_user_error_no_speaker(self, mock_hass):
        flow = LoupGarouConfigFlow()
        flow.hass = mock_hass
        flow._async_current_entries = MagicMock(return_value=[])
        flow._async_show_form = AsyncMock()
        flow.async_create_entry = AsyncMock()

        result = await flow.async_step_user(user_input={
            "speaker_entity": "",
            "light_entities": "",
            "language": "fr",
        })

        assert result["errors"]["speaker_entity"] == "no_speaker"

    @pytest.mark.asyncio
    async def test_async_step_user_success(self, mock_hass):
        flow = LoupGarouConfigFlow()
        flow.hass = mock_hass
        flow._async_current_entries = MagicMock(return_value=[])
        flow.async_create_entry = AsyncMock()

        result = await flow.async_step_user(user_input={
            "speaker_entity": "media_player.speaker",
            "light_entities": "light.1, light.2",
            "language": "fr",
        })

        flow.async_create_entry.assert_called_once()
        entry_data = flow.async_create_entry.call_args[1]["data"]
        assert entry_data["speaker_entity"] == "media_player.speaker"
        assert entry_data["light_entities"] == ["light.1", "light.2"]
        assert entry_data["language"] == "fr"

    @pytest.mark.asyncio
    async def test_async_step_user_light_parsing(self, mock_hass):
        flow = LoupGarouConfigFlow()
        flow.hass = mock_hass
        flow._async_current_entries = MagicMock(return_value=[])
        flow.async_create_entry = AsyncMock()

        await flow.async_step_user(user_input={
            "speaker_entity": "mp",
            "light_entities": "light.1, light.2, light.3",
            "language": "en",
        })

        entry_data = flow.async_create_entry.call_args[1]["data"]
        assert entry_data["light_entities"] == ["light.1", "light.2", "light.3"]

    def test_async_get_options_flow(self, mock_hass):
        config_entry = MagicMock()
        flow = LoupGarouConfigFlow()
        result = flow.async_get_options_flow(config_entry)
        assert isinstance(result, LoupGarouOptionsFlow)


class TestLoupGarouOptionsFlow:
    def test_init(self, mock_hass):
        config_entry = MagicMock()
        config_entry.data = {
            "speaker_entity": "mp",
            "light_entities": ["l1"],
            "language": "fr",
        }
        flow = LoupGarouOptionsFlow(config_entry)
        assert flow._entry is config_entry

    @pytest.mark.asyncio
    async def test_async_step_init_shows_form(self, mock_hass):
        config_entry = MagicMock()
        config_entry.data = {
            "speaker_entity": "mp",
            "light_entities": ["l1", "l2"],
            "language": "fr",
        }
        flow = LoupGarouOptionsFlow(config_entry)
        flow.hass = mock_hass

        result = await flow.async_step_init(user_input=None)

        assert result["type"] == "form"
        assert result["step_id"] == "init"

    @pytest.mark.asyncio
    async def test_async_step_init_updates_lights(self, mock_hass):
        config_entry = MagicMock()
        config_entry.data = {
            "speaker_entity": "mp",
            "light_entities": ["l1"],
            "language": "fr",
        }
        flow = LoupGarouOptionsFlow(config_entry)
        flow.hass = mock_hass
        flow.async_create_entry = AsyncMock()

        await flow.async_step_init(user_input={
            "speaker_entity": "mp",
            "light_entities": "l1, l2, l3",
            "language": "en",
        })

        entry_data = flow.async_create_entry.call_args[1]["data"]
        assert entry_data["light_entities"] == ["l1", "l2", "l3"]

    @pytest.mark.asyncio
    async def test_async_step_init_creates_entry(self, mock_hass):
        config_entry = MagicMock()
        config_entry.data = {
            "speaker_entity": "mp",
            "light_entities": [],
            "language": "fr",
        }
        flow = LoupGarouOptionsFlow(config_entry)
        flow.hass = mock_hass
        flow.async_create_entry = AsyncMock()

        await flow.async_step_init(user_input={
            "speaker_entity": "mp",
            "light_entities": "",
            "language": "en",
        })

        flow.async_create_entry.assert_called_once()