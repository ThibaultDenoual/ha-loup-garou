# game-server Specification

## Purpose

Defines the aiohttp WebSocket server that bridges browser clients to the game engine:
connection handling, command dispatch, state/event broadcasting, browser-TTS
handshake, and client-safe error reporting — usable both inside Home Assistant and by
the standalone dev server.

## Requirements

### Requirement: Connection lifecycle

The server SHALL accept WebSocket connections at its registered path, track each open socket in a client set, and remove it when the connection closes or errors.

#### Scenario: Client disconnect
- **WHEN** a client's socket closes
- **THEN** the server SHALL stop broadcasting to that socket

### Requirement: Message payload validation

The server SHALL parse each text frame as JSON; malformed JSON SHALL receive an error message with code `bad_request` and message "Invalid JSON message.", and a JSON payload that is not an object SHALL receive an error with code `bad_request` and message "WebSocket message must be a JSON object."

#### Scenario: Non-object payload
- **WHEN** a client sends a JSON array as a message
- **THEN** the server SHALL reject it with `bad_request` without dispatching

### Requirement: Command dispatch

The server SHALL route recognized commands — `start_game`, `begin_night`, `submit_night_action`, `submit_pending_action`, `begin_vote`, `resolve_vote`, `elect_sheriff`, `get_state`, `get_config`, `get_entities`, `save_config`, `tts_done` — to the engine or callbacks; an unrecognized command SHALL return `{"type": "error", "msg": "unknown command: <cmd>"}`.

#### Scenario: State query
- **WHEN** a client sends `get_state`
- **THEN** the server SHALL reply with `{"type": "state", "state": ...}` for that socket only

#### Scenario: Sheriff election broadcast
- **WHEN** `elect_sheriff` succeeds
- **THEN** the server SHALL broadcast updated public state to all clients

### Requirement: Single concurrent night

`begin_night` SHALL start the night sequence as a background task only when no night task is already running; otherwise it SHALL warn and ignore the request.

#### Scenario: Duplicate begin_night
- **WHEN** `begin_night` arrives while a night is in progress
- **THEN** the server SHALL not start a second night

### Requirement: Client-safe error handling

Dispatch SHALL map `KeyError` to `bad_request` with "Missing required field: <name>", other `TypeError`/`ValueError` to `bad_request` with the generic "Invalid request." text, and any unexpected exception to `internal_error` with "An internal error occurred. Check the server logs." — never leaking raw exception text, paths, or stack traces to clients.

#### Scenario: Runtime failure in command
- **WHEN** an engine call raises `RuntimeError("/private/path/secret")`
- **THEN** the client SHALL receive only the sanitized internal error message

### Requirement: Player names checked on start

`start_game` SHALL apply the setup screen's rules to the player names before dealing: at least 3 players, no empty name, at most 20 characters, no `{` or `}`, and no two names that differ only by case. Names SHALL be trimmed first. A broken rule SHALL return `{"type": "error", "code": "invalid_setup", "reason": <reason>}`, where the reason (`need_players`, `empty_name`, `long_name`, `bad_chars`, `duplicate`) names the `ui.setup.hint.<reason>` key the browser shows, and the game SHALL stay in setup.

#### Scenario: Duplicate names from a scripted client
- **WHEN** a client sends `start_game` with players `Alice`, `Bob` and `alice `
- **THEN** the server SHALL reply with `invalid_setup` and reason `duplicate`, and no game SHALL start

### Requirement: Engine event broadcasting

`wire_events()` SHALL subscribe to engine lifecycle events (`game_started`, `phase_changed`, `night_resolved`, `day_started`, `vote_started`, `vote_resolved`, `game_over`) and broadcast full public state, and SHALL broadcast `player_eliminated`, `night_role_wake`, and `night_role_sleep` as typed events to every connected client.

#### Scenario: Elimination sync
- **WHEN** a player is eliminated
- **THEN** clients SHALL receive the `player_eliminated` event followed by updated state

### Requirement: Wake-event enrichment

For each `night_role_wake` broadcast the server SHALL resolve `pending_kills` entries into `pending_kill_players` player objects, and for the witch it SHALL merge `get_role_public_state("witch")` (witch id and potion availability) into the payload.

#### Scenario: Witch potion state
- **WHEN** the witch wakes
- **THEN** the broadcast SHALL include `witch_id`, `witch_save_available`, and `witch_poison_available`

### Requirement: Browser TTS handshake

In browser TTS mode the server SHALL broadcast `{"type": "narrate", "data": {"text", "lang"}}`, block until a client sends `tts_done`, and release after a 10-second timeout so narration can never stall the game; with no connected clients it SHALL skip narration instantly.

#### Scenario: No clients connected
- **WHEN** `narrate` is called with an empty client set
- **THEN** it SHALL return without broadcasting

### Requirement: Configuration bridge

The server SHALL expose its in-memory config via `get_config`, and on `save_config` SHALL invoke a registered save callback (when present) then broadcast the resulting config; it SHALL provide HA entity discovery through a `get_entities` callback returning speaker and light entity lists.

#### Scenario: Entities when no callback
- **WHEN** `get_entities` arrives and no callback is registered
- **THEN** the server SHALL reply with an empty entities payload
