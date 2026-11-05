## ADDED Requirements

### Requirement: One open prompt
During a game the core SHALL have at most one open prompt, and answering it SHALL be the only way to advance the game.

#### Scenario: Vote outside a ballot
- **WHEN** a client sends a removed command such as `resolve_vote`
- **THEN** the server SHALL reply with an error and the game SHALL not change

### Requirement: Prompt opens after narration
A prompt SHALL open only after the narration announcing it has finished.

#### Scenario: Wake line still playing
- **WHEN** a role's wake narration is in progress
- **THEN** the snapshot SHALL carry no prompt for that role

### Requirement: Answer handling
The server SHALL handle `answer` by prompt id and validate it against the prompt's picks.

#### Scenario: Legal answer
- **WHEN** the answer matches the open prompt and its picks
- **THEN** the game SHALL advance

#### Scenario: Double tap
- **WHEN** the most recently answered prompt is answered again
- **THEN** the server SHALL ignore it without an error

#### Scenario: Stale prompt
- **WHEN** an answer names any other prompt id
- **THEN** the server SHALL send `stale_prompt` and a fresh snapshot

#### Scenario: Illegal choice
- **WHEN** an answer breaks the prompt's picks
- **THEN** the server SHALL send `illegal_answer` and a fresh snapshot, and the prompt SHALL stay open

### Requirement: Complete snapshots
Every change SHALL broadcast a snapshot holding phase, night, winner, players, news and the open prompt, so a client can render from the latest snapshot alone.

#### Scenario: Reconnect mid-vote
- **WHEN** a client reconnects during a vote
- **THEN** `get_state` SHALL return the open ballot and earlier ballots SHALL be kept

### Requirement: Secret roles
A snapshot SHALL include a player's role only when that player is dead or the game is over. A prompt MAY include a role its holder needs.

#### Scenario: Living player
- **WHEN** a snapshot is sent during a game
- **THEN** living players SHALL have no `role_id`

### Requirement: Leaving a game
`abandon_game` SHALL stop any game and return to setup. `start_game` SHALL be refused with `game_in_progress` outside setup.

#### Scenario: Start during a game
- **WHEN** `start_game` arrives during a game
- **THEN** the running game SHALL be unaffected
