"""The WebSocket auth handshake — required inside HA, a no-op on the dev server."""
from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import patch

import aiohttp
from aiohttp import WSMsgType
from aiohttp.test_utils import TestServer

from tests.e2e.conftest import make_app, make_server

VALID_TOKEN = "good-token"


@asynccontextmanager
async def connected(require_auth: bool):
    engine, srv = make_server()
    if require_auth:
        srv.set_auth_callback(lambda token: token == VALID_TOKEN)
    async with TestServer(make_app(srv)) as ts:
        async with aiohttp.ClientSession() as sess:
            async with sess.ws_connect(ts.make_url("/ws")) as ws:
                yield ws, srv


async def test_without_auth_callback_commands_work_immediately():
    async with connected(require_auth=False) as (ws, srv):
        await ws.send_json({"cmd": "get_state"})
        msg = await ws.receive_json(timeout=2)
    assert msg["type"] == "state"


async def test_without_auth_callback_an_auth_message_is_acknowledged():
    async with connected(require_auth=False) as (ws, srv):
        await ws.send_json({"type": "auth", "access_token": "anything"})
        msg = await ws.receive_json(timeout=2)
    assert msg["type"] == "auth_ok"


async def test_valid_token_is_accepted_and_joins_broadcasts():
    async with connected(require_auth=True) as (ws, srv):
        await ws.send_json({"type": "auth", "access_token": VALID_TOKEN})
        assert (await ws.receive_json(timeout=2))["type"] == "auth_ok"

        await srv.broadcast({"type": "ping"})
        assert (await ws.receive_json(timeout=2))["type"] == "ping"


async def test_invalid_token_is_rejected_and_closed():
    async with connected(require_auth=True) as (ws, srv):
        await ws.send_json({"type": "auth", "access_token": "stolen"})
        assert (await ws.receive_json(timeout=2))["type"] == "auth_invalid"
        msg = await ws.receive(timeout=2)
        assert msg.type is WSMsgType.CLOSE
        assert not srv._clients


async def test_command_before_auth_is_rejected():
    async with connected(require_auth=True) as (ws, srv):
        await ws.send_json({"cmd": "get_state"})
        assert (await ws.receive_json(timeout=2))["type"] == "auth_invalid"


async def test_silent_client_is_dropped_after_the_timeout():
    with patch("loup_garou.game_server.AUTH_TIMEOUT", 0.1):
        async with connected(require_auth=True) as (ws, srv):
            assert (await ws.receive_json(timeout=2))["type"] == "auth_invalid"
            msg = await ws.receive(timeout=2)
    assert msg.type is WSMsgType.CLOSE


async def test_shutdown_disconnects_clients():
    async with connected(require_auth=False) as (ws, srv):
        await ws.send_json({"cmd": "get_state"})
        await ws.receive_json(timeout=2)

        await srv.async_shutdown()

        msg = await ws.receive(timeout=2)
    assert msg.type is WSMsgType.CLOSE
