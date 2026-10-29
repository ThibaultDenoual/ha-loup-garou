"""async_setup_entry against a real HA: panel, static paths, WebSocket view."""
from __future__ import annotations

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


async def test_static_paths_are_served(hass: HomeAssistant, setup_entry, hass_client) -> None:
    client = await hass_client()

    for path in (
        "/loup_garou/game/index.html",
        "/loup_garou/game/launcher.html",
        "/loup_garou/game/js/app.js",
        "/loup_garou/locales/fr.json",
        "/loup_garou/locales/en.json",
    ):
        resp = await client.get(path)
        assert resp.status == 200, path


async def test_websocket_rejects_unauthenticated_clients(
    hass: HomeAssistant, setup_entry, hass_client_no_auth
) -> None:
    client = await hass_client_no_auth()

    resp = await client.get("/loup_garou/ws")

    assert resp.status == 401


async def test_websocket_round_trip(hass: HomeAssistant, setup_entry, hass_client) -> None:
    client = await hass_client()

    async with client.ws_connect("/loup_garou/ws") as ws:
        await ws.send_json({"cmd": "get_config"})
        msg = await ws.receive_json(timeout=2)
        assert msg["type"] == "config"
        assert msg["config"]["language"] == "fr"

        await ws.send_json({"cmd": "get_state"})
        msg = await ws.receive_json(timeout=2)
        assert msg["type"] == "state"
        assert msg["state"]["phase"] == "setup"
