"""WebSocket message handlers for Loup Garou."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..const import NightActionType, EliminationCause

if TYPE_CHECKING:
    from aiohttp import web
    from ..core_game.io_adapters.ha_adapter import AsyncGameAdapter as GameEngine
    from ..services.phase_manager import PhaseManager

_LOGGER = logging.getLogger(__name__)

try:
    from .websocket import add_debug_log
except ImportError:
    def add_debug_log(msg, level="info"):
        pass


async def handle_get_state(
    ws: web.WebSocketResponse,
    data: dict,
    engine: GameEngine,
    phase_manager: PhaseManager | None,
) -> None:
    add_debug_log("handle_get_state called", "info")
    state = engine.get_public_state()
    add_debug_log(f"Returning state: phase={state.get('phase')}, round={state.get('round')}", "info")
    await ws.send_json({
        "type": "state",
        "data": state,
        "callback_id": data.get("callback_id"),
    })


async def handle_start_game(
    ws: web.WebSocketResponse,
    data: dict,
    engine: GameEngine,
    phase_manager: PhaseManager | None,
) -> None:
    try:
        player_names = data.get("player_names", [])
        role_config = data.get("role_config", {})
        add_debug_log(f"handle_start_game: players={player_names}, config={role_config}", "info")

        await engine.async_start_game(player_names, role_config)

        if phase_manager:
            await phase_manager.on_game_started()

        add_debug_log(f"Game started with {len(player_names)} players", "info")
        await ws.send_json({
            "type": "state",
            "data": engine.get_public_state(),
            "callback_id": data.get("callback_id"),
        })
    except Exception as exc:
        add_debug_log(f"handle_start_game error: {exc}", "error")
        _LOGGER.exception("start_game failed")
        await ws.send_json({
            "type": "error",
            "message": str(exc),
            "callback_id": data.get("callback_id"),
        })


async def handle_confirm_role_seen(
    ws: web.WebSocketResponse,
    data: dict,
    engine: GameEngine,
    phase_manager: PhaseManager | None,
) -> None:
    try:
        player_id = data.get("player_id")
        add_debug_log(f"handle_confirm_role_seen: player_id={player_id}", "info")

        if not player_id:
            next_id = engine.state.reveal_order[engine.state.reveal_index] if engine.state.reveal_index < len(engine.state.reveal_order) else None
            if not next_id:
                raise ValueError("No player to confirm")
            player_id = next_id
            add_debug_log(f"Auto-selected next player: {player_id}", "info")

        await engine.async_confirm_role_seen(player_id)
        add_debug_log(f"Role confirmed for: {player_id}", "info")

        await ws.send_json({
            "type": "state",
            "data": engine.get_public_state(),
            "callback_id": data.get("callback_id"),
        })
    except Exception as exc:
        add_debug_log(f"handle_confirm_role_seen error: {exc}", "error")
        await ws.send_json({
            "type": "error",
            "message": str(exc),
            "callback_id": data.get("callback_id"),
        })


async def handle_select_target(
    ws: web.WebSocketResponse,
    data: dict,
    engine: GameEngine,
    phase_manager: PhaseManager | None,
) -> None:
    try:
        target_id = data.get("target_id", "")
        add_debug_log(f"handle_select_target: target={target_id}", "info")

        await engine.async_select_target(target_id)
        add_debug_log(f"Target selected: {target_id}", "info")

        await ws.send_json({
            "type": "state",
            "data": engine.get_public_state(),
            "callback_id": data.get("callback_id"),
        })
    except Exception as exc:
        add_debug_log(f"handle_select_target error: {exc}", "error")
        await ws.send_json({
            "type": "error",
            "message": str(exc),
            "callback_id": data.get("callback_id"),
        })


async def handle_skip_action(
    ws: web.WebSocketResponse,
    data: dict,
    engine: GameEngine,
    phase_manager: PhaseManager | None,
    skip_delay: bool = False,
) -> None:
    try:
        add_debug_log("handle_skip_action called", "info")

        await engine.async_skip_night_action(skip_delay)
        add_debug_log("Night action skipped", "info")

        await ws.send_json({
            "type": "state",
            "data": engine.get_public_state(),
            "callback_id": data.get("callback_id"),
        })
    except Exception as exc:
        add_debug_log(f"handle_skip_action error: {exc}", "error")
        await ws.send_json({
            "type": "error",
            "message": str(exc),
            "callback_id": data.get("callback_id"),
        })


async def handle_night_action(
    ws: web.WebSocketResponse,
    data: dict,
    engine: GameEngine,
    phase_manager: PhaseManager | None,
    skip_delay: bool = False,
) -> None:
    try:
        action_type = data.get("action_type", "")
        target_id = data.get("target_id", "")
        add_debug_log(f"handle_night_action: type={action_type}, target={target_id}", "info")

        acting_role = engine.current_night_role
        await engine.async_submit_night_action(action_type, target_id, skip_delay)

        if phase_manager and acting_role:
            await phase_manager.on_night_action_submitted(acting_role)

        add_debug_log(f"Night action submitted: {action_type} -> {target_id}", "info")

        await ws.send_json({
            "type": "state",
            "data": engine.get_public_state(),
            "callback_id": data.get("callback_id"),
        })
    except Exception as exc:
        add_debug_log(f"handle_night_action error: {exc}", "error")
        await ws.send_json({
            "type": "error",
            "message": str(exc),
            "callback_id": data.get("callback_id"),
        })


async def handle_submit_vote(
    ws: web.WebSocketResponse,
    data: dict,
    engine: GameEngine,
    phase_manager: PhaseManager | None,
) -> None:
    try:
        voter_id = data.get("voter_id", "")
        target_id = data.get("target_id", "")
        add_debug_log(f"handle_submit_vote: voter={voter_id}, target={target_id}", "info")

        await engine.async_submit_vote(voter_id, target_id)
        add_debug_log(f"Vote submitted: {voter_id} -> {target_id}", "info")

        await ws.send_json({
            "type": "state",
            "data": engine.get_public_state(),
            "callback_id": data.get("callback_id"),
        })
    except Exception as exc:
        add_debug_log(f"handle_submit_vote error: {exc}", "error")
        await ws.send_json({
            "type": "error",
            "message": str(exc),
            "callback_id": data.get("callback_id"),
        })


async def handle_resolve_votes(
    ws: web.WebSocketResponse,
    data: dict,
    engine: GameEngine,
    phase_manager: PhaseManager | None,
) -> None:
    try:
        add_debug_log("handle_resolve_votes called", "info")

        result = await engine.async_resolve_vote()
        eliminated = result.get("eliminated_this_round", [])
        add_debug_log(f"Votes resolved: eliminated={eliminated}", "info")

        await ws.send_json({
            "type": "state",
            "data": result,
            "callback_id": data.get("callback_id"),
        })
    except Exception as exc:
        add_debug_log(f"handle_resolve_votes error: {exc}", "error")
        await ws.send_json({
            "type": "error",
            "message": str(exc),
            "callback_id": data.get("callback_id"),
        })


async def handle_eliminate_player(
    ws: web.WebSocketResponse,
    data: dict,
    engine: GameEngine,
    phase_manager: PhaseManager | None,
) -> None:
    try:
        player_id = data.get("player_id", "")
        cause = data.get("cause", "")
        add_debug_log(f"handle_eliminate_player: player={player_id}, cause={cause}", "info")

        cause_enum = EliminationCause(cause)
        winner = await engine.async_eliminate_player(player_id, cause_enum)

        if winner is None and phase_manager:
            await phase_manager.on_player_eliminated(player_id, cause)

        add_debug_log(f"Player eliminated: {player_id}, winner={winner}", "info")

        await ws.send_json({
            "type": "state",
            "data": {"winner": winner, **engine.get_public_state()},
            "callback_id": data.get("callback_id"),
        })
    except Exception as exc:
        add_debug_log(f"handle_eliminate_player error: {exc}", "error")
        await ws.send_json({
            "type": "error",
            "message": str(exc),
            "callback_id": data.get("callback_id"),
        })


async def handle_begin_vote(
    ws: web.WebSocketResponse,
    data: dict,
    engine: GameEngine,
    phase_manager: PhaseManager | None,
) -> None:
    try:
        await engine.async_begin_vote()
        if phase_manager:
            await phase_manager.on_vote_started()
        await ws.send_json({
            "type": "state",
            "data": engine.get_public_state(),
            "callback_id": data.get("callback_id"),
        })
    except Exception as exc:
        await ws.send_json({
            "type": "error",
            "message": str(exc),
            "callback_id": data.get("callback_id"),
        })


async def handle_reset(
    ws: web.WebSocketResponse,
    data: dict,
    engine: GameEngine,
    phase_manager: PhaseManager | None,
) -> None:
    try:
        add_debug_log("handle_reset called", "info")

        await engine.async_reset()
        add_debug_log("Game reset complete", "info")

        await ws.send_json({
            "type": "state",
            "data": {"status": "reset"},
            "callback_id": data.get("callback_id"),
        })
    except Exception as exc:
        add_debug_log(f"handle_reset error: {exc}", "error")
        await ws.send_json({
            "type": "error",
            "message": str(exc),
            "callback_id": data.get("callback_id"),
        })


async def handle_next_phase(
    ws: web.WebSocketResponse,
    data: dict,
    engine: GameEngine,
    phase_manager: PhaseManager | None,
) -> None:
    try:
        current_phase = engine.state.phase
        add_debug_log(f"handle_next_phase: current={current_phase}", "info")

        await engine.async_next_phase()
        new_state = engine.get_public_state()
        add_debug_log(f"Next phase: {current_phase} -> {new_state.get('phase')}", "info")

        await ws.send_json({
            "type": "state",
            "data": new_state,
            "callback_id": data.get("callback_id"),
        })
    except Exception as exc:
        add_debug_log(f"handle_next_phase error: {exc}", "error")
        await ws.send_json({
            "type": "error",
            "message": str(exc),
            "callback_id": data.get("callback_id"),
        })


async def handle_get_debug_log(
    ws: web.WebSocketResponse,
    data: dict,
    engine: GameEngine,
    phase_manager: PhaseManager | None,
) -> None:
    try:
        from .websocket import get_debug_log
        add_debug_log("handle_get_debug_log called", "info")
        await ws.send_json({
            "type": "debug_log",
            "data": get_debug_log(),
            "callback_id": data.get("callback_id"),
        })
    except Exception as exc:
        add_debug_log(f"handle_get_debug_log error: {exc}", "error")
        await ws.send_json({
            "type": "error",
            "message": str(exc),
            "callback_id": data.get("callback_id"),
        })


HANDLERS = {
    "get_state": handle_get_state,
    "start_game": handle_start_game,
    "confirm_role_seen": handle_confirm_role_seen,
    "select_target": handle_select_target,
    "skip_action": handle_skip_action,
    "night_action": handle_night_action,
    "submit_vote": handle_submit_vote,
    "resolve_votes": handle_resolve_votes,
    "eliminate_player": handle_eliminate_player,
    "begin_vote": handle_begin_vote,
    "reset": handle_reset,
    "next_phase": handle_next_phase,
    "get_debug_log": handle_get_debug_log,
}