"""Override autouse fixtures from pytest-homeassistant-custom-component that conflict with playwright."""
from __future__ import annotations

import re
import pytest
from pathlib import Path


@pytest.fixture(autouse=True)
def enable_event_loop_debug():
    pass


@pytest.fixture(autouse=True)
def verify_cleanup():
    yield


@pytest.fixture
def page(browser):
    page = browser.new_page()
    yield page
    page.close()


def _load_js_files():
    """Load all JS files and wrap them in separate IIFEs to avoid global scope conflicts."""
    root = Path(__file__).parent.parent.parent
    www = root / 'custom_components' / 'loup_garou' / 'www'

    i18n = (www / 'js' / 'i18n.js').read_text()
    utils = (www / 'js' / 'utils.js').read_text()

    views = []
    view_names = []
    for view in ['view-setup', 'view-reveal', 'view-night', 'view-day', 'view-vote', 'view-end']:
        path = www / 'js' / 'views' / f'{view}.js'
        if path.exists():
            content = path.read_text()
            views.append(content)
            # Extract view name from "const ViewName ="
            match = re.search(r'const\s+(View\w+)\s*=', content)
            view_names.append(match.group(1) if match else 'View')

    core = (www / 'js' / 'core.js').read_text()

    return i18n, utils, views, view_names, core


def _build_init_script():
    i18n, utils, views, view_names, core = _load_js_files()

    scripts = []

    # i18n
    scripts.append(f"""
(function() {{
{i18n}
window.LoupGarouI18n = LoupGarouI18n;
}})();
""")

    # utils - fix function names
    utils_fixed = utils.replace('function show(el)', 'function _show(el)')
    utils_fixed = utils_fixed.replace('function hide(el)', 'function _hide(el)')
    utils_fixed = utils_fixed.replace('function showToast(', 'function _showToast(')
    scripts.append(f"""
(function() {{
{utils_fixed}
window.LoupGarouUtils = LoupGarouUtils;
}})();
""")

    # views - fix function names and export
    for i, v in enumerate(views):
        v_fixed = v.replace('function show(', 'function _view_show(')
        v_fixed = v_fixed.replace('function hide(', 'function _view_hide(')
        view_name = view_names[i]
        scripts.append(f"""
(function() {{
{v_fixed}
window.{view_name} = {view_name};
}})();
""")

    # core
    scripts.append(f"""
(function() {{
{core}
window.LoupGarouCore = LoupGarouCore;
}})();
""")

    return '\n'.join(scripts)


_INIT_SCRIPT = None


def _get_init_script():
    global _INIT_SCRIPT
    if _INIT_SCRIPT is None:
        _INIT_SCRIPT = _build_init_script()
    return _INIT_SCRIPT


