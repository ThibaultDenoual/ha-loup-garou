"""Console runner — plays a full game from stdin/stdout, zero HA imports."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from ..game_engine import PROMPT_NEW_GAME, AnswerResult, GameEngine

from ..const import GameEvent, Phase


def _load_locale(language: str) -> dict:
    path = Path(__file__).parent.parent / "locales" / f"{language}.json"
    with open(path) as f:
        return json.load(f)


def _t(locale: dict, key: str, **kwargs) -> str:
    text = locale.get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass
    return text


class ConsoleRunner:
    def __init__(self, language: str = "fr") -> None:
        self._engine = GameEngine()
        self._locale = _load_locale(language)
        self._prompts: asyncio.Queue[dict] = asyncio.Queue()

    def t(self, key: str, **kwargs) -> str:
        return _t(self._locale, key, **kwargs)

    def _wire_events(self) -> None:
        e = self._engine

        async def on_phase(data):
            phase = data.get("phase")
            if phase == Phase.NIGHT:
                print(f"\n🌙  {self.t('phase.night.start')}")
            elif phase == Phase.DAY:
                pass  # Day start narration comes from on_day_started

        async def on_day_started(data):
            elim = data.get("eliminated", [])
            if not elim:
                print(f"\n☀️  {self.t('phase.day.start_no_death')}")
            else:
                for pid in elim:
                    p = next(
                        (pl for pl in e.get_public_state()["players"] if pl["id"] == pid),
                        None,
                    )
                    if p:
                        print(f"\n☀️  {self.t('phase.day.start_with_death', name=p['name'], article='un', role=p['role_id'])}")

        async def on_eliminated(data):
            cause = data.get("cause", "")
            name = data.get("name", "?")
            role = data.get("role", "?")
            if cause == "hunter_shot":
                print(f"🔫  {self.t('elimination.hunter_shot', name=name, target=name)}")
            elif cause == "lover_grief":
                print(f"💔  {self.t('elimination.lover_grief', name=name)}")
            elif cause == "witch_poison":
                print(f"☠️  {self.t('elimination.witch_poison', name=name, article='un', role=role)}")
            elif cause == "village_vote":
                print(f"⚖️  {self.t('elimination.village_vote', name=name, article='un', role=role)}")

        async def on_role_wake(data):
            role = data.get("role")
            result = data.get("result")
            if result:
                # Seer investigation result
                pid = result["player_id"]
                rid = result["role_id"]
                print(f"🔮  Seer result: {rid}")

        async def on_game_over(data):
            winner = data.get("winner")
            if winner == "wolves":
                print(f"\n🐺  {self.t('phase.game_over.wolves_win')}")
            elif winner == "village":
                print(f"\n🏘️  {self.t('phase.game_over.village_win')}")
            elif winner == "lovers":
                print(f"\n❤️  {self.t('phase.game_over.lovers_win')}")

        e.on(GameEvent.PHASE_CHANGED, on_phase)
        e.on(GameEvent.DAY_STARTED, on_day_started)
        e.on(GameEvent.PLAYER_ELIMINATED, on_eliminated)
        e.on(GameEvent.NIGHT_ROLE_WAKE, on_role_wake)
        e.on(GameEvent.GAME_OVER, on_game_over)

    async def _setup_game(self) -> None:
        print("\n=== Loup Garou Console ===")
        print("Entrez les noms des joueurs (vide pour terminer) :")
        names: list[str] = []
        while True:
            name = input(f"  Joueur {len(names)+1}: ").strip()
            if not name:
                break
            names.append(name)

        print("\nRôles disponibles :", ", ".join(self._engine._roles.keys()))
        print(f"Attribuez {len(names)} rôles (un par ligne) :")
        roles: list[str] = []
        for name in names:
            while True:
                role = input(f"  Rôle de {name}: ").strip()
                if role in self._engine._roles:
                    roles.append(role)
                    break
                print(f"  Rôle inconnu: {role}")

        await self._engine.start_game(names, roles)

    def _read_answer(self, prompt: dict) -> dict:
        names = {p["id"]: p["name"] for p in self._engine.get_public_state()["players"]}
        print(f"\n  [{prompt['kind']}] {names.get(prompt['actor'], prompt['role'] or '')} {prompt['info']}")
        if not prompt["picks"]:
            input("  [ENTRÉE]")
        answer: dict = {}
        for name, spec in prompt["picks"].items():
            options = ", ".join(f"{o}={names.get(o, o)}" for o in spec["options"])
            print(f"  {name} ({spec['counts']}) : {options}")
            answer[name] = input("  Choix (séparés par des espaces) : ").split()
        return answer

    async def _answer_prompts(self) -> None:
        while True:
            prompt = await self._prompts.get()
            result = None
            while result not in (AnswerResult.ACCEPTED, AnswerResult.STALE):
                answer = await asyncio.get_running_loop().run_in_executor(
                    None, self._read_answer, prompt
                )
                result = await self._engine.answer(prompt["id"], answer)
                if result == AnswerResult.ILLEGAL:
                    print("  Choix invalide.")

    async def run(self) -> None:
        self._wire_events()
        await self._setup_game()

        async def on_prompt(prompt: dict) -> None:
            if prompt["kind"] != PROMPT_NEW_GAME:
                self._prompts.put_nowait(prompt)

        self._engine.on(GameEvent.PROMPT_OPENED, on_prompt)
        answering = asyncio.create_task(self._answer_prompts())
        game = asyncio.create_task(self._engine.run_game())

        async def on_game_over(_data: dict) -> None:
            game.cancel()

        self._engine.on(GameEvent.GAME_OVER, on_game_over)
        try:
            await game
        except asyncio.CancelledError:
            pass
        finally:
            answering.cancel()


def main() -> None:
    import sys
    lang = sys.argv[1] if len(sys.argv) > 1 else "fr"
    runner = ConsoleRunner(language=lang)
    asyncio.run(runner.run())


if __name__ == "__main__":
    main()
