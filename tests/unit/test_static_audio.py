"""STATIC_AUDIO_SECONDS must match the recorded clips in www/audio/."""
from pathlib import Path

import pytest

from loup_garou.const import STATIC_AUDIO_MAP, STATIC_AUDIO_SECONDS

mutagen_mp3 = pytest.importorskip("mutagen.mp3")

AUDIO = Path(__file__).parent.parent.parent / "custom_components" / "loup_garou" / "www" / "audio"
CLIPS = sorted(AUDIO.glob("*/*.mp3"))


@pytest.mark.parametrize("path", CLIPS, ids=lambda p: f"{p.parent.name}/{p.stem}")
def test_clip_length_is_recorded(path):
    actual = mutagen_mp3.MP3(path).info.length
    recorded = STATIC_AUDIO_SECONDS[path.parent.name][path.stem]
    # Rounded up to 0.1 s: never shorter than the clip, never far off.
    assert actual <= recorded < actual + 0.1 + 1e-9


@pytest.mark.parametrize("lang", sorted(STATIC_AUDIO_SECONDS))
def test_every_mapped_clip_has_a_length(lang):
    assert set(STATIC_AUDIO_MAP.values()) <= set(STATIC_AUDIO_SECONDS[lang])
