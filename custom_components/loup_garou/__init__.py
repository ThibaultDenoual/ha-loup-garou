"""Loup Garou — Home Assistant Werewolves Game Master integration."""
from __future__ import annotations

import logging
import os

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.http import StaticPathConfig

from .const import (
    DOMAIN,
    CONF_SPEAKER,
    CONF_LIGHTS,
    CONF_LANGUAGE,
)
from .game_engine import GameEngine
from .light_controller import LightController
from .speaker_controller import SpeakerController
from .phase_manager import PhaseManager
from .websocket_api import async_register_commands

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = []


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Loup Garou component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Loup Garou from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    conf = entry.data

    # ── Hardware controllers ──────────────────────────────────────────────────
    light_controller = LightController(
        hass=hass,
        light_entities=conf.get(CONF_LIGHTS, []),
    )
    speaker_controller = SpeakerController(
        hass=hass,
        media_player_entity=conf.get(CONF_SPEAKER, ""),
        language=conf.get(CONF_LANGUAGE, "fr"),
    )

    # ── Phase manager (coordinates lights + TTS) ──────────────────────────────
    phase_manager = PhaseManager(
        hass=hass,
        light_controller=light_controller,
        speaker_controller=speaker_controller,
        language=conf.get(CONF_LANGUAGE, "fr"),
    )

    # ── Game engine (state machine + persistence) ─────────────────────────────
    engine = GameEngine(hass=hass, config_entry_id=entry.entry_id)
    await engine.async_load()

    hass.data[DOMAIN] = {
        "engine": engine,
        "light_controller": light_controller,
        "speaker_controller": speaker_controller,
        "phase_manager": phase_manager,
    }

    # ── Serve the frontend ────────────────────────────────────────────────────
    www_path = os.path.join(os.path.dirname(__file__), "www", "game")
    await hass.http.async_register_static_paths([
        StaticPathConfig(
            url_path="/loup_garou",
            path=www_path,
            cache_headers=False,
        )
    ])

    # ── Register sidebar panel ────────────────────────────────────────────────
    hass.components.frontend.async_register_built_in_panel(
        component_name="iframe",
        sidebar_title="🐺 Loup Garou",
        sidebar_icon="mdi:wolf",
        frontend_url_path="loup_garou_panel",
        config={"url": "/loup_garou/index.html"},
        require_admin=False,
    )

    # ── Register WebSocket commands ───────────────────────────────────────────
    async_register_commands(hass)

    # ── Listen for config entry option updates ────────────────────────────────
    entry.async_on_unload(entry.add_update_listener(_async_update_options))

    _LOGGER.info("Loup Garou integration loaded (entry: %s)", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data.pop(DOMAIN, None)
    _LOGGER.info("Loup Garou integration unloaded")
    return True


async def _async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """React to options flow changes — update controllers without full reload."""
    conf = {**entry.data, **entry.options}
    domain_data = hass.data.get(DOMAIN, {})

    lc: LightController | None = domain_data.get("light_controller")
    sc: SpeakerController | None = domain_data.get("speaker_controller")
    pm: PhaseManager | None = domain_data.get("phase_manager")

    if lc:
        lc.update_entities(conf.get(CONF_LIGHTS, []))
    if sc:
        sc.update_config(
            media_player_entity=conf.get(CONF_SPEAKER, ""),
            language=conf.get(CONF_LANGUAGE, "fr"),
        )
    if pm:
        pm.set_language(conf.get(CONF_LANGUAGE, "fr"))