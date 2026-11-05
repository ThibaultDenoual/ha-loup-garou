## Decisions
- **A coroutine, not a saved state machine.** A game does not survive an HA restart (owner's decision), so one task owned by the server runs the game and pauses in `GameEngine.ask()`.
- **Narration completes before a prompt opens.** Wake events are awaited first, so a control can't exist before the core accepts it. Silence in the UI is simply "no prompt".
- **Picks are data.** A prompt lists named picks with `options` and allowed `counts`. One validator covers all roles and the UI renders from it.
- **The demo uses prompts** but drives phases from its script, and may abstain on ballots, so presets stay short.
- **No protocol version check.** The game's static files are served without cache headers, and an old page has no snapshot handler to run such a check.
