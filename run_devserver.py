#!/usr/bin/env python3
"""
Standalone dev server — serves the game UI + WebSocket without Home Assistant.

Usage:
    python run_devserver.py [--port 8099]

Then open: http://localhost:8099/loup_garou/game/index.html
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Make `custom_components` importable
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "custom_components"))

from aiohttp import web

from loup_garou.game_engine import GameEngine
from loup_garou.game_server import LoupGarouServer

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
_LOGGER = logging.getLogger("devserver")


def build_app(port: int) -> web.Application:
    engine = GameEngine()
    server = LoupGarouServer(engine, config={
        "language":     "fr",
        "audio_source": "static",
        "audio_output": "browser",
        "speaker":      "",
        "lights":       [],
        "tts_engine":   "tts.cloud_say",
    })
    server.wire_events()

    app = web.Application()

    # WebSocket
    app.router.add_get("/loup_garou/ws", server.handle_ws)

    # Static: game UI, locales, and pre-recorded audio
    www_root    = ROOT / "custom_components" / "loup_garou" / "www"
    locale_root = ROOT / "custom_components" / "loup_garou" / "locales"
    app.router.add_static("/loup_garou/game",    www_root / "game",   show_index=True)
    app.router.add_static("/loup_garou/locales", locale_root,         show_index=True)
    app.router.add_static("/loup_garou/audio",   www_root / "audio",  show_index=True)

    # Redirect / → game index
    async def _root(request: web.Request) -> web.Response:
        raise web.HTTPFound("/loup_garou/game/index.html")

    app.router.add_get("/", _root)

    async def _on_startup(app: web.Application) -> None:
        _LOGGER.info("Dev server ready → http://localhost:%d/", port)
        _LOGGER.info("Game UI         → http://localhost:%d/loup_garou/game/index.html", port)
        _LOGGER.info("Launcher        → http://localhost:%d/loup_garou/game/launcher.html", port)

    app.on_startup.append(_on_startup)
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Loup Garou dev server")
    parser.add_argument("--port", type=int, default=8099, help="HTTP port (default: 8099)")
    args = parser.parse_args()

    app = build_app(args.port)
    web.run_app(app, host="0.0.0.0", port=args.port, print=None)


if __name__ == "__main__":
    main()
