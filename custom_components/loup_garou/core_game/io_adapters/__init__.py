"""
io_adapters/__init__.py — Home Assistant specific IO implementations.
"""

from .ha_io import HomeAssistantIO, MockIO

__all__ = ["HomeAssistantIO", "MockIO"]