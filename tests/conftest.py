"""Shared test fixtures for Loup Garou tests."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_hass():
    hass = MagicMock()
    hass.bus = MagicMock()
    hass.bus.async_fire = MagicMock()
    hass.http = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()
    hass.components = MagicMock()
    hass.components.frontend = MagicMock()
    hass.components.frontend.async_register_built_in_panel = MagicMock()
    return hass


@pytest.fixture
def mock_store():
    store = MagicMock()
    store.async_load = AsyncMock(return_value=None)
    store.async_save = AsyncMock()
    return store
