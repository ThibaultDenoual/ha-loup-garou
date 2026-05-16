"""Config flow for Loup Garou integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_SPEAKER,
    CONF_LIGHTS,
    CONF_LANGUAGE,
    CONF_TTS_ENGINE,
    DEFAULT_TTS_ENGINE,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SPEAKER): str,
        vol.Optional(CONF_LIGHTS, default=""): str,
        vol.Optional(CONF_LANGUAGE, default="fr"): vol.In(["fr", "en"]),
        vol.Optional(CONF_TTS_ENGINE, default=DEFAULT_TTS_ENGINE): str,
    }
)


class LoupGarouConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Loup Garou."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        # Only allow one instance
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            speaker = user_input.get(CONF_SPEAKER, "")
            lights_raw = user_input.get(CONF_LIGHTS, "")
            lights = [l.strip() for l in lights_raw.split(",") if l.strip()]
            language = user_input.get(CONF_LANGUAGE, "fr")
            tts_engine = user_input.get(CONF_TTS_ENGINE, DEFAULT_TTS_ENGINE)

            if not speaker:
                errors[CONF_SPEAKER] = "no_speaker"
            else:
                return self.async_create_entry(
                    title="Loup Garou",
                    data={
                        CONF_SPEAKER: speaker,
                        CONF_LIGHTS: lights,
                        CONF_LANGUAGE: language,
                        CONF_TTS_ENGINE: tts_engine,
                    },
                )

        # Build entity selector schemas
        # In HA config flows the actual entity pickers are done via selectors
        # in strings.json, but we provide a basic vol schema for validation.
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "doc_url": "https://github.com/your-username/ha-loup-garou"
            },
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "LoupGarouOptionsFlow":
        return LoupGarouOptionsFlow(config_entry)


class LoupGarouOptionsFlow(config_entries.OptionsFlow):
    """Allow reconfiguring speaker, lights, and language after initial setup."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        if user_input is not None:
            lights_raw = user_input.get(CONF_LIGHTS, "")
            user_input = {
                **user_input,
                CONF_LIGHTS: [l.strip() for l in lights_raw.split(",") if l.strip()],
            }
            return self.async_create_entry(title="", data=user_input)

        current = self._entry.data
        lights_default = ",".join(current.get(CONF_LIGHTS, []))
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SPEAKER, default=current.get(CONF_SPEAKER, "")
                ): str,
                vol.Optional(
                    CONF_LIGHTS, default=lights_default
                ): str,
                vol.Optional(
                    CONF_LANGUAGE, default=current.get(CONF_LANGUAGE, "fr")
                ): vol.In(["fr", "en"]),
                vol.Optional(
                    CONF_TTS_ENGINE, default=current.get(CONF_TTS_ENGINE, DEFAULT_TTS_ENGINE)
                ): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)