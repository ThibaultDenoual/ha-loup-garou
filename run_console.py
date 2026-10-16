#!/usr/bin/env python3
"""
Console runner for Loup Garou (Werewolf) game.
Run with: python run_console.py [--config dev.yaml] [--non-interactive --players "A,B" --roles "werewolf,seer"]

Dev features:
- TTS simulation (mock: logs [TTS] to console)
- Light simulation (logs [LIGHT] scene changes)
- Full event wiring matching HA integration
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "custom_components"))

from custom_components.loup_garou.console.console_runner import ConsoleRunner
from custom_components.loup_garou.const import (
    Phase,
)
from custom_components.loup_garou.game_engine import GameEngine
from custom_components.loup_garou.roles.loader import load_roles
from dev_config import DevConfig, add_common_args, load_config
from dev_lights import DevLights
from dev_output import DevOutputHandler
from dev_tts import create_tts

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
_LOGGER = logging.getLogger("console")


async def run_interactive(config: DevConfig) -> None:
    """Interactive mode — prompts for players and roles."""
    runner = ConsoleRunner(language=config.language)
    await runner.run()


async def run_non_interactive(config: DevConfig) -> None:
    """Non-interactive mode — uses config.players and config.roles."""
    if not config.players:
        print("Error: --players required in non-interactive mode")
        sys.exit(1)
    if not config.roles:
        print("Error: --roles required in non-interactive mode")
        sys.exit(1)
    if len(config.players) != len(config.roles):
        print(f"Error: player count ({len(config.players)}) != role count ({len(config.roles)})")
        sys.exit(1)

    # Load roles to validate
    load_roles()
    engine = GameEngine()

    # Setup TTS + lights + output handler
    tts = create_tts(config.tts_mode, delays=config.tts_delays)
    lights = DevLights(config.lights)
    DevOutputHandler(engine, tts, lights, config.language).wire_events()

    print("\n=== Loup Garou Console (non-interactive) ===")
    print(f"Players: {config.players}")
    print(f"Roles:   {config.roles}")
    print(f"Language: {config.language}")
    print(f"TTS mode: {config.tts_mode}")

    await engine.start_game(config.players, config.roles)

    # Game loop — drive phases automatically
    while engine._state.phase not in (Phase.GAME_OVER,):
        phase = engine._state.phase
        if phase == Phase.ROLE_REVEAL:
            # Start night and let it begin (reach first await for night action)
            night_task = asyncio.create_task(engine.begin_night())
            await asyncio.sleep(0.01)  # Let begin_night start and wait for first action
            await _auto_night_actions(engine)
            # Wait for night to fully resolve
            await night_task
        elif phase == Phase.DAY:
            await _auto_vote(engine)
        elif phase == Phase.NIGHT:
            # Should not reach here if we handle it in ROLE_REVEAL
            night_task = asyncio.create_task(engine.begin_night())
            await asyncio.sleep(0.01)
            await _auto_night_actions(engine)
            await night_task
        else:
            await asyncio.sleep(0.1)

    print("\n=== Game Over ===")


async def _auto_night_actions(engine: GameEngine) -> None:
    """Automatically submit night actions for all roles that wake up."""
    state = engine.get_public_state()
    alive_players = {p["id"]: p for p in state["players"] if p["alive"]}

    while engine._state.phase == Phase.NIGHT:
        # Handle regular night actions
        pending_role = getattr(engine, "_pending_action_role", None)
        pending_fut = getattr(engine, "_pending_action", None)
        if pending_role and pending_fut and not pending_fut.done():
            action = _choose_action_for_role(engine, pending_role, alive_players)
            await engine.submit_night_action(pending_role, action)
        # Handle interrupt actions (e.g., Seer result acknowledgment)
        interrupt_role = getattr(engine._state, "pending_interrupt_role", None)
        interrupt_fut = getattr(engine._state, "pending_interrupt", None)
        if interrupt_role and interrupt_fut and not interrupt_fut.done():
            await engine.submit_pending_action(interrupt_role, {})
        else:
            # Check if night is done (engine._resolve_night will transition to DAY)
            if engine._state.phase != Phase.NIGHT:
                break
            await asyncio.sleep(0.05)


def _choose_action_for_role(engine: GameEngine, role_id: str, alive_players: dict) -> dict:
    """Choose an automatic action for the given role."""
    alive_ids = list(alive_players.keys())
    other_ids = [pid for pid in alive_ids if alive_players[pid].get("role_id") != role_id]

    if not other_ids:
        return {}

    if role_id in ("werewolf", "alpha_wolf"):
        return {"target": other_ids[0]}
    if role_id == "seer":
        return {"target": other_ids[0]}
    if role_id == "cupid":
        if len(other_ids) >= 2:
            return {"lovers": [other_ids[0], other_ids[1]]}
        return {"lovers": [other_ids[0], other_ids[0]]}
    if role_id == "witch":
        pending = getattr(engine._state, "pending_kills", [])
        save_target = pending[0][0] if pending else None
        poison_target = next((cid for cid in other_ids if cid != save_target), None)
        return {"save_target": save_target, "poison_target": poison_target}
    return {}


async def _auto_vote(engine: GameEngine) -> None:
    """Automatically vote: each alive player votes for first other alive player."""
    await engine.begin_vote()
    state = engine.get_public_state()
    alive = [p for p in state["players"] if p["alive"]]
    if len(alive) >= 2:
        votes = {}
        for voter in alive:
            others = [p for p in alive if p["id"] != voter["id"]]
            if others:
                votes[voter["id"]] = others[0]["id"]
        await engine.resolve_vote(votes)
    else:
        await engine.resolve_vote({})


def add_console_args(parser: argparse.ArgumentParser) -> None:
    add_common_args(parser)
    parser.add_argument(
        "--non-interactive", action="store_true", help="Run without prompts (requires --players --roles)"
    )
    parser.add_argument(
        "--players", help="Comma-separated player names (non-interactive)"
    )
    parser.add_argument(
        "--roles", help="Comma-separated role IDs (non-interactive)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Loup Garou console runner")
    add_console_args(parser)
    args = parser.parse_args()

    config = load_config(parser, args)

    if args.non_interactive:
        asyncio.run(run_non_interactive(config))
    else:
        asyncio.run(run_interactive(config))


if __name__ == "__main__":
    main()