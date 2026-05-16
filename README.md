# Loup Garou for Home Assistant

![Version](https://img.shields.io/badge/version-0.1.0-blue)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

A Home Assistant integration that turns your smart home into a game master for **Loup Garou** (the Werewolf party game). Orchestrate complete games with automatic lighting, TTS narration, and a mobile-friendly player interface — no cloud, no apps, just your home and a phone.

---

## Overview

One phone (or tablet) runs the entire game interface. Players pass it around for private role reveals, silent night actions, and voting. Meanwhile, your smart home handles the atmosphere:

- **Lights** shift color and intensity for every phase — deep blue at night, blood red when wolves wake, warm white at dawn, a death flash on every elimination
- **Speaker** narrates all public events via TTS — who died, who was eliminated, which team won — so the whole room follows the story without looking at the screen
- **Phone** handles only private, silent actions — night actions produce zero audio or light feedback

---

## Requirements

| Requirement | Details |
|-------------|---------|
| Home Assistant | `2024.1.0` or newer |
| Speaker | Any `media_player` entity with TTS support (Nabu Casa, Cast, Sonos, etc.) |
| Smart lights | One or more `light` entities with RGB + brightness (Hue, WLED, etc.) |
| Device | Any browser-enabled phone/tablet on the local network |
| Players | 4 to 18 people, physically present |

---

## Installation

### Via HACS (recommended)

1. Open **HACS** → **Integrations** → three-dot menu → **Add custom repository**
2. Add `https://github.com/ThibaultDenoual/ha-loup-garou` with category **Integration**
3. Search for **Loup Garou** and install
4. Restart Home Assistant

### Manual

1. Clone or download this repository
2. Copy `custom_components/loup_garou/` to your HA `config/custom_components/` directory
3. Restart Home Assistant

---

## Configuration

After restart, go to **Settings → Devices & Services → Add Integration** and search for **Loup Garou**.

| Field | Description |
|-------|-------------|
| **Speaker** | The `media_player` entity for TTS narration (e.g., `media_player.living_room`) |
| **Lights** | Comma-separated list of `light` entities to control |
| **Language** | French (fr) or English (en) — controls both TTS and UI |

Once configured, a **Loup Garou** entry appears in the HA sidebar. Open it on your game device to start.

---

## How to Play

### 1. Setup
The host enters player names (minimum 4). The interface suggests a role distribution based on player count, customizable within valid bounds.

### 2. Role Reveal
The phone prompts passing to each player in random order. Each player taps **Reveal my role**, reads it privately, then confirms. Screen blanks immediately after.

### 3. Night Phase
The speaker narrates each role's turn. Lights shift to the role's color. The phone is passed to the active player for their silent action:
- **Seer** → investigates one player (result shown only on screen)
- **Werewolves** → silently choose their victim

### 4. Day Phase
The speaker announces any deaths. Lights shift to warm white. Players debate freely.

### 5. Vote Phase
Players silently vote by passing the phone around. The tally is revealed, and the host confirms elimination.

### 6. Repeat
Game loops until a win condition:

| Winner | Condition |
|--------|-----------|
| Werewolves | Alive wolves ≥ alive village players |
| Village | All werewolves eliminated |

---

## Supported Roles (12 total)

| Role | Team | Night Action |
|------|------|--------------|
| Villager | Village | None |
| Werewolf | Wolves | Choose victim |
| Seer | Village | Investigate player |
| Doctor | Village | Protect player |
| Bodyguard | Village | Guard player |
| Hunter | Village | Final shot on death |
| Witch | Village | Heal or poison (one-time each) |
| Cupid | Village | Link two lovers |
| Alpha Wolf | Wolves | Convert a villager |
| Minion | Wolves | Knows wolves, can't kill |
| Serial Killer | Solo | Kill each night |
| Jester | Solo | Wins if voted out |

---

## Light Scenes

Defined in `const.py` — fully configurable.

| Scene | Trigger | Color | Brightness | Transition |
|-------|---------|-------|-------------|------------|
| `night` | Night start | Deep blue `#0a1628` | 8% | 3s |
| `seer_wake` | Seer's turn | Violet `#6a0dad` | 20% | 1s |
| `wolf_wake` | Wolves' turn | Blood red `#8b0000` | 20% | 1s |
| `day` | Day/Vote | Warm white `#fff5e0` | 75% | 4s |
| `death` | Any elimination | Red flash → hold | 15% | 0.5s |
| `wolves_win` | Wolf victory | Red strobe | 60% | — |
| `village_win` | Village victory | Gold/white | 100% | 1s |

---

## Architecture

```
custom_components/loup_garou/
├── __init__.py              # Bootstrap: wires all components, registers sidebar panel
├── manifest.json           # HACS/HA integration manifest
├── config_flow.py          # HA UI config flow (speaker, lights, language)
├── const.py                # All constants: roles, phases, TTS strings, light scenes
│
├── core_game/              # Pure game logic (no HA imports)
│   ├── engine.py           # State machine: setup → night → day → vote → ...
│   ├── game_state.py       # Player, GameState dataclasses with serialization
│   ├── roles.py            # 12 role classes with night actions
│   ├── i18n.py             # Internationalization helper
│   └── io_adapters/        # IO abstraction layer
│       ├── ha_adapter.py   # Async adapter bridging core_game with HA
│       ├── ha_io.py        # HA-specific IO implementation
│       └── __init__.py
│
├── services/               # HA service integrations
│   ├── phase_manager.py   # Coordinates engine, lights, TTS per phase
│   ├── lights.py           # Light scene controller
│   └── tts.py              # Text-to-speech controller
│
├── server/                 # WebSocket server
│   ├── websocket.py        # Custom WebSocket handler
│   ├── handlers.py         # Message handlers (start_game, night_action, vote, etc.)
│   └── __init__.py
│
└── www/                    # Frontend (static files served by HA)
    ├── launcher.html       # Landing page
    ├── game.html           # Main game UI shell
    ├── css/                # Styling (variables, base, components, animations)
    └── js/
        ├── core.js         # Main orchestrator
        ├── i18n.js         # Translations
        ├── utils.js        # WebSocket, stars, helpers
        ├── components/     # Reusable UI components
        └── views/         # Game views (setup, reveal, night, day, vote, end)
```

### Data Flow

```
Browser (phone)
    │ WebSocket
    ▼
websocket.py → handlers.py → AsyncGameAdapter → GameEngine
                                               │
                                               ▼
                                    GameState (HA Store persistence)
                                               │
                                               ▼
                                    PhaseManager
                                       │      │
                                       ▼      ▼
                               speaker (TTS)  lights
                                       │
                                       ▼
                              Browser (state update via WS)
```

### State Machine

```
SETUP → ROLE_REVEAL → NIGHT_SEER → NIGHT_WOLVES → DAY → VOTE → (NIGHT | GAME_OVER)
```

---

## WebSocket API

All commands are prefixed with `loup_garou/`.

| Command | Payload | Description |
|---------|---------|-------------|
| `start_game` | `player_names: [str]`, `role_config: dict` | Start new game |
| `confirm_role_seen` | `player_id: str` | Player confirmed role view |
| `submit_night_action` | `action_type: str`, `target_id: str` | Night action (wolf_kill, seer_investigate) |
| `submit_vote` | `voter_id: str`, `target_id: str` | Day vote |
| `resolve_votes` | — | Tally and resolve votes |
| `eliminate_player` | `player_id: str`, `cause: str` | Eliminate a player |
| `begin_vote` | — | Transition DAY → VOTE |
| `next_phase` | — | Advance to next game phase |
| `get_state` | — | Return current public state |
| `reset` | — | Reset game to SETUP |

---

## Running Tests

### Prerequisites

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements_test.txt
```

### Run Tests

```bash
pytest                    # All tests
pytest tests/unit/        # Unit tests only
pytest tests/e2e/         # End-to-end tests
pytest --cov=custom_components/loup_garou --cov-report=term-missing
```

---

## Supported Languages

- **French** (fr) — default
- **English** (en)

To add a language, add entries to the `TTS` dict in `const.py` and update `config_flow.py`.

---

## License

MIT — see [LICENSE](LICENSE).

---

## Contributing

Contributions welcome. Please open an issue or pull request on GitHub.