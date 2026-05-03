"""Phase orchestration: coordinates GameEngine, LightController, SpeakerController.

PhaseManager is the glue layer. It receives high-level game events
(night started, wolf acted, day began, etc.) and fires the appropriate
TTS narration and light scenes in the right order.

It does NOT contain game logic — that lives in GameEngine.
It does NOT drive the UI — that is driven by WebSocket events fired by GameEngine.
"""
from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant

from .const import (
    Phase,
    Role,
    NightActionType,
    EliminationCause,
    WinCondition,
    ROLE_NAMES_FR,
    ROLE_NAMES_EN,
    ROLE_ARTICLES_FR,
    TTS,
    EVENT_GAME_STATE_CHANGED,
)
from .game_engine import GameEngine
from .light_controller import LightController
from .speaker_controller import SpeakerController

_LOGGER = logging.getLogger(__name__)


def _role_display(role: Role, lang: str) -> str:
    if lang == "fr":
        return ROLE_NAMES_FR.get(role, role)
    return ROLE_NAMES_EN.get(role, role)


def _format_tts(key: str, lang: str, **kwargs) -> str:
    template = TTS[key][lang]
    return template.format(**kwargs)


class PhaseManager:
    """Coordinates phase transitions across engine, lights, and speaker."""

    def __init__(
        self,
        hass: HomeAssistant,
        engine: GameEngine,
        lights: LightController,
        speaker: SpeakerController,
        language: str,
    ) -> None:
        self._hass = hass
        self._engine = engine
        self._lights = lights
        self._speaker = speaker
        self._lang = language

        # Listen to engine events so PhaseManager can react
        hass.bus.async_listen(
            EVENT_GAME_STATE_CHANGED,
            self._handle_state_changed,
        )

    # ── Entry points called by websocket_api ──

    async def on_game_started(self) -> None:
        """Called after GameEngine.start_game() completes.

        Announces role distribution; lights stay neutral (day) at this point.
        """
        await self._speaker.async_speak(
            _format_tts("roles_distributed", self._lang)
        )

    async def on_night_started(self) -> None:
        """Called when a new night begins (after role reveal OR after a day/vote cycle)."""
        await self._lights.async_set_scene("night")
        await self._speaker.async_speak(_format_tts("night_start", self._lang))
        # Kick off the first role's wake sequence
        await self._on_night_role_advanced()

    async def on_role_wake(self, role: Role) -> None:
        """Announce a specific role waking up and set the matching light scene."""
        scene_map: dict[Role, str] = {
            Role.SEER: "seer_wake",
            Role.WEREWOLF: "wolf_wake",
        }
        tts_wake_map: dict[Role, str] = {
            Role.SEER: "seer_wake",
            Role.WEREWOLF: "wolf_wake",
        }
        tts_sleep_map: dict[Role, str] = {
            Role.SEER: "seer_sleep",
            Role.WEREWOLF: "wolf_sleep",
        }

        scene = scene_map.get(role, "night")
        await self._lights.async_set_scene(scene)

        wake_key = tts_wake_map.get(role)
        if wake_key:
            await self._speaker.async_speak(_format_tts(wake_key, self._lang))

        # Note: we do NOT announce sleep here.
        # The sleep TTS fires after the action is submitted (see on_night_action_submitted).
        _ = tts_sleep_map  # kept for future use

    async def on_night_action_submitted(self, role: Role) -> None:
        """Announce the role going back to sleep after their action."""
        tts_sleep_map: dict[Role, str] = {
            Role.SEER: "seer_sleep",
            Role.WEREWOLF: "wolf_sleep",
        }
        sleep_key = tts_sleep_map.get(role)
        if sleep_key:
            await self._speaker.async_speak(_format_tts(sleep_key, self._lang))
        # Return lights to neutral night scene
        await self._lights.async_set_scene("night")

    async def on_day_started(self, eliminated_player_id: str | None) -> None:
        """Announce the day, including who (if anyone) was killed overnight."""
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
        """Announce the vote phase."""
        await self._speaker.async_speak(_format_tts("vote_start", self._lang))

    async def on_vote_tie(self) -> None:
        await self._speaker.async_speak(_format_tts("vote_tie", self._lang))

    async def on_player_eliminated(
        self,
        player_id: str,
        cause: EliminationCause,
    ) -> None:
        """Announce an elimination (from a village vote, not from wolf kill at night)."""
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
        """Play the win scene and announce the winner."""
        scene = "wolves_win" if winner == WinCondition.WOLVES else "village_win"
        await self._lights.async_set_scene(scene)

        tts_key = "wolves_win" if winner == WinCondition.WOLVES else "villagers_win"
        await self._speaker.async_speak(_format_tts(tts_key, self._lang))

    # ── Internal event listener ───────────────

    async def _handle_state_changed(self, event) -> None:
        """React to engine state changes and trigger atmosphere effects."""
        subtype: str = event.data.get("subtype", "")
        _LOGGER.debug("PhaseManager received event subtype: %s", subtype)

        if subtype == "night_started":
            await self.on_night_started()

        elif subtype == "night_role_advanced":
            await self._on_night_role_advanced()

        elif subtype == "day_started":
            # Find who was killed this night (last elimination this round)
            eliminations = self._engine.state.eliminations
            night_kills = [
                e for e in eliminations
                if e["round"] == self._engine.state.round
                and e["cause"] == EliminationCause.WOLF_KILL
            ]
            killed_id = night_kills[-1]["player_id"] if night_kills else None
            await self.on_day_started(killed_id)

        elif subtype == "vote_started":
            await self.on_vote_started()

        elif subtype == "player_eliminated":
            player_id = event.data.get("player_id")
            if player_id and self._engine.state.phase == Phase.VOTE:
                await self.on_player_eliminated(player_id, EliminationCause.VILLAGE_VOTE)

        elif subtype == "game_over":
            winner = WinCondition(event.data["winner"])
            await self.on_game_over(winner)

    async def _on_night_role_advanced(self) -> None:
        """Announce the currently-acting night role."""
        acting_role = self._engine.state.phase == Phase.NIGHT and \
            self._engine._current_night_role()  # noqa: SLF001
        if acting_role:
            await self.on_role_wake(acting_role)