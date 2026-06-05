"""Atmosphere — subscribes to engine events → lights + TTS, in sync with the UI."""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant

from ..const import (
    GameEvent, LIGHT_SCENES, ROLE_SCENE, STATIC_AUDIO_MAP, TTS_PHASE_DELAYS,
    CONF_AUDIO_SOURCE, CONF_AUDIO_OUTPUT, CONF_SPEAKER, CONF_LIGHTS, CONF_LANGUAGE, CONF_TTS_ENGINE,
)

if TYPE_CHECKING:
    from ..game_server import LoupGarouServer
    from ..game_engine import GameEngine

_LOGGER = logging.getLogger(__name__)

# Roles whose French article is "une" (feminine)
_FEMININE_ROLES = {"seer", "witch", "little_girl"}


class Atmosphere:
    def __init__(
        self,
        hass: HomeAssistant,
        engine: "GameEngine",
        light_entities: list[str],
        speaker_entity: str,
        tts_engine: str,
        language: str,
        locale: dict | None = None,
        audio_source: str = "tts",
        audio_output: str = "browser",
        server: "LoupGarouServer | None" = None,
    ) -> None:
        self._hass = hass
        self._engine = engine
        self._lights = light_entities
        self._speaker = speaker_entity
        self._tts_engine = tts_engine
        self._language = language
        self._locale: dict = locale if locale is not None else self._load_locale(language)
        self._current_scene: str = "day"
        self._audio_source = audio_source
        self._audio_output = audio_output
        self._server = server

    def update_config(self, cfg: dict) -> None:
        self._audio_source = cfg.get(CONF_AUDIO_SOURCE, self._audio_source)
        self._audio_output = cfg.get(CONF_AUDIO_OUTPUT, self._audio_output)
        self._speaker      = cfg.get(CONF_SPEAKER,      self._speaker)
        self._lights       = cfg.get(CONF_LIGHTS,       self._lights)
        self._language     = cfg.get(CONF_LANGUAGE,     self._language)
        self._tts_engine   = cfg.get(CONF_TTS_ENGINE,   self._tts_engine)

    # ── Locale ────────────────────────────────────────────────────────────────

    def _load_locale(self, language: str) -> dict:
        path = Path(__file__).parent.parent / "locales" / f"{language}.json"
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            _LOGGER.exception("Failed to load locale %s", language)
            return {}

    def t(self, key: str, **kwargs) -> str:
        text = self._locale.get(key, "")
        if not text:
            return ""
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, ValueError):
                pass
        return text

    def _article(self, role_id: str) -> str:
        if self._language == "fr":
            return "une" if role_id in _FEMININE_ROLES else "un"
        return self.t("article.male") or "a"

    # ── Event wiring ──────────────────────────────────────────────────────────

    def wire_events(self) -> None:
        e = self._engine
        e.on(GameEvent.PHASE_CHANGED, self._on_phase_changed)
        e.on(GameEvent.NIGHT_ROLE_WAKE, self._on_role_wake)
        e.on(GameEvent.NIGHT_ROLE_SLEEP, self._on_role_sleep)
        e.on(GameEvent.DAY_STARTED, self._on_day_started)
        e.on(GameEvent.VOTE_STARTED, self._on_vote_started)
        e.on(GameEvent.VOTE_RESOLVED, self._on_vote_resolved)
        e.on(GameEvent.PLAYER_ELIMINATED, self._on_player_eliminated)
        e.on(GameEvent.HUNTER_SHOT, self._on_hunter_shot)
        e.on(GameEvent.GAME_OVER, self._on_game_over)

    # ── Handlers ──────────────────────────────────────────────────────────────

    async def _on_phase_changed(self, data: dict) -> None:
        phase = data.get("phase")
        if phase == "night":
            await self._set_lights("night")
            await self.speak(self.t("phase.night.start"), delay_key="night_start", locale_key="phase.night.start")
        # day and vote handled by their dedicated events

    async def _on_role_wake(self, data: dict) -> None:
        role_id = data.get("role")
        result = data.get("result")

        if result:
            # Seer investigation result — TTS deliberately omitted (seer reads screen)
            return

        scene_key = ROLE_SCENE.get(role_id or "")
        if scene_key:
            self._current_scene = scene_key
            await self._set_lights(scene_key)

        wake_text = self.t(f"role.{role_id}.wake")
        if wake_text:
            await self.speak(wake_text, delay_key="role_wake", locale_key=f"role.{role_id}.wake")

    async def _on_role_sleep(self, data: dict) -> None:
        role_id = data.get("role")
        sleep_text = self.t(f"role.{role_id}.sleep")
        if sleep_text:
            await self.speak(sleep_text, delay_key="role_sleep", locale_key=f"role.{role_id}.sleep")
        await self._set_lights("night")
        self._current_scene = "night"

    async def _on_day_started(self, data: dict) -> None:
        await self._set_lights("day")
        self._current_scene = "day"
        eliminated_ids: list[str] = data.get("eliminated", [])
        pub = self._engine.get_public_state()
        players_by_id = {p["id"]: p for p in pub["players"]}

        if not eliminated_ids:
            await self.speak(self.t("phase.day.start_no_death"), delay_key="day_no_death", locale_key="phase.day.start_no_death")
            return

        for pid in eliminated_ids:
            p = players_by_id.get(pid, {})
            name = p.get("name", "?")
            role_id = p.get("role_id", "?")
            role_name = self.t(f"role.{role_id}.name") or role_id
            article = self._article(role_id)
            await self.speak(
                self.t("phase.day.start_with_death", name=name, article=article, role=role_name),
                delay_key="day_with_death",
            )

    async def _on_vote_started(self, data: dict) -> None:
        await self.speak(self.t("phase.vote.start"), delay_key="vote_start", locale_key="phase.vote.start")

    async def _on_vote_resolved(self, data: dict) -> None:
        eliminated_id = data.get("eliminated")
        is_tie = data.get("tie", False)
        if is_tie and not eliminated_id:
            await self.speak(self.t("phase.vote.tie"), delay_key="vote_result", locale_key="phase.vote.tie")
            return
        if eliminated_id:
            pub = self._engine.get_public_state()
            players_by_id = {p["id"]: p for p in pub["players"]}
            p = players_by_id.get(eliminated_id, {})
            name = p.get("name", "?")
            role_id = p.get("role_id", "?")
            role_name = self.t(f"role.{role_id}.name") or role_id
            article = self._article(role_id)
            await self.speak(
                self.t("phase.vote.result", name=name, article=article, role=role_name),
                delay_key="vote_result",
            )

    async def _on_player_eliminated(self, data: dict) -> None:
        cause = data.get("cause", "")
        # Wolf kills and witch poison are announced on day start.
        # Lover grief and scapegoat happen live — speak them immediately.
        # Hunter shots are handled by _on_hunter_shot via HUNTER_SHOT event.
        if cause == "lover_grief":
            name = data.get("name", "?")
            await self.speak(self.t("elimination.lover_grief", name=name), delay_key="elimination_live")
            await self._set_lights("death")
        elif cause == "scapegoat":
            name = data.get("name", "?")
            role_id = data.get("role", "?")
            role_name = self.t(f"role.{role_id}.name") or role_id
            article = self._article(role_id)
            await self.speak(
                self.t("elimination.scapegoat", name=name, article=article, role=role_name),
                delay_key="elimination_live",
            )
            await self._set_lights("death")

    async def _on_hunter_shot(self, data: dict) -> None:
        """Fired by the Hunter role before its target enters the elimination queue.

        The HUNTER_SHOT event carries both the hunter's name and the target's
        name, so the TTS message can correctly say 'Alice drags Bob into death'
        rather than using the generic PLAYER_ELIMINATED payload (which only
        carries the target's own name, and arrives with the original cause).
        """
        hunter_name = data.get("hunter_name", "?")
        target_name = data.get("target_name", "?")
        await self.speak(
            self.t("elimination.hunter_shot", name=hunter_name, target=target_name),
            delay_key="elimination_live",
        )
        await self._set_lights("death")

    async def _on_game_over(self, data: dict) -> None:
        winner = data.get("winner")
        scene_map = {"wolves": "wolves_win", "village": "village_win", "lovers": "lovers_win"}
        msg_map = {
            "wolves": "phase.game_over.wolves_win",
            "village": "phase.game_over.village_win",
            "lovers": "phase.game_over.lovers_win",
        }
        scene_key = scene_map.get(winner or "")
        if scene_key:
            await self._set_lights(scene_key)
        msg_key = msg_map.get(winner or "")
        if msg_key:
            await self.speak(self.t(msg_key), delay_key="game_over", locale_key=msg_key)

    # ── HA service calls ──────────────────────────────────────────────────────

    async def _set_lights(self, scene_key: str) -> None:
        scene = LIGHT_SCENES.get(scene_key)
        if not scene or not self._lights:
            return
        for entity_id in self._lights:
            service_data: dict = {"entity_id": entity_id, **scene}
            service_data.pop("flash", None)
            service_data.pop("strobe", None)
            try:
                await self._hass.services.async_call(
                    "light", "turn_on", service_data, blocking=False
                )
            except Exception:
                _LOGGER.exception("Failed to set light scene %s on %s", scene_key, entity_id)

    async def speak(self, text: str, delay_key: str = "role_wake", locale_key: str | None = None) -> None:
        """Speak narration text and wait for completion.

        audio_source determines content:
          "tts"    — synthesised at runtime (Web Speech API or HA TTS service)
          "static" — pre-recorded MP3; falls back to Web Speech for dynamic text

        audio_output determines the playback channel:
          "browser" — delegates to server.narrate(); browser plays and sends tts_done
          "ha"      — plays directly on a HA media_player entity
        """
        if not text:
            return

        # Resolve a static audio URL when the locale key has a pre-recorded file
        audio_url: str | None = None
        if self._audio_source == "static" and locale_key and locale_key in STATIC_AUDIO_MAP:
            stem = STATIC_AUDIO_MAP[locale_key]
            audio_url = f"/loup_garou/audio/{self._language}/{stem}.mp3"

        if self._audio_output == "browser":
            if self._server is not None:
                await self._server.narrate(text, self._language, audio_url=audio_url)
            return

        # HA output
        if audio_url:
            await self._play_static_ha(audio_url, delay_key)
        else:
            await self._speak_tts_ha(text, delay_key)

    async def _speak_tts_ha(self, text: str, delay_key: str) -> None:
        if not self._speaker:
            return
        try:
            await self._hass.services.async_call(
                "tts",
                "speak",
                {
                    "entity_id": self._tts_engine,
                    "media_player_entity_id": self._speaker,
                    "message": text,
                    "language": self._language,
                },
                blocking=False,
            )
        except Exception:
            _LOGGER.exception("Failed to speak via TTS: %s", text)
        await asyncio.sleep(TTS_PHASE_DELAYS.get(delay_key, 2.5))

    async def _play_static_ha(self, audio_url: str, delay_key: str) -> None:
        if not self._speaker:
            return
        base_url = (
            getattr(self._hass.config, "internal_url", None)
            or getattr(self._hass.config, "external_url", None)
            or ""
        ).rstrip("/")
        if not base_url:
            _LOGGER.warning("static+ha: no HA base URL configured; cannot play %s", audio_url)
            await asyncio.sleep(TTS_PHASE_DELAYS.get(delay_key, 2.5))
            return
        try:
            await self._hass.services.async_call(
                "media_player",
                "play_media",
                {
                    "entity_id": self._speaker,
                    "media_content_id": f"{base_url}{audio_url}",
                    "media_content_type": "music",
                },
                blocking=False,
            )
        except Exception:
            _LOGGER.exception("Failed to play static audio on HA: %s", audio_url)
        await asyncio.sleep(TTS_PHASE_DELAYS.get(delay_key, 2.5))
