"""Reloading the config entry, as HA does from the UI or after an update."""
from __future__ import annotations

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import DOMAIN


@pytest.mark.xfail(
    reason="#15: the WebSocket view registered by the first setup keeps routing "
    "to the old server after a reload",
    strict=True,
)
async def test_reload_on_a_running_server(hass: HomeAssistant, setup_entry, hass_client) -> None:
    client = await hass_client()
    async with client.ws_connect("/loup_garou/ws") as ws:
        await ws.send_json({
            "cmd": "start_game",
            "data": {
                "players": ["Alice", "Bob", "Carol", "Dave"],
                "roles": ["villager", "werewolf", "villager", "seer"],
            },
        })
        await ws.receive_json(timeout=2)
    old_server = hass.data[DOMAIN][setup_entry.entry_id]["server"]

    assert await hass.config_entries.async_reload(setup_entry.entry_id)
    await hass.async_block_till_done()

    assert setup_entry.state is ConfigEntryState.LOADED
    assert hass.data[DOMAIN][setup_entry.entry_id]["server"] is not old_server
    async with client.ws_connect("/loup_garou/ws") as ws:
        await ws.send_json({"cmd": "get_state"})
        msg = await ws.receive_json(timeout=2)
    assert msg["state"]["phase"] == "setup"
