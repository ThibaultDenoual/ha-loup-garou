"""Pytest plugin: isolate playwright from pytest-asyncio event loop issues."""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

_original_await = asyncio.ensure_future


def _isolated_ensure_future(coro, *args, **kwargs):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return _original_await(coro, *args, **kwargs)


@pytest.hookimpl(hookwrapper=True)
def pytest_pyfunc_call(item: Any) -> Any:
    """Prevent asyncio event loop conflicts during playwright browser lifecycle."""
    yield