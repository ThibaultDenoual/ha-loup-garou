"""WebSocket message handlers for Loup Garou."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..const import NightActionType, EliminationCause

if TYPE_CHECKING:
    from aiohttp import web
    from ..core.engine import GameEngine
    from ..services.phase_manager import PhaseManager

_LOGGER = logging.getLogger(__name__)


async def handle_get_state(
    ws: web.WebSocketResponse,
    data: dict,
    engine: GameEngine,
    phase_manager: PhaseManager | None,
) -> None:
    await ws.send_json({
        "type": "state",
        "data": engine.get_public_state(),
        "callback_id": data.get("callback_id"),
    })


async def handle_start_game(
    ws: web.WebSocketResponse,
    data: dict,
    engine: GameEngine,
    phase_manager: PhaseManager | None,
) -> None:
    try:
        await engine.async_start_game(
            data.get("player_names", []),
            data.get("role_config", {}),
        )
        if phase_manager:
            await phase_manager.on_game_started()
        await ws.send_json({
            "type": "state",
            "data": engine.get_public_state(),
            "callback_id": data.get("callback_id"),
        })
    except Exception as exc:
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
        if not player_id:
            next_id = engine.state.reveal_order[engine.state.reveal_index] if engine.state.reveal_index < len(engine.state.reveal_order) else None
            if not next_id:
                raise ValueError("No player to confirm")
            player_id = next_id
        await engine.async_confirm_role_seen(player_id)
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


async def handle_select_target(
    ws: web.WebSocketResponse,
    data: dict,
    engine: GameEngine,
    phase_manager: PhaseManager | None,
) -> None:
    try:
        await engine.async_select_target(data.get("target_id", ""))
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


async def handle_skip_action(
    ws: web.WebSocketResponse,
    data: dict,
    engine: GameEngine,
    phase_manager: PhaseManager | None,
) -> None:
    try:
        await engine.async_skip_night_action()
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


async def handle_night_action(
    ws: web.WebSocketResponse,
    data: dict,
    engine: GameEngine,
    phase_manager: PhaseManager | None,
) -> None:
    try:
        action_type = NightActionType(data.get("action_type", ""))
        acting_role = engine.current_night_role
        await engine.async_submit_night_action(action_type, data.get("target_id"))
        if phase_manager and acting_role:
            await phase_manager.on_night_action_submitted(acting_role)
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


async def handle_submit_vote(
    ws: web.WebSocketResponse,
    data: dict,
    engine: GameEngine,
    phase_manager: PhaseManager | None,
) -> None:
    try:
        await engine.async_submit_vote(data.get("voter_id", ""), data.get("target_id", ""))
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


async def handle_resolve_votes(
    ws: web.WebSocketResponse,
    data: dict,
    engine: GameEngine,
    phase_manager: PhaseManager | None,
) -> None:
    try:
        result = await engine.async_resolve_vote()
        await ws.send_json({
            "type": "state",
            "data": result,
            "callback_id": data.get("callback_id"),
        })
    except Exception as exc:
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
        cause = EliminationCause(data.get("cause", ""))
        winner = await engine.async_eliminate_player(data.get("player_id", ""), cause)
        if winner is None and phase_manager:
            await phase_manager.on_player_eliminated(data.get("player_id", ""), cause)
        await ws.send_json({
            "type": "state",
            "data": {"winner": winner, **engine.get_public_state()},
            "callback_id": data.get("callback_id"),
        })
    except Exception as exc:
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
        await engine.async_reset()
        await ws.send_json({
            "type": "state",
            "data": {"status": "reset"},
            "callback_id": data.get("callback_id"),
        })
    except Exception as exc:
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
        await engine.async_next_phase()
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
}