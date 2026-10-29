"""Fixtures shared by every test tier."""
from __future__ import annotations

# pycares (aiohttp's DNS resolver) starts a singleton daemon thread on the first
# Channel() creation, which happens inside aiohttp.ClientSession().  That thread
# runs an infinite loop and never exits.  Triggering it here — at import time,
# before pytest collects any tests — ensures it is already in threads_before when
# verify_cleanup records the thread snapshot for the very first test.
try:
    import pycares as _pycares
    _pycares.Channel()
    del _pycares
except (ImportError, Exception):
    pass
