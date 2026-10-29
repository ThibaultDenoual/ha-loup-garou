"""Fixtures for tests that load the integration inside a real (in-process) Home Assistant.

Unlike tests/unit and tests/e2e, nothing here imports `loup_garou.*` directly:
the integration is loaded by HA's own loader as `custom_components.loup_garou`,
exactly as it is on a real instance.
"""
from __future__ import annotations

# The `hass` fixture mounts the plugin's own testing_config (which has a
# `custom_components` package) at the front of sys.path. Importing ours first
# pins it in sys.modules so HA's loader finds loup_garou.
import custom_components  # noqa: F401

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

DOMAIN = "loup_garou"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let HA's loader find custom_components/loup_garou."""
    yield


@pytest.fixture
def entry_data() -> dict:
    """Config entry data; override in a test module to change the setup."""
    return {}


@pytest.fixture
async def setup_entry(hass: HomeAssistant, entry_data: dict):
    """Add and set up a config entry, unloading it after the test."""
    entry = MockConfigEntry(domain=DOMAIN, title="Loup Garou", data=entry_data)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    # A real HA never freezes its router (http/server.py start()), so routes can
    # be registered after boot. The test clients start the app without that.
    hass.http.app._router.freeze = lambda: None

    yield entry

    runtime = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if runtime is not None:
        server = runtime["server"]
        if server._demo_running():
            await server._cmd_stop_demo()
        if server._night_task and not server._night_task.done():
            server._night_task.cancel()
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
