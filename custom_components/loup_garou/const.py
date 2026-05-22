"""Constants for the Loup Garou integration — enums, validation, light scenes. No strings."""
from __future__ import annotations

from enum import StrEnum

DOMAIN = "loup_garou"

# ── Configuration keys ────────────────────────────────────────────────────────
CONF_SPEAKER = "speaker_entity"
CONF_LIGHTS = "light_entities"
CONF_LANGUAGE = "language"
CONF_TTS_ENGINE = "tts_engine"

LANGUAGES = ["fr", "en"]
DEFAULT_LANGUAGE = "fr"
DEFAULT_TTS_ENGINE = "tts.home_assistant_cloud"


# ── Game events (used by engine.on() / engine._emit()) ───────────────────────
class GameEvent(StrEnum):
    GAME_STARTED       = "game_started"
    GAME_OVER          = "game_over"
    PHASE_CHANGED      = "phase_changed"
    PLAYER_ELIMINATED  = "player_eliminated"
    NIGHT_ROLE_WAKE    = "night_role_wake"
    NIGHT_ROLE_SLEEP   = "night_role_sleep"
    NIGHT_RESOLVED     = "night_resolved"
    DAY_STARTED        = "day_started"
    VOTE_STARTED       = "vote_started"
    VOTE_RESOLVED      = "vote_resolved"


# ── Game phases ───────────────────────────────────────────────────────────────
class Phase(StrEnum):
    SETUP       = "setup"
    ROLE_REVEAL = "role_reveal"
    NIGHT       = "night"
    DAY         = "day"
    VOTE        = "vote"
    GAME_OVER   = "game_over"


# ── Win conditions ─────────────────────────────────────────────────────────────
class WinCondition(StrEnum):
    VILLAGE = "village"
    WOLVES  = "wolves"
    LOVERS  = "lovers"


# ── Light scenes — rgb (0-255), brightness 0-255, transition seconds ──────────
LIGHT_SCENES: dict[str, dict] = {
    "night": {
        "rgb_color": (10, 22, 40),
        "brightness": 20,
        "transition": 3,
    },
    "cupid": {
        "rgb_color": (255, 107, 157),
        "brightness": 64,
        "transition": 1,
    },
    "seer_wake": {
        "rgb_color": (106, 13, 173),
        "brightness": 51,
        "transition": 1,
    },
    "wolf_wake": {
        "rgb_color": (139, 0, 0),
        "brightness": 51,
        "transition": 1,
    },
    "witch_wake": {
        "rgb_color": (26, 122, 26),
        "brightness": 51,
        "transition": 1,
    },
    "day": {
        "rgb_color": (255, 245, 224),
        "brightness": 191,
        "transition": 4,
    },
    "death": {
        "rgb_color": (139, 0, 0),
        "brightness": 38,
        "transition": 1,
        "flash": True,
    },
    "wolves_win": {
        "rgb_color": (200, 0, 0),
        "brightness": 153,
        "transition": 0,
        "strobe": True,
    },
    "village_win": {
        "rgb_color": (255, 220, 100),
        "brightness": 255,
        "transition": 1,
    },
    "lovers_win": {
        "rgb_color": (255, 107, 157),
        "brightness": 128,
        "transition": 1,
    },
}

# Role id → light scene key for that role's night turn
ROLE_SCENE: dict[str, str] = {
    "cupid":      "cupid",
    "seer":       "seer_wake",
    "werewolf":   "wolf_wake",
    "alpha_wolf": "wolf_wake",
    "witch":      "witch_wake",
}
