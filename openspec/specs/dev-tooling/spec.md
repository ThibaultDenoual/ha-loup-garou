# dev-tooling Specification

## Purpose

Defines the Home Assistant-free development and playtest tooling: the standalone aiohttp
dev server, the console runner, shared YAML/CLI dev configuration, and the simulated
TTS/light output layers that mirror the HA atmosphere for human testing.

## Requirements

### Requirement: Standalone dev server

`run_devserver.py` SHALL build an aiohttp application that constructs a fresh engine, server (with dev config including version), and `DevOutputHandler`, serves the game UI at `/loup_garou/game` and locales at `/loup_garou/locales`, redirects `/` to the game index, logs the ready URLs on startup, and runs on `0.0.0.0` with the configured port (default 8099).

#### Scenario: Single WebSocket route
- **WHEN** the dev app is built
- **THEN** exactly one `/loup_garou/ws` route SHALL be registered, handled by a wrapper that lets the dev TTS consume `tts_done` before dispatching each JSON message to the game server

#### Scenario: Root redirect
- **WHEN** a tester opens `http://localhost:<port>/`
- **THEN** the browser SHALL land on the game index page

### Requirement: Shared dev configuration

`dev_config.py` SHALL provide a `DevConfig` (language, tts_mode, tts_engine, speaker, lights, tts_delays, port, players, roles) built either from a YAML file (`--config dev.yaml`) or common CLI flags, starting from the integration's default language, TTS mode, engine, and phase delays, with comma-separated parsing for lights/players/roles and JSON merging for delays.

#### Scenario: YAML precedence
- **WHEN** `--config dev.yaml` is passed
- **THEN** values SHALL load from the file, filling any missing keys with integration defaults

#### Scenario: Missing PyYAML
- **WHEN** a YAML config is requested without PyYAML installed
- **THEN** loading SHALL fail with a clear install instruction

### Requirement: Console game runner

`run_console.py` SHALL default to an interactive mode driven by `ConsoleRunner` — prompting for names, one role per player (rejecting unknown role ids), then playing the full phase loop (night actions, vote or next-night choice) over stdin until the phase becomes `game_over` — and a `--non-interactive` mode that auto-drives night actions and votes from `players`/`roles` in config.

#### Scenario: Non-interactive validation
- **WHEN** `--non-interactive` is used without matching player and role lists
- **THEN** the runner SHALL exit with a usage error before starting the engine

#### Scenario: Automatic playthrough
- **WHEN** a non-interactive game runs
- **THEN** wolves/seer SHALL pick targets, the witch SHALL save the pending victim and poison another, and play SHALL continue until a winner ends the game

### Requirement: Simulated TTS backends

`dev_tts.py` SHALL provide a mock backend that logs each line as `[TTS] (lang) text` and sleeps a short delay, and a browser backend that broadcasts `narrate` messages to connected clients and waits (bounded timeout) for `tts_done`, skipping silently when no client is connected.

#### Scenario: Browser mode in dev server
- **WHEN** `tts_mode: browser` is configured
- **THEN** narration SHALL flow through the WebSocket and resume the game on the client's `tts_done`

### Requirement: Simulated lights

`dev_lights.py` SHALL log scene transitions (rgb, brightness, transition, flash/strobe markers) for configured light entities using the shared `LIGHT_SCENES` table, ignore unknown scene keys, and still describe the scene when no lights are configured.

#### Scenario: Death flash
- **WHEN** the `death` scene is set
- **THEN** the log line SHALL include a FLASH marker

### Requirement: Dev output mirrors atmosphere

`dev_output.py` SHALL wire the same engine events as the HA atmosphere (phase, wake/sleep, day, vote, elimination, game over) to the dev TTS and lights, skip narration for seer results (logging them instead), and defer `wolf_kill`/vote deaths to day/vote announcements.

#### Scenario: No HA imports
- **WHEN** the dev stack runs
- **THEN** no module in the dev path SHALL import `homeassistant`

### Requirement: Import path bootstrap

The dev entry scripts SHALL make the integration importable by inserting the repository root and `custom_components/` onto `sys.path` before importing `custom_components.loup_garou` modules.

#### Scenario: Fresh checkout run
- **WHEN** `python run_devserver.py --config dev.yaml` is executed from the repo root without installation
- **THEN** imports SHALL resolve and the server SHALL start
