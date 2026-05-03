"""Light controller for Loup Garou.

Sets colour/brightness on the user-configured light entities
according to the game phase. All scene definitions live in const.py.
"""
from __future__ import annotations

import asyncio
import logging

from homeassistant.core import HomeAssistant
from homeassistant.components.light import (
    ATTR_RGB_COLOR,
    ATTR_BRIGHTNESS,
    ATTR_TRANSITION,
)
from homeassistant.const import SERVICE_TURN_ON

from .const import LIGHT_SCENES, DOMAIN

_LOGGER = logging.getLogger(__name__)

LIGHT_DOMAIN = "light"


class LightController:
    """Controls the set of lights linked to the game."""

    def __init__(self, hass: HomeAssistant, light_entities: list[str]) -> None:
        self._hass = hass
        self._lights = light_entities

    async def async_set_scene(self, scene_key: str) -> None:
        """Apply a named scene to all configured lights.

        Scene keys are defined in const.LIGHT_SCENES.
        Unknown keys are logged and ignored.
        """
        scene = LIGHT_SCENES.get(scene_key)
        if scene is None:
            _LOGGER.warning("Unknown light scene: %s", scene_key)
            return

        if not self._lights:
            _LOGGER.debug("No lights configured — skipping scene '%s'.", scene_key)
            return

        flash = scene.get("flash", False)
        strobe = scene.get("strobe", False)

        if flash:
            await self._async_flash_then_hold(scene)
        elif strobe:
            await self._async_strobe_then_hold(scene)
        else:
            await self._async_apply(scene)

    # ── Internal helpers ──────────────────────

    async def _async_apply(self, scene: dict) -> None:
        """Apply a scene directly to all lights."""
        service_data = {
            "entity_id": self._lights,
            ATTR_RGB_COLOR: scene["rgb_color"],
            ATTR_BRIGHTNESS: scene["brightness"],
            ATTR_TRANSITION: scene.get("transition", 1),
        }
        await self._hass.services.async_call(
            LIGHT_DOMAIN, SERVICE_TURN_ON, service_data, blocking=False
        )
        _LOGGER.debug(
            "Light scene applied: rgb=%s brightness=%s",
            scene["rgb_color"],
            scene["brightness"],
        )

    async def _async_flash_then_hold(self, scene: dict) -> None:
        """Flash bright red once, then hold the scene colour at dim."""
        flash_data = {
            "entity_id": self._lights,
            ATTR_RGB_COLOR: (220, 0, 0),
            ATTR_BRIGHTNESS: 255,
            ATTR_TRANSITION: 0,
        }
        await self._hass.services.async_call(
            LIGHT_DOMAIN, SERVICE_TURN_ON, flash_data, blocking=False
        )
        await asyncio.sleep(0.6)
        await self._async_apply(scene)

    async def _async_strobe_then_hold(self, scene: dict, strobes: int = 3) -> None:
        """Strobe the lights N times, then settle into the scene colour."""
        for _ in range(strobes):
            on_data = {
                "entity_id": self._lights,
                ATTR_RGB_COLOR: scene["rgb_color"],
                ATTR_BRIGHTNESS: 255,
                ATTR_TRANSITION: 0,
            }
            off_data = {
                "entity_id": self._lights,
                ATTR_RGB_COLOR: scene["rgb_color"],
                ATTR_BRIGHTNESS: 10,
                ATTR_TRANSITION: 0,
            }
            await self._hass.services.async_call(
                LIGHT_DOMAIN, SERVICE_TURN_ON, on_data, blocking=False
            )
            await asyncio.sleep(0.4)
            await self._hass.services.async_call(
                LIGHT_DOMAIN, SERVICE_TURN_ON, off_data, blocking=False
            )
            await asyncio.sleep(0.3)

        # Settle
        await self._async_apply(scene)