# Phase 5 Testing Plan — Full Game Flow Verification

## Overview

This document outlines the end-to-end testing strategy for the Loup Garou frontend refactoring. Tests verify the complete game cycle from setup through game over, ensuring frontend-backend integration works correctly.

**Prerequisites:**
- Home Assistant running with Loup Garou integration loaded
- Web browser with developer console (`?debug=1` for debug panel)
- At least 5 players for full game testing

---

## Test Checklist

### Phase 5.1: Basic Game Flow (Critical)

#### 1.1 Launcher & Entry
- [ ] `launcher.html` loads without console errors
- [ ] "Lancer le Jeu" opens `game.html` in new tab
- [ ] "Ouvrir dans cet onglet" navigates to game.html

#### 1.2 Setup Phase
- [ ] Debug panel visible with `?debug=1` URL parameter
- [ ] Debug panel hidden without debug flag
- [ ] Add player input accepts names
- [ ] Player list updates when adding players
- [ ] Can remove players from list
- [ ] Role preset buttons update role config
- [ ] "Commencer la partie" sends `start_game` WS message
- [ ] Error toast appears with invalid config (< 5 players)

#### 1.3 Role Reveal Phase
- [ ] Reveal view shows current player name
- [ ] "J'ai vu mon rôle" button advances reveal
- [ ] Progress shows "X/Y" players seen
- [ ] After all reveals, transitions to night phase
- [ ] Header shows round number after reveal

#### 1.4 Night Phase
- [ ] Night view displays "Le village s'endort..."
- [ ] Seer wake: "Voyante, ouvrez les yeux..."
- [ ] Seer can select another player as target
- [ ] Confirm button advances to next role
- [ ] Wolf wake: "Loups-garous, ouvrez les yeux..."
- [ ] Wolves can select victim
- [ ] Day resolution shows eliminated players
- [ ] Stars background visible during night

#### 1.5 Day Phase
- [ ] Day view shows alive players list
- [ ] Dead players from night shown separately
- [ ] "Commencer le vote" transitions to vote view
- [ ] "Passer (sans vote)" skips to next night

#### 1.6 Vote Phase
- [ ] Vote view shows all alive players
- [ ] Each player can vote (click target)
- [ ] Vote counter shows "X/Y" votes cast
- [ ] "Terminer le vote" resolves elimination
- [ ] Tie handling: no elimination on tie

#### 1.7 Game Over
- [ ] Winner banner shows correct team
- [ ] "Nouvelle partie" resets to setup
- [ ] Phase overlay shows during transitions

---

### Phase 5.2: Backend Integration (High)

#### 2.1 WebSocket Message Types
| Message | Expected Response |
|---------|-------------------|
| `get_state` | Full state object |
| `start_game` | Phase = `role_reveal` |
| `confirm_role_seen` | Increment reveal_index |
| `next_phase` | Advance to next phase |
| `night_action` | Store target, return state |
| `begin_vote` | Phase = `vote` |
| `submit_vote` | Update vote tallies |
| `resolve_votes` | Eliminate player |
| `reset` | Phase = `setup` |

#### 2.2 State Synchronization
- [ ] Frontend receives state on every phase change
- [ ] Header stats (round, alive count) update correctly
- [ ] View renders based on `state.phase`
- [ ] Debug buttons update when players change

#### 2.3 Error Handling
- [ ] Server errors show as toast notifications
- [ ] Disconnected state shows in WS indicator
- [ ] Auto-reconnect after network drop

---

### Phase 5.3: Edge Cases (Medium)

#### 3.1 Game Configurations
- [ ] 5 players (minimum) — small preset works
- [ ] 6-8 players — medium preset works
- [ ] 9+ players — large preset works
- [ ] Custom role config validates correctly

#### 3.2 Win Conditions
- [ ] Wolves win when wolves >= villagers
- [ ] Village wins when all wolves eliminated
- [ ] Solo roles (Jester, Serial Killer) win correctly

