"""Phase transition orchestrator — coordinates TTS and lights."""
from __future__ import annotations

import asyncio
import logging

from homeassistant.core import HomeAssistant

from .const import (
    PHASE_NIGHT,
    PHASE_DAY,
    PHASE_VOTE,
    PHASE_GAME_OVER,
    PHASE_ROLE_REVEAL,
    ROLE_WEREWOLF,
    ROLE_SEER,
    WIN_WOLVES,
    WIN_VILLAGERS,
    NIGHT_WAKE_ORDER,
    ROLE_WAKE_SCENE,
    PHASE_LIGHT_SCENE,
    TTS_STRINGS,
    ROLE_DISPLAY_NAMES,
)
from .light_controller import LightController
from .speaker_controller import SpeakerController


_LOGGER = logging.getLogger(__name__)


class PhaseManager:
    """
    Reacts to game state changes and drives lights + TTS.

    This is the layer between GameEngine (pure state) and the hardware
    controllers. It is called by the WebSocket API after each state mutation.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        light_controller: LightController,
        speaker_controller: SpeakerController,
        language: str = "fr",
    ) -> None:
        self.hass = hass
        self._lights = light_controller
        self._speaker = speaker_controller
        self._language = language

    def set_language(self, language: str) -> None:
        self._language = language

    def _t(self, key: str, **kwargs) -> str:
        """Get a translated string, with optional format kwargs."""
        strings = TTS_STRINGS.get(self._language, TTS_STRINGS["fr"])
        text = strings.get(key, key)
        if kwargs:
            text = text.format(**kwargs)
        return text

    def _role_name(self, role: str) -> str:
        names = ROLE_DISPLAY_NAMES.get(self._language, ROLE_DISPLAY_NAMES["fr"])
        return names.get(role, role)

    # ─── Phase event handlers ─────────────────────────────────────────────────

    async def on_roles_distributed(self) -> None:
        """Called when all roles have been assigned (start of ROLE_REVEAL)."""
        await self._speaker.async_speak(self._t("roles_distributed"))

    async def on_night_start(self) -> None:
        """Called when NIGHT phase begins."""
        await self._lights.async_set_scene("night")
        await self._speaker.async_speak(self._t("night_start"))

    async def on_role_wake(self, role: str) -> None:
        """Called when a specific role wakes up during the night."""
        scene = ROLE_WAKE_SCENE.get(role, "night")
        await self._lights.async_set_scene(scene)

        if role == ROLE_SEER:
            await self._speaker.async_speak(self._t("seer_wake"))
        elif role == ROLE_WEREWOLF:
            await self._speaker.async_speak(self._t("wolves_wake"))

    async def on_role_sleep(self, role: str) -> None:
        """Called when a role finishes their night action."""
        # Return to generic night scene before next role wakes
        await self._lights.async_set_scene("night")

        if role == ROLE_SEER:
            await self._speaker.async_speak(self._t("seer_sleep"))
        elif role == ROLE_WEREWOLF:
            await self._speaker.async_speak(self._t("wolves_sleep"))

    async def on_day_start(
        self,
        eliminated_names: list[tuple[str, str]],  # [(name, role), ...]
    ) -> None:
        """Called when DAY phase begins."""
        await self._lights.async_set_scene("day")

        if not eliminated_names:
            await self._speaker.async_speak(self._t("day_no_death"))
        else:
            for name, role in eliminated_names:
                await self._speaker.async_speak(
                    self._t("day_death", name=name, role=self._role_name(role))
                )

    async def on_vote_start(self) -> None:
        """Called when VOTE phase begins."""
        await self._speaker.async_speak(self._t("vote_start"))

    async def on_player_eliminated(self, name: str, role: str) -> None:
        """Called when a player is eliminated by vote."""
        await self._lights.async_flash_death()
        await self._speaker.async_speak(
            self._t("player_eliminated", name=name, role=self._role_name(role))
        )

    async def on_game_over(self, winner: str) -> None:
        """Called when the game ends."""
        if winner == WIN_WOLVES:
            await self._lights.async_set_scene("wolves_win")
            await self._speaker.async_speak(self._t("wolves_win"))
        elif winner == WIN_VILLAGERS:
            await self._lights.async_set_scene("villagers_win")
            await self._speaker.async_speak(self._t("villagers_win"))