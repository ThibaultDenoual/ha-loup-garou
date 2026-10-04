"""Dev output handler — wires GameEngine events to TTS + lights."""
from __future__ import annotations

import logging

from custom_components.loup_garou.const import GameEvent, Phase, WinCondition
from custom_components.loup_garou.game_engine import GameEngine
from dev_lights import DevLights
from dev_tts import DevTTS

_LOGGER = logging.getLogger("dev_output")


class DevOutputHandler:
    """Subscribes to GameEngine events and drives TTS narration + light scenes."""

    def __init__(
        self,
        engine: GameEngine,
        tts: DevTTS,
        lights: DevLights,
        language: str = "fr",
        locale: dict | None = None,
    ) -> None:
        self._engine = engine
        self._tts = tts
        self._lights = lights
        self._language = language
        self._locale = locale or {}
        self._prev_phase: Phase | None = None

    def _t(self, key: str, **kwargs) -> str:
        text = self._locale.get(key, key)
        if kwargs:
            try:
                text = text.format(**kwargs)
            except KeyError:
                pass
        return text

    async def _narrate(self, key: str, **kwargs) -> None:
        text = self._t(key, **kwargs)
        await self._tts.narrate(text, self._language)

    def wire_events(self) -> None:
        """Attach handlers to GameEngine events."""

        async def on_phase_changed(data: dict) -> None:
            phase = data.get("phase")
            if phase == Phase.NIGHT:
                await self._narrate("phase.night.start")
                await self._lights.set_scene("night")
            elif phase == Phase.DAY:
                pass  # DAY_STARTED handles narration
            self._prev_phase = phase

        async def on_day_started(data: dict) -> None:
            elim = data.get("eliminated", [])
            if not elim:
                await self._narrate("phase.day.start_no_death")
                await self._lights.set_scene("day")
            else:
                pub = self._engine.get_public_state()
                for pid in elim:
                    p = next((pl for pl in pub["players"] if pl["id"] == pid), None)
                    if p:
                        article = "une" if p["role_id"] in ("witch", "seer") else "un"
                        await self._narrate(
                            "phase.day.start_with_death", name=p["name"], article=article, role=p["role_id"]
                        )
                await self._lights.set_scene("death")
                await self._lights.set_scene("day")

        async def on_player_eliminated(data: dict) -> None:
            cause = data.get("cause", "")
            name = data.get("name", "?")
            role = data.get("role", "?")
            if cause == "hunter_shot":
                await self._narrate("elimination.hunter_shot", name=name, target=name)
            elif cause == "lover_grief":
                await self._narrate("elimination.lover_grief", name=name)
            elif cause == "witch_poison":
                article = "une" if role == "witch" else "un"
                await self._narrate("elimination.witch_poison", name=name, article=article, role=role)
            elif cause == "village_vote":
                article = "une" if role == "witch" else "un"
                await self._narrate("elimination.village_vote", name=name, article=article, role=role)
            await self._lights.set_scene("death")
            await self._lights.set_scene("day")

        async def on_night_role_wake(data: dict) -> None:
            role = data.get("role", "")
            role_scenes = {
                "cupid": "cupid",
                "seer": "seer_wake",
                "werewolf": "wolf_wake",
                "alpha_wolf": "wolf_wake",
                "witch": "witch_wake",
            }
            scene = role_scenes.get(role)
            if scene:
                await self._lights.set_scene(scene)

            # Narrate role wake prompt
            if role == "cupid":
                await self._narrate("night.cupid.prompt")
            elif role == "seer":
                await self._narrate("night.seer.prompt")
            elif role in ("werewolf", "alpha_wolf"):
                await self._narrate("night.werewolf.prompt")
            elif role == "witch":
                await self._narrate("night.witch.prompt")

        async def on_night_role_sleep(data: dict) -> None:
            role = data.get("role", "")
            if role == "cupid":
                await self._narrate("night.cupid.done")
            elif role == "seer":
                await self._narrate("night.seer.done")
            elif role in ("werewolf", "alpha_wolf"):
                await self._narrate("night.werewolf.done")
            elif role == "witch":
                await self._narrate("night.witch.done")
            await self._lights.set_scene("night")

        async def on_vote_started(data: dict) -> None:
            await self._narrate("phase.vote.start")
            await self._lights.set_scene("day")

        async def on_vote_resolved(data: dict) -> None:
            eliminated = data.get("eliminated")
            if eliminated:
                pub = self._engine.get_public_state()
                p = next((pl for pl in pub["players"] if pl["id"] == eliminated), None)
                if p:
                    article = "une" if p["role_id"] == "witch" else "un"
                    await self._narrate(
                        "phase.vote.result", name=p["name"], article=article, role=p["role_id"]
                    )
                await self._lights.set_scene("death")
            else:
                await self._narrate("phase.vote.tie")
            await self._lights.set_scene("day")

        async def on_game_over(data: dict) -> None:
            winner = data.get("winner")
            if winner == WinCondition.WOLVES:
                await self._narrate("phase.game_over.wolves_win")
                await self._lights.set_scene("wolves_win")
            elif winner == WinCondition.VILLAGE:
                await self._narrate("phase.game_over.village_win")
                await self._lights.set_scene("village_win")
            elif winner == WinCondition.LOVERS:
                await self._narrate("phase.game_over.lovers_win")
                await self._lights.set_scene("lovers_win")

        async def on_game_started(data: dict) -> None:
            await self._narrate("phase.game_started")
            await self._lights.set_scene("night")

        self._engine.on(GameEvent.PHASE_CHANGED, on_phase_changed)
        self._engine.on(GameEvent.DAY_STARTED, on_day_started)
        self._engine.on(GameEvent.PLAYER_ELIMINATED, on_player_eliminated)
        self._engine.on(GameEvent.NIGHT_ROLE_WAKE, on_night_role_wake)
        self._engine.on(GameEvent.NIGHT_ROLE_SLEEP, on_night_role_sleep)
        self._engine.on(GameEvent.VOTE_STARTED, on_vote_started)
        self._engine.on(GameEvent.VOTE_RESOLVED, on_vote_resolved)
        self._engine.on(GameEvent.GAME_OVER, on_game_over)
        self._engine.on(GameEvent.GAME_STARTED, on_game_started)