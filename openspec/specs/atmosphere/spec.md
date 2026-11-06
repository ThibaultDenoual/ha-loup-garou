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

On `day_started` after a night (`after: "night"`) Atmosphere SHALL apply the `day` scene, speak the no-death line when the eliminated list is empty, and otherwise announce each eliminated player by name, article, and role. On `day_started` after a vote (`after: "vote"`) it SHALL leave the lights as they are and say nothing, since the verdict has already been narrated.

#### Scenario: Morning after a kill
- **WHEN** day starts after a night with one eliminated player
- **THEN** Atmosphere SHALL speak the with-death line using the player's name and role

#### Scenario: Day after a vote
- **WHEN** day starts after a vote that eliminated a player
- **THEN** Atmosphere SHALL change no light and speak no line

### Requirement: Deaths announced by public role

Night deaths, the vote result, the Hunter's target, a lover's grief and the scapegoat SHALL be announced without the player's name, from recorded parts: a lead-in (`part.victim`, `part.vote`, `part.hunter`, `part.grief`, `part.scapegoat`), the player's `public.<id>.spoken`, `part.was`, and `role.<id>.spoken`. With recorded voice the parts SHALL be one URL, `/loup_garou/voice/<lang>/<stem>+…mp3`, whose length is the sum of the parts. A player without a public role SHALL get the older line with their name.

#### Scenario: Night death
- **WHEN** the Baker, a Seer, died in the night
- **THEN** the narration SHALL be "The victim is…" + "the Baker" + "They were…" + "a Seer" as one joined clip

### Requirement: Live elimination narration

On `player_eliminated` Atmosphere SHALL narrate and flash the `death` scene only for causes that happen live (`hunter_shot`, `lover_grief`, `scapegoat`); wolf kills and vote eliminations SHALL be deferred to day/vote announcements. A live death SHALL set the `death` scene, narrate, then hold for `DEATH_BEAT` seconds before returning, so the next step (game over included) waits for it.

When the Hunter wakes to shoot, Atmosphere SHALL set the `death` scene and play the recorded `role.hunter.wake` line before the Hunter's choice opens.

#### Scenario: Hunter shoots the last wolf
- **WHEN** the Hunter's shot eliminates the last wolf
- **THEN** the death scene and the shot line SHALL play, and game over SHALL start only after `DEATH_BEAT`

#### Scenario: Wolf kill not double-announced
- **WHEN** a player is eliminated with cause `wolf_kill`
- **THEN** Atmosphere SHALL not narrate at the moment of death

### Requirement: Vote and game-over cues

Atmosphere SHALL speak the vote-start line, the tie or result line on vote resolution, and on game over SHALL apply the winner's light scene (wolves strobe, village warm, lovers rose) with the matching win message.

#### Scenario: Wolves win
- **WHEN** the winner is `wolves`
- **THEN** Atmosphere SHALL set the wolves-win scene and speak the wolves-win line

### Requirement: TTS mode behaviour

Atmosphere SHALL support `browser` TTS by delegating to `server.narrate` (which awaits the real `tts_done`), and HA output by calling `tts.speak` or `media_player.play_media` on the configured speaker; with no speaker configured in HA mode it SHALL skip speaking.

In HA mode Atmosphere SHALL wait for the speaker itself: it SHALL wait up to `SPEAKER_START_TIMEOUT` for the speaker to enter `playing`, then until it leaves `playing` (at most `SPEAKER_MAX_LINE`), then pause `SPEAKER_GAP` before the next line. It SHALL fall back to the per-phase delay (or the recorded clip length) when the speaker has no state, is already playing, or has never been seen playing; a speaker that misses its first line SHALL be logged once and use fixed delays until the speaker setting changes.

Recorded clips SHALL be sent as absolute URLs built from `get_url` (the Network settings, falling back to the local address), and as announcements when the speaker supports `MEDIA_ANNOUNCE`, as `tts.speak` does. Service calls SHALL be blocking so a refused call is logged with the speaker and the line.

"Test the narration" SHALL watch the speaker afresh and report one result to the browser: `played`, `sent` (the speaker has no state), `not_started`, `refused`, `no_url` or `no_speaker`.

#### Scenario: HA mode waits for the speaker
- **WHEN** a line is spoken in HA mode and the speaker goes from `idle` to `playing`
- **THEN** Atmosphere SHALL not return until the speaker leaves `playing`

#### Scenario: Speaker that never plays the test line
- **WHEN** "Test the narration" runs and the speaker never enters `playing`
- **THEN** the browser SHALL receive `test_audio_done` with result `not_started`

#### Scenario: Speaker without state
- **WHEN** a line is spoken in HA mode on a speaker with no state
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
