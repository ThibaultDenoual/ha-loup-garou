"""WebSocket API — registers HA WebSocket commands for the game interface."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import (
    DOMAIN,
    WS_START_GAME,
    WS_CONFIRM_ROLE_SEEN,
    WS_NIGHT_ACTION,
    WS_SUBMIT_VOTE,
    WS_NEXT_PHASE,
    WS_GET_STATE,
    WS_SUBSCRIBE,
    EVENT_PHASE_CHANGED,
    EVENT_PLAYER_ELIMINATED,
    EVENT_GAME_OVER,
    EVENT_STATE_UPDATED,
    PHASE_DAY,
    PHASE_VOTE,
    PHASE_GAME_OVER,
    WIN_WOLVES,
    WIN_VILLAGERS,
)

_LOGGER = logging.getLogger(__name__)


def async_register_commands(hass: HomeAssistant) -> None:
    """Register all WebSocket commands. Called from __init__.py on setup."""
    websocket_api.async_register_command(hass, ws_start_game)
    websocket_api.async_register_command(hass, ws_confirm_role_seen)
    websocket_api.async_register_command(hass, ws_night_action)
    websocket_api.async_register_command(hass, ws_submit_vote)
    websocket_api.async_register_command(hass, ws_next_phase)
    websocket_api.async_register_command(hass, ws_get_state)
    websocket_api.async_register_command(hass, ws_get_role_reveal)
    websocket_api.async_register_command(hass, ws_get_seer_result)
    websocket_api.async_register_command(hass, ws_get_end_state)


def _get_engine(hass: HomeAssistant):
    """Retrieve the GameEngine from hass.data."""
    return hass.data[DOMAIN]["engine"]


def _get_phase_manager(hass: HomeAssistant):
    return hass.data[DOMAIN]["phase_manager"]


# ─── Command: start_game ──────────────────────────────────────────────────────

@websocket_api.websocket_command({
    vol.Required("type"): WS_START_GAME,
    vol.Required("players"): [str],
    vol.Required("role_config"): {str: int},
    vol.Optional("language", default="fr"): str,
})
@websocket_api.async_response
async def ws_start_game(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    engine = _get_engine(hass)
    phase_manager = _get_phase_manager(hass)

    try:
        state = await engine.async_start_game(
            player_names=msg["players"],
            role_config=msg["role_config"],
            language=msg.get("language", "fr"),
        )
        phase_manager.set_language(msg.get("language", "fr"))
        await phase_manager.on_roles_distributed()
        connection.send_result(msg["id"], state)
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_config", str(err))


# ─── Command: confirm_role_seen ───────────────────────────────────────────────

@websocket_api.websocket_command({
    vol.Required("type"): WS_CONFIRM_ROLE_SEEN,
    vol.Required("player_id"): str,
})
@websocket_api.async_response
async def ws_confirm_role_seen(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    engine = _get_engine(hass)
    phase_manager = _get_phase_manager(hass)

    try:
        state = await engine.async_confirm_role_seen(msg["player_id"])

        # If all roles seen, night has started — trigger TTS + lights
        if state["phase"] == "night" and state["reveal_index"] == state["reveal_total"]:
            await phase_manager.on_night_start()
            # Wake first role
            current_role = state.get("current_night_role")
            if current_role:
                await phase_manager.on_role_wake(current_role)

        connection.send_result(msg["id"], state)
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_action", str(err))


# ─── Command: night_action ────────────────────────────────────────────────────

@websocket_api.websocket_command({
    vol.Required("type"): WS_NIGHT_ACTION,
    vol.Required("role"): str,
    vol.Required("action_type"): str,
    vol.Required("target_id"): str,
})
@websocket_api.async_response
async def ws_night_action(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    engine = _get_engine(hass)
    phase_manager = _get_phase_manager(hass)

    try:
        state = await engine.async_submit_night_action(
            role=msg["role"],
            action_type=msg["action_type"],
            target_id=msg["target_id"],
        )
        # Sleep current role, check if more roles to wake
        role = msg["role"]
        await phase_manager.on_role_sleep(role)

        current_role = state.get("current_night_role")
        if current_role:
            await phase_manager.on_role_wake(current_role)

        connection.send_result(msg["id"], state)
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_action", str(err))


# ─── Command: submit_vote ─────────────────────────────────────────────────────

@websocket_api.websocket_command({
    vol.Required("type"): WS_SUBMIT_VOTE,
    vol.Required("voter_id"): str,
    vol.Required("target_id"): str,
})
@websocket_api.async_response
async def ws_submit_vote(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    engine = _get_engine(hass)

    try:
        state = await engine.async_submit_vote(
            voter_id=msg["voter_id"],
            target_id=msg["target_id"],
        )
        connection.send_result(msg["id"], state)
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_action", str(err))


# ─── Command: next_phase ──────────────────────────────────────────────────────

@websocket_api.websocket_command({
    vol.Required("type"): WS_NEXT_PHASE,
})
@websocket_api.async_response
async def ws_next_phase(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    engine = _get_engine(hass)
    phase_manager = _get_phase_manager(hass)

    prev_phase = engine._state.phase
    state = await engine.async_next_phase()
    new_phase = state["phase"]

    # Drive TTS + lights for the new phase
    if new_phase == PHASE_DAY and prev_phase == "night":
        eliminated = state.get("eliminated_this_round", [])
        eliminated_info = [
            (p["name"], _get_player_role(engine, p["id"]))
            for p in engine._state.players
            if p.id in eliminated
        ]
        await phase_manager.on_day_start(eliminated_info)

    elif new_phase == PHASE_VOTE:
        await phase_manager.on_vote_start()

    elif new_phase == PHASE_GAME_OVER:
        winner = state.get("winner")
        await phase_manager.on_game_over(winner)

    connection.send_result(msg["id"], state)


# ─── Command: get_state ───────────────────────────────────────────────────────

@websocket_api.websocket_command({
    vol.Required("type"): WS_GET_STATE,
})
@websocket_api.async_response
async def ws_get_state(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    engine = _get_engine(hass)
    connection.send_result(msg["id"], engine.get_public_state())


# ─── Command: get_role_reveal ─────────────────────────────────────────────────

@websocket_api.websocket_command({
    vol.Required("type"): f"{DOMAIN}/get_role_reveal",
    vol.Required("player_id"): str,
})
@websocket_api.async_response
async def ws_get_role_reveal(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    engine = _get_engine(hass)
    try:
        data = engine.get_role_reveal_data(msg["player_id"])
        connection.send_result(msg["id"], data)
    except ValueError as err:
        connection.send_error(msg["id"], "not_allowed", str(err))


# ─── Command: get_seer_result ─────────────────────────────────────────────────

@websocket_api.websocket_command({
    vol.Required("type"): f"{DOMAIN}/get_seer_result",
    vol.Required("seer_player_id"): str,
})
@websocket_api.async_response
async def ws_get_seer_result(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    engine = _get_engine(hass)
    try:
        data = engine.get_seer_result(msg["seer_player_id"])
        connection.send_result(msg["id"], data)
    except ValueError as err:
        connection.send_error(msg["id"], "not_allowed", str(err))


# ─── Command: get_end_state ───────────────────────────────────────────────────

@websocket_api.websocket_command({
    vol.Required("type"): f"{DOMAIN}/get_end_state",
})
@websocket_api.async_response
async def ws_get_end_state(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    engine = _get_engine(hass)
    try:
        data = engine.get_full_state_for_end()
        connection.send_result(msg["id"], data)
    except ValueError as err:
        connection.send_error(msg["id"], "game_not_over", str(err))


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_player_role(engine, player_id: str) -> str:
    p = engine._get_player(player_id)
    return p.role if p else "?"