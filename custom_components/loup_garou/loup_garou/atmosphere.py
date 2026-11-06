"""Atmosphere — subscribes to engine events → lights + TTS, in sync with the UI."""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.network import NoURLAvailableError, get_url

from ..const import (
    GameEvent, LIGHT_SCENES, ROLE_SCENE, STATIC_AUDIO_MAP, STATIC_AUDIO_MARGIN,
    STATIC_AUDIO_SECONDS, TTS_PHASE_DELAYS,
    SPEAKER_GAP, SPEAKER_MAX_LINE, SPEAKER_START_TIMEOUT, DEATH_BEAT,
    CONF_AUDIO_SOURCE, CONF_AUDIO_OUTPUT, CONF_SPEAKER, CONF_LIGHTS, CONF_LANGUAGE, CONF_TTS_ENGINE,
)

from .. import voice
from ..narration import NarrationMessage

if TYPE_CHECKING:
    from ..game_server import LoupGarouServer
    from ..game_engine import GameEngine

_LOGGER = logging.getLogger(__name__)

_PLAYING = "playing"
_FEATURE_MEDIA_ANNOUNCE = 1048576  # MediaPlayerEntityFeature.MEDIA_ANNOUNCE


class SpeakerResult:
    """What happened to a line sent to a Home Assistant speaker."""

    PLAYED = "played"            # the speaker went to "playing" and back
    SENT = "sent"                # sent, but the speaker can't tell us if it played
    NOT_STARTED = "not_started"  # sent, and the speaker never started playing
    REFUSED = "refused"          # Home Assistant refused the service call
    NO_URL = "no_url"            # Home Assistant has no address to give the speaker
    NO_SPEAKER = "no_speaker"    # no speaker chosen

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
        self._intro_task: asyncio.Task | None = None
        # None until the speaker has played a line; False once it failed to
        # report "playing" before ever doing so, which means fixed delays.
        self._speaker_reports_state: bool | None = None

    @property
    def language(self) -> str:
        return self._language

    def update_config(self, cfg: dict, locale: dict | None = None) -> None:
        """Apply saved settings; pass the new locale when the language changed."""
        self._audio_source = cfg.get(CONF_AUDIO_SOURCE, self._audio_source)
        self._audio_output = cfg.get(CONF_AUDIO_OUTPUT, self._audio_output)
        speaker = cfg.get(CONF_SPEAKER, self._speaker)
        if speaker != self._speaker:
            self._speaker_reports_state = None
        self._speaker      = speaker
        self._lights       = cfg.get(CONF_LIGHTS,       self._lights)
        self._language     = cfg.get(CONF_LANGUAGE,     self._language)
        self._tts_engine   = cfg.get(CONF_TTS_ENGINE,   self._tts_engine)
        if locale is not None:
            self._locale = locale

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
            _LOGGER.warning("Missing locale key: %r (language=%s)", key, self._language)
            return ""
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, ValueError):
                _LOGGER.error("Format error on locale key: %r (language=%s)", key, self._language)
        return text

    def _article(self, role_id: str) -> str:
        if self._language == "fr":
            return "une" if role_id in _FEMININE_ROLES else "un"
        return self.t("article.male") or "a"

    # ── Event wiring ──────────────────────────────────────────────────────────

    def wire_events(self) -> None:
        e = self._engine
        e.on(GameEvent.GAME_STARTED, self._on_game_started)
        e.on(GameEvent.REVEAL_TURN, self._on_reveal_turn)
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

    async def _on_game_started(self, data: dict) -> None:
        # Set the scene while the phone goes round for the secret roles. Not
        # awaited: start_game runs inside the WebSocket handler, which must stay
        # free to receive the browser's tts_done.
        self._intro_task = asyncio.create_task(
            self.speak(self._narrate("phase.role_reveal.start", delay_key="intro"))
        )

    async def _on_reveal_turn(self, data: dict) -> None:
        """Call the next player to the phone by their trade: "Step forward… the Baker".

        Hearing it once per player is how everyone learns their public role.
        """
        if self._intro_task and not self._intro_task.done():
            await asyncio.shield(self._intro_task)
        public = self._player(data.get("player_id")).get("public_role")
        if public:
            await self.speak(self._narrate_parts(
                ["part.step_forward", f"public.{public}.spoken"], delay_key="reveal_turn",
            ))

    def shutdown(self) -> None:
        """Stop narration still running in the background (entry unload)."""
        if self._intro_task and not self._intro_task.done():
            self._intro_task.cancel()

    async def _on_phase_changed(self, data: dict) -> None:
        phase = data.get("phase")
        if phase == "night":
            # Start dark fade simultaneously with narration so darkness builds as narrator speaks
            asyncio.create_task(self._set_lights("night"))
            await asyncio.sleep(0.5)
            await self.speak(self._narrate("phase.night.start", delay_key="night_start"))
            # Let darkness settle before first role wakes
            await asyncio.sleep(2.0)
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
            # Start role-color flash just before speaking so it's fully lit by command's end
            asyncio.create_task(self._set_lights(scene_key))
            await asyncio.sleep(0.3)

        if self.t(f"role.{role_id}.wake"):
            await self.speak(self._narrate(f"role.{role_id}.wake", delay_key="role_wake"))

    async def _on_role_sleep(self, data: dict) -> None:
        role_id = data.get("role")
        if self.t(f"role.{role_id}.sleep"):
            await self.speak(self._narrate(f"role.{role_id}.sleep", delay_key="role_sleep"))
        # Lights fade back to night as the role "obeys" the command
        asyncio.create_task(self._set_lights("night"))
        self._current_scene = "night"
        # Settle pause before next role wakes
        await asyncio.sleep(1.0)

    async def _on_day_started(self, data: dict) -> None:
        if data.get("after") == "vote":
            # The engine also starts a day after each vote. The verdict and any
            # live deaths have already been narrated, and it isn't a new dawn.
            return
        # Gentle day brightening starts immediately while players wait in suspense
        asyncio.create_task(self._set_lights("day"))
        self._current_scene = "day"
        eliminated_ids: list[str] = data.get("eliminated", [])

        # Dramatic pause while lights brighten — the most tense moment of the game
        await asyncio.sleep(2.5)

        if not eliminated_ids:
            await self.speak(self._narrate("phase.day.start_no_death", delay_key="day_no_death"))
        else:
            await self._announce_deaths(eliminated_ids)
        await self.speak(self._narrate("phase.day.debate", delay_key="day_debate"))

    async def _announce_deaths(self, eliminated_ids: list[str]) -> None:
        pub = self._engine.get_public_state()
        players_by_id = {p["id"]: p for p in pub["players"]}

        # Suspense prelude before revealing who died
        await self.speak(self._narrate("phase.day.prelude_death", delay_key="day_prelude"))
        await asyncio.sleep(0.8)

        for i, pid in enumerate(eliminated_ids):
            await self.speak(self._death_line(
                "part.victim", players_by_id.get(pid, {}),
                fallback="phase.day.start_with_death", delay_key="day_with_death",
            ))
            if i < len(eliminated_ids) - 1:
                await asyncio.sleep(0.5)

    async def _on_vote_started(self, data: dict) -> None:
        await self.speak(self._narrate("phase.vote.start", delay_key="vote_start"))

    async def _on_vote_resolved(self, data: dict) -> None:
        eliminated_id = data.get("eliminated")
        is_tie = data.get("tie", False)
        await asyncio.sleep(0.5)
        if is_tie and not eliminated_id:
            await self.speak(self._narrate("phase.vote.tie", delay_key="vote_result"))
            return
        if eliminated_id:
            await self.speak(self._death_line(
                "part.vote", self._player(eliminated_id),
                fallback="phase.vote.result", delay_key="vote_result",
            ))

    async def _on_player_eliminated(self, data: dict) -> None:
        cause = data.get("cause", "")
        # Wolf kills and witch poison are announced on day start.
        # Lover grief and scapegoat happen live — speak them immediately.
        # Hunter shots are handled by _on_hunter_shot via HUNTER_SHOT event.
        if cause == "lover_grief":
            await self._live_death(self._death_line(
                "part.grief", self._player(data.get("player_id"), data),
                fallback="elimination.lover_grief", delay_key="elimination_live",
            ))
        elif cause == "scapegoat":
            await self._live_death(self._death_line(
                "part.scapegoat", self._player(data.get("player_id"), data),
                fallback="elimination.scapegoat", delay_key="elimination_live",
            ))

    async def _on_hunter_shot(self, data: dict) -> None:
        """Fired by the Hunter role before its target enters the elimination queue.

        The HUNTER_SHOT event carries both the hunter's name and the target's
        name, so the TTS message can correctly say 'Alice drags Bob into death'
        rather than using the generic PLAYER_ELIMINATED payload (which only
        carries the target's own name, and arrives with the original cause).
        """
        target = self._player(data.get("target_id"), {
            "name": data.get("target_name", "?"), "role_id": data.get("target_role", "?"),
        })
        if target.get("public_role"):
            msg = self._death_line(
                "part.hunter", target, fallback="", delay_key="elimination_live",
            )
        else:
            msg = self._narrate(
                "elimination.hunter_shot", delay_key="elimination_live",
                name=data.get("hunter_name", "?"), target=data.get("target_name", "?"),
            )
        await self._live_death(msg)

    async def _live_death(self, msg: NarrationMessage) -> None:
        """A death in front of everyone: red light, the line, then a beat.

        The engine waits for this handler, so the beat also holds back the
        next step, game over included, and the death has time to sink in.
        """
        asyncio.create_task(self._set_lights("death"))
        self._current_scene = "death"
        await self.speak(msg)
        await asyncio.sleep(DEATH_BEAT)

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
            asyncio.create_task(self._set_lights(scene_key))
        await asyncio.sleep(0.5)
        msg_key = msg_map.get(winner or "")
        if msg_key:
            await self.speak(self._narrate(msg_key, delay_key="game_over"))
            await self.speak(self._narrate("phase.game_over.reveal", delay_key="game_over_reveal"))

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

    def _player(self, player_id: str | None, fallback: dict | None = None) -> dict:
        """A player as the engine's full state has them, roles included."""
        for p in self._engine.get_public_state()["players"]:
            if p["id"] == player_id:
                return p
        fallback = dict(fallback or {})
        fallback.setdefault("role_id", fallback.get("role", "?"))
        return fallback

    def _death_line(
        self, lead: str, player: dict, *, fallback: str, delay_key: str,
    ) -> NarrationMessage:
        """Announce a death by the player's public role, from recorded parts:
        "The victim is…" + "the Baker" + "They were…" + "a Seer".

        Without a public role, the older line with the player's name is used.
        """
        role_id = player.get("role_id", "?")
        public = player.get("public_role")
        if public:
            return self._narrate_parts(
                [lead, f"public.{public}.spoken", "part.was", f"role.{role_id}.spoken"],
                delay_key=delay_key,
            )
        return self._narrate(
            fallback, delay_key=delay_key, name=player.get("name", "?"),
            article=self._article(role_id), role=self.t(f"role.{role_id}.name") or role_id,
        )

    def _narrate_parts(self, keys: list[str], *, delay_key: str) -> NarrationMessage:
        """One line from several recorded parts, played as a single joined clip."""
        parts = [part for part in (self.t(k) for k in keys) if part]
        # Parts that don't end a phrase themselves ("the Baker") get a full stop.
        text = " ".join(p if p[-1] in ".…!?:" else p + "." for p in parts)
        audio_url: str | None = None
        audio_seconds: float | None = None
        if self._audio_source == "static" and all(k in STATIC_AUDIO_MAP for k in keys):
            stems = [STATIC_AUDIO_MAP[k] for k in keys]
            lengths = STATIC_AUDIO_SECONDS.get(self._language, {})
            audio_url = voice.url(self._language, stems)
            if all(stem in lengths for stem in stems):
                audio_seconds = round(sum(lengths[stem] for stem in stems), 1)
        return NarrationMessage(
            text=text, lang=self._language, audio_url=audio_url,
            delay_key=delay_key, audio_seconds=audio_seconds,
        )

    def _narrate(self, key: str, *, delay_key: str, **params) -> NarrationMessage:
        """Build a NarrationMessage from a locale key, resolving text and static
        audio from that single key.

        Static MP3s exist only for fixed-text keys; parameterized messages
        (names/roles) interpolate at runtime and are absent from STATIC_AUDIO_MAP,
        so the `not params` guard keeps the rule explicit and self-enforcing.
        """
        text = self.t(key, **params)
        audio_url: str | None = None
        audio_seconds: float | None = None
        if self._audio_source == "static" and not params and key in STATIC_AUDIO_MAP:
            stem = STATIC_AUDIO_MAP[key]
            audio_url = f"/loup_garou/audio/{self._language}/{stem}.mp3"
            audio_seconds = STATIC_AUDIO_SECONDS.get(self._language, {}).get(stem)
        return NarrationMessage(
            text=text, lang=self._language, audio_url=audio_url,
            delay_key=delay_key, audio_seconds=audio_seconds,
        )

    async def speak(self, msg: NarrationMessage) -> str | None:
        """Route a narration message to the configured output (browser or HA).

        audio_output determines the playback channel:
          "browser" — delegates to server.narrate(); browser plays and sends tts_done
          "ha"      — plays directly on a HA media_player entity

        On a HA speaker it returns a SpeakerResult value; in the browser, None.
        """
        if not msg.text:
            return None
        if self._audio_output == "browser":
            if self._server is not None:
                await self._server.narrate(msg)
            return None
        if msg.audio_url:
            return await self._play_static_ha(msg.audio_url, msg.delay_key, msg.audio_seconds)
        return await self._speak_tts_ha(msg.text, msg.delay_key)

    async def test_speaker(self) -> str | None:
        """Play the night-fall line for "Test the narration", watching the speaker afresh."""
        self._speaker_reports_state = None
        return await self.speak(self._narrate("phase.night.start", delay_key="night_start"))

    async def _speak_tts_ha(self, text: str, delay_key: str) -> str:
        if not self._speaker:
            return SpeakerResult.NO_SPEAKER
        return await self._play_and_wait(
            "tts",
            "speak",
            {
                "entity_id": self._tts_engine,
                "media_player_entity_id": self._speaker,
                "message": text,
                "language": self._language,
            },
            fallback=TTS_PHASE_DELAYS.get(delay_key, 2.5),
            what=text,
        )

    async def _play_static_ha(
        self, audio_url: str, delay_key: str, audio_seconds: float | None = None
    ) -> str:
        if not self._speaker:
            return SpeakerResult.NO_SPEAKER
        # Wait out the whole clip: a speaker given the next play_media while
        # still playing (or loading) cuts or drops one of the two.
        wait = TTS_PHASE_DELAYS.get(delay_key, 2.5)
        if audio_seconds:
            wait = max(wait, audio_seconds + STATIC_AUDIO_MARGIN)
        base_url = self._base_url()
        if not base_url:
            _LOGGER.warning(
                "Home Assistant has no URL the speaker can reach, so %s can't play. "
                "Set one in Settings > System > Network.", audio_url,
            )
            await asyncio.sleep(wait)
            return SpeakerResult.NO_URL
        data = {
            "entity_id": self._speaker,
            "media_content_id": f"{base_url}{audio_url}",
            "media_content_type": "music",
        }
        # Narration is an announcement, as tts.speak sends it. Some speakers
        # (ESPHome with only an announcement pipeline) play nothing otherwise.
        if self._speaker_supports_announce():
            data["announce"] = True
        return await self._play_and_wait(
            "media_player", "play_media", data, fallback=wait, what=audio_url,
        )

    def _base_url(self) -> str:
        """The address a speaker on the network can fetch Home Assistant's files from.

        get_url() follows the Network settings and falls back to the local IP,
        so it works without an internal URL set by hand.
        """
        try:
            url = get_url(self._hass, allow_cloud=False)
        except NoURLAvailableError:
            url = None
        except Exception:  # noqa: BLE001 — never let URL lookup stop the game
            _LOGGER.debug("get_url failed", exc_info=True)
            url = None
        if not isinstance(url, str):
            url = (
                getattr(self._hass.config, "internal_url", None)
                or getattr(self._hass.config, "external_url", None)
            )
        return url.rstrip("/") if isinstance(url, str) else ""

    def _speaker_supports_announce(self) -> bool:
        state = self._hass.states.get(self._speaker)
        features = getattr(state, "attributes", {}).get("supported_features", 0)
        return isinstance(features, int) and bool(features & _FEATURE_MEDIA_ANNOUNCE)

    def _speaker_state(self) -> str | None:
        state = self._hass.states.get(self._speaker)
        value = getattr(state, "state", None)
        return value if isinstance(value, str) else None

    async def _play_and_wait(
        self, domain: str, service: str, data: dict, *, fallback: float, what: str
    ) -> str:
        """Send one line to the speaker, then wait until it has been played.

        The speaker is watched while it goes to "playing" and back. A speaker
        that is already playing, has no state, or never reported "playing"
        before gets the fixed `fallback` wait instead.
        """
        watch = (
            self._speaker_reports_state is not False
            and self._speaker_state() not in (None, _PLAYING)
        )
        started, finished = asyncio.Event(), asyncio.Event()

        @callback
        def _on_change(event: Event) -> None:
            new_state = getattr(event.data.get("new_state"), "state", None)
            if new_state == _PLAYING:
                started.set()
            elif started.is_set():
                finished.set()

        # Subscribe before the call, so a fast speaker can't be missed.
        unsub = (
            async_track_state_change_event(self._hass, [self._speaker], _on_change)
            if watch else None
        )
        try:
            # Blocking, so a refused call (unknown TTS engine, speaker
            # unavailable) is logged here instead of lost in the background.
            try:
                # Shielded: giving up on the wait must not cancel the playback.
                await asyncio.wait_for(
                    asyncio.shield(
                        self._hass.services.async_call(domain, service, data, blocking=True)
                    ),
                    SPEAKER_START_TIMEOUT,
                )
            except TimeoutError:
                _LOGGER.warning(
                    "%s.%s took over %.0f s for %s", domain, service, SPEAKER_START_TIMEOUT, what
                )
            except Exception:
                _LOGGER.exception(
                    "Home Assistant refused %s.%s on %s for %s",
                    domain, service, self._speaker, what,
                )
                await asyncio.sleep(fallback)
                return SpeakerResult.REFUSED
            if not watch:
                await asyncio.sleep(fallback)
                return SpeakerResult.SENT
            try:
                await asyncio.wait_for(started.wait(), SPEAKER_START_TIMEOUT)
            except TimeoutError:
                if self._speaker_reports_state is None:
                    self._speaker_reports_state = False
                    _LOGGER.warning(
                        "%s did not start playing within %.0f s (%s). Check that it "
                        "can play this audio; narration now uses fixed delays.",
                        self._speaker, SPEAKER_START_TIMEOUT, what,
                    )
                else:
                    _LOGGER.warning("%s did not play %s", self._speaker, what)
                return SpeakerResult.NOT_STARTED
            self._speaker_reports_state = True
            try:
                await asyncio.wait_for(finished.wait(), SPEAKER_MAX_LINE)
            except TimeoutError:
                _LOGGER.warning(
                    "%s still playing after %.0f s; moving on", self._speaker, SPEAKER_MAX_LINE
                )
            await asyncio.sleep(SPEAKER_GAP)
            return SpeakerResult.PLAYED
        finally:
            if unsub is not None:
                unsub()
