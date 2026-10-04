"""Dev TTS simulator — browser (WebSocket) or mock (console log)."""
from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any

from aiohttp import web

_LOGGER = logging.getLogger("dev_tts")


class DevTTS(ABC):
    """Abstract TTS backend for dev environments."""

    @abstractmethod
    async def narrate(self, text: str, lang: str) -> None:
        """Speak text and wait for completion (or timeout)."""

    @abstractmethod
    async def handle_client_message(self, ws: web.WebSocketResponse, msg: dict) -> bool:
        """Handle WS message from client. Return True if handled."""


class MockTTS(DevTTS):
    """Mock TTS — logs to console, no audio."""

    def __init__(self, delays: dict[str, float] | None = None) -> None:
        self._delays = delays or {}

    async def narrate(self, text: str, lang: str) -> None:
        _LOGGER.info("[TTS] (%s) %s", lang, text)
        delay = self._delays.get("default", 0.5)
        await asyncio.sleep(delay)

    async def handle_client_message(self, ws: web.WebSocketResponse, msg: dict) -> bool:
        return False


class BrowserTTS(DevTTS):
    """Browser TTS — broadcasts narrate via WebSocket, waits for tts_done."""

    def __init__(
        self,
        server: Any,
        delays: dict[str, float] | None = None,
        timeout: float = 15.0,
    ) -> None:
        self._server = server
        self._delays = delays or {}
        self._timeout = timeout
        self._tts_future: asyncio.Future | None = None

    async def narrate(self, text: str, lang: str) -> None:
        if not self._server._clients:
            _LOGGER.debug("[TTS] no clients connected, skipping: %.60s", text)
            return

        await self._server.broadcast({"type": "narrate", "data": {"text": text, "lang": lang}})
        self._tts_future = asyncio.get_event_loop().create_future()

        try:
            await asyncio.wait_for(self._tts_future, timeout=self._timeout)
        except asyncio.TimeoutError:
            _LOGGER.warning("[TTS] timed out after %.1fs for: %.60s", self._timeout, text)
        except asyncio.CancelledError:
            pass
        finally:
            self._tts_future = None

    async def handle_client_message(self, ws: web.WebSocketResponse, msg: dict) -> bool:
        if msg.get("cmd") == "tts_done":
            if self._tts_future and not self._tts_future.done():
                self._tts_future.set_result(None)
            return True
        return False


def create_tts(
    mode: str,
    server: Any | None = None,
    delays: dict[str, float] | None = None,
) -> DevTTS:
    if mode == "browser":
        if server is None:
            raise ValueError("BrowserTTS requires a server instance")
        return BrowserTTS(server, delays)
    return MockTTS(delays)