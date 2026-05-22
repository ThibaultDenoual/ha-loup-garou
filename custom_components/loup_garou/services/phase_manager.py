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
    EVENT_GAME_STARTED,
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
        io_interface=None,
        language: str = "fr",
    ) -> None:
        self._hass = hass
        self._engine = engine
        self._io = io_interface
        self._lang = language

        hass.bus.async_listen(
            EVENT_GAME_STATE_CHANGED,
            self._handle_state_changed,
        )
        hass.bus.async_listen(
            EVENT_GAME_STARTED,
            self._handle_game_started,
        )

    async def on_game_started(self) -> None:
        if self._io:
            self._io.speak(_format_tts("roles_distributed", self._lang))

    async def on_night_started(self) -> None:
        if self._io:
            self._io.set_scene("night")
            self._io.speak(_format_tts("night_start", self._lang))

    async def on_phase_changed(self, phase: str) -> None:
        """Handle phase change events from the engine."""
        if not self._io:
            return
        if phase == Phase.NIGHT_START:
            await self.on_night_started()
        elif phase == Phase.NIGHT_SEER_WAKE:
            self._io.set_scene("seer_wake")
            self._io.speak(_format_tts("seer_wake", self._lang))
        elif phase == Phase.NIGHT_SEER_SLEEP:
            self._io.speak(_format_tts("seer_sleep", self._lang))
            self._io.set_scene("night")
        elif phase == Phase.NIGHT_WOLF_WAKE:
            self._io.set_scene("wolf_wake")
            self._io.speak(_format_tts("wolf_wake", self._lang))
        elif phase == Phase.NIGHT_WOLF_SLEEP:
            self._io.speak(_format_tts("wolf_sleep", self._lang))
            self._io.set_scene("night")

    async def on_role_wake(self, role: str) -> None:
        """Handle a role waking up - compatibility method for tests."""
        if not self._io:
            return
        if role == Role.SEER:
            self._io.set_scene("seer_wake")
            self._io.speak(_format_tts("seer_wake", self._lang))
        elif role == Role.WEREWOLF:
            self._io.set_scene("wolf_wake")
            self._io.speak(_format_tts("wolf_wake", self._lang))

    async def on_night_action_submitted(self, role: str) -> None:
        pass  # No longer needed - handled by phase events

    async def on_day_started(self, eliminated_player_id: str | None) -> None:
        if not self._io:
            return
        self._io.set_scene("day")

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

        self._io.speak(text)

    async def on_vote_started(self) -> None:
        if self._io:
            self._io.speak(_format_tts("vote_start", self._lang))

    async def on_vote_tie(self) -> None:
        if self._io:
            self._io.speak(_format_tts("vote_tie", self._lang))

    async def on_player_eliminated(
        self,
        player_id: str,
        cause: EliminationCause,
    ) -> None:
        if not self._io:
            return
        player = self._engine.state.players[player_id]
        role_name = _role_display(player.role, self._lang)

        self._io.set_scene("death")

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

        self._io.speak(text)

    async def on_game_over(self, winner: WinCondition) -> None:
        if not self._io:
            return
        scene = "wolves_win" if winner == WinCondition.WOLVES else "village_win"
        self._io.set_scene(scene)

        tts_key = "wolves_win" if winner == WinCondition.WOLVES else "villagers_win"
        self._io.speak(_format_tts(tts_key, self._lang))

    async def _handle_state_changed(self, event) -> None:
        phase = event.data.get("phase", "")
        _LOGGER.debug("PhaseManager received event phase: %s", phase)

        if Phase.is_night_subphase(phase):
            await self.on_phase_changed(phase)
        elif phase == Phase.DAY:
            eliminated = event.data.get("eliminated", [])
            killed_id = eliminated[-1] if eliminated else None
            await self.on_day_started(killed_id)
        elif phase == Phase.VOTE:
            await self.on_vote_started()

    async def _handle_game_started(self, event) -> None:
        io_interface = event.data.get("io")
        if io_interface:
            self._io = io_interface
            await self.on_game_started()

    def set_language(self, lang: str) -> None:
        self._lang = lang

    def set_io(self, io_interface) -> None:
        """Set the IO interface (called when game starts)."""
        self._io = io_interface