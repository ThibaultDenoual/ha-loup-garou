# browser-game-ui Specification

## Purpose

Defines the browser experience served under `/{DOMAIN}/game`: the launcher hub page and
the single-phone, pass-the-player game UI (setup, role reveal, night, day, vote, game
over), including the WebSocket client behaviour, localization, accessibility, and
safe rendering of player-supplied text.

## Requirements

### Requirement: Launcher hub

`launcher.html` SHALL present Play, Rules, and Config tabs with ARIA tab semantics and keyboard arrow navigation, link into the game UI, show a role reference and a compact config summary, and mirror HA configuration through the game WebSocket.

#### Scenario: Save configuration
- **WHEN** the user presses save on the Config tab
- **THEN** the launcher SHALL send `save_config` with mode, speaker, lights, language, engine, and delays and confirm via the echoed config message

#### Scenario: HA-only fields hidden in browser mode
- **WHEN** the TTS mode select is set to browser
- **THEN** speaker/engine/delay fields SHALL be hidden

### Requirement: WebSocket client with backoff

The UI SHALL connect to `/loup_garou/ws`, request config and state on open, and on close reconnect with exponential backoff capped at 30 seconds, resetting the counter on a successful open; the status bar SHALL show connected/reconnecting state.

#### Scenario: Repeated failures
- **WHEN** reconnects keep failing
- **THEN** the delay SHALL grow 1s → 2s → 4s … up to the cap without hammering the server

### Requirement: Phase-aware status bar

The header SHALL show the localized phase label and a compact progress track marking completed and current phases among setup, role reveal, night, day, vote, and game over.

#### Scenario: Night active
- **WHEN** the engine reports phase `night`
- **THEN** the track SHALL mark earlier phases complete and night current

### Requirement: Setup validation and guidance

Setup SHALL allow adding/removing named players, require at least 3, unique non-empty names, and a role count exactly equal to the player count; the start button SHALL stay disabled with a localized hint explaining the remaining condition, and role counters SHALL be bounded by the current player total.

#### Scenario: Duplicate names
- **WHEN** two players share a name
- **THEN** the hint SHALL report names must be unique and starting SHALL stay disabled

#### Scenario: Role allocation exceeds players
- **WHEN** assigned roles equal the player count
- **THEN** further "+" presses SHALL be disabled

### Requirement: Secret role reveal with handoff

Reveal SHALL prompt "pass the phone to <name>", flip a card on tap/Enter/Space, keep hidden faces out of the accessibility tree, hide the role before handing off, and begin the night after the final player confirms.

#### Scenario: Handoff protection
- **WHEN** a player presses "hide role and pass"
- **THEN** the card SHALL flip face-down before the next player's role is loaded

### Requirement: Night action screens

For each waking role the UI SHALL render the localized prompt and target grid: wolves/alpha/seer single-select with confirm disabled until a pick, cupid exactly-two-lovers selection, witch save/poison toggles driven by server-enriched victim and potion data, seer result screen with acknowledgement, and hunter last-shot screen; player cards SHALL be keyboard-operable and announce selection state.

#### Scenario: Witch with protected Elder
- **WHEN** the wake payload lists no saveable victim because the Elder is protected
- **THEN** the save button SHALL be disabled and the poison target list SHALL remain available

#### Scenario: Skip
- **WHEN** a turn offers "do nothing"
- **THEN** the UI SHALL submit an empty action and return to sleep

### Requirement: Day, vote, and game over screens

Day SHALL show the localized morning announcement with dead players dimmed and offer next-night or vote; vote SHALL pass the phone voter-by-voter, excluding the voter as a target, show vote progress, and submit the collected ballot for resolution; game over SHALL show the winning banner, reveal every role with team colour, and offer a new game.

#### Scenario: Vote progress
- **WHEN** three of five voters have voted
- **THEN** the progress line SHALL read 3 of 5

### Requirement: Safe rendering of player text

All player names and server-derived labels SHALL be rendered through DOM APIs (`textContent`, element creation), never via HTML string interpolation into `innerHTML`.

#### Scenario: Hostile name
- **WHEN** a player is named `<img onerror=alert(1)>`
- **THEN** the name SHALL display literally without executing markup

### Requirement: Localized UI language

Static copy SHALL resolve through locale JSON loaded for `en`/`fr` (falling back to French for unsupported values), update `[data-i18n]`, placeholder, and aria-label attributes on language change, and follow the server's configured language received via `get_config`.

#### Scenario: Configured English
- **WHEN** the server config says `language: "en"`
- **THEN** the game UI SHALL render English strings

### Requirement: Browser narration handshake

The UI SHALL play a `narrate` message's recorded clip when it has one, otherwise speak its text with the Web Speech API, and send `tts_done` once the line is over.

Every clip SHALL play through one shared audio element, which the first tap on the page unlocks, so lines that start without a tap still play on phones that only allow sound from a tap (the Android Companion App's WebView).

When neither the clip nor speech can play, the UI SHALL wait for the line's length (`audio_seconds`, or an estimate from the text) before sending `tts_done`, so the game keeps its pace in silence. A clip or utterance that never ends SHALL be given up a few seconds after its expected length.

#### Scenario: Line after the first tap
- **WHEN** the page has been tapped once and a `narrate` message arrives later with no tap
- **THEN** its clip SHALL play

#### Scenario: Nothing can play
- **WHEN** a clip is refused and `window.speechSynthesis` is absent
- **THEN** the client SHALL send `tts_done` after about `audio_seconds`, not at once

### Requirement: Reduced motion and atmosphere budget

Decorative animation (starfield canvas, grain drift) SHALL be suppressed under `prefers-reduced-motion`, and the starfield SHALL cap particle count for cheap per-frame work.

#### Scenario: Reduced motion set
- **WHEN** the user prefers reduced motion
- **THEN** the canvas SHALL not run its animation loop
