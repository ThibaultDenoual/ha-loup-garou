"""Tests for server/websocket.py"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from custom_components.loup_garou.server.websocket import LoupGarouWebSocketView


@pytest.fixture
def mock_hass():
    hass = MagicMock()
    hass.data = {"loup_garou": {}}
    return hass


@pytest.fixture
def ws_view(mock_hass):
    return LoupGarouWebSocketView(mock_hass)


@pytest.fixture
def mock_ws():
    ws = MagicMock()
    ws.send_json = AsyncMock()
    ws.closed = False
    return ws


class TestLoupGarouWebSocketView:
    def test_init(self, ws_view, mock_hass):
        assert ws_view.hass is mock_hass
        assert isinstance(ws_view.connections, set)
        assert ws_view.url == "/loup_garou/ws"
        assert ws_view.name == "loup_garou:ws"
        assert ws_view.requires_auth is False

    def test_init_connections_empty(self, ws_view):
        assert len(ws_view.connections) == 0


class TestHandleMessage:
    @pytest.mark.asyncio
    async def test_unknown_message_type_only_logs(self, ws_view, mock_ws):
        ws_view.hass.data["loup_garou"]["engine"] = MagicMock()
        await ws_view._handle_message(mock_ws, {"type": "unknown_cmd"})
        mock_ws.send_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_engine_returns_error(self, ws_view, mock_ws):
        ws_view.hass.data["loup_garou"]["engine"] = None
        await ws_view._handle_message(mock_ws, {"type": "get_state"})
        mock_ws.send_json.assert_called_once()
        call_args = mock_ws.send_json.call_args[0][0]
        assert call_args["type"] == "error"
        assert "not ready" in call_args["message"]

    @pytest.mark.asyncio
    async def test_handler_called(self, ws_view, mock_ws):
        engine = MagicMock()
        engine.get_public_state.return_value = {"phase": "setup"}
        ws_view.hass.data["loup_garou"]["engine"] = engine
        handler = AsyncMock()
        with patch.dict("custom_components.loup_garou.server.handlers.HANDLERS", {"test_cmd": handler}, clear=False):
            await ws_view._handle_message(mock_ws, {"type": "test_cmd"})
        handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_loup_garou_prefix_stripped(self, ws_view, mock_ws):
        engine = MagicMock()
        engine.get_public_state.return_value = {"phase": "setup"}
        ws_view.hass.data["loup_garou"]["engine"] = engine
        handler = AsyncMock()
        with patch.dict("custom_components.loup_garou.server.handlers.HANDLERS", {"get_state": handler}, clear=False):
            await ws_view._handle_message(mock_ws, {"type": "loup_garou/get_state"})

    @pytest.mark.asyncio
    async def test_handler_includes_phase_manager(self, ws_view, mock_ws):
        engine = MagicMock()
        engine.get_public_state.return_value = {"phase": "setup"}
        pm = MagicMock()
        ws_view.hass.data["loup_garou"]["engine"] = engine
        ws_view.hass.data["loup_garou"]["phase_manager"] = pm
        handler = AsyncMock()
        with patch.dict("custom_components.loup_garou.server.handlers.HANDLERS", {"get_state": handler}, clear=False):
            await ws_view._handle_message(mock_ws, {"type": "get_state"})


class TestBroadcast:
    @pytest.mark.asyncio
    async def test_broadcast_no_connections(self, ws_view):
        ws_view.connections = set()
        result = await ws_view.broadcast({"type": "test"})
        assert result is None

    @pytest.mark.asyncio
    async def test_broadcast_single_connection(self, ws_view, mock_ws):
        ws_view.connections.add(mock_ws)
        mock_ws.send_json = AsyncMock()
        await ws_view.broadcast({"type": "test"})
        mock_ws.send_json.assert_called_once_with({"type": "test"})

    @pytest.mark.asyncio
    async def test_broadcast_multiple_connections(self, ws_view):
        ws1 = MagicMock()
        ws1.send_json = AsyncMock()
        ws1.closed = False
        ws2 = MagicMock()
        ws2.send_json = AsyncMock()
        ws2.closed = False
        ws_view.connections.add(ws1)
        ws_view.connections.add(ws2)
        await ws_view.broadcast({"type": "test"})
        ws1.send_json.assert_called_once()
        ws2.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_skips_closed(self, ws_view):
        ws1 = MagicMock()
        ws1.send_json = AsyncMock()
        ws1.closed = False
        ws2 = MagicMock()
        ws2.send_json = AsyncMock()
        ws2.closed = True
        ws_view.connections.add(ws1)
        ws_view.connections.add(ws2)
        await ws_view.broadcast({"type": "test"})
        ws1.send_json.assert_called_once()
        ws2.send_json.assert_not_called()


class TestSafeSend:
    @pytest.mark.asyncio
    async def test_safe_send_closed_ws(self, ws_view, mock_ws):
        mock_ws.closed = True
        await ws_view._safe_send(mock_ws, {"type": "test"})
        mock_ws.send_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_safe_send_error(self, ws_view, mock_ws):
        mock_ws.closed = False
        mock_ws.send_json = AsyncMock(side_effect=Exception("send error"))
        await ws_view._safe_send(mock_ws, {"type": "test"})
        mock_ws.send_json.assert_called_once()


class TestWebSocketGet:
    pass


class TestWSMessageTypes:
    pass