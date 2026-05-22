"""Constants for the Loup Garou integration."""
from __future__ import annotations

from enum import StrEnum

DOMAIN = "loup_garou"
STORAGE_KEY = f"{DOMAIN}_game_state"
STORAGE_VERSION = 1

# ──────────────────────────────────────────────
# Configuration keys
# ──────────────────────────────────────────────
CONF_SPEAKER = "speaker_entity"
CONF_LIGHTS = "light_entities"
CONF_LANGUAGE = "language"

LANGUAGES = ["fr", "en"]
DEFAULT_LANGUAGE = "fr"


# ──────────────────────────────────────────────
# Roles
# ──────────────────────────────────────────────
class Role(StrEnum):
    VILLAGER = "villager"
    WEREWOLF = "werewolf"
    SEER = "seer"


# Team membership — used for win condition checks
WOLF_TEAM: set[Role] = {Role.WEREWOLF}
VILLAGE_TEAM: set[Role] = {Role.VILLAGER, Role.SEER}

# Night wake order (roles that act at night, in order)
# Only roles present in the current game are actually called
NIGHT_WAKE_ORDER: list[Role] = [
    Role.SEER,
    Role.WEREWOLF,
]

# Role display metadata (used by frontend)
ROLE_META: dict[str, dict] = {
    Role.VILLAGER: {
        "icon": "🏘️",
        "team": "village",
        "has_night_action": False,
        "description_fr": "Vous êtes un simple villageois. Débattez le jour et votez wisément.",
        "description_en": "You are a simple villager. Debate by day and vote wisely.",
    },
    Role.WEREWOLF: {
        "icon": "🐺",
        "team": "wolves",
        "has_night_action": True,
        "description_fr": "Vous êtes un loup-garou. La nuit, choisissez votre victime en silence.",
        "description_en": "You are a werewolf. At night, silently choose your victim.",
    },
    Role.SEER: {
        "icon": "🔮",
        "team": "village",
        "has_night_action": True,
        "description_fr": "Vous êtes la voyante. Chaque nuit, découvrez la vraie nature d'un joueur.",
        "description_en": "You are the seer. Each night, discover the true nature of one player.",
    },
}


# ──────────────────────────────────────────────
# Game phases
# ──────────────────────────────────────────────
class Phase(StrEnum):
    SETUP = "setup"
    ROLE_REVEAL = "role_reveal"
    NIGHT = "night"
    DAY = "day"
    VOTE = "vote"
    GAME_OVER = "game_over"


# ──────────────────────────────────────────────
# Night action types
# ──────────────────────────────────────────────
class NightActionType(StrEnum):
    WOLF_KILL = "wolf_kill"        # payload: {"target_id": str}
    SEER_INVESTIGATE = "seer_investigate"  # payload: {"target_id": str}


# ──────────────────────────────────────────────
# Elimination causes
# ──────────────────────────────────────────────
class EliminationCause(StrEnum):
    WOLF_KILL = "wolf_kill"
    VILLAGE_VOTE = "village_vote"


# ──────────────────────────────────────────────
# Win conditions
# ──────────────────────────────────────────────
class WinCondition(StrEnum):
    WOLVES = "wolves"
    VILLAGERS = "villagers"


# ──────────────────────────────────────────────
# HA WebSocket event names
# ──────────────────────────────────────────────
EVENT_GAME_STATE_CHANGED = f"{DOMAIN}_state_changed"
EVENT_GAME_OVER = f"{DOMAIN}_game_over"


# ──────────────────────────────────────────────
# Light scenes
# ──────────────────────────────────────────────
# Each scene: rgb tuple (0-255), brightness 0-255, transition seconds
LIGHT_SCENES: dict[str, dict] = {
    "night": {
        "rgb_color": (10, 22, 40),    # deep blue #0a1628
        "brightness": 20,              # ~8%
        "transition": 3,
    },
    "wolf_wake": {
        "rgb_color": (139, 0, 0),      # blood red #8b0000
        "brightness": 51,              # ~20%
        "transition": 1,
    },
    "seer_wake": {
        "rgb_color": (106, 13, 173),   # violet #6a0dad
        "brightness": 51,
        "transition": 1,
    },
    "day": {
        "rgb_color": (255, 245, 224),  # warm white #fff5e0
        "brightness": 191,             # ~75%
        "transition": 4,
    },
    "death": {
        "rgb_color": (139, 0, 0),
        "brightness": 38,              # ~15%
        "transition": 1,
        "flash": True,                 # frontend/controller does 1 flash then holds
    },
    "wolves_win": {
        "rgb_color": (200, 0, 0),
        "brightness": 153,             # ~60%
        "transition": 0,
        "strobe": True,
    },
    "village_win": {
        "rgb_color": (255, 220, 100),
        "brightness": 255,
        "transition": 1,
    },
}

