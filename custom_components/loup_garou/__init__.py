"""Loup Garou — Home Assistant Werewolves Game Master integration.

This file is the HA entry point. All game logic (game_engine.py, roles/) is
pure Python with zero HA imports. HA-specific code lives in ha_integration/.
"""
from __future__ import annotations

import logging

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = []


async def async_setup(hass, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass, entry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    from .loup_garou import async_setup_entry as _setup
    return await _setup(hass, entry)


async def async_unload_entry(hass, entry) -> bool:
    from .loup_garou import async_unload_entry as _unload
    return await _unload(hass, entry)
