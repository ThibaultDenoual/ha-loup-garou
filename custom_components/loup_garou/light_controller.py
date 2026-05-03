"""Light controller — drives HA light entities for each game scene."""
from __future__ import annotations

import asyncio
import logging

from homeassistant.core import HomeAssistant
from homeassistant.components.light import (
    ATTR_RGB_COLOR,
    ATTR_BRIGHTNESS_PCT,
    ATTR_TRANSITION,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.const import SERVICE_TURN_ON

from .const import LIGHT_SCENES

_LOGGER = logging.getLogger(__name__)


class LightController:
    """Controls the list of configured light entities."""

    def __init__(self, hass: HomeAssistant, light_entities: list[str]) -> None:
        self.hass = hass
        self._entities = light_entities

    def update_entities(self, light_entities: list[str]) -> None:
        self._entities = light_entities

    async def async_set_scene(self, scene_name: str) -> None:
        """Apply a named scene to all configured lights."""
        if not self._entities:
            _LOGGER.debug("No lights configured, skipping scene: %s", scene_name)
            return

        scene = LIGHT_SCENES.get(scene_name)
        if scene is None:
            _LOGGER.warning("Unknown light scene: %s", scene_name)
            return

        service_data: dict = {
            "entity_id": self._entities,
            ATTR_RGB_COLOR: scene["rgb_color"],
            ATTR_BRIGHTNESS_PCT: scene["brightness_pct"],
            ATTR_TRANSITION: scene["transition"],
        }

        try:
            await self.hass.services.async_call(
                LIGHT_DOMAIN,
                SERVICE_TURN_ON,
                service_data,
                blocking=True,
            )
            _LOGGER.debug("Applied light scene '%s' to %s", scene_name, self._entities)
        except Exception as err:
            _LOGGER.error("Failed to apply light scene '%s': %s", scene_name, err)

    async def async_flash_death(self) -> None:
        """
        Flash red for a death reveal:
        instant red → 0.5s pause → dim red hold.
        No audio — the drama comes from the light, TTS follows.
        """
        await self.async_set_scene("death")
        await asyncio.sleep(0.5)
        # Dim hold — reuse death scene (already at 15% dim red)
        # A second call isn't strictly needed but makes intent explicit
        await self.async_set_scene("death")