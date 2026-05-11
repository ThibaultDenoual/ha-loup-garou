"""Custom WebSocket handler for Loup Garou game connections."""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from aiohttp import WSMsgType, web
from homeassistant.components.http import HomeAssistantView

from .handlers import HANDLERS

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


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
        _LOGGER.debug("WebSocket connected, total: %d", len(self.connections))

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        await self._handle_message(ws, msg.json())
                    except Exception as err:
                        _LOGGER.warning("Failed to parse WebSocket message: %s", err)
                elif msg.type == WSMsgType.ERROR:
                    _LOGGER.error("WebSocket error: %s", ws.exception())

        finally:
            self.connections.discard(ws)
            _LOGGER.debug("WebSocket disconnected, total: %d", len(self.connections))

        return ws

    async def _handle_message(self, ws: web.WebSocketResponse, data: dict) -> None:
        msg_type = data.get("type") or ""
        if msg_type.startswith("loup_garou/"):
            msg_type = msg_type[len("loup_garou/"):]

        domain_data = self.hass.data.get("loup_garou", {})
        engine = domain_data.get("engine")
        phase_manager = domain_data.get("phase_manager")

        if not engine:
            await ws.send_json({"type": "error", "message": "Game engine not ready"})
            return

        handler = HANDLERS.get(msg_type)
        if handler:
            await handler(ws, data, engine, phase_manager)
        else:
            _LOGGER.warning("Unknown message type: %s", msg_type)

    async def broadcast(self, message: dict) -> None:
        """Broadcast message to all connected clients."""
        if not self.connections:
            return

        tasks = []
        for ws in list(self.connections):
            if not ws.closed:
                tasks.append(self._safe_send(ws, message))

        if tasks:
            await asyncio.gather(*tasks)

    async def _safe_send(self, ws: web.WebSocketResponse, message: dict) -> None:
        """Safely send a message, ignoring closed connections."""
        try:
            if not ws.closed:
                await ws.send_json(message)
        except Exception:
            pass