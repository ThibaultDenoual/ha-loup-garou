# Loup Garou — Game Engine API

## Overview

The Loup Garou integration is a Home Assistant custom component that turns the smart home into a "game master" for playing Werewolf/Loup Garou. The game runs on a single device (phone/tablet) passed between players, with lighting and TTS providing atmospheric cues.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (index.html)                │
│                     Single-device game controller            │
└──────────────────────────────┬──────────────────────────────┘
                               │ WebSocket /api/loup_garou/ws
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 Custom WebSocket Handler                     │
│              (websocket.py — no HA auth)                    │
└──────────┬──────────────────────────┬──────────────────────┘
           │                          │
           ▼                          ▼
┌──────────────────────┐    ┌────────────────────────────────┐
│     GameEngine       │    │      PhaseManager              │
│   (game_engine.py)   │    │    (phase_manager.py)          │
│   - Game state       │    │    - Lights/TTS coordination   │
│   - Role assignment  │    └────────────────────────────────┘
│   - Phase transitions│
└──────────────────────┘
```

---

## Game Phases

| Phase | Value | Description |
|-------|-------|-------------|
| `setup` | `"setup"` | Pre-game, players being added |
| `role_reveal` | `"role_reveal"` | Roles are being distributed one-by-one |
| `night` | `"night"` | Night actions (wolves/seer) |
| `day` | `"day"` | Discussion and day actions |
| `vote` | `"vote"` | Village voting in progress |
| `game_over` | `"game_over"` | Game ended, winner determined |

### Phase Transitions

```
setup → role_reveal → night ↔ day ↔ vote → (night or game_over)
                                              ↓
                                          game_over