@pytest.fixture
def mock_ws(page):
    page.add_init_script(_get_init_script())
    page.add_init_script("""
        (function() {
            var gameState = {
                phase: 'setup',
                round: 0,
                players: [],
                language: 'fr',
                winner: null,
                reveal_index: 0,
                reveal_total: 0,
                next_reveal_player: null,
                eliminated_this_round: [],
                vote_tallies_count: {},
                votes_cast: 0,
                alive_voter_count: 0,
                current_night_role: null,
                current_target_id: null,
                night_actions_completed: []
            };

            var messageHandlers = [];

            window.WebSocket = function(url) {
                this.url = url;
                this.readyState = 1;
                this.send = function(data) {
                    var msg = JSON.parse(data);
                    // Handle messages from the game
                    if (msg.type === 'get_state') {
                        // Return current game state
                        setTimeout(function() {
                            if (self.onmessage) {
                                self.onmessage({ data: JSON.stringify({
                                    type: 'state',
                                    data: gameState
                                })});
                            }
                        }, 10);
                    } else if (msg.type === 'start_game') {
                        // Start game - create players with roles
                        var playerNames = msg.player_names || [];
                        // Fixed role assignment for 6 players: 1 seer, 2 wolves, 3 villagers
                        var roles = ['seer', 'wolf', 'wolf', 'villager', 'villager', 'villager'];
                        gameState.players = playerNames.map(function(name, i) {
                            return { id: 'p' + (i+1), name: name, alive: true, role_seen: false, role: roles[i] || 'villager' };
                        });
                        gameState.phase = 'role_reveal';
                        gameState.reveal_index = 0;
                        gameState.reveal_total = playerNames.length;
                        gameState.round = 1;
                        gameState.alive_voter_count = playerNames.length;
                        if (playerNames.length > 0) {
                            gameState.next_reveal_player = gameState.players[0];
                        }
                        setTimeout(function() {
                            if (self.onmessage) {
                                self.onmessage({ data: JSON.stringify({
                                    type: 'state',
                                    data: gameState
                                })});
                            }
                        }, 10);
                    } else if (msg.type === 'next_phase') {
                        // Advance to next phase
                        var nextPhase = gameState.phase;
                        if (gameState.phase === 'role_reveal') {
                            // After role reveal, go to night
                            nextPhase = 'night_start';
                            gameState.next_reveal_player = null;
                            gameState.current_night_role = 'seer';
                        } else if (gameState.phase === 'night_start') {
                            nextPhase = 'night_seer_wake';
                        } else if (gameState.phase === 'night_seer_wake') {
                            nextPhase = 'night_seer_act';
                        } else if (gameState.phase === 'night_seer_act') {
                            nextPhase = 'night_seer_sleep';
                        } else if (gameState.phase === 'night_seer_sleep') {
                            nextPhase = 'night_wolf_wake';
                        } else if (gameState.phase === 'night_wolf_wake') {
                            nextPhase = 'night_wolf_act';
                        } else if (gameState.phase === 'night_wolf_act') {
                            nextPhase = 'night_wolf_sleep';
                        } else if (gameState.phase === 'night_wolf_sleep') {
                            nextPhase = 'day_start';
                            gameState.current_night_role = null;
                        } else if (gameState.phase === 'day_start') {
                            nextPhase = 'day';
                        } else if (gameState.phase === 'day') {
                            nextPhase = 'vote';
                        } else if (gameState.phase === 'vote') {
                            nextPhase = 'day';
                        }
                        gameState.phase = nextPhase;
                        setTimeout(function() {
                            if (self.onmessage) {
                                self.onmessage({ data: JSON.stringify({
                                    type: 'state',
                                    data: gameState
                                })});
                            }
                        }, 10);
                    } else if (msg.type === 'confirm_role_seen') {
                        // Player confirmed seeing their role - advance reveal
                        gameState.reveal_index++;
                        if (gameState.reveal_index < gameState.reveal_total) {
                            gameState.next_reveal_player = gameState.players[gameState.reveal_index];
                        } else {
                            gameState.next_reveal_player = null;
                            // All players seen - transition to night_start
                            gameState.phase = 'night_start';
                        }
                        setTimeout(function() {
                            if (self.onmessage) {
                                self.onmessage({ data: JSON.stringify({
                                    type: 'state',
                                    data: gameState
                                })});
                            }
                        }, 10);
                    } else if (msg.type === 'reset') {
                        // Reset game to setup
                        gameState.phase = 'setup';
                        gameState.round = 0;
                        gameState.players = [];
                        gameState.reveal_index = 0;
                        gameState.reveal_total = 0;
                        gameState.next_reveal_player = null;
                        setTimeout(function() {
                            if (self.onmessage) {
                                self.onmessage({ data: JSON.stringify({
                                    type: 'state',
                                    data: gameState
                                })});
                            }
                        }, 10);
                    }
                };
                this.close = function() {};
                var self = this;
                setTimeout(function() { if (self.onopen) self.onopen({}); }, 10);
            };
            window.WebSocket.OPEN = 1;
            window.WebSocket.CLOSED = 3;

            window._setGameState = function(state) {
                Object.assign(gameState, state);
            };

            window._getGameState = function() {
                return gameState;
            };

            if (window.location.search.includes('debug=1')) {
                localStorage.setItem('lg_debug', '1');
            }
        })();
    """)
    return page


@pytest.fixture
def game_url():
    root = Path(__file__).parent.parent.parent
    return f"file://{root / 'custom_components' / 'loup_garou' / 'www' / 'game.html'}"


