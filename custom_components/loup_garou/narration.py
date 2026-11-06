from __future__ import annotations

from dataclasses import dataclass

# Rough speaking rate, as in www/game/js/tts.js.
CHARS_PER_SECOND = 14


@dataclass
class NarrationMessage:
    text: str
    lang: str
    audio_url: str | None = None
    delay_key: str = "role_wake"
    # Length of the recorded clip at audio_url, when known.
    audio_seconds: float | None = None

    def to_payload(self) -> dict:
        payload = {"text": self.text, "lang": self.lang}
        if self.audio_url:
            payload["audio_url"] = self.audio_url
        if self.audio_seconds:
            payload["audio_seconds"] = self.audio_seconds
        return payload

    def expected_seconds(self) -> float:
        """How long the line should last: the clip, or an estimate from the text."""
        if self.audio_seconds:
            return self.audio_seconds
        return max(1.5, len(self.text) / CHARS_PER_SECOND)