# Map each phase/event to a scene key
PHASE_SCENE_MAP: dict[str, str] = {
    Phase.NIGHT: "night",
    Phase.DAY: "day",
    Phase.VOTE: "day",
    "wolf_wake": "wolf_wake",
    "seer_wake": "seer_wake",
    "death": "death",
    WinCondition.WOLVES: "wolves_win",
    WinCondition.VILLAGERS: "village_win",
}


# ──────────────────────────────────────────────
# TTS announcement strings
# ──────────────────────────────────────────────
TTS: dict[str, dict[str, str]] = {
    # ── Setup / Role reveal ──────────────────
    "roles_distributed": {
        "fr": "Les rôles ont été distribués. Le village se prépare pour sa première nuit.",
        "en": "The roles have been distributed. The village prepares for its first night.",
    },
    # ── Night start ──────────────────────────
    "night_start": {
        "fr": "Le village s'endort… Fermez les yeux, tout le monde.",
        "en": "The village falls asleep… Eyes closed, everyone.",
    },
    # ── Seer ─────────────────────────────────
    "seer_wake": {
        "fr": "Voyante, ouvre les yeux. Choisis un joueur à observer.",
        "en": "Seer, open your eyes. Choose a player to investigate.",
    },
    "seer_sleep": {
        "fr": "Voyante, ferme les yeux.",
        "en": "Seer, close your eyes.",
    },
    # ── Wolves ───────────────────────────────
    "wolf_wake": {
        "fr": "Loups-garous, ouvrez les yeux. Choisissez votre victime en silence.",
        "en": "Werewolves, open your eyes. Choose your victim silently.",
    },
    "wolf_sleep": {
        "fr": "Loups-garous, fermez les yeux.",
        "en": "Werewolves, close your eyes.",
    },
    # ── Day ──────────────────────────────────
    "day_start_death": {
        "fr": "Le village se réveille. {name} a été retrouvé mort. C'était {article} {role}.",
        "en": "The village wakes up. {name} was found dead. They were a {role}.",
    },
    "day_start_no_death": {
        "fr": "Le village se réveille. Miraculeusement, personne n'est mort cette nuit.",
        "en": "The village wakes up. Miraculously, no one died last night.",
    },
    # ── Vote ─────────────────────────────────
    "vote_start": {
        "fr": "Le village doit voter pour éliminer un suspect.",
        "en": "The village must vote to eliminate a suspect.",
    },
    "vote_tie": {
        "fr": "Égalité ! Le village ne parvient pas à se décider.",
        "en": "It's a tie! The village cannot reach a decision.",
    },
    # ── Elimination ──────────────────────────
    "elimination": {
        "fr": "{name} est éliminé. C'était {article} {role}.",
        "en": "{name} is eliminated. They were a {role}.",
    },
    # ── Win ──────────────────────────────────
    "wolves_win": {
        "fr": "Les loups-garous ont gagné ! Le village est tombé.",
        "en": "The werewolves win! The village has fallen.",
    },
    "villagers_win": {
        "fr": "Le village a gagné ! Tous les loups-garous sont morts.",
        "en": "The village wins! All werewolves are dead.",
    },
}

# French articles for roles (used in TTS formatting)
ROLE_ARTICLES_FR: dict[str, str] = {
    Role.VILLAGER: "un",
    Role.WEREWOLF: "un",
    Role.SEER: "la",
}

ROLE_NAMES_FR: dict[str, str] = {
    Role.VILLAGER: "Villageois",
    Role.WEREWOLF: "Loup-Garou",
    Role.SEER: "Voyante",
}

ROLE_NAMES_EN: dict[str, str] = {
    Role.VILLAGER: "Villager",
    Role.WEREWOLF: "Werewolf",
    Role.SEER: "Seer",
}