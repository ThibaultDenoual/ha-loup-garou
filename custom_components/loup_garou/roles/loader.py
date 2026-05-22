"""Discovers and registers role plugins at startup."""
from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

from .base import BaseRole


_registry: dict[str, BaseRole] = {}


def load_roles() -> dict[str, BaseRole]:
    """Import all modules in roles/impl/ and return id→instance registry."""
    global _registry
    if _registry:
        return _registry

    impl_path = Path(__file__).parent / "impl"
    package = f"{__package__}.impl"

    for finder, name, _ in pkgutil.iter_modules([str(impl_path)]):
        importlib.import_module(f"{package}.{name}")

    for cls in _find_subclasses(BaseRole):
        if cls.id:
            _registry[cls.id] = cls()

    return _registry


def _find_subclasses(base: type) -> list[type]:
    result = []
    for sub in base.__subclasses__():
        result.append(sub)
        result.extend(_find_subclasses(sub))
    return result


def get_role(role_id: str) -> BaseRole | None:
    return _registry.get(role_id)
