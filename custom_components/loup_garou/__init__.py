"""Loup Garou — Home Assistant Werewolves Game Master integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.frontend import async_register_built_in_panel, async_remove_panel

from .const import DOMAIN, CONF_SPEAKER, CONF_LIGHTS, CONF_LANGUAGE
from .core_game.io_adapters.ha_adapter import AsyncGameAdapter as GameEngine
from .services.lights import LightController
from .services.tts import TTSController
from .services.phase_manager import PhaseManager
from .server import async_register_static_paths
from .server.websocket import LoupGarouWebSocketView

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

    light_controller = LightController(
        hass=hass,
        light_entities=conf.get(CONF_LIGHTS, []),
    )
    speaker_controller = TTSController(
        hass=hass,
        media_player_entity=conf.get(CONF_SPEAKER, ""),
        language=conf.get(CONF_LANGUAGE, "fr"),
    )

    engine = GameEngine(hass=hass, config_entry_id=entry.entry_id)
    #await engine.async_load()

    phase_manager = PhaseManager(
        hass=hass,
        engine=engine,
        lights=light_controller,
        speaker=speaker_controller,
        language=conf.get(CONF_LANGUAGE, "fr"),
    )

    hass.data[DOMAIN] = {
        "engine": engine,
        "light_controller": light_controller,
        "speaker_controller": speaker_controller,
        "phase_manager": phase_manager,
    }

    await async_register_static_paths(hass)

    async_register_built_in_panel(
        hass,
        component_name="iframe",
        sidebar_title="Loup Garou",
        sidebar_icon="mdi:weather-night",
        frontend_url_path="loup_garou",
        config={"url": "/loup_garou/launcher.html"},
        require_admin=False,
    )

    hass.http.register_view(LoupGarouWebSocketView(hass))

    entry.async_on_unload(entry.add_update_listener(_async_update_options))

    _LOGGER.info("Loup Garou integration loaded (entry: %s)", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    async_remove_panel(hass, "loup_garou")
    hass.data.pop(DOMAIN, None)
    _LOGGER.info("Loup Garou integration unloaded")
    return True


async def _async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """React to options flow changes — update controllers without full reload."""
    conf = {**entry.data, **entry.options}
    domain_data = hass.data.get(DOMAIN, {})

    lc: LightController | None = domain_data.get("light_controller")
    sc: TTSController | None = domain_data.get("speaker_controller")
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