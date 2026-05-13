"""
i18n.py — Internationalization helper for the game engine.

Usage:
    from i18n import t, set_language, get_language

    # Basic translation
    t("roles.Seer.name")  # -> "Seer" or "Voyante"

    # With interpolation
    t("roles.Seer.prompt_investigate", player_name="Alice")
    # -> "[SEER] Alice, choose someone to investigate:"

    # Switch language
    set_language("fr")
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

_current_language: str = "en"
_translations: dict[str, dict] = {}


def _load_locales() -> None:
    """Load all locale files from the locales directory."""
    global _translations

    locales_dir = Path(__file__).parent / "locales"
    if not locales_dir.exists():
        return

    for file in locales_dir.glob("*.json"):
        lang = file.stem
        try:
            with open(file, "r", encoding="utf-8") as f:
                _translations[lang] = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load locale {file}: {e}")


_load_locales()


def set_language(lang: str) -> None:
    """Set the current language for translations."""
    global _current_language
    if lang in _translations:
        _current_language = lang
    else:
        print(f"Warning: Unknown language '{lang}', falling back to 'en'")
        _current_language = "en"


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

    Example:
        t("roles.Seer.prompt_investigate", player_name="Alice")
    """
    keys = key.split(".")
    lang = _current_language

    # Try current language, fall back to English
    for attempt_lang in (lang, "en"):
        if attempt_lang not in _translations:
            continue
        d = _translations[attempt_lang]
        try:
            for k in keys:
                d = d[k]
            if isinstance(d, str):
                return d.format(**kwargs) if kwargs else d
        except (KeyError, TypeError):
            continue

    # Return the key itself if not found
    return key


def available_languages() -> list[str]:
    """Return list of available language codes."""
    return list(_translations.keys())


def has_key(key: str) -> bool:
    """Check if a translation key exists in the current language."""
    keys = key.split(".")
    d = _translations.get(_current_language, {})
    try:
        for k in keys:
            d = d[k]
        return isinstance(d, str)
    except (KeyError, TypeError):
        return False