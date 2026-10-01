"""Demo mode against the real Atmosphere, in browser audio mode.

This is the path a user actually walks: the launcher plays the narration and
replies `tts_done`, which is what releases the engine between phases. Only the
HA service calls are mocked.
"""
from __future__ import annotations

import asyncio
import sys
import time
from unittest.mock import AsyncMock, MagicMock

# `loup_garou/` is the one layer that imports homeassistant, so the atmosphere
# cannot be loaded without it. Probing the real import target (not the top-level
# package, which pulls in nothing) means this is a no-op under the HA test plugin
# used in CI, and only stubs out in environments where homeassistant is installed
# but cannot actually be imported — e.g. an incompatible pyOpenSSL, which breaks
# the whole thing via hass_nabucasa -> acme -> OpenSSL.
try:
    import homeassistant.components.http  # noqa: F401
except Exception:  # pragma: no cover - depends on the local env
    for _mod in [
        "homeassistant",
        "homeassistant.core",
        "homeassistant.config_entries",
        "homeassistant.helpers",
        "homeassistant.helpers.entity",
        "homeassistant.components",
        "homeassistant.components.frontend",
        "homeassistant.components.http",
    ]:
        sys.modules.setdefault(_mod, MagicMock())

import aiohttp  # noqa: E402
from aiohttp.test_utils import TestServer  # noqa: E402

from loup_garou.game_engine import GameEngine  # noqa: E402
from loup_garou.game_server import LoupGarouServer  # noqa: E402
from loup_garou.loup_garou.atmosphere import Atmosphere  # noqa: E402
from loup_garou.roles.loader import load_roles  # noqa: E402
from tests.e2e.conftest import make_app  # noqa: E402


class FakeBrowser:
    """A connected client that plays every narration line and confirms it.

    Owns the single WebSocket reader — a second concurrent receive is not allowed.
    """

    def __init__(self, ws) -> None:
        self.ws = ws
        self.spoken: list[str] = []
        # Time from a narrate going out to the browser confirming it with tts_done.
        self.confirm_latencies: list[float] = []
        self.finished = asyncio.Event()
        self._pump = asyncio.create_task(self._run())

    async def _run(self) -> None:
        try:
            async for msg in self.ws:
                if msg.type != aiohttp.WSMsgType.TEXT:
                    continue
                data = msg.json()
                kind = data.get("type")
                if kind == "narrate":
                    self.spoken.append(data["data"]["text"])
                    sent = time.monotonic()
                    await self.ws.send_json({"cmd": "tts_done", "data": {}})
                    self.confirm_latencies.append(time.monotonic() - sent)
                elif kind == "demo_finished":
                    self.finished.set()
        except asyncio.CancelledError:
            raise
        except Exception:
            self.finished.set()

    async def close(self) -> None:
        self._pump.cancel()
        try:
            await self._pump
        except asyncio.CancelledError:
            pass


async def run_demo_with_atmosphere():
    hass = MagicMock()
    hass.services.async_call = AsyncMock()

    engine = GameEngine(roles=load_roles())
    server = LoupGarouServer(engine, demo_action_delay=0, demo_step_delay=0)
    server.wire_events()

    atmosphere = Atmosphere(
        hass=hass,
        engine=engine,
        light_entities=["light.hall"],
        speaker_entity="",
        tts_engine="tts.home_assistant_cloud",
        language="fr",
        audio_source="tts",
        audio_output="browser",  # the launcher speaks, the server waits for it
        server=server,
    )
    atmosphere.wire_events()

    app = make_app(server)
    async with TestServer(app) as ts:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(ts.make_url("/ws")) as ws:
                browser = FakeBrowser(ws)
                await ws.send_json({"cmd": "run_demo", "data": {"preset": "smoke_test"}})
                await asyncio.wait_for(browser.finished.wait(), timeout=15)
                await browser.close()
                return browser, engine


async def test_demo_narration_reaches_the_browser():
    browser, _ = await run_demo_with_atmosphere()
    joined = "\n".join(browser.spoken)
    assert "La nuit tombe" in joined
    assert "Voyante" in joined
    assert "Loups-garous" in joined
    assert "Alice" in joined
    assert any("gagné" in text for text in browser.spoken)


async def test_browser_confirmation_releases_every_narration():
    """A missing tts_done costs a 10-second stall per line — assert none happened."""
    browser, engine = await run_demo_with_atmosphere()

    assert len(browser.spoken) >= 6, browser.spoken
    worst = max(browser.confirm_latencies)
    assert worst < 1.0, (
        f"slowest narration took {worst:.1f}s to be confirmed — the browser is not "
        "replying with tts_done"
    )
    assert engine.get_public_state()["phase"] == "setup"