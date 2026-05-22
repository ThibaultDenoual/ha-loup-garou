"""Custom WebSocket handler for Loup Garou game connections."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from aiohttp import WSMsgType, web
from homeassistant.components.http import HomeAssistantView

from .handlers import HANDLERS

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

DEBUG_LOG = []


def get_debug_log():
    return list(DEBUG_LOG)


def add_debug_log(message: str, level: str = "info"):
    timestamp = time.strftime("%H:%M:%S")
    DEBUG_LOG.append({"timestamp": timestamp, "message": message, "level": level})
    _LOGGER.debug(f"[DEBUG] {message}")


class LoupGarouWebSocketView(HomeAssistantView):
    """Handle WebSocket connections for Loup Garou."""

    url = "/loup_garou/ws"
    name = "loup_garou:ws"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.connections: set[web.WebSocketResponse] = set()

    async def get(self, request: web.Request) -> web.StreamResponse:
        """Handle WebSocket connection."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        self.connections.add(ws)
        add_debug_log(f"WS connected — total: {len(self.connections)}", "info")
        _LOGGER.debug("WebSocket connected, total: %d", len(self.connections))

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        msg_data = msg.json()
                        add_debug_log(f"WS received: {msg_data.get('type', 'unknown')}", "info")
                        await self._handle_message(ws, msg_data)
                    except Exception as err:
                        add_debug_log(f"WS parse error: {err}", "error")
                        _LOGGER.warning("Failed to parse WebSocket message: %s", err)
                elif msg.type == WSMsgType.ERROR:
                    add_debug_log(f"WS error: {ws.exception()}", "error")
                    _LOGGER.error("WebSocket error: %s", ws.exception())

        finally:
            self.connections.discard(ws)
            add_debug_log(f"WS disconnected — remaining: {len(self.connections)}", "info")
            _LOGGER.debug("WebSocket disconnected, total: %d", len(self.connections))

        return ws

    async def _handle_message(self, ws: web.WebSocketResponse, data: dict) -> None:
        msg_type = data.get("type") or ""
        add_debug_log(f"Handling message type: {msg_type}", "info")

        if msg_type.startswith("loup_garou/"):
            msg_type = msg_type[len("loup_garou/"):]

        domain_data = self.hass.data.get("loup_garou", {})
        engine = domain_data.get("engine")
        phase_manager = domain_data.get("phase_manager")

        if not engine:
            add_debug_log("Game engine not ready!", "error")
            await ws.send_json({"type": "error", "message": "Game engine not ready"})
            return

        handler = HANDLERS.get(msg_type)
        if handler:
            add_debug_log(f"Calling handler for: {msg_type}", "info")
            await handler(ws, data, engine, phase_manager)
            add_debug_log(f"Handler completed: {msg_type}", "info")
        else:
            add_debug_log(f"Unknown message type: {msg_type}", "error")
            _LOGGER.warning("Unknown message type: %s", msg_type)

    async def broadcast(self, message: dict) -> None:
        """Broadcast message to all connected clients."""
        add_debug_log(f"Broadcasting: {message.get('type', 'unknown')}", "info")

        if not self.connections:
            add_debug_log("No clients to broadcast to", "warn")
            return

        tasks = []
        for ws in list(self.connections):
            if not ws.closed:
                tasks.append(self._safe_send(ws, message))

        if tasks:
            await asyncio.gather(*tasks)
            add_debug_log(f"Broadcast sent to {len(tasks)} clients", "info")

    async def _safe_send(self, ws: web.WebSocketResponse, message: dict) -> None:
        """Safely send a message, ignoring closed connections."""
        try:
            if not ws.closed:
                await ws.send_json(message)
        except Exception:
            pass


async def handle_get_debug_log(
    ws: web.WebSocketResponse,
    data: dict,
    engine,
    phase_manager,
) -> None:
    """Handler to get debug logs."""
    from .websocket import get_debug_log
    add_debug_log("handle_get_debug_log called", "info")
    await ws.send_json({
        "type": "debug_log",
        "data": get_debug_log(),
    })