```

---

## Roles

| Role | Value | Team | Has Night Action |
|------|-------|------|------------------|
| `villager` | `"villager"` | Village | No |
| `werewolf` | `"werewolf"` | Wolves | Yes (kill) |
| `seer` | `"seer"` | Village | Yes (investigate) |

### Teams

- **Village team**: `villager`, `seer`
- **Wolf team**: `werewolf`

### Night Wake Order

Roles act in this order each night: `seer` → `werewolf`

---

## Win Conditions

| Condition | Value | Triggered When |
|-----------|-------|---------------|
| Villagers win | `"villagers"` | All werewolves are eliminated |
| Wolves win | `"wolves"` | Wolves >= Village (alive count) |

---

## WebSocket Protocol

### Endpoint

```
ws[s]://<ha-host>/loup_garou/ws
```

### Message Format

**Client → Server:**
```json
{
  "type": "<command>",
  ...other_fields,
  "callback_id": "cb_<timestamp>_<random>"
}
```

**Server → Client:**
```json
{
  "type": "state",
  "data": { ... },
  "callback_id": "cb_<timestamp>_<random>"
}
```
or
```json
{
  "type": "error",
  "message": "Human-readable error",
  "callback_id": "cb_<timestamp>_<random>"
}
```

### Commands

The frontend may send command types with or without the `loup_garou/` prefix (e.g., `start_game` or `loup_garou/start_game` — the handler strips the prefix).

| Command | Description | Required Fields |
|---------|-------------|-----------------|
| `get_state` | Get current game state | — |
| `start_game` | Start a new game | `player_names`, `role_config` |
| `confirm_role_seen` | Player acknowledged their role | `player_id` |
| `night_action` | Submit night action | `action_type`, `target_id` |
| `submit_vote` | Submit a day vote | `voter_id`, `target_id` |
| `resolve_votes` | Host ends voting phase | — |
| `eliminate_player` | Manually eliminate a player | `player_id`, `cause` |
| `begin_vote` | Start the vote phase | — |
| `next_phase` | Host override to advance phase | — |
| `reset` | Reset game to initial state | — |

---

## GameEngine Public API

All methods are async coroutines.

### `async_start_game(player_names, role_config, language='fr')`

Initialize a new game with players and role distribution.

**Parameters:**
- `player_names`: `list[str]` — list of player names (min 4, max ~20)
- `role_config`: `dict[str, int]` — e.g., `{"villager": 3, "werewolf": 1, "seer": 1}`
- `language`: `str` — `"fr"` or `"en"` (default: `"fr"`)

**Returns:** `dict` — public state

**Errors:** `RoleConfigError` if role counts don't sum to player count or violate balance rules

**Side effects:**
- Shuffles reveal order randomly
- Persists state to HA storage
- Fires `EVENT_GAME_STATE_CHANGED` with `phase: role_reveal`

---

### `async_confirm_role_seen(player_id: str)`

Mark a player as having seen their role during the reveal phase.

**Parameters:**
- `player_id`: `str` — the player's UUID

**Returns:** `dict` — public state

**Logic:**
- Marks player's `role_seen = true`
- Increments `reveal_index`
- When all players have seen → triggers `_async_start_night()` to begin first night

---

### `async_submit_night_action(role: str, action_type: str, target_id: str)`

Record a night action (wolf kill or seer investigate).

**Parameters:**
- `role`: `str` — acting role (from `_current_night_role()`)
- `action_type`: `str` — `NightActionType.WOLF_KILL` or `NightActionType.SEER_INVESTIGATE`
- `target_id`: `str` — target player's UUID

**Returns:** `dict` — public state

**Errors:**
- `"Not in night phase"` if wrong phase
- `"Invalid target"` if target dead or unknown
- `"Wolves cannot target each other"` if wolf targets a wolf
- `"...already submitted"` if action already recorded

---

### `async_submit_vote(voter_id: str, target_id: str)`

Record a day's vote from one player.

**Parameters:**
- `voter_id`: `str` — voting player's UUID
- `target_id`: `str` — elimination target's UUID

**Returns:** `dict` — public state

**Errors:**
- `"Not in vote phase"` if wrong phase
- `"Invalid voter"` / `"Invalid target"` if player unknown or dead
- `"Cannot vote for yourself"`
- `"<id> has already voted"`

---

### `async_resolve_vote()`

Host-triggered end of voting. Eliminates the plurality leader (or nobody on tie).

**Returns:** `dict` — public state

**Logic:**
- If no votes cast → advance to night without elimination
- If tie (multiple players with same max votes) → no elimination
- Otherwise → call `async_eliminate_player()` on the winner
- Clears `vote_tallies` and advances to next phase

---

### `async_eliminate_player(player_id: str, cause: str)`

Eliminate a player and check win condition.

**Parameters:**
- `player_id`: `str` — player's UUID
- `cause`: `str` — `EliminationCause.WOLF_KILL` or `EliminationCause.VILLAGE_VOTE`

**Returns:** `dict` — public state

**Logic:**
- Sets `player.alive = false`
- Fires `EVENT_GAME_STATE_CHANGED` with player info
- Checks win condition → if won, sets `phase: GAME_OVER` and fires `EVENT_GAME_OVER`
- Persists state

---

### `async_begin_vote()`

Manually start the vote phase (from day phase).

**Errors:** `"Can only begin vote during DAY phase"`

---

### `async_next_phase()`

Host override to advance phase without going through normal game logic.

**Logic:**
- `night` → `_async_advance_to_day()`
- `day` → sets phase to `vote`, clears tallies
- `vote` → calls `async_resolve_vote()`

---

### `async_reset()`

Reset game to initial `SETUP` state. Clears all players and state.

---

### `get_public_state() -> dict`

Return sanitized state for frontend. **Does not include roles** (roles are secret except during individual reveal).

**Returns:**
```python
{
    "phase": str,
    "round": int,
    "language": str,
    "winner": str | None,
    "players": [
        {"id": str, "name": str, "alive": bool, "role_seen": bool}
        for p in all_players
    ],
    "alive_count": int,
    "dead_count": int,
    "reveal_index": int,
    "reveal_total": int,
    "next_reveal_player": str | None,  # name of next player to receive role
    "eliminated_this_round": list[str],  # player IDs eliminated this cycle
    "vote_tallies_count": {target_id: vote_count},
    "votes_cast": int,
    "alive_voter_count": int,
    "current_night_role": str | None,  # role currently acting at night
    "night_actions_completed": list[str],  # roles that have acted tonight
}
```

---

### `get_role_reveal_data(player_id: str) -> dict`

Return role data for the next player in the reveal sequence.

**Returns:**
```python
{
    "player_id": str,
    "player_name": str,
    "role": str,  # "villager", "werewolf", or "seer"
}
```

**Errors:** `"Not in role reveal phase"` / `"Not this player's turn"` / `"Unknown player"`

---

### `get_seer_result(seer_player_id: str) -> dict`

Return seer's investigation result from last night.

**Returns:**
```python
{
    "target_name": str,
    "target_role": str,  # role name
}
```

**Errors:** `"Not a seer"` / `"Seer has not investigated yet"`

---

### `get_full_state_for_end() -> dict`

Return state including all roles — only sent at game over.

**Returns:** `get_public_state()` + `"players_full"` field with role data

---

## Data Models

### Player

```python
@dataclass
class Player:
    id: str                    # UUID
    name: str
    role: str                  # "villager", "werewolf", "seer"
    alive: bool = True
    role_seen: bool = False
