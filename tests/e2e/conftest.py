"""Shared fixtures and helpers for e2e WebSocket tests."""
from __future__ import annotations

import asyncio

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer


@pytest.fixture(autouse=True)
def _allow_sockets(socket_enabled):
    """Re-enable TCP sockets for all e2e tests (blocked by HA plugin by default)."""
    yield

from loup_garou.game_engine import GameEngine
from loup_garou.game_server import LoupGarouServer
from loup_garou.roles.impl.villager import Villager
from loup_garou.roles.impl.werewolf import Werewolf
from loup_garou.roles.impl.seer import Seer


def make_server(role_classes=None, **server_kwargs):
    """Build a GameEngine + LoupGarouServer with the given role classes."""
    classes = role_classes or (Villager, Werewolf, Seer)
    roles = {cls.id: cls() for cls in classes}
    engine = GameEngine(roles=roles)
    server = LoupGarouServer(engine, **server_kwargs)
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


def snapshot_where(predicate):
    return lambda m: predicate(m["state"])


def prompt_of(kind, role=None):
    """Predicate: a snapshot whose open prompt is of this kind (and role)."""
    def matches(msg):
        prompt = msg["state"]["prompt"]
        return bool(prompt and prompt["kind"] == kind and (role is None or prompt["role"] == role))
    return matches


async def wait_prompt(ws, kind, role=None, timeout: float = 2.0) -> dict:
    msgs = await drain(ws, until_type="snapshot", predicate=prompt_of(kind, role), timeout=timeout)
    return msgs[-1]["state"]["prompt"]


async def answer(ws, prompt: dict, **choices) -> None:
    await ws.send_json({"cmd": "answer", "data": {"prompt_id": prompt["id"], "answer": choices}})


async def deal(ws, roles: list[str]) -> None:
    """Start a game and answer every reveal, leaving night 1 running."""
    names = [f"P{i}" for i in range(len(roles))]
    await ws.send_json({"cmd": "start_game", "data": {"players": names, "roles": roles}})
    for _ in roles:
        await answer(ws, await wait_prompt(ws, "reveal"))


async def wait_day_choice(ws, *, options=None) -> dict:
    prompt = await wait_prompt(ws, "day_choice")
    if options is not None:
        assert prompt["picks"]["next"]["options"] == options
    return prompt


async def vote_out(ws, target: str, players: list[str]) -> None:
    """From a day choice: start the vote, and everyone votes for target."""
    await answer(ws, await wait_day_choice(ws), next="vote")
    for _ in players:
        ballot = await wait_prompt(ws, "ballot")
        options = ballot["picks"]["target"]["options"]
        await answer(ws, ballot, target=target if target in options else options[0])
