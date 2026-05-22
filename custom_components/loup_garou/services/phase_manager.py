"""Phase orchestration: coordinates engine, lights, and TTS."""
from __future__ import annotations

import logging

from ..const import (
    Phase,
    Role,
    EliminationCause,
    WinCondition,
    ROLE_NAMES_FR,
    ROLE_NAMES_EN,
    ROLE_ARTICLES_FR,
    TTS,
    EVENT_GAME_STATE_CHANGED,
)

_LOGGER = logging.getLogger(__name__)


def _role_display(role: str, lang: str) -> str:
    if lang == "fr":
        return ROLE_NAMES_FR.get(role, role)
    return ROLE_NAMES_EN.get(role, role)


def _format_tts(key: str, lang: str, **kwargs) -> str:
    template = TTS[key][lang]
    return template.format(**kwargs)


class PhaseManager:
    """Coordinates phase transitions across engine, lights, and TTS."""

    def __init__(
        self,
        hass,
        engine,
        lights,
        speaker,
        language: str,
    ) -> None:
        self._hass = hass
        self._engine = engine
        self._lights = lights
        self._speaker = speaker
        self._lang = language

        hass.bus.async_listen(
            EVENT_GAME_STATE_CHANGED,
            self._handle_state_changed,
        )

    async def on_game_started(self) -> None:
        await self._speaker.async_speak(
            _format_tts("roles_distributed", self._lang)
        )

    async def on_night_started(self) -> None:
        await self._lights.async_set_scene("night")
        await self._speaker.async_speak(_format_tts("night_start", self._lang))
        await self._on_night_role_advanced()

    async def on_role_wake(self, role: str) -> None:
        scene_map = {
            Role.SEER: "seer_wake",
            Role.WEREWOLF: "wolf_wake",
        }
        tts_wake_map = {
            Role.SEER: "seer_wake",
            Role.WEREWOLF: "wolf_wake",
        }

        scene = scene_map.get(role, "night")
        await self._lights.async_set_scene(scene)

        wake_key = tts_wake_map.get(role)
        if wake_key:
            await self._speaker.async_speak(_format_tts(wake_key, self._lang))

    async def on_night_action_submitted(self, role: str) -> None:
        tts_sleep_map = {
            Role.SEER: "seer_sleep",
            Role.WEREWOLF: "wolf_sleep",
        }
        sleep_key = tts_sleep_map.get(role)
        if sleep_key:
            await self._speaker.async_speak(_format_tts(sleep_key, self._lang))
        await self._lights.async_set_scene("night")

    async def on_day_started(self, eliminated_player_id: str | None) -> None:
        await self._lights.async_set_scene("day")

        if eliminated_player_id:
            player = self._engine.state.players[eliminated_player_id]
            role_name = _role_display(player.role, self._lang)
            if self._lang == "fr":
                article = ROLE_ARTICLES_FR.get(player.role, "un")
                text = _format_tts(
                    "day_start_death", self._lang,
                    name=player.name, article=article, role=role_name
                )
            else:
                text = _format_tts(
                    "day_start_death", self._lang,
                    name=player.name, role=role_name
                )
        else:
            text = _format_tts("day_start_no_death", self._lang)

        await self._speaker.async_speak(text)

    async def on_vote_started(self) -> None:
        await self._speaker.async_speak(_format_tts("vote_start", self._lang))

    async def on_vote_tie(self) -> None:
        await self._speaker.async_speak(_format_tts("vote_tie", self._lang))

    async def on_player_eliminated(
        self,
        player_id: str,
        cause: EliminationCause,
    ) -> None:
        player = self._engine.state.players[player_id]
        role_name = _role_display(player.role, self._lang)

        await self._lights.async_set_scene("death")

        if self._lang == "fr":
            article = ROLE_ARTICLES_FR.get(player.role, "un")
            text = _format_tts(
                "elimination", self._lang,
                name=player.name, article=article, role=role_name
            )
        else:
            text = _format_tts(
                "elimination", self._lang,
                name=player.name, role=role_name
            )

        await self._speaker.async_speak(text)

    async def on_game_over(self, winner: WinCondition) -> None:
        scene = "wolves_win" if winner == WinCondition.WOLVES else "village_win"
        await self._lights.async_set_scene(scene)

        tts_key = "wolves_win" if winner == WinCondition.WOLVES else "villagers_win"
        await self._speaker.async_speak(_format_tts(tts_key, self._lang))

    async def _handle_state_changed(self, event) -> None:
        phase = event.data.get("phase", "")
        _LOGGER.debug("PhaseManager received event phase: %s", phase)

        if phase == Phase.NIGHT:
            await self.on_night_started()
        elif phase == Phase.DAY:
            eliminated = event.data.get("eliminated", [])
            killed_id = eliminated[-1] if eliminated else None
            await self.on_day_started(killed_id)
        elif phase == Phase.VOTE:
            await self.on_vote_started()

    async def _on_night_role_advanced(self) -> None:
        acting_role = self._engine.current_night_role
        if acting_role:
            await self.on_role_wake(acting_role)

    def set_language(self, lang: str) -> None:
        self._lang = lang