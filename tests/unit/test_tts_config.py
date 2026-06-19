"""Unit tests for config_flow TTS mode + server narrate/tts_done protocol."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from loup_garou.const import (
    CONF_LIGHTS,
    CONF_SPEAKER,
    CONF_LANGUAGE,
    CONF_TTS_ENGINE,
    CONF_AUDIO_SOURCE,
    CONF_AUDIO_OUTPUT,
    DEFAULT_TTS_ENGINE,
    DEFAULT_AUDIO_SOURCE,
    DEFAULT_AUDIO_OUTPUT,
)
from loup_garou.game_server import LoupGarouServer
from loup_garou.narration import NarrationMessage


# ═══════════════════════════════════════════════════════════════════════════════
# Config constants
# ═══════════════════════════════════════════════════════════════════════════════

def test_default_audio_source_is_tts():
    assert DEFAULT_AUDIO_SOURCE == "tts"


def test_default_audio_output_is_browser():
    assert DEFAULT_AUDIO_OUTPUT == "browser"


def test_conf_audio_source_key():
    assert CONF_AUDIO_SOURCE == "audio_source"


def test_conf_audio_output_key():
    assert CONF_AUDIO_OUTPUT == "audio_output"


# ═══════════════════════════════════════════════════════════════════════════════
# LoupGarouServer.narrate() — broadcast + future
# ═══════════════════════════════════════════════════════════════════════════════

def make_server_with_fake_client():
    """Return (server, fake_ws) with one mock client connected."""
    engine = MagicMock()
    engine.on = MagicMock()
    server = LoupGarouServer(engine)
    ws = MagicMock()
    ws.send_json = AsyncMock()
    server._clients.add(ws)
    return server, ws


async def test_narrate_returns_immediately_when_no_clients():
    engine = MagicMock()
    engine.on = MagicMock()
    server = LoupGarouServer(engine)
    # Should complete without blocking
    await asyncio.wait_for(server.narrate(NarrationMessage("hello", "fr")), timeout=1.0)


async def test_narrate_broadcasts_narrate_message():
    server, ws = make_server_with_fake_client()
    async def resolve_future():
        await asyncio.sleep(0)
        if server._tts_future and not server._tts_future.done():
            server._tts_future.set_result(None)
    asyncio.ensure_future(resolve_future())
    await server.narrate(NarrationMessage("Good night", "fr"))
    ws.send_json.assert_awaited_once()
    sent = ws.send_json.call_args[0][0]
    assert sent["type"] == "narrate"
    assert sent["data"]["text"] == "Good night"
    assert sent["data"]["lang"] == "fr"


async def test_narrate_blocks_until_tts_done():
    server, ws = make_server_with_fake_client()
    resolved_at = []
    async def resolver():
        await asyncio.sleep(0.05)
        resolved_at.append(asyncio.get_running_loop().time())
        if server._tts_future and not server._tts_future.done():
            server._tts_future.set_result(None)
    asyncio.ensure_future(resolver())
    start = asyncio.get_running_loop().time()
    await server.narrate(NarrationMessage("Wait for me", "fr"))
    end = asyncio.get_running_loop().time()
    assert end - start >= 0.04, "narrate() should have blocked until tts_done"


async def test_narrate_times_out_after_10_seconds():
    """narrate() must not block forever if the client never responds."""
    server, ws = make_server_with_fake_client()
    # Patch wait_for only in the game_server module so the outer await is unaffected.
    # The argument is a Future (not a coroutine) so we cancel it before raising.
    call_count = 0
    async def fast_wait_for(future_or_coro, timeout):
        nonlocal call_count
        call_count += 1
        if hasattr(future_or_coro, "cancel"):
            future_or_coro.cancel()
        raise asyncio.TimeoutError()
    from unittest.mock import patch as _patch
    with _patch("loup_garou.game_server.asyncio.wait_for", fast_wait_for):
        await server.narrate(NarrationMessage("stuck", "fr"))
    assert server._tts_future is None
    assert call_count == 1


async def test_tts_done_command_resolves_future():
    engine = MagicMock()
    engine.on = MagicMock()
    server = LoupGarouServer(engine)
    ws = MagicMock()
    ws.send_json = AsyncMock()
    server._clients.add(ws)

    # Manually plant a future as if narrate() set it
    future = asyncio.get_running_loop().create_future()
    server._tts_future = future

    # Dispatch tts_done
    await server._dispatch(ws, {"cmd": "tts_done"})

    assert future.done()
    assert future.result() is None


async def test_tts_done_when_no_future_is_noop():
    engine = MagicMock()
    engine.on = MagicMock()
    server = LoupGarouServer(engine)
    ws = MagicMock()
    ws.send_json = AsyncMock()
    # No tts_future set
    server._tts_future = None
    # Should not raise
    await server._dispatch(ws, {"cmd": "tts_done"})


async def test_tts_done_when_future_already_done_is_noop():
    engine = MagicMock()
    engine.on = MagicMock()
    server = LoupGarouServer(engine)
    ws = MagicMock()
    ws.send_json = AsyncMock()

    future = asyncio.get_running_loop().create_future()
    future.set_result(None)  # already resolved
    server._tts_future = future

    # Should not raise InvalidStateError
    await server._dispatch(ws, {"cmd": "tts_done"})


async def test_narrate_clears_future_after_completion():
    server, ws = make_server_with_fake_client()
    async def resolve():
        await asyncio.sleep(0)
        if server._tts_future and not server._tts_future.done():
            server._tts_future.set_result(None)
    asyncio.ensure_future(resolve())
    await server.narrate(NarrationMessage("clean up", "fr"))
    assert server._tts_future is None


async def test_get_config_returns_audio_keys():
    """get_config exposes audio_source and audio_output to the browser."""
    engine = MagicMock()
    engine.on = MagicMock()
    config = {CONF_AUDIO_SOURCE: "static", CONF_AUDIO_OUTPUT: "browser", CONF_LANGUAGE: "fr"}
    server = LoupGarouServer(engine, config=config)
    ws = MagicMock()
    ws.send_json = AsyncMock()
    await server._dispatch(ws, {"cmd": "get_config"})
    sent = ws.send_json.call_args[0][0]
    assert sent["type"] == "config"
    assert sent["config"][CONF_AUDIO_SOURCE] == "static"
    assert sent["config"][CONF_AUDIO_OUTPUT] == "browser"


# ═══════════════════════════════════════════════════════════════════════════════
# narrate() with audio_url
# ═══════════════════════════════════════════════════════════════════════════════

async def test_narrate_with_audio_url_broadcasts_field():
    server, ws = make_server_with_fake_client()

    async def resolve():
        await asyncio.sleep(0)
        if server._tts_future and not server._tts_future.done():
            server._tts_future.set_result(None)

    asyncio.ensure_future(resolve())
    await server.narrate(NarrationMessage("La nuit tombe.", "fr", audio_url="/loup_garou/audio/fr/night_start.mp3"))

    ws.send_json.assert_awaited_once()
    sent = ws.send_json.call_args[0][0]
    assert sent["type"] == "narrate"
    assert sent["data"]["audio_url"] == "/loup_garou/audio/fr/night_start.mp3"
    assert sent["data"]["text"] == "La nuit tombe."
    assert sent["data"]["lang"] == "fr"


async def test_narrate_without_audio_url_omits_field():
    server, ws = make_server_with_fake_client()

    async def resolve():
        await asyncio.sleep(0)
        if server._tts_future and not server._tts_future.done():
            server._tts_future.set_result(None)

    asyncio.ensure_future(resolve())
    await server.narrate(NarrationMessage("Alice a été dévorée.", "fr"))

    ws.send_json.assert_awaited_once()
    sent = ws.send_json.call_args[0][0]
    assert "audio_url" not in sent["data"]


async def test_get_config_returns_ha_output():
    engine = MagicMock()
    engine.on = MagicMock()
    config = {CONF_AUDIO_SOURCE: "tts", CONF_AUDIO_OUTPUT: "ha", CONF_LANGUAGE: "fr"}
    server = LoupGarouServer(engine, config=config)
    ws = MagicMock()
    ws.send_json = AsyncMock()
    await server._dispatch(ws, {"cmd": "get_config"})
    sent = ws.send_json.call_args[0][0]
    assert sent["config"][CONF_AUDIO_OUTPUT] == "ha"
    assert sent["config"][CONF_AUDIO_SOURCE] == "tts"
