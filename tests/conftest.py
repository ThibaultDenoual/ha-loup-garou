"""Pytest configuration and fixtures for Loup Garou tests."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.resolve()

if str(ROOT / "custom_components") not in sys.path:
    sys.path.insert(0, str(ROOT / "custom_components"))
if str(ROOT / "custom_components" / "loup_garou") not in sys.path:
    sys.path.insert(0, str(ROOT / "custom_components" / "loup_garou"))
if str(ROOT / "custom_components" / "loup_garou" / "core_game") not in sys.path:
    sys.path.insert(0, str(ROOT / "custom_components" / "loup_garou" / "core_game"))

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def mock_hass():
    """Create a mock HomeAssistant instance."""
    hass = MagicMock()
    hass.data = {}
    hass.bus = MagicMock()
    hass.bus.async_listen = MagicMock()
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()

    async def mock_executor(func, *args, **kwargs):
        return func(*args, **kwargs)
    hass.async_add_executor_job = mock_executor

    async def mock_add_job(func, *args, **kwargs):
        pass
    hass.async_add_job = mock_add_job

    mock_ws = MagicMock()
    mock_ws.send_json = AsyncMock()
    hass.http = MagicMock()

    def async_fire(event_type, data):
        pass
    hass.bus.async_fire = async_fire

    return hass


@pytest.fixture
def mock_store():
    """Create a mock Store that works synchronously in tests."""
    store = MagicMock()
    store.async_load = AsyncMock(return_value=None)
    store.async_save = AsyncMock()
    return store


@pytest.fixture
def mock_engine(mock_hass):
    """Create an AsyncGameAdapter (new engine wrapper)."""
    from custom_components.loup_garou.core.adapter import AsyncGameAdapter

    engine = AsyncGameAdapter(hass=mock_hass, config_entry_id="test_entry")
    return engine


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket response."""
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    ws.closed = False
    return ws


@pytest.fixture
def mock_phase_manager():
    """Create a mock PhaseManager."""
    pm = MagicMock()
    pm.on_game_started = AsyncMock()
    pm.on_night_started = AsyncMock()
    pm.on_role_wake = AsyncMock()
    pm.on_night_action_submitted = AsyncMock()
    pm.on_day_started = AsyncMock()
    pm.on_vote_started = AsyncMock()
    pm.on_player_eliminated = AsyncMock()
    pm.on_game_over = AsyncMock()
    return pm


@pytest.fixture
def sample_players():
    """Return a list of sample player data."""
    return ["Alice", "Bob", "Charlie", "Diana", "Eve"]


@pytest.fixture
def sample_role_config():
    """Return a valid role configuration for 5 players."""
    return {"villagers": 3, "werewolves": 1, "seers": 1}


def run_async(coro):
    """Run a coroutine synchronously for testing."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()