```

### NightActions

```python
@dataclass
class NightActions:
    wolf_victim_id: str | None = None
    seer_target_id: str | None = None
    seer_result: str | None = None  # role name (for screen only)
    completed_roles: list[str] = []
```

### GameState

```python
@dataclass
class GameState:
    phase: str = "setup"
    round: int = 0
    players: list[Player] = []
    night_actions: NightActions = NightActions()
    vote_tallies: dict[str, list[str]] = {}  # target_id → [voter_ids]
    eliminated_this_round: list[str] = []
    current_night_role_index: int = 0
    reveal_order: list[str] = []  # player IDs in reveal order
    reveal_index: int = 0
    winner: str | None = None
    language: str = "fr"
```

---

## Events

Fired on Home Assistant event bus under domain `loup_garou`:

| Event | Data |
|-------|------|
| `loup_garou_state_changed` | `config_entry_id`, `phase`, plus phase-specific fields |
| `loup_garou_game_over` | `config_entry_id`, `winner` |

---

## Light Scenes

| Key | RGB | Brightness | Transition |
|-----|-----|------------|------------|
| `night` | `(10, 22, 40)` | 20 (~8%) | 3s |
| `wolf_wake` | `(139, 0, 0)` | 51 (~20%) | 1s |
| `seer_wake` | `(106, 13, 173)` | 51 | 1s |
| `day` | `(255, 245, 224)` | 191 (~75%) | 4s |
| `death` | `(139, 0, 0)` | 38 (~15%) | 1s |
| `wolves_win` | `(200, 0, 0)` | 153 (~60%) | 0s, strobe |
| `village_win` | `(255, 220, 100)` | 255 | 1s |

---

## TTS Strings

All TTS announcements support `fr` and `en` languages. Template variables:
- `{name}` — player name
- `{article}` — French article ("un"/"une")
- `{role}` — role name

Key messages:
- `roles_distributed` — after role reveal begins
- `night_start` — when night begins
- `seer_wake` / `seer_sleep` — seer wake/sleep cues
- `wolf_wake` / `wolf_sleep` — wolf wake/sleep cues
- `day_start_death` — morning with victim
- `day_start_no_death` — peaceful morning
- `vote_start` — vote phase begins
- `vote_tie` — tie during voting
- `elimination` — player eliminated
- `wolves_win` / `villagers_win` — game end

---

## Validation Rules

- **Minimum players**: 4
- **Role balance**: Werewolf count must leave village with > 0 players (werewolves < non-werewolves at start)
- **Role sum**: Total roles must equal player count
- **Werewolf minimum**: At least 1 werewolf
- **Seer limit**: Max 1 seer

---

## File Structure

```
custom_components/loup_garou/
├── __init__.py          # Integration entry, panel registration
├── config_flow.py       # HA config flow (speaker, lights, language)
├── const.py             # Enums, constants, TTS strings, light scenes
├── game_engine.py       # GameEngine + data models
├── role_manager.py      # Role assignment + validation
├── phase_manager.py     # Phase coordination (lights + TTS)
├── websocket.py         # Custom WebSocket handler (no HA auth)
├── websocket_api.py    # HA WebSocket command registration (legacy)
├── light_controller.py  # Smart light control
├── speaker_controller.py # TTS/mmedia player control
└── www/game/
    ├── index.html       # Game UI (single-device controller)
    └── launcher.html    # Landing page for sidebar entry
```