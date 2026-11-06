# home-assistant-integration Specification

## Purpose

Defines how the integration mounts into Home Assistant: the config flow, the setup
entry wiring that composes engine + WebSocket server + atmosphere, static game UI and
locale hosting, the authenticated game WebSocket view, the sidebar panel, and entry
unloading.

## Requirements

### Requirement: Root entry point delegation

The package root `__init__.py` SHALL keep no game logic; `async_setup` SHALL initialize `hass.data[DOMAIN]`, and `async_setup_entry` / `async_unload_entry` SHALL delegate to the integration wiring module.

#### Scenario: Domain data bootstrap
- **WHEN** HA sets up the integration domain
- **THEN** `hass.data["loup_garou"]` SHALL exist as a dict

### Requirement: Single-instance config flow

The config flow SHALL present an empty form and create an entry titled "Loup Garou" with empty data, and SHALL abort with reason `single_instance_allowed` when an entry already exists.

#### Scenario: Second instance blocked
- **WHEN** a user adds the integration while one entry exists
- **THEN** the flow SHALL abort instead of creating a second entry

### Requirement: Entry setup composition

Setting up an entry SHALL merge stored data over documented defaults (tts_mode, speaker, lights, language, tts_engine, tts_delays, version), pre-warm the role registry and load the locale file in an executor job, construct the `GameEngine` and `LoupGarouServer` with the merged config, wire server and atmosphere events, and store engine/server/atmosphere per entry id.

#### Scenario: Blocking work off the event loop
- **WHEN** the role registry is loaded or the locale JSON is read during setup
- **THEN** both operations SHALL run in an executor rather than blocking the loop

### Requirement: Authenticated game WebSocket

The integration SHALL register a Home Assistant HTTP view at `/loup_garou/ws` with `requires_auth = True` that delegates to the server's WebSocket handler.

#### Scenario: Unauthenticated request
- **WHEN** a client connects to `/loup_garou/ws` without HA credentials
- **THEN** HA SHALL reject the handshake per the view's auth requirement

### Requirement: Game UI and locale hosting

The integration SHALL serve the browser game at `/{DOMAIN}/game` with `Cache-Control: no-cache` (refusing paths outside the game folder), and register static paths for the locale JSON files at `/{DOMAIN}/locales` and the clips at `/{DOMAIN}/audio`. The config sent to pages SHALL carry `build`, a fingerprint of the game's web files.

#### Scenario: Launcher load
- **WHEN** a browser requests `/loup_garou/game/launcher.html`
- **THEN** the file SHALL be served from the integration's `www` directory

### Requirement: Joined narration clips

Setup SHALL register `/loup_garou/voice/{lang}/{name}`, without auth like `/loup_garou/audio`, serving the named recorded clips joined into one MP3 (`voice.py`). It SHALL accept only `en`/`fr`, one to six stems of known clips and a `.mp3` name, and answer 404 otherwise.

### Requirement: Sidebar panel

Setup SHALL register a built-in `iframe` panel with sidebar title "Loup Garou", icon `mdi:weather-night`, frontend path `loup_garou`, pointing at `/loup_garou/game/index.html`, and available to non-admin users.

#### Scenario: Panel removal on unload
- **WHEN** the config entry is unloaded
- **THEN** the `loup_garou` panel SHALL be removed and the entry data dropped

### Requirement: Live configuration bridge

Setup SHALL give the server a save callback that merges new values into the config entry, updates the server's in-memory config (with version), and live-updates the atmosphere; and an entities callback that lists `media_player` and `light` entity ids for the launcher.

#### Scenario: Save from launcher
- **WHEN** a client sends `save_config` with new speaker/lights/language/tts settings
- **THEN** the config entry, server config, and atmosphere SHALL reflect the merged values without a restart
