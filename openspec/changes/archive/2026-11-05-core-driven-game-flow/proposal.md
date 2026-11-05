## Why
The core and the UI both decide what happens next. The UI runs the reveal and collects ballots, the core accepts any command at any time, and an action sent during narration is silently dropped.

## What Changes
- **BREAKING** The core runs the whole game as one loop that opens one prompt at a time. Answering the open prompt is the only way to advance a game.
- **BREAKING** The WebSocket sends full snapshots instead of state and event messages. `begin_night`, `begin_vote`, `resolve_vote`, `submit_night_action`, `submit_pending_action` and `elect_sheriff` are removed.
- Roles declare their legal choices; the core validates answers against them.
- Role identities stop being sent for living players.
- Fixes wrong death causes, out-of-turn votes, the unreachable Sheriff election and the repeated vote announcement.

Out of scope: surviving an HA restart, the Little Girl and Minion mechanics, `save_config` validation.

## Capabilities
### New Capabilities
- `game-protocol`: prompts, answers and snapshots between the core and the browser.
