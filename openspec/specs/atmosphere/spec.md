# atmosphere Specification

## Purpose

Defines the Home Assistant atmosphere layer that subscribes to engine events and keeps
the physical room in sync with the game: light scenes, TTS narration of phases, role
wake/sleep cues, death and vote announcements, and win celebrations, in French or
English.

## Requirements

### Requirement: Locale-driven narration

Atmosphere SHALL build narration text from the loaded locale via `t(key, **vars)`, returning empty (and thus staying silent) when a key is absent, and SHALL format `{...}` placeholders.

#### Scenario: Missing key stays silent
- **WHEN** a role has no `role.<id>.wake` text
- **THEN** Atmosphere SHALL not speak on that role's wake

### Requirement: Night fall scene and announcement

On `phase_changed` to night, Atmosphere SHALL apply the `night` light scene to configured lights and speak the night-start line.

#### Scenario: Night begins
- **WHEN** the engine transitions to night
- **THEN** configured lights SHALL move to the night scene

### Requirement: Role wake and sleep cues

On `night_role_wake` Atmosphere SHALL set the mapped per-role scene (cupid, seer, wolf, alpha, witch) and speak the role's wake line, but SHALL stay silent and change no scene for a seer `result` payload; on `night_role_sleep` it SHALL speak the sleep line and restore the night scene.

#### Scenario: Seer result muted
- **WHEN** a wake event carries a seer `result`
- **THEN** Atmosphere SHALL neither narrate nor re-light

### Requirement: Day announcement

On `day_started` Atmosphere SHALL apply the `day` scene, speak the no-death line when the eliminated list is empty, and otherwise announce each eliminated player by name, article, and role.

#### Scenario: Morning after a kill
- **WHEN** day starts with one eliminated player
- **THEN** Atmosphere SHALL speak the with-death line using the player's name and role

### Requirement: Live elimination narration

On `player_eliminated` Atmosphere SHALL narrate and flash the `death` scene only for causes that happen live (`hunter_shot`, `lover_grief`, `scapegoat`); wolf kills and vote eliminations SHALL be deferred to day/vote announcements.

#### Scenario: Wolf kill not double-announced
- **WHEN** a player is eliminated with cause `wolf_kill`
- **THEN** Atmosphere SHALL not narrate at the moment of death

### Requirement: Vote and game-over cues

Atmosphere SHALL speak the vote-start line, the tie or result line on vote resolution, and on game over SHALL apply the winner's light scene (wolves strobe, village warm, lovers rose) with the matching win message.

#### Scenario: Wolves win
- **WHEN** the winner is `wolves`
- **THEN** Atmosphere SHALL set the wolves-win scene and speak the wolves-win line

### Requirement: TTS mode behaviour

Atmosphere SHALL support `browser` TTS by delegating to `server.narrate` (which awaits the real `tts_done`), and HA TTS by calling the `tts.speak` service on the configured engine/speaker and sleeping for the configured per-phase delay so the game does not race ahead of audio; with no speaker configured in HA mode it SHALL skip speaking.

#### Scenario: HA mode paces on estimated delay
- **WHEN** a line is spoken in HA mode
- **THEN** Atmosphere SHALL await the phase delay mapped to that event's `delay_key`

### Requirement: Dynamic config updates

`update_config` SHALL accept a merged config and change TTS mode, speaker, lights, language, engine, and phase delays without re-wiring events.

#### Scenario: Speaker changed
- **WHEN** a new speaker entity is applied
- **THEN** subsequent narration SHALL target the new speaker

### Requirement: French article handling

For French, Atmosphere SHALL use "une" for the feminine roles (seer, witch, little girl) and "un" otherwise; for other languages it SHALL use the locale's article key.

#### Scenario: Feminine role article
- **WHEN** announcing a witch's death in French
- **THEN** the article SHALL be "une"
