#!/usr/bin/env python3
"""
Standalone dev server — serves the game UI + WebSocket without Home Assistant.

Usage:
    python run_devserver.py [--port 8099] [--config dev.yaml] [--tts-mode browser|mock] ...

Then open: http://localhost:8099/loup_garou/game/index.html
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Make `custom_components` importable
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "custom_components"))

from aiohttp import web

from custom_components.loup_garou.const import VERSION
from custom_components.loup_garou.game_engine import GameEngine
from custom_components.loup_garou.game_server import LoupGarouServer
from dev_config import DevConfig, add_common_args, load_config
from dev_lights import DevLights
from dev_output import DevOutputHandler
from dev_tts import BrowserTTS, create_tts

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
_LOGGER = logging.getLogger("devserver")


def build_app(config: DevConfig) -> web.Application:
    engine = GameEngine()
    server = LoupGarouServer(engine, config={
        "language": config.language,
        "tts_mode": config.tts_mode,
        "speaker": config.speaker,
        "lights": config.lights,
        "tts_engine": config.tts_engine,
        "tts_delays": config.tts_delays,
        "version": VERSION,
    })
    server.wire_events()

    # Dev output handler (TTS + lights simulation)
    tts = create_tts(config.tts_mode, server, config.tts_delays)
    lights = DevLights(config.lights)
    DevOutputHandler(engine, tts, lights, config.language).wire_events()

    app = web.Application()

    # WebSocket
    app.router.add_get("/loup_garou/ws", server.handle_ws)

    # Static: game UI and locales
    www_root = ROOT / "custom_components" / "loup_garou" / "www"
    locale_root = ROOT / "custom_components" / "loup_garou" / "locales"
    app.router.add_static("/loup_garou/game", www_root / "game", show_index=True)
    app.router.add_static("/loup_garou/locales", locale_root, show_index=True)

    # Redirect / → game index
    async def _root(request: web.Request) -> web.Response:
        raise web.HTTPFound("/loup_garou/game/index.html")

    app.router.add_get("/", _root)

    async def handle_ws_with_tts(request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        server._clients.add(ws)
        _LOGGER.debug("WS client connected")

        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    # Let BrowserTTS handle tts_done
                    if isinstance(tts, BrowserTTS):
                        await tts.handle_client_message(ws, data)
                    await server._dispatch(ws, data)
                elif msg.type == web.WSMsgType.ERROR:
                    _LOGGER.warning("WS error: %s", ws.exception())
        finally:
            server._clients.discard(ws)
            _LOGGER.debug("WS client disconnected")

        return ws

    app.router.add_get("/loup_garou/ws", handle_ws_with_tts)

    async def _on_startup(app: web.Application) -> None:
        _LOGGER.info("Dev server ready → http://localhost:%d/", config.port)
        _LOGGER.info("Game UI         → http://localhost:%d/loup_garou/game/index.html", config.port)
        _LOGGER.info("Launcher        → http://localhost:%d/loup_garou/game/launcher.html", config.port)
        _LOGGER.info("TTS mode: %s", config.tts_mode)
        if config.lights:
            _LOGGER.info("Lights: %s", ", ".join(config.lights))

    app.on_startup.append(_on_startup)
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Loup Garou dev server")
    add_common_args(parser)
    args = parser.parse_args()

    config = load_config(parser, args)

    app = build_app(config)
    web.run_app(app, host="0.0.0.0", port=config.port, print=None)


if __name__ == "__main__":
    main()