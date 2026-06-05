"""HA integration — wires engine + server + atmosphere at startup."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.frontend import async_register_built_in_panel, async_remove_panel
from homeassistant.components.http import HomeAssistantView

from ..const import (
    DOMAIN, CONF_SPEAKER, CONF_LIGHTS, CONF_LANGUAGE, CONF_TTS_ENGINE,
    CONF_AUDIO_SOURCE, CONF_AUDIO_OUTPUT,
    DEFAULT_TTS_ENGINE, DEFAULT_AUDIO_SOURCE, DEFAULT_AUDIO_OUTPUT, VERSION,
)
from ..game_engine import GameEngine
from ..game_server import LoupGarouServer
from ..roles.loader import load_roles
from .atmosphere import Atmosphere

_LOGGER = logging.getLogger(__name__)


DEFAULTS = {
    CONF_AUDIO_SOURCE: DEFAULT_AUDIO_SOURCE,
    CONF_AUDIO_OUTPUT: DEFAULT_AUDIO_OUTPUT,
    CONF_SPEAKER:      "",
    CONF_LIGHTS:       [],
    CONF_LANGUAGE:     "fr",
    CONF_TTS_ENGINE:   DEFAULT_TTS_ENGINE,
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    conf = {**DEFAULTS, **entry.data}
    language = conf[CONF_LANGUAGE]

    # pkgutil.iter_modules + importlib.import_module are blocking — pre-warm in executor
    await hass.async_add_executor_job(load_roles)

    # open() is blocking — read locale file in executor
    _locale_path = Path(__file__).parent.parent / "locales" / f"{language}.json"
    _locale: dict = await hass.async_add_executor_job(
        lambda: json.loads(_locale_path.read_text())
    )

    engine = GameEngine()
    server = LoupGarouServer(engine, config={
        "language":     language,
        "audio_source": conf[CONF_AUDIO_SOURCE],
        "audio_output": conf[CONF_AUDIO_OUTPUT],
        "speaker":      conf[CONF_SPEAKER],
        "lights":       conf[CONF_LIGHTS],
        "tts_engine":   conf[CONF_TTS_ENGINE],
        "version":      VERSION,
    })
    server.wire_events()

    atmosphere = Atmosphere(
        hass=hass,
        engine=engine,
        light_entities=conf[CONF_LIGHTS],
        speaker_entity=conf[CONF_SPEAKER],
        tts_engine=conf[CONF_TTS_ENGINE],
        language=language,
        locale=_locale,
        audio_source=conf[CONF_AUDIO_SOURCE],
        audio_output=conf[CONF_AUDIO_OUTPUT],
        server=server,
    )
    atmosphere.wire_events()

    hass.data[DOMAIN][entry.entry_id] = {
        "engine": engine,
        "server": server,
        "atmosphere": atmosphere,
    }

    async def _save_config(new_config: dict) -> None:
        merged = {**DEFAULTS, **entry.data, **new_config}
        hass.config_entries.async_update_entry(entry, data=merged)
        server._config.update({"version": VERSION, **merged})
        atmosphere.update_config(merged)

    def _get_entities() -> dict:
        return {
            "speakers": hass.states.async_entity_ids("media_player"),
            "lights":   hass.states.async_entity_ids("light"),
        }

    server.set_save_callback(_save_config)
    server.set_entities_callback(_get_entities)

    hass.http.register_view(_WebSocketView(server))

    await _register_static_paths(hass)

    async_register_built_in_panel(
        hass,
        component_name="iframe",
        sidebar_title="Loup Garou",
        sidebar_icon="mdi:weather-night",
        frontend_url_path="loup_garou",
        config={"url": "/loup_garou/game/index.html"},
        require_admin=False,
    )

    _LOGGER.info("Loup Garou loaded (entry: %s)", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data[DOMAIN].pop(entry.entry_id, None)
    async_remove_panel(hass, "loup_garou")
    return True


async def _register_static_paths(hass: HomeAssistant) -> None:
    from pathlib import Path
    from homeassistant.components.http import StaticPathConfig

    www_root = Path(__file__).parent.parent / "www"
    locales_root = Path(__file__).parent.parent / "locales"

    await hass.http.async_register_static_paths([
        StaticPathConfig(f"/{DOMAIN}/game",    str(www_root / "game"),  False),
        StaticPathConfig(f"/{DOMAIN}/locales", str(locales_root),       False),
        StaticPathConfig(f"/{DOMAIN}/audio",   str(www_root / "audio"), True),
    ])


class _WebSocketView(HomeAssistantView):
    """Thin aiohttp view wrapper."""

    url = f"/{DOMAIN}/ws"
    name = f"{DOMAIN}_ws"
    requires_auth = False

    def __init__(self, server: LoupGarouServer) -> None:
        self._server = server

    async def get(self, request):
        return await self._server.handle_ws(request)
