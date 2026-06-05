"""Shared fixtures and helpers for e2e WebSocket tests."""
from __future__ import annotations

import asyncio
import threading
import time

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer


@pytest.fixture(autouse=True)
def _allow_sockets(socket_enabled):
    """Re-enable TCP sockets for all e2e tests (blocked by HA plugin by default)."""
    yield
    # aiohttp spawns a _run_safe_shutdown_loop daemon thread during ClientSession teardown.
    # Wait for it to finish before verify_cleanup (a plugin fixture) checks for stray threads.
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        if not any("_run_safe_shutdown_loop" in t.name for t in threading.enumerate()):
            break
        time.sleep(0.05)

from loup_garou.game_engine import GameEngine
from loup_garou.game_server import LoupGarouServer
from loup_garou.roles.impl.villager import Villager
from loup_garou.roles.impl.werewolf import Werewolf
from loup_garou.roles.impl.seer import Seer


def make_server(role_classes=None):
    """Build a GameEngine + LoupGarouServer with the given role classes."""
    classes = role_classes or (Villager, Werewolf, Seer)
    roles = {cls.id: cls() for cls in classes}
    engine = GameEngine(roles=roles)
    server = LoupGarouServer(engine)
    server.wire_events()
    return engine, server


def make_app(server: LoupGarouServer) -> web.Application:
    app = web.Application()
    app.router.add_get("/ws", server.handle_ws)
    return app


async def drain(
    ws: aiohttp.ClientWebSocketResponse,
    *,
    until_type: str,
    predicate=None,
    timeout: float = 2.0,
) -> list[dict]:
    """Collect JSON messages until a message of until_type arrives (and predicate passes).

    predicate, if given, is called with the candidate message dict; collection continues
    until both the type matches AND predicate returns truthy.
    """
    collected: list[dict] = []
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        remaining = deadline - loop.time()
        if remaining <= 0:
            raise AssertionError(
                f"Timed out waiting for type={until_type!r} (predicate={predicate}); got: {collected}"
            )
        try:
            msg = await asyncio.wait_for(ws.receive_json(), timeout=remaining)
        except asyncio.TimeoutError:
            raise AssertionError(
                f"Timed out waiting for type={until_type!r} (predicate={predicate}); got: {collected}"
            )
        collected.append(msg)
        if msg.get("type") == until_type:
            if predicate is None or predicate(msg):
                return collected


@pytest.fixture
async def ws_session():
    """Yield (ws, engine) connected to a live TestServer. Villager + Werewolf + Seer roles."""
    engine, srv = make_server()
    app = make_app(srv)
    async with TestServer(app) as test_server:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(test_server.make_url("/ws")) as ws:
                yield ws, engine
