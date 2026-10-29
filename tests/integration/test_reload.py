"""Reloading the config entry, as HA does from the UI or after an update (#15)."""
from __future__ import annotations

from aiohttp import WSMsgType

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import DOMAIN


async def _start_game(ws) -> None:
    await ws.send_json({
        "cmd": "start_game",
        "data": {
            "players": ["Alice", "Bob", "Carol", "Dave"],
            "roles": ["villager", "werewolf", "villager", "seer"],
        },
    })
    await ws.receive_json(timeout=2)


async def test_reload_reaches_the_new_server(hass: HomeAssistant, setup_entry, game_ws) -> None:
    async with game_ws() as ws:
        await _start_game(ws)
    old_server = hass.data[DOMAIN][setup_entry.entry_id]["server"]

    assert await hass.config_entries.async_reload(setup_entry.entry_id)
    await hass.async_block_till_done()

    assert setup_entry.state is ConfigEntryState.LOADED
    assert hass.data[DOMAIN][setup_entry.entry_id]["server"] is not old_server
    async with game_ws() as ws:
        await ws.send_json({"cmd": "get_state"})
        msg = await ws.receive_json(timeout=2)
    assert msg["state"]["phase"] == "setup"


async def test_reload_disconnects_open_pages(hass: HomeAssistant, setup_entry, game_ws) -> None:
    async with game_ws() as ws:
        assert await hass.config_entries.async_reload(setup_entry.entry_id)
        await hass.async_block_till_done()

        msg = await ws.receive(timeout=2)

    # The page reconnects on close, which lands it on the new server.
    assert msg.type is WSMsgType.CLOSE