#### 3.3 UI Edge Cases
- [ ] Long player names truncate properly
- [ ] Empty player name rejected
- [ ] Duplicate player name shows error
- [ ] Network disconnect shows reconnecting state

---

### Phase 5.4: Mobile Compatibility (Medium)

- [ ] Viewport scales correctly on mobile
- [ ] Touch targets are minimum 44px
- [ ] Debug panel stacks vertically on narrow screens
- [ ] Phase overlay fits smaller screens
- [ ] No horizontal scroll on any viewport

---

### Phase 5.5: Debug Panel (Low)

#### Debug Navigation
- [ ] Reset button sends `reset` message
- [ ] "Phase suivante" sends `next_phase`
- [ ] "Commencer vote" sends `begin_vote`
- [ ] "Résoudre votes" sends `resolve_votes`

#### Dynamic Debug Buttons
- [ ] Elimination buttons for each alive player
- [ ] Wolf kill buttons for non-wolf players
- [ ] Seer investigate buttons for all players

#### Log Area
- [ ] Shows timestamped messages
- [ ] Auto-scrolls to bottom
- [ ] Color-codes message types

---

## Test Execution Order

```
1. Setup Phase Tests
   └── Run: Manual browser test with debug=1

2. Role Reveal → Night → Day → Vote → End
   └── Run: Complete game with 6 players, medium preset

3. Edge Cases
   └── Run: Minimum players, maximum players

4. Mobile Test
   └── Run: Chrome DevTools device toolbar

5. Backend Tests
   └── Run: pytest tests/e2e/ (future)
```

---

## Manual Test Script

```bash
# Step 1: Start HA and navigate to:
# http://homeassistant:8123/loup_garou/launcher.html?debug=1

# Step 2: Add players (click, type, Enter):
# Alice, Bob, Charlie, Diana, Eve, Frank

# Step 3: Click "medium" preset

# Step 4: Click "Commencer la partie"

# Step 5: For each player:
# - Click "J'ai vu mon rôle"

# Step 6: Night phase:
# - Click seer player → click "Continuer"
# - Click wolf victim → click "Continuer"

# Step 7: Day phase:
# - Review eliminated players
# - Click "Commencer le vote"

# Step 8: Vote:
# - Click on player to vote
# - Click "Terminer le vote"

# Step 9: Either win or continue:
# - If game over: verify winner → click "Nouvelle partie"
# - If continue: repeat steps 6-8

# Step 10: Use debug panel to skip ahead
```

---

## Known Issues to Verify Fixed

| Issue | Expected Fix |
|-------|--------------|
| www/ vs wwwOLD file paths | All JS/CSS in subdirs, HTML paths updated |
| Missing inline styles converted | No inline styles in game.html |
| Debug panel missing | Full debug panel with styling |
| Mobile layout broken | Responsive breakpoints at 768px, 480px |
| Phase mapping mismatch | Frontend PHASE_VIEW_MAP matches backend phases |

---

## Future: Automated E2E Tests

```python
# tests/e2e/test_game_flow.py
import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By

class TestGameFlow:
    def test_complete_game(self):
        driver = webdriver.Chrome()
        driver.get("http://ha/loup_garou/launcher.html?debug=1")

        # Add players
        for name in ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank"]:
            driver.find_element(By.ID, "setup-player-input").send_keys(name)
            driver.find_element(By.ID, "setup-add-btn").click()

        # Start game
        driver.find_element(By.ID, "setup-start-btn").click()

        # Complete role reveal
        for _ in range(6):
            driver.find_element(By.ID, "reveal-confirm-btn").click()

        # Verify night phase
        assert "view-night" in driver.page_source

        # ... continue for full flow
```

---

## Notes

- Debug panel requires `?debug=1` or `localStorage.setItem('lg_debug', '1')`
- Use browser developer console to see `debugLog` output
- Phase transitions may take 2-3 seconds (configured delay)
- Use debug buttons to speed up testing

---

**Last Updated:** 2026-05-15
**Branch:** feature/frontend-refactoring-phase2