"""Constants for the Loup Garou integration — enums, validation, light scenes. No strings."""
from __future__ import annotations

import json as _json
from enum import StrEnum
from pathlib import Path as _Path

from .public_roles import ALL as PUBLIC_ROLES


def _read_version() -> str:
    try:
        return _json.loads(
            (_Path(__file__).parent / "manifest.json").read_text()
        ).get("version", "dev")
    except Exception:
        return "dev"


VERSION: str = _read_version()


def _read_build() -> str:
    """A fingerprint of the game's web files: it changes with any update.

    Pages compare it on every reconnect and reload when it changed, so a page
    the Companion App kept open never keeps running an older game.
    """
    import hashlib

    digest = hashlib.sha1(VERSION.encode())
    root = _Path(__file__).parent / "www" / "game"
    try:
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            digest.update(str(path.relative_to(root)).encode())
            digest.update(path.read_bytes())
    except OSError:
        return VERSION
    return digest.hexdigest()[:12]


BUILD: str = _read_build()

DOMAIN = "loup_garou"

# ── Configuration keys ────────────────────────────────────────────────────────
CONF_SPEAKER = "speaker_entity"
CONF_LIGHTS = "light_entities"
CONF_LANGUAGE = "language"
CONF_TTS_ENGINE = "tts_engine"
CONF_AUDIO_SOURCE = "audio_source"   # "tts" | "static"
CONF_AUDIO_OUTPUT = "audio_output"   # "browser" | "ha"

LANGUAGES = ["fr", "en"]
DEFAULT_LANGUAGE = "fr"
DEFAULT_TTS_ENGINE = "tts.home_assistant_cloud"
DEFAULT_AUDIO_SOURCE = "tts"      # synthesised speech
DEFAULT_AUDIO_OUTPUT = "browser"  # phone/browser speaker

# Estimated post-TTS sleep durations (seconds) used in HA TTS mode so the
# engine waits for narration to finish before advancing to the next event.
# In browser mode these are ignored — the engine waits for the real tts_done signal.
TTS_PHASE_DELAYS: dict[str, float] = {
    "night_start":         9.0,
    "role_wake":           7.0,
    "role_sleep":          3.0,
    "day_no_death":        3.0,
    "day_prelude":         2.5,
    "day_with_death":      3.5,
    "day_debate":          8.5,
    "vote_start":          3.5,
    "vote_result":         3.5,
    "elimination_live":    3.0,
    "game_over":           5.0,
    "game_over_reveal":    4.0,
    "intro":               9.0,
}

