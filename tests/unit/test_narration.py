"""NarrationMessage: what the browser is sent, and how long a line should last."""
from __future__ import annotations

from loup_garou.narration import CHARS_PER_SECOND, NarrationMessage


def test_payload_carries_the_clip_and_its_length():
    msg = NarrationMessage(text="La nuit tombe.", lang="fr",
                           audio_url="/loup_garou/audio/fr/night_start.mp3", audio_seconds=9.4)
    assert msg.to_payload() == {
        "text": "La nuit tombe.", "lang": "fr",
        "audio_url": "/loup_garou/audio/fr/night_start.mp3", "audio_seconds": 9.4,
    }


def test_payload_without_a_clip_is_text_only():
    assert NarrationMessage(text="Bob est mort.", lang="fr").to_payload() == {
        "text": "Bob est mort.", "lang": "fr",
    }


def test_expected_length_is_the_clip_when_known():
    assert NarrationMessage(text="x" * 500, lang="en", audio_seconds=4.3).expected_seconds() == 4.3


def test_expected_length_is_estimated_from_the_text_otherwise():
    text = "x" * (CHARS_PER_SECOND * 6)
    assert NarrationMessage(text=text, lang="en").expected_seconds() == 6
    assert NarrationMessage(text="Hi.", lang="en").expected_seconds() == 1.5
