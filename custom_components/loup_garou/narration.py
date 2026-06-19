from __future__ import annotations

from dataclasses import dataclass


@dataclass
class NarrationMessage:
    text: str
    lang: str
    audio_url: str | None = None
    delay_key: str = "role_wake"

    def to_payload(self) -> dict:
        payload = {"text": self.text, "lang": self.lang}
        if self.audio_url:
            payload["audio_url"] = self.audio_url
        return payload
