"""Tests for the standalone human-playtesting server."""

from dev_config import DevConfig
from run_devserver import build_app


def test_devserver_registers_one_websocket_route():
    app = build_app(DevConfig(tts_mode="mock"))

    routes = [
        route
        for route in app.router.routes()
        if route.method == "GET" and route.resource.canonical == "/loup_garou/ws"
    ]

    assert len(routes) == 1
