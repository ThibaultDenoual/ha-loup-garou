"""Dev light simulator — logs scene changes to console."""
from __future__ import annotations

import logging

from custom_components.loup_garou.const import LIGHT_SCENES

_LOGGER = logging.getLogger("dev_lights")


class DevLights:
    """Simulates light control by logging scene transitions."""

    def __init__(self, lights: list[str] | None = None) -> None:
        self._lights = lights or []
        self._current_scene: str | None = None

    async def set_scene(self, scene_key: str, transition: float | None = None) -> None:
        scene = LIGHT_SCENES.get(scene_key)
        if not scene:
            _LOGGER.debug("[LIGHT] unknown scene: %s", scene_key)
            return

        rgb = scene.get("rgb_color", (0, 0, 0))
        brightness = scene.get("brightness", 0)
        trans = transition if transition is not None else scene.get("transition", 0)
        flash = scene.get("flash", False)
        strobe = scene.get("strobe", False)

        extra = []
        if flash:
            extra.append("FLASH")
        if strobe:
            extra.append("STROBE")
        extra_str = f" [{', '.join(extra)}]" if extra else ""

        if self._lights:
            _LOGGER.info(
                "[LIGHT] scene=%s rgb=%s brightness=%d transition=%.1fs lights=%s%s",
                scene_key, rgb, brightness, trans, self._lights, extra_str
            )
        else:
            _LOGGER.info(
                "[LIGHT] scene=%s rgb=%s brightness=%d transition=%.1fs%s",
                scene_key, rgb, brightness, trans, extra_str
            )

        self._current_scene = scene_key

    async def turn_off(self, transition: float = 1.0) -> None:
        if self._lights:
            _LOGGER.info("[LIGHT] OFF transition=%.1fs lights=%s", transition, self._lights)
        else:
            _LOGGER.info("[LIGHT] OFF transition=%.1fs", transition)
        self._current_scene = None

    def get_current_scene(self) -> str | None:
        return self._current_scene