@pytest.fixture
def launcher_url():
    root = Path(__file__).parent.parent.parent
    return f"file://{root / 'custom_components' / 'loup_garou' / 'www' / 'launcher.html'}"


@pytest.fixture
def goto_game(mock_ws, page, game_url):
    page.goto(game_url)
    page.wait_for_timeout(1500)
    return page


@pytest.fixture
def goto_launcher(mock_ws, page, launcher_url):
    page.goto(launcher_url)
    page.wait_for_timeout(800)
    return page


@pytest.fixture
def index_url():
    root = Path(__file__).parent.parent.parent
    return f"file://{root / 'custom_components' / 'loup_garou' / 'www' / 'index.html'}"


@pytest.fixture
def goto_index(mock_ws, page, index_url):
    page.goto(index_url)
    page.wait_for_timeout(800)
    return page


@pytest.fixture
def night_state():
    return {
        "phase": "night_wolf_act", "round": 1,
        "players": [
            {"id": "p1", "name": "Alice", "alive": True, "role": "villager"},
            {"id": "p2", "name": "Bob", "alive": True, "role": "werewolf"},
            {"id": "p3", "name": "Charlie", "alive": True, "role": "seer"},
            {"id": "p4", "name": "Diana", "alive": True, "role": "villager"},
            {"id": "p5", "name": "Eve", "alive": True, "role": "villager"},
        ],
        "winner": None, "language": "fr",
        "reveal_index": 5, "reveal_total": 5, "next_reveal_player": None,
        "eliminated_this_round": [], "vote_tallies_count": {},
        "votes_cast": 0, "alive_voter_count": 5,
        "current_night_role": "werewolf",
        "current_target_id": None, "night_actions_completed": [],
    }


@pytest.fixture
def vote_state():
    return {
        "phase": "vote", "round": 1,
        "players": [
            {"id": "p1", "name": "Alice", "alive": True, "role": "villager"},
            {"id": "p2", "name": "Bob", "alive": True, "role": "werewolf"},
            {"id": "p3", "name": "Charlie", "alive": True, "role": "seer"},
            {"id": "p4", "name": "Diana", "alive": True, "role": "villager"},
            {"id": "p5", "name": "Eve", "alive": True, "role": "villager"},
        ],
        "winner": None, "language": "fr",
        "reveal_index": 5, "reveal_total": 5, "next_reveal_player": None,
        "eliminated_this_round": [], "vote_tallies_count": {"p1": 2, "p3": 3},
        "votes_cast": 5, "alive_voter_count": 5,
        "current_night_role": None,
        "current_target_id": None, "night_actions_completed": [],
    }


@pytest.fixture
def goto_reveal_phase(mock_ws, page, game_url):
    """Navigate to game.html and advance to role_reveal phase."""
    page.goto(f"{game_url}?debug=1")
    page.wait_for_timeout(1500)

    # Fill in player names using preset
    # Select 'small' preset which has 6 players
    page.click(".preset-btn[data-preset='small']")
    page.wait_for_timeout(300)

    # Update player names (preset has 6 empty slots)
    inputs = page.locator("input.input[type='text']")
    inputs.nth(0).fill("Alice")
    inputs.nth(1).fill("Bob")
    inputs.nth(2).fill("Charlie")
    inputs.nth(3).fill("Diana")
    inputs.nth(4).fill("Eve")
    inputs.nth(5).fill("Frank")

    # Click start game button
    page.click("#start-game-btn")
    # Wait for WebSocket response to be processed
    page.wait_for_timeout(2000)

    return page


@pytest.fixture
def goto_night_phase(goto_reveal_phase):
    """Navigate to game.html and advance to night phase (after role reveal)."""
    # Click through all role reveals
    for _ in range(6):
        confirm_btn = goto_reveal_phase.locator("#reveal-confirm-btn, .reveal-confirm-btn")
        if confirm_btn.count() > 0:
            confirm_btn.click()
            goto_reveal_phase.wait_for_timeout(500)
    # Then advance to night
    goto_reveal_phase.click("#debug-next-phase")
    goto_reveal_phase.wait_for_timeout(500)
    return goto_reveal_phase