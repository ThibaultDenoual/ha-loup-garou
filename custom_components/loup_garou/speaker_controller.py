"""Speaker controller — drives TTS via HA media_player entities."""
from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# HA TTS service domain and service name
TTS_DOMAIN = "tts"
TTS_SERVICE = "speak"

# Default TTS engine — user may override in config (Phase 2)
DEFAULT_TTS_ENGINE = "tts.home_assistant_cloud"


class SpeakerController:
    """Wraps HA TTS service calls for game narration."""

    def __init__(
        self,
        hass: HomeAssistant,
        media_player_entity: str,
        tts_engine: str = DEFAULT_TTS_ENGINE,
        language: str = "fr",
    ) -> None:
        self.hass = hass
        self._media_player = media_player_entity
        self._tts_engine = tts_engine
        self._language = language

    def update_config(
        self,
        media_player_entity: str,
        language: str,
        tts_engine: str | None = None,
    ) -> None:
        self._media_player = media_player_entity
        self._language = language
        if tts_engine:
            self._tts_engine = tts_engine

    async def async_speak(self, message: str) -> None:
        """Speak a message via the configured TTS engine and media player."""
        if not self._media_player:
            _LOGGER.debug("No speaker configured, skipping TTS: %s", message)
            return

        # Map language codes to BCP-47 for TTS engines
        lang_map = {"fr": "fr-FR", "en": "en-US"}
        tts_language = lang_map.get(self._language, self._language)

        service_data = {
            "entity_id": self._media_player,
            "message": message,
            "language": tts_language,
        }

        try:
            await self.hass.services.async_call(
                TTS_DOMAIN,
                TTS_SERVICE,
                service_data,
                blocking=True,  # Wait for TTS to finish before returning
            )
            _LOGGER.debug("TTS spoke: %r", message)
        except Exception as err:
            # TTS failures are non-fatal — game continues
            _LOGGER.error("TTS failed: %s — message was: %r", err, message)