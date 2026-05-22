"""Console runner — plays a full game from stdin/stdout, zero HA imports."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from ..game_engine import GameEngine

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
        self._pending_hunter_shot: asyncio.Future | None = None

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

    async def _run_night(self) -> None:
        night_roles = self._engine._night_roles()
        for role in night_roles:
            ctx = self._engine._make_ctx()
            if not ctx.alive_players_by_role(role.id):
                continue

            print(f"\n  [{role.id.upper()}] action:")
            action = await asyncio.get_event_loop().run_in_executor(
                None, self._get_action_for_role, role.id, ctx
            )
            await self._engine.submit_night_action(role.id, action)

    def _get_action_for_role(self, role_id: str, ctx) -> dict:
        alive = ctx.alive_players
        if role_id in ("werewolf", "alpha_wolf", "seer"):
            print("  Joueurs en vie :", ", ".join(f"{p['id']}={p['name']}" for p in alive))
            target = input("  Cible (id) : ").strip()
            return {"target": target}
        if role_id == "witch":
            kills = ctx.pending_kills
            print(f"  Morts cette nuit : {kills}")
            save = input("  Sauver (id ou vide) : ").strip()
            poison = input("  Empoisonner (id ou vide) : ").strip()
            return {"save_target": save or None, "poison_target": poison or None}
        if role_id == "cupid":
            print("  Joueurs :", ", ".join(f"{p['id']}={p['name']}" for p in alive))
            a = input("  Amoureux 1 (id) : ").strip()
            b = input("  Amoureux 2 (id) : ").strip()
            return {"lovers": [a, b]}
        return {}

    async def _run_vote(self) -> None:
        await self._engine.begin_vote()
        state = self._engine.get_public_state()
        alive = [p for p in state["players"] if p["alive"]]
        print("\n  Joueurs en vie :", ", ".join(f"{p['id']}={p['name']}" for p in alive))

        votes: dict[str, str] = {}
        for voter in alive:
            target = input(f"  {voter['name']} vote contre (id) : ").strip()
            if target:
                votes[voter["id"]] = target

        eliminated = await self._engine.resolve_vote(votes)
        if eliminated is None:
            print(f"\n  {self.t('phase.vote.tie')}")
        else:
            p = next((pl for pl in state["players"] if pl["id"] == eliminated), None)
            if p:
                print(f"\n  {self.t('phase.vote.result', name=p['name'], article='un', role=p['role_id'])}")

    async def run(self) -> None:
        self._wire_events()
        await self._setup_game()

        while self._engine._state.phase not in (Phase.GAME_OVER,):
            phase = self._engine._state.phase
            if phase == Phase.ROLE_REVEAL:
                input("\n[ENTRÉE pour commencer la première nuit]")
                await self._engine.begin_night()
            elif phase == Phase.DAY:
                action = input("\n[V]oter ou [N]uit ? ").strip().lower()
                if action.startswith("v"):
                    await self._run_vote()
                elif action.startswith("n"):
                    await self._engine.begin_night()
            elif phase == Phase.VOTE:
                pass  # resolve_vote transitions to DAY
            else:
                await asyncio.sleep(0.1)


def main() -> None:
    import sys
    lang = sys.argv[1] if len(sys.argv) > 1 else "fr"
    runner = ConsoleRunner(language=lang)
    asyncio.run(runner.run())


if __name__ == "__main__":
    main()
