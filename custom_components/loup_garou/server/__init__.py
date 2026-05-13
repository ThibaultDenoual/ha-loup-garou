"""Server module — HTTP views and WebSocket handling."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from homeassistant.components.http import StaticPathConfig

_LOGGER = logging.getLogger(__name__)


async def async_register_static_paths(hass) -> None:
    """Register static file paths for the frontend."""
    www_path = Path(__file__).parent.parent / "www"
    if www_path.is_dir():
        await hass.http.async_register_static_paths([
            StaticPathConfig(
                url_path="/loup_garou",
                path=str(www_path),
                cache_headers=False,
            )
        ])
        _LOGGER.debug("Static paths registered for /loup_garou")