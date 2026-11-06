"""Joined narration clips — zero HA imports.

A line that names a player is recorded in parts ("The victim is…" + "the
Baker" + "They were…" + "a Seer"). The browser or the speaker fetches it as one
MP3 from /loup_garou/voice/<lang>/<stem>+<stem>….mp3, which this module builds
by joining the parts: the clips are headerless MP3 frames in one format
(24 kHz, 48 kbps, mono), so the bytes simply follow each other.

Only stems of known clips are accepted, so the URL can't read anything else.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from .const import STATIC_AUDIO_MAP

URL_PREFIX = "/loup_garou/voice"
LANGUAGES = ("en", "fr")
MAX_PARTS = 6
_KNOWN = frozenset(STATIC_AUDIO_MAP.values())
_STEM = re.compile(r"^[a-z0-9_]+$")


def url(lang: str, stems: list[str]) -> str:
    return f"{URL_PREFIX}/{lang}/{'+'.join(stems)}.mp3"


def parse(lang: str, name: str) -> list[str] | None:
    """The stems in a voice URL's file name, or None when it isn't allowed."""
    if lang not in LANGUAGES or not name.endswith(".mp3"):
        return None
    stems = name[: -len(".mp3")].split("+")
    if not 1 <= len(stems) <= MAX_PARTS:
        return None
    if not all(_STEM.match(s) and s in _KNOWN for s in stems):
        return None
    return stems


@lru_cache(maxsize=256)
def join(audio_root: Path, lang: str, stems: tuple[str, ...]) -> bytes:
    """The parts' bytes, one after the other. Blocking: run it in an executor."""
    return b"".join((audio_root / lang / f"{stem}.mp3").read_bytes() for stem in stems)
