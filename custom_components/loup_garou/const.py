"""Constants for the Loup Garou integration."""
from __future__ import annotations

DOMAIN = "loup_garou"
VERSION = "0.1.0"

# ─── Config entry keys ────────────────────────────────────────────────────────
CONF_SPEAKER = "speaker_entity"
CONF_LIGHTS = "light_entities"
CONF_LANGUAGE = "language"

# ─── Roles ────────────────────────────────────────────────────────────────────
ROLE_VILLAGER = "villager"
ROLE_WEREWOLF = "werewolf"
ROLE_SEER = "seer"

# Phase 1 roles only; Phase 2 will add witch, hunter, cupid, little_girl
ROLES_PHASE1 = [ROLE_VILLAGER, ROLE_WEREWOLF, ROLE_SEER]

ROLE_TEAMS = {
    ROLE_VILLAGER: "village",
    ROLE_WEREWOLF: "wolves",
    ROLE_SEER: "village",
}

# Night wake order (Phase 1 subset).
# Roles not in this list have no night action.
NIGHT_WAKE_ORDER = [ROLE_SEER, ROLE_WEREWOLF]

# ─── Game phases ──────────────────────────────────────────────────────────────
PHASE_SETUP = "setup"
PHASE_ROLE_REVEAL = "role_reveal"
PHASE_NIGHT = "night"
PHASE_DAY = "day"
PHASE_VOTE = "vote"
PHASE_GAME_OVER = "game_over"

# ─── Night action types ───────────────────────────────────────────────────────
ACTION_WOLF_KILL = "wolf_kill"
ACTION_SEER_INVESTIGATE = "seer_investigate"

# ─── Elimination causes ───────────────────────────────────────────────────────
CAUSE_WOLF = "wolf"
CAUSE_VOTE = "vote"

# ─── Win conditions ───────────────────────────────────────────────────────────
WIN_WOLVES = "wolves"
WIN_VILLAGERS = "villagers"

# ─── HA events ────────────────────────────────────────────────────────────────
EVENT_PHASE_CHANGED = f"{DOMAIN}_phase_changed"
EVENT_PLAYER_ELIMINATED = f"{DOMAIN}_player_eliminated"
EVENT_GAME_OVER = f"{DOMAIN}_game_over"
EVENT_STATE_UPDATED = f"{DOMAIN}_state_updated"

# ─── WebSocket commands ───────────────────────────────────────────────────────
WS_START_GAME = f"{DOMAIN}/start_game"
WS_CONFIRM_ROLE_SEEN = f"{DOMAIN}/confirm_role_seen"
WS_NIGHT_ACTION = f"{DOMAIN}/night_action"
WS_SUBMIT_VOTE = f"{DOMAIN}/submit_vote"
WS_NEXT_PHASE = f"{DOMAIN}/next_phase"
WS_GET_STATE = f"{DOMAIN}/get_state"
WS_SUBSCRIBE = f"{DOMAIN}/subscribe"

# ─── Light scene definitions ──────────────────────────────────────────────────
# Each scene: {rgb_color, brightness_pct, transition_seconds}
LIGHT_SCENES: dict[str, dict] = {
    "night": {
        "rgb_color": (10, 22, 40),       # deep blue #0a1628
        "brightness_pct": 8,
        "transition": 3,
    },
    "wolf_wake": {
        "rgb_color": (139, 0, 0),         # blood red #8b0000
        "brightness_pct": 20,
        "transition": 1,
    },
    "seer_wake": {
        "rgb_color": (106, 13, 173),      # violet #6a0dad — used in Phase 1 even though subtle
        "brightness_pct": 15,
        "transition": 1,
    },
    "day": {
        "rgb_color": (255, 245, 224),     # warm white #fff5e0
        "brightness_pct": 75,
        "transition": 4,
    },
    "death": {
        "rgb_color": (139, 0, 0),
        "brightness_pct": 15,
        "transition": 0,                  # instant flash
    },
    "wolves_win": {
        "rgb_color": (180, 0, 0),
        "brightness_pct": 60,
        "transition": 0,
    },
    "villagers_win": {
        "rgb_color": (255, 220, 120),
        "brightness_pct": 100,
        "transition": 1,
    },
}

# Scene to use per phase transition
PHASE_LIGHT_SCENE: dict[str, str] = {
    PHASE_NIGHT: "night",
    PHASE_DAY: "day",
    PHASE_VOTE: "day",          # keep day lighting during vote
    PHASE_GAME_OVER: "day",     # overridden by win condition scene
}

