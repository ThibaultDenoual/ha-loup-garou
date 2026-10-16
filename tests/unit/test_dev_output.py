"""Tests for DevOutputHandler — dev TTS/lights wiring to GameEngine events.

These lock in parity with the production Atmosphere handler:
- NIGHT_ROLE_WAKE carrying a seer `result` is a screen display, not a wake
  prompt, so it must NOT re-narrate the wake prompt (see atmosphere.py _on_role_wake).
- Village-vote deaths are announced once, via VOTE_RESOLVED, and never live
  via PLAYER_ELIMINATED (atmosphere omits cause == "village_vote" for the same reason).
"""
import asyncio

from custom_components.loup_garou.game_engine import GameEngine
from custom_components.loup_garou.roles.impl.seer import Seer
from custom_components.loup_garou.roles.impl.villager import Villager
from custom_components.loup_garou.roles.impl.werewolf import Werewolf
from dev_lights import DevLights
from dev_output import DevOutputHandler
from dev_tts import MockTTS


class RecordingTTS(MockTTS):
    def __init__(self) -> None:
        super().__init__(delays={})
        self.spoken: list[str] = []

    async def narrate(self, text: str, lang: str) -> None:
        self.spoken.append(text)


class RecordingLights(DevLights):
    def __init__(self) -> None:
        super().__init__([])
        self.scenes: list[str] = []

    async def set_scene(self, scene_key: str, transition: float | None = None) -> None:
        self.scenes.append(scene_key)

    async def turn_off(self, transition: float = 1.0) -> None:
        self.scenes.append("off")


def make_output():
    engine = GameEngine(
        roles={"seer": Seer(), "villager": Villager(), "werewolf": Werewolf()}
    )
    tts = RecordingTTS()
    lights = RecordingLights()
    DevOutputHandler(engine, tts, lights, "en").wire_events()
    return engine, tts, lights


async def test_seer_result_does_not_repeat_wake_prompt():
    """Seer investigation result is shown on-screen; the wake prompt must only play once."""
    engine, tts, _ = make_output()
    await engine.start_game(
        ["Alice", "Bob", "Carol", "Dave"],
        ["seer", "villager", "villager", "werewolf"],
    )

    async def drive():
        await asyncio.sleep(0)
        await engine.submit_night_action("seer", {"target": "p3"})
        await asyncio.sleep(0)
        await engine.submit_pending_action("seer", {})
        await asyncio.sleep(0)
        await engine.submit_night_action("werewolf", {"target": "p0"})

    asyncio.get_event_loop().create_task(drive())
    await engine.begin_night()

    prompts = [t for t in tts.spoken if t == "night.seer.prompt"]
    assert prompts == ["night.seer.prompt"]  # once, not twice


async def test_village_vote_death_announced_once_and_before_game_over():
    """Voting out the wolf announces vote.result (not a live elimination) before game_over."""
    engine, tts, _ = make_output()
    await engine.start_game(["Alice", "Bob", "Carol"], ["villager", "villager", "werewolf"])

    await engine.begin_vote()
    await engine.resolve_vote({"p0": "p2", "p1": "p2"})

    assert tts.spoken.count("phase.vote.result") == 1
    assert "elimination.village_vote" not in tts.spoken
    assert tts.spoken.index("phase.vote.result") < tts.spoken.index("phase.game_over.village_win")