# Length in seconds of each recorded clip, rounded up to 0.1 s.
# tests/unit/test_static_audio.py checks it against the files in www/audio/.
STATIC_AUDIO_SECONDS: dict[str, dict[str, float]] = {
    "en": {
        "day_debate":              8.4,
        "day_no_death":            4.3,
        "day_prelude_death":       3.0,
        "game_over_lovers":        3.4,
        "game_over_reveal":        3.7,
        "game_over_village":       3.9,
        "game_over_wolves":        4.8,
        "intro":                   11.8,
        "night_start":             9.1,
        "part_grief":              4.3,
        "part_hunter":             4.0,
        "part_scapegoat":          5.3,
        "part_victim":             1.8,
        "part_vote":               3.3,
        "part_was":                1.9,
        "public_baker":            1.9,
        "public_baker_apprentice": 1.8,
        "public_blacksmith":       1.9,
        "public_blacksmith_apprentice":2.1,
        "public_fisher":           1.9,
        "public_fisher_apprentice":1.8,
        "public_herbalist":        1.9,
        "public_herbalist_apprentice":1.9,
        "public_innkeeper":        1.9,
        "public_innkeeper_apprentice":2.0,
        "public_miller":           1.9,
        "public_miller_apprentice":1.9,
        "public_potter":           1.9,
        "public_potter_apprentice":1.8,
        "public_shepherd":         1.9,
        "public_shepherd_apprentice":1.9,
        "public_weaver":           1.9,
        "public_weaver_apprentice":1.9,
        "public_woodcutter":       1.9,
        "public_woodcutter_apprentice":1.9,
        "role_alpha_wolf_sleep":   2.5,
        "role_alpha_wolf_wake":    7.0,
        "role_cupid_sleep":        2.0,
        "role_cupid_wake":         7.2,
        "role_hunter_wake":        7.2,
        "role_seer_sleep":         2.2,
        "role_seer_wake":          6.6,
        "role_werewolf_sleep":     4.0,
        "role_werewolf_wake":      6.3,
        "role_witch_sleep":        1.9,
        "role_witch_wake":         6.2,
        "spoken_alpha_wolf":       1.9,
        "spoken_cupid":            1.9,
        "spoken_elder":            1.9,
        "spoken_hunter":           1.1,
        "spoken_little_girl":      1.2,
        "spoken_minion":           1.9,
        "spoken_scapegoat":        1.9,
        "spoken_seer":             1.9,
        "spoken_sheriff":          1.9,
        "spoken_villager":         1.9,
        "spoken_werewolf":         1.9,
        "spoken_witch":            1.1,
        "vote_start":              4.2,
        "vote_tie":                4.2,
    },
    "fr": {
        "day_debate":              9.0,
        "day_no_death":            5.9,
        "day_prelude_death":       4.0,
        "game_over_lovers":        4.2,
        "game_over_reveal":        4.1,
        "game_over_village":       4.4,
        "game_over_wolves":        4.7,
        "intro":                   12.0,
        "night_start":             9.4,
        "part_grief":              4.1,
        "part_hunter":             3.6,
        "part_scapegoat":          5.0,
        "part_victim":             1.9,
        "part_vote":               3.5,
        "part_was":                1.9,
        "public_baker":            1.9,
        "public_baker_apprentice": 2.2,
        "public_blacksmith":       1.9,
        "public_blacksmith_apprentice":2.2,
        "public_fisher":           1.9,
        "public_fisher_apprentice":2.1,
        "public_herbalist":        1.9,
        "public_herbalist_apprentice":2.4,
        "public_innkeeper":        1.9,
        "public_innkeeper_apprentice":2.4,
        "public_miller":           1.9,
        "public_miller_apprentice":2.3,
        "public_potter":           1.9,
        "public_potter_apprentice":2.3,
        "public_shepherd":         1.9,
        "public_shepherd_apprentice":2.3,
        "public_weaver":           1.9,
        "public_weaver_apprentice":2.3,
        "public_woodcutter":       1.5,
        "public_woodcutter_apprentice":2.0,
        "role_alpha_wolf_sleep":   2.7,
        "role_alpha_wolf_wake":    6.9,
        "role_cupid_sleep":        2.4,
        "role_cupid_wake":         7.3,
        "role_hunter_wake":        8.4,
        "role_seer_sleep":         2.6,
        "role_seer_wake":          6.6,
        "role_werewolf_sleep":     3.5,
        "role_werewolf_wake":      6.8,
        "role_witch_sleep":        2.8,
        "role_witch_wake":         8.7,
        "spoken_alpha_wolf":       1.9,
        "spoken_cupid":            1.9,
        "spoken_elder":            1.9,
        "spoken_hunter":           1.9,
        "spoken_little_girl":      1.9,
        "spoken_minion":           1.9,
        "spoken_scapegoat":        1.9,
        "spoken_seer":             1.9,
        "spoken_sheriff":          1.9,
        "spoken_villager":         1.9,
        "spoken_werewolf":         1.9,
        "spoken_witch":            1.9,
        "vote_start":              4.5,
        "vote_tie":                4.5,
    },
}

# Extra wait after a clip on an HA speaker, which takes a moment to start.
STATIC_AUDIO_MARGIN = 1.0

# Narration on a Home Assistant speaker waits for the speaker itself: it starts
# playing, then leaves the "playing" state. TTS_PHASE_DELAYS (and the clip
# lengths) only apply to speakers that don't report their state.
SPEAKER_START_TIMEOUT = 10.0  # TTS generation can take several seconds
SPEAKER_MAX_LINE = 60.0       # a speaker stuck in "playing" can't hold the game
SPEAKER_GAP = 0.4             # breath between two lines

# How long a live death (the Hunter's shot, a lover's grief, the scapegoat)
# holds the death scene before the game moves on, game over included.
DEATH_BEAT = 3.0


