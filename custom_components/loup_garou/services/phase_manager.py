"""Phase orchestration: coordinates engine, lights, and TTS."""
from __future__ import annotations

import logging

from ..const import (
    Phase,
    Role,
    EliminationCause,
    WinCondition,
    EVENT_GAME_STATE_CHANGED,
    EVENT_GAME_STARTED,
)
from ..core_game.i18n import t as i18n_t, role_name, role_article, tts, set_language as i18n_set_language

_LOGGER = logging.getLogger(__name__)


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
        self._pending_phase: str | None = None

        i18n_set_language(language)

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
            self._io.speak(tts("roles_distributed"))

    async def on_night_started(self) -> None:
        if self._io:
            self._io.set_scene("night")
            self._io.speak(tts("night_start"))

    async def on_phase_changed(self, phase: str) -> None:
        """Handle phase change events from the engine."""
        if not self._io:
            return
        if phase == Phase.NIGHT_START:
            await self.on_night_started()
        elif phase == Phase.NIGHT_SEER_WAKE:
            self._io.set_scene("seer_wake")
            self._io.speak(tts("seer_wake"))
        elif phase == Phase.NIGHT_SEER_SLEEP:
            self._io.speak(tts("seer_sleep"))
            self._io.set_scene("night")
        elif phase == Phase.NIGHT_WOLF_WAKE:
            self._io.set_scene("wolf_wake")
            self._io.speak(tts("wolf_wake"))
        elif phase == Phase.NIGHT_WOLF_SLEEP:
            self._io.speak(tts("wolf_sleep"))
            self._io.set_scene("night")

    async def on_role_wake(self, role: str) -> None:
        """Handle a role waking up - compatibility method for tests."""
        if not self._io:
            return
        if role == Role.SEER:
            self._io.set_scene("seer_wake")
            self._io.speak(tts("seer_wake"))
        elif role == Role.WEREWOLF:
            self._io.set_scene("wolf_wake")
            self._io.speak(tts("wolf_wake"))

    async def on_night_action_submitted(self, role: str) -> None:
        pass

    async def on_day_started(self, eliminated_player_id: str | None) -> None:
        if not self._io:
            return
        self._io.set_scene("day")

        if eliminated_player_id:
            player = self._engine.state.players[eliminated_player_id]
            r_name = role_name(player.role)
            if self._lang == "fr":
                article = role_article(player.role)
                text = tts("day_start_death", name=player.name, article=article, role=r_name)
            else:
                text = tts("day_start_death", name=player.name, role=r_name)
        else:
            text = tts("day_start_no_death")

        self._io.speak(text)

    async def on_vote_started(self) -> None:
        if self._io:
            self._io.speak(tts("vote_start"))

    async def on_vote_tie(self) -> None:
        if self._io:
            self._io.speak(tts("vote_tie"))

    async def on_player_eliminated(
        self,
        player_id: str,
        cause: EliminationCause,
    ) -> None:
        if not self._io:
            return
        player = self._engine.state.players[player_id]
        r_name = role_name(player.role)

        self._io.set_scene("death")

        if self._lang == "fr":
            article = role_article(player.role)
            text = tts("elimination", name=player.name, article=article, role=r_name)
        else:
            text = tts("elimination", name=player.name, role=r_name)

        self._io.speak(text)

    async def on_game_over(self, winner: WinCondition) -> None:
        if not self._io:
            return
        scene = "wolves_win" if winner == WinCondition.WOLVES else "village_win"
        self._io.set_scene(scene)

        tts_key = "wolves_win" if winner == WinCondition.WOLVES else "villagers_win"
        self._io.speak(tts(tts_key))

    async def _handle_state_changed(self, event) -> None:
        phase = event.data.get("phase", "")
        _LOGGER.debug("PhaseManager received event phase: %s", phase)

        if not self._io:
            self._pending_phase = phase
            return

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
            if self._pending_phase:
                pending = self._pending_phase
                self._pending_phase = None
                _LOGGER.debug("Processing pending phase: %s", pending)
                if Phase.is_night_subphase(pending):
                    await self.on_phase_changed(pending)

    def set_language(self, lang: str) -> None:
        self._lang = lang
        i18n_set_language(lang)

    def set_io(self, io_interface) -> None:
        """Set the IO interface (called when game starts)."""
        self._io = io_interface