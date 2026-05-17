"""
i18n.py — Internationalization helper for the game engine.

Loads translations from JSON locale files at startup.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_current_language: str = "fr"
_translations: dict[str, dict] = {}


def _load_locales() -> None:
    """Load all locale files from the locales directory."""
    global _translations

    locales_dir = Path(__file__).parent / "locales"
    if not locales_dir.exists():
        raise FileNotFoundError(f"Locales directory not found: {locales_dir}")

    for file in locales_dir.glob("*.json"):
        lang = file.stem
        with open(file, "r", encoding="utf-8") as f:
            _translations[lang] = json.load(f)


_load_locales()


def set_language(lang: str) -> None:
    """Set the current language for translations."""
    global _current_language
    if lang not in _translations:
        raise ValueError(f"Unknown language '{lang}'. Available: {list(_translations.keys())}")
    _current_language = lang


def get_language() -> str:
    """Get the current language."""
    return _current_language


def t(key: str, **kwargs: Any) -> str:
    """
    Translate a key with optional interpolation.

    Args:
        key: Dot-separated path to the translation (e.g., "roles.Seer.name")
        **kwargs: Values to interpolate into the template

    Returns:
        Translated string with placeholders replaced
    """
    keys = key.split(".")
    d = _translations[_current_language]
    for k in keys:
        d = d[k]
    if isinstance(d, str):
        return d.format(**kwargs) if kwargs else d
    return key


def role_name(role_key: str) -> str:
    """Get translated role name."""
    return _translations[_current_language]["roles"][role_key]["name"]


def role_description(role_key: str) -> str:
    """Get translated role description."""
    return _translations[_current_language]["roles"][role_key]["description"]


def role_team(role_key: str) -> str:
    """Get role team."""
    return _translations[_current_language]["roles"][role_key]["team"]


def role_article(role_key: str) -> str:
    """Get French article for role (for TTS formatting)."""
    return _translations[_current_language]["articles"].get(role_key, "un")


def tts(key: str, **kwargs: Any) -> str:
    """Get TTS string."""
    return t(f"tts.{key}", **kwargs)


def available_languages() -> list[str]:
    """Return list of available language codes."""
    return list(_translations.keys())