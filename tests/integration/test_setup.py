"""async_setup_entry against a real HA: panel, static paths, WebSocket view."""
from __future__ import annotations

import pytest
from aiohttp import WSMsgType

from homeassistant.components.frontend import DATA_PANELS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import DOMAIN


async def test_setup_registers_runtime_and_panel(hass: HomeAssistant, setup_entry) -> None:
    runtime = hass.data[DOMAIN][setup_entry.entry_id]
    assert set(runtime) == {"engine", "server", "atmosphere"}

    panel = hass.data[DATA_PANELS]["loup_garou"]
    assert panel.config == {"url": "/loup_garou/game/index.html"}
    assert panel.require_admin is False


async def test_unload_removes_runtime_and_panel(hass: HomeAssistant, setup_entry) -> None:
    assert await hass.config_entries.async_unload(setup_entry.entry_id)
    await hass.async_block_till_done()

    assert setup_entry.state is ConfigEntryState.NOT_LOADED
    assert setup_entry.entry_id not in hass.data[DOMAIN]
    assert "loup_garou" not in hass.data.get(DATA_PANELS, {})


async def test_static_paths_are_served(
    hass: HomeAssistant, setup_entry, hass_client_no_auth
) -> None:
    # The panel iframe loads these without any Authorization header.
    client = await hass_client_no_auth()

    for path in (
        "/loup_garou/game/index.html",
        "/loup_garou/game/launcher.html",
        "/loup_garou/game/js/app.js",
        "/loup_garou/game/js/ha_auth.js",
        "/loup_garou/locales/fr.json",
        "/loup_garou/locales/en.json",
    ):
        resp = await client.get(path)
        assert resp.status == 200, path


@pytest.mark.parametrize(
    "first_message",
    [
        {"cmd": "get_state"},
        {"type": "auth"},
        {"type": "auth", "access_token": "not-a-token"},
    ],
    ids=["no-auth-message", "no-token", "bad-token"],
)
async def test_websocket_rejects_connections_without_a_valid_token(
    hass: HomeAssistant, setup_entry, hass_client_no_auth, first_message
) -> None:
    client = await hass_client_no_auth()

    async with client.ws_connect("/loup_garou/ws") as ws:
        await ws.send_json(first_message)
        assert (await ws.receive_json(timeout=2))["type"] == "auth_invalid"
        msg = await ws.receive(timeout=2)

    assert msg.type is WSMsgType.CLOSE


async def test_websocket_round_trip(hass: HomeAssistant, setup_entry, game_ws) -> None:
    async with game_ws() as ws:
        await ws.send_json({"cmd": "get_config"})
        msg = await ws.receive_json(timeout=2)
        assert msg["type"] == "config"
        assert msg["config"]["language"] == "fr"

        await ws.send_json({"cmd": "get_state"})
        msg = await ws.receive_json(timeout=2)
        assert msg["type"] == "state"
        assert msg["state"]["phase"] == "setup"
