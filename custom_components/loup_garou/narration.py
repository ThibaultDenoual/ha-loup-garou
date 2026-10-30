from __future__ import annotations

from dataclasses import dataclass


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
        return payload
