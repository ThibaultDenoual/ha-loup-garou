"""Shared dev configuration for run_devserver.py and run_console.py."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

from custom_components.loup_garou.const import (
    DEFAULT_LANGUAGE,
    DEFAULT_TTS_ENGINE,
    DEFAULT_TTS_MODE,
    LANGUAGES,
    TTS_PHASE_DELAYS,
)


@dataclass
class DevConfig:
    language: str = DEFAULT_LANGUAGE
    tts_mode: str = DEFAULT_TTS_MODE
    tts_engine: str = DEFAULT_TTS_ENGINE
    speaker: str = ""
    lights: list[str] = field(default_factory=list)
    tts_delays: dict[str, float] = field(default_factory=lambda: dict(TTS_PHASE_DELAYS))
    port: int = 8099

    # Console-specific (non-interactive mode)
    players: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> DevConfig:
        delays = dict(TTS_PHASE_DELAYS)
        if args.tts_delays:
            if isinstance(args.tts_delays, str):
                try:
                    delays.update(json.loads(args.tts_delays))
                except json.JSONDecodeError:
                    pass
            elif isinstance(args.tts_delays, dict):
                delays.update(args.tts_delays)

        lights = []
        if args.lights:
            if isinstance(args.lights, str):
                lights = [l.strip() for l in args.lights.split(",") if l.strip()]
            elif isinstance(args.lights, list):
                lights = args.lights

        players = []
        if getattr(args, "players", None):
            if isinstance(args.players, str):
                players = [p.strip() for p in args.players.split(",") if p.strip()]
            elif isinstance(args.players, list):
                players = args.players

        roles = []
        if getattr(args, "roles", None):
            if isinstance(args.roles, str):
                roles = [r.strip() for r in args.roles.split(",") if r.strip()]
            elif isinstance(args.roles, list):
                roles = args.roles

        return cls(
            language=args.language,
            tts_mode=args.tts_mode,
            tts_engine=args.tts_engine,
            speaker=args.speaker or "",
            lights=lights,
            tts_delays=delays,
            port=args.port,
            players=players,
            roles=roles,
        )

    @classmethod
    def from_yaml(cls, path: str | Path) -> DevConfig:
        if not HAS_YAML:
            raise RuntimeError("PyYAML not installed. Run: pip install pyyaml")
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        delays = dict(TTS_PHASE_DELAYS)
        delays.update(data.get("tts_delays", {}))
        return cls(
            language=data.get("language", DEFAULT_LANGUAGE),
            tts_mode=data.get("tts_mode", DEFAULT_TTS_MODE),
            tts_engine=data.get("tts_engine", DEFAULT_TTS_ENGINE),
            speaker=data.get("speaker", ""),
            lights=data.get("lights", []),
            tts_delays=delays,
            port=data.get("port", 8099),
            players=data.get("players", []),
            roles=data.get("roles", []),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "tts_mode": self.tts_mode,
            "tts_engine": self.tts_engine,
            "speaker": self.speaker,
            "lights": self.lights,
            "tts_delays": self.tts_delays,
            "port": self.port,
            "players": self.players,
            "roles": self.roles,
        }


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config", type=str, help="Path to YAML config file (dev.yaml)"
    )
    parser.add_argument(
        "--language", choices=LANGUAGES, default=DEFAULT_LANGUAGE, help="Language (fr/en)"
    )
    parser.add_argument(
        "--tts-mode", choices=["browser", "mock"], default=DEFAULT_TTS_MODE, help="TTS backend"
    )
    parser.add_argument(
        "--tts-engine", default=DEFAULT_TTS_ENGINE, help="TTS engine entity (HA mode)"
    )
    parser.add_argument(
        "--speaker", default="", help="Speaker entity_id (HA mode)"
    )
    parser.add_argument(
        "--lights", default="", help="Comma-separated light entity_ids"
    )
    parser.add_argument(
        "--tts-delays", default="", help="JSON string of phase delays"
    )
    parser.add_argument(
        "--port", type=int, default=8099, help="HTTP port (devserver only)"
    )


def load_config(parser: argparse.ArgumentParser, args: argparse.Namespace) -> DevConfig:
    if args.config:
        return DevConfig.from_yaml(args.config)
    return DevConfig.from_args(args)