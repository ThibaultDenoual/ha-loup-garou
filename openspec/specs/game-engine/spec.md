# game-engine Specification

## Purpose

Defines the Home Assistant-free game engine that owns Werewolf game state, drives the
night/day/vote lifecycle, resolves eliminations, detects the winner, and publishes
engine events to subscribed presenters (WebSocket server, atmosphere, console, dev).

## Requirements

### Requirement: Pure game logic module

The engine SHALL be implemented in `game_engine.py` with zero Home Assistant imports, so it can run inside the integration or standalone.

#### Scenario: Standalone import
- **WHEN** `GameEngine` is imported outside Home Assistant
- **THEN** it SHALL construct and operate using only the in-process role registry and asyncio

### Requirement: Game state model

The engine SHALL keep a single `GameState` holding players (id, name, role, alive), current phase, night number, pending kills as `(player_id, cause)` pairs, per-player flags, player links, winner, and any pending interrupt.

#### Scenario: Player identity
- **WHEN** a game starts with N player names
- **THEN** each player SHALL receive a stable id `p0..p<N-1>` in the order provided

### Requirement: Event publication

The engine SHALL expose `on(event, handler)` and emit `GameEvent` signals (`game_started`, `game_over`, `phase_changed`, `player_eliminated`, `night_role_wake`, `night_role_sleep`, `night_resolved`, `day_started`, `vote_started`, `vote_resolved`). `day_started` SHALL carry the eliminated player ids and `after`, set to `night` when a night led to the day and `vote` when a vote did.

#### Scenario: Day after a vote
- **WHEN** a vote eliminates a player and the game goes on
- **THEN** the engine SHALL emit `day_started` with that player in `eliminated` and `after` set to `vote`

#### Scenario: Handler failure is isolated
- **WHEN** one event handler raises
- **THEN** the engine SHALL log the error and continue invoking the remaining handlers

### Requirement: Public state exposure

The engine SHALL provide `get_public_state()` returning phase, night number, winner, and serialized players, and `get_role_public_state(role_id)` delegating to that role's public data without exposing engine internals.

#### Scenario: Missing role id
- **WHEN** `get_role_public_state` is called for an unknown role
- **THEN** it SHALL return an empty mapping

### Requirement: Game start

`start_game(player_names, role_ids)` SHALL require equal-length inputs, build players, run each present role's `on_game_start`, set phase to `role_reveal`, and emit `game_started` then `phase_changed`.

#### Scenario: Mismatched lengths
- **WHEN** the number of names and roles differ
- **THEN** `start_game` SHALL raise `ValueError`

### Requirement: Night sequence

`begin_night()` SHALL set phase to `night`, increment the night number, clear pending kills, then for each active night role (ordered by `night_priority`) that has living members and passes `should_wake`, emit `night_role_wake` with the role's wake data, await a submitted action, run `on_night_action`, emit `night_role_sleep`, and finally resolve the night.

#### Scenario: Dead role skipped
- **WHEN** a role has no living players
- **THEN** the engine SHALL neither wake it nor await an action for it

#### Scenario: Night action awaited
- **WHEN** the engine wakes a role
- **THEN** it SHALL block until `submit_night_action` is called for that role id

### Requirement: Action submission gating

`submit_night_action(role_id, action)` SHALL only resolve the pending action future when `role_id` matches the role currently awaited; otherwise it SHALL log a warning and ignore the submission. `submit_pending_action` SHALL similarly gate mid-chain interrupts by the current `pending_interrupt_role`.

#### Scenario: Out-of-turn submission
- **WHEN** a client submits an action for a role that is not currently awaiting
- **THEN** the engine SHALL leave the future unresolved and warn

### Requirement: Vote resolution

`resolve_vote(votes)` SHALL tally only votes from living players, counting the elected sheriff's vote as two, eliminate the top target with cause `village_vote`, and on a tie either eliminate the living scapegoat or eliminate no one before returning to day.

#### Scenario: Sheriff double vote
- **WHEN** the sheriff votes for a target
- **THEN** that target's tally SHALL increase by two

#### Scenario: Tie with scapegoat
- **WHEN** the vote is tied and a scapegoat is alive
- **THEN** the scapegoat SHALL be eliminated with cause `scapegoat`

#### Scenario: Tie without scapegoat
- **WHEN** the vote is tied and no scapegoat is alive
- **THEN** `resolve_vote` SHALL eliminate no one and advance to day

### Requirement: Elimination cascade

When eliminating a player the engine SHALL consult every active role's `on_before_eliminate` (which may cancel the death or add further eliminations such as linked lovers), mark the player dead, emit `player_eliminated`, then run every role's `on_after_eliminate`.

#### Scenario: Lover chain
- **WHEN** a linked lover is eliminated
- **THEN** the surviving lover SHALL be eliminated with cause `lover_grief`

### Requirement: Win detection

After eliminations the engine SHALL ask each active role to `check_win`; a returned team ends the game, and if every player is dead the village SHALL win by default.

#### Scenario: All players dead
- **WHEN** no players remain alive and no role claimed victory
- **THEN** the engine SHALL declare the village the winner

### Requirement: Game end

`_end_game(winner)` SHALL set phase to `game_over`, record the winner, and emit `phase_changed` then `game_over`.

#### Scenario: Winner recorded
- **WHEN** the game ends
- **THEN** public state SHALL expose the winning team id

### Requirement: Sheriff election

`elect_sheriff(player_id)` SHALL ensure exactly one sheriff by clearing any existing `sheriff` flag before setting it on the chosen player.

#### Scenario: Re-election
- **WHEN** a second player is elected sheriff
- **THEN** the previous sheriff's double-vote flag SHALL be removed