# ── Game events (used by engine.on() / engine._emit()) ───────────────────────
class GameEvent(StrEnum):
    GAME_STARTED       = "game_started"
    GAME_OVER          = "game_over"
    PHASE_CHANGED      = "phase_changed"
    PLAYER_ELIMINATED  = "player_eliminated"
    HUNTER_SHOT        = "hunter_shot"
    NIGHT_ROLE_WAKE    = "night_role_wake"
    NIGHT_ROLE_SLEEP   = "night_role_sleep"
    NIGHT_RESOLVED     = "night_resolved"
    DAY_STARTED        = "day_started"
    VOTE_STARTED       = "vote_started"
    VOTE_RESOLVED      = "vote_resolved"
    STATE_CHANGED      = "state_changed"
    PROMPT_OPENED      = "prompt_opened"


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
        "brightness":             20,
        "transition":             3,
    },
    "cupid": {
        "rgb_color": (255, 107, 157),
        "brightness":             64,
        "transition":             1,
    },
    "seer_wake": {
        "rgb_color": (106, 13, 173),
        "brightness":             51,
        "transition":             1,
    },
    "wolf_wake": {
        "rgb_color": (139, 0, 0),
        "brightness":             51,
        "transition":             1,
    },
    "witch_wake": {
        "rgb_color": (26, 122, 26),
        "brightness":             51,
        "transition":             1,
    },
    "day": {
        "rgb_color": (255, 245, 224),
        "brightness":             191,
        "transition":             4,
    },
    "death": {
        "rgb_color": (139, 0, 0),
        "brightness":             38,
        "transition":             1,
        "flash": True,
    },
    "wolves_win": {
        "rgb_color": (200, 0, 0),
        "brightness":             153,
        "transition":             0,
        "strobe": True,
    },
    "village_win": {
        "rgb_color": (255, 220, 100),
        "brightness":             255,
        "transition":             1,
    },
    "lovers_win": {
        "rgb_color": (255, 107, 157),
        "brightness":             128,
        "transition":             1,
    },
}

# Locale keys whose text never changes at runtime — can be served as pre-recorded MP3s.
# Maps locale key → audio filename stem (no lang prefix, no extension).
# URL template: /loup_garou/audio/{lang}/{stem}.mp3
STATIC_AUDIO_MAP: dict[str, str] = {
    "phase.night.start":           "night_start",
    "phase.day.start_no_death":    "day_no_death",
    "phase.day.prelude_death":     "day_prelude_death",
    "phase.day.debate":            "day_debate",
    "phase.vote.start":            "vote_start",
    "phase.vote.tie":              "vote_tie",
    "phase.game_over.wolves_win":  "game_over_wolves",
    "phase.game_over.village_win": "game_over_village",
    "phase.game_over.lovers_win":  "game_over_lovers",
    "phase.game_over.reveal":      "game_over_reveal",
    "phase.role_reveal.start":     "intro",
    "role.werewolf.wake":          "role_werewolf_wake",
    "role.werewolf.sleep":         "role_werewolf_sleep",
    "role.seer.wake":              "role_seer_wake",
    "role.seer.sleep":             "role_seer_sleep",
    "role.witch.wake":             "role_witch_wake",
    "role.witch.sleep":            "role_witch_sleep",
    "role.cupid.wake":             "role_cupid_wake",
    "role.cupid.sleep":            "role_cupid_sleep",
    "role.alpha_wolf.wake":        "role_alpha_wolf_wake",
    "role.alpha_wolf.sleep":       "role_alpha_wolf_sleep",
    "role.hunter.wake":            "role_hunter_wake",
}

# Lines that name a player are joined from these parts at /loup_garou/voice
# (see voice.py): a lead-in, the public role, "They were…", the secret role.
NARRATION_PARTS: tuple[str, ...] = (
    "part.victim", "part.vote", "part.hunter", "part.grief", "part.scapegoat", "part.was",
)
SPOKEN_ROLES: tuple[str, ...] = (
    "villager", "werewolf", "seer", "hunter", "elder", "scapegoat",
    "little_girl", "witch", "cupid", "alpha_wolf", "minion", "sheriff",
)
STATIC_AUDIO_MAP.update({key: key.replace(".", "_") for key in NARRATION_PARTS})
STATIC_AUDIO_MAP.update({f"public.{p}.spoken": f"public_{p}" for p in PUBLIC_ROLES})
STATIC_AUDIO_MAP.update({f"role.{r}.spoken": f"spoken_{r}" for r in SPOKEN_ROLES})

# Role id → light scene key for that role's night turn
ROLE_SCENE: dict[str, str] = {
    "cupid":      "cupid",
    "seer":       "seer_wake",
    "werewolf":   "wolf_wake",
    "alpha_wolf": "wolf_wake",
    "witch":      "witch_wake",
    "hunter":     "death",
}
