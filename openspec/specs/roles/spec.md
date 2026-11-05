# roles Specification

## Purpose

Defines the role plugin system: the `BaseRole` interface, the discovery/registration
loader, the `RoleContext` read-write facade, and the concrete behaviour and night
ordering of the twelve shipped roles.

## Requirements

### Requirement: Base role interface

Every role SHALL subclass `BaseRole` and MAY declare `id`, `team`, `night_priority`, `has_night_action`, and override the hooks `on_game_start`, `on_night_start`, `on_night_action`, `on_before_eliminate`, `on_after_eliminate`, `check_win`, `should_wake`, `get_wake_data`, and `get_public_state`.

#### Scenario: Default hooks are inert
- **WHEN** a role does not override a hook
- **THEN** the base implementation SHALL be a no-op returning no effect

### Requirement: Role discovery and registry

`load_roles()` SHALL import every module in `roles/impl/`, find all `BaseRole` subclasses with a non-empty `id`, and return a cached `id -> instance` registry; `get_role(id)` SHALL look up that registry.

#### Scenario: Registry is a singleton
- **WHEN** `load_roles()` is called more than once in a process
- **THEN** it SHALL reuse the existing registry rather than rebuilding it

### Requirement: Role context facade

Roles SHALL mutate state only through `RoleContext` (`alive_players`, `all_players`, `pending_kills`, `pending_kill_entries`, `get_player`, `get_flag`, `get_link`, `set_flag`, `add_pending_kill`, `remove_pending_kill`, `add_link`, `change_role`, `request_action`), never by touching `GameState` directly.

#### Scenario: Pending kill de-duplication
- **WHEN** `add_pending_kill` is called for a player already marked
- **THEN** the pending list SHALL not gain a duplicate entry

### Requirement: Night ordering

Night roles SHALL wake in ascending `night_priority`: Cupid (5), Seer (10), Werewolf/Alpha Wolf (50), Witch (60). Passive roles SHALL carry priority 99 and `has_night_action = False`.

#### Scenario: Witch acts after wolves
- **WHEN** the night sequence runs with wolves and a witch present
- **THEN** the witch SHALL wake after the wolves so she can see the victim

### Requirement: Villager

The Villager SHALL have no night action and village team; its `check_win` SHALL return `village` when no werewolf or alpha wolf remains alive and at least one player is alive.

#### Scenario: Wolves eliminated
- **WHEN** all wolf-type players are dead
- **THEN** the villager check SHALL report a village win

### Requirement: Werewolf

The Werewolf SHALL be wolf-team with a night action that marks one alive target for death with cause `wolf_kill`, and its `check_win` SHALL return `wolves` when wolf-type players are greater than or equal to the remaining non-wolf, non-minion players.

#### Scenario: Kill only living targets
- **WHEN** a wolf designates a dead player
- **THEN** no pending kill SHALL be added

### Requirement: Alpha Wolf

The Alpha Wolf SHALL act with the wolves, and once per game SHALL convert one living non-wolf player into a `werewolf`, marking `alpha_conversion_used` to prevent further conversions; it SHALL not convert existing wolves and SHALL win with the wolves.

#### Scenario: Conversion used once
- **WHEN** a second conversion is submitted after one has been used
- **THEN** the alpha SHALL make no change

### Requirement: Seer

The Seer SHALL, each night, designate one living player and reveal that player's true role by `request_action` (emitting a wake event carrying a `result` and pausing until the seer acknowledges).

#### Scenario: Result pauses for acknowledgement
- **WHEN** the seer designates a target
- **THEN** the engine SHALL emit a `result` wake and block until `submit_pending_action` is received

### Requirement: Witch

The Witch SHALL hold one save potion and one poison potion, each usable once. Her wake data SHALL list pending kills EXCEPT an Elder's still-protected first wolf kill. A save SHALL only lift a genuine pending `wolf_kill` victim who is not a protected Elder; a poison SHALL mark any chosen living player with cause `witch_poison`.

#### Scenario: Save withheld from protected Elder
- **WHEN** the only victim is an Elder with first life remaining
- **THEN** the save SHALL not consume the healing potion

#### Scenario: Poison consumed once
- **WHEN** a poison target is submitted after the poison was already used
- **THEN** no further pending kill SHALL be added

### Requirement: Cupid

Cupid SHALL wake only on night one and link exactly two players as `lovers`; linked players SHALL die together, and the lovers SHALL win when both are alive and no other player is alive.

#### Scenario: Lovers only on night one
- **WHEN** it is night two or later
- **THEN** Cupid SHALL not wake

### Requirement: Elder

The Elder SHALL be flagged with `elder_first_life` at game start; the first `wolf_kill` against the Elder SHALL be cancelled and clear that flag, so the second wolf attack is fatal.

#### Scenario: Survives first attack
- **WHEN** the Elder is targeted by a wolf kill and still has first life
- **THEN** the elimination SHALL be cancelled and first life cleared

### Requirement: Hunter

When a Hunter is eliminated by any cause, the Hunter SHALL pause the chain via `request_action` and, if a living target is chosen, add that target to the same elimination chain.

#### Scenario: No target chosen
- **WHEN** the hunter's shot resolves with no valid living target
- **THEN** no additional player SHALL be eliminated

### Requirement: Little Girl

The Little Girl SHALL be a passive village role; her spying mechanic SHALL be presented in the UI without engine interaction.

#### Scenario: No engine effect
- **WHEN** night runs with a Little Girl present
- **THEN** the role SHALL not wake or alter state

### Requirement: Minion

The Minion SHALL be wolf-team with no night action and SHALL know the wolves; its `check_win` SHALL report a wolves win under the same numeric condition as the wolves.

#### Scenario: Minion excluded from village count
- **WHEN** computing the wolves-versus-village balance
- **THEN** the Minion SHALL not be counted among villagers

### Requirement: Scapegoat

The Scapegoat SHALL be a passive village role whose effect SHALL be applied by the engine during tied votes (see vote resolution).

#### Scenario: Passive at night
- **WHEN** the night sequence runs
- **THEN** the Scapegoat SHALL not wake

### Requirement: Sheriff

The Sheriff SHALL be a passive village role; being elected SHALL make that player's vote count double during vote resolution.

#### Scenario: Double vote after election
- **WHEN** an elected sheriff casts a vote
- **THEN** the target's tally SHALL increase by two