# Scene to use per role wake during night
ROLE_WAKE_SCENE: dict[str, str] = {
    ROLE_SEER: "seer_wake",
    ROLE_WEREWOLF: "wolf_wake",
}

# ─── TTS narration strings ────────────────────────────────────────────────────
# Keyed by language, then by event key.
# Placeholders: {name}, {role}, {count}
TTS_STRINGS: dict[str, dict[str, str]] = {
    "fr": {
        "roles_distributed": (
            "Les rôles ont été distribués. "
            "Le village se prépare pour sa première nuit."
        ),
        "night_start": (
            "Le village s'endort… Tout le monde ferme les yeux."
        ),
        "seer_wake": (
            "Voyante, ouvre les yeux. Désigne un joueur à investiguer."
        ),
        "seer_sleep": (
            "Voyante, ferme les yeux."
        ),
        "wolves_wake": (
            "Loups-garous, ouvrez les yeux. "
            "Désignez silencieusement votre victime."
        ),
        "wolves_sleep": (
            "Loups-garous, fermez les yeux."
        ),
        "day_death": (
            "Le village se réveille. {name} a été retrouvé mort. "
            "Il était {role}."
        ),
        "day_no_death": (
            "Le village se réveille. "
            "Miraculeusement, personne n'est mort cette nuit."
        ),
        "vote_start": (
            "Le village doit voter pour éliminer un suspect."
        ),
        "player_eliminated": (
            "{name} est éliminé. Il était {role}."
        ),
        "wolves_win": (
            "Les loups-garous ont gagné ! Le village a succombé."
        ),
        "villagers_win": (
            "Le village a gagné ! Tous les loups-garous sont morts."
        ),
        "role_villager": "Villageois",
        "role_werewolf": "Loup-Garou",
        "role_seer": "Voyante",
    },
    "en": {
        "roles_distributed": (
            "The roles have been distributed. "
            "The village prepares for its first night."
        ),
        "night_start": (
            "The village falls asleep… Eyes closed, everyone."
        ),
        "seer_wake": (
            "Seer, open your eyes. Choose a player to investigate."
        ),
        "seer_sleep": (
            "Seer, close your eyes."
        ),
        "wolves_wake": (
            "Werewolves, open your eyes. "
            "Choose your victim silently."
        ),
        "wolves_sleep": (
            "Werewolves, close your eyes."
        ),
        "day_death": (
            "The village wakes up. {name} was found dead. "
            "They were a {role}."
        ),
        "day_no_death": (
            "The village wakes up. "
            "Miraculously, no one died tonight."
        ),
        "vote_start": (
            "The village must vote to eliminate a suspect."
        ),
        "player_eliminated": (
            "{name} is eliminated. They were a {role}."
        ),
        "wolves_win": (
            "The werewolves win! The village has fallen."
        ),
        "villagers_win": (
            "The village wins! All werewolves are dead."
        ),
        "role_villager": "Villager",
        "role_werewolf": "Werewolf",
        "role_seer": "Seer",
    },
}

ROLE_DISPLAY_NAMES: dict[str, dict[str, str]] = {
    "fr": {
        ROLE_VILLAGER: "Villageois",
        ROLE_WEREWOLF: "Loup-Garou",
        ROLE_SEER: "Voyante",
    },
    "en": {
        ROLE_VILLAGER: "Villager",
        ROLE_WEREWOLF: "Werewolf",
        ROLE_SEER: "Seer",
    },
}

# ─── Default role distribution suggestions ────────────────────────────────────
# {player_count: {role: count}}
DEFAULT_ROLE_DISTRIBUTION: dict[int, dict[str, int]] = {
    4: {ROLE_VILLAGER: 2, ROLE_WEREWOLF: 1, ROLE_SEER: 1},
    5: {ROLE_VILLAGER: 3, ROLE_WEREWOLF: 1, ROLE_SEER: 1},
    6: {ROLE_VILLAGER: 4, ROLE_WEREWOLF: 1, ROLE_SEER: 1},
    7: {ROLE_VILLAGER: 4, ROLE_WEREWOLF: 2, ROLE_SEER: 1},
    8: {ROLE_VILLAGER: 5, ROLE_WEREWOLF: 2, ROLE_SEER: 1},
    9: {ROLE_VILLAGER: 6, ROLE_WEREWOLF: 2, ROLE_SEER: 1},
    10: {ROLE_VILLAGER: 6, ROLE_WEREWOLF: 3, ROLE_SEER: 1},
}