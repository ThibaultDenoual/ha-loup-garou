/**
 * core.js - Main Entry Point for Loup Garou Game UI
 *
 * Manages:
 * - WebSocket connection to /loup_garou/ws
 * - Game state from server
 * - Phase transitions
 * - View rendering orchestration
 * - Debug panel integration
 */

const LoupGarouCore = (function() {
    'use strict';

    // ============================================
    // Dependencies
    // ============================================

    const { $, $$, createWebSocket, debugLog, isDebugMode } = LoupGarouUtils;
    const { t } = LoupGarouI18n;

    // ============================================
    // State
    // ============================================

    const state = {
        ws: null,
        connected: false,
        currentPhase: 'setup',
        round: 0,
        players: [],
        roles: { villagers: 3, werewolves: 2, seers: 1 },
        winner: null,
        language: 'fr',
        revealIndex: 0,
        revealTotal: 0,
        nextRevealPlayer: null,
        eliminatedThisRound: [],
        voteTallies: {},
        votesCast: 0,
        aliveVoterCount: 0,
        currentNightRole: null,
        currentTargetId: null,
        nightActionsCompleted: [],
        nightActions: {
            wolfVictimId: null,
            seerTargetId: null,
            seerResult: null,
            completedRoles: [],
        },
        seerReveals: [],
        deadTonight: [],
        gameOver: false,
    };

    // View modules (setup by init())
    let views = {};

    // Callbacks for game.html integration
    let onStateUpdate = null;
    let onLog = null;

    // ============================================
    // WebSocket
    // ============================================

    function createConnection() {
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${protocol}//${location.host}/loup_garou/ws`;
        const ws = new WebSocket(url);

        ws.onopen = () => {
            state.connected = true;
            debugLog('[WS] Connected', 'info');
            updateStatusBar('status.connected');
            sendMessage('get_state', {});
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                handleMessage(data);
            } catch (e) {
                debugLog('[WS] Parse error: ' + e, 'error');
            }
        };

        ws.onerror = (err) => {
            debugLog('[WS] Error', 'error');
            updateStatusBar('status.error');
        };

        ws.onclose = () => {
            state.connected = false;
            debugLog('[WS] Disconnected', 'info');
            updateStatusBar('status.error');
            setTimeout(createConnection, 3000);
        };

        state.ws = ws;
    }

    function sendMessage(type, data = {}) {
        if (state.ws && state.ws.readyState === WebSocket.OPEN) {
            state.ws.send(JSON.stringify({ type, ...data }));
        } else {
            debugLog('[WS] Not connected, cannot send: ' + type, 'warn');
        }
    }

    // ============================================
    // Message Handlers
    // ============================================

    function handleMessage(data) {
        debugLog('[WS] ← ' + data.type + ' ' + JSON.stringify(data.data || data.message || '').slice(0, 80), 'info');

        switch (data.type) {
            case 'state':
                onStateReceived(data.data);
                break;
            case 'error':
                onError(data);
                break;
            case 'connected':
                state.connected = true;
                updateStatusBar('status.connected');
                break;
            default:
                debugLog('[WS] Unknown type: ' + data.type, 'warn');
        }
    }

    function onStateReceived(data) {
        if (!data) return;

        state.currentPhase = data.phase || 'setup';
        state.round = data.round || 0;
        state.players = data.players || [];
        state.winner = data.winner || null;
        state.language = data.language || 'fr';
        state.revealIndex = data.reveal_index || 0;
        state.revealTotal = data.reveal_total || 0;
        state.nextRevealPlayer = data.next_reveal_player || null;
        state.eliminatedThisRound = data.eliminated_this_round || [];
        state.voteTallies = data.vote_tallies_count || {};
        state.votesCast = data.votes_cast || 0;
        state.aliveVoterCount = data.alive_voter_count || 0;
        state.currentNightRole = data.current_night_role || null;
        state.currentTargetId = data.current_target_id || null;
        state.nightActionsCompleted = data.night_actions_completed || [];

        // Check winner
        state.gameOver = (data.phase === 'game_over');
        state.winner = data.winner || null;

        // Update dead players
        state.players.forEach(p => {
            if (p.alive === false) {
                if (!state.deadTonight.includes(p.name)) {
                    state.deadTonight.push(p.name);
                }
            }
        });

        if (onStateUpdate) {
            onStateUpdate(getState());
        }

        if (window.updateDebugButtons) {
            window.updateDebugButtons(state.players);
        }

        renderCurrentView();
        updatePhaseLabel();
    }

    function onError(data) {
        debugLog('[Error] ' + (data.message || 'Unknown error'), 'err');
        showError(data.message || 'Unknown error');
        if (onLog) {
            onLog(data.message || 'Unknown error', 'err');
        }
    }

    // ============================================
    // View Rendering
    // ============================================

    function renderCurrentView() {
        const phase = state.currentPhase;
        debugLog('[View] Phase: ' + phase, 'info');

        hideAllViews();

        if (phase === 'setup' || phase === 'waiting_setup') {
            if (views.setup) {
                views.setup.show(getState());
            }
        } else if (phase === 'role_reveal') {
            if (views.reveal) {
                views.reveal.show(getState());
            }
        } else if (isNightPhase(phase)) {
            if (views.night) {
                views.night.show(getState());
            }
        } else if (phase === 'day' || phase === 'day_start' || phase === 'discussion') {
            if (views.day) {
                views.day.show(getState());
            }
        } else if (phase === 'vote' || phase === 'vote_start' || phase === 'vote_end') {
            if (views.vote) {
                views.vote.show(getState());
            }
        } else if (phase === 'game_over') {
            if (views.end) {
                views.end.show(getState());
            }
        } else {
            debugLog('[View] Unknown phase: ' + phase, 'warn');
        }
    }

    function isNightPhase(phase) {
        return phase === 'night_start' ||
            phase === 'night_seer_wake' ||
            phase === 'night_seer_act' ||
            phase === 'night_seer_sleep' ||
            phase === 'night_wolf_wake' ||
            phase === 'night_wolf_act' ||
            phase === 'night_wolf_sleep';
    }

    function hideAllViews() {
        if (views.setup) views.setup.hide();
        if (views.reveal) views.reveal.hide();
        if (views.night) views.night.hide();
        if (views.day) views.day.hide();
        if (views.vote) views.vote.hide();
        if (views.end) views.end.hide();
    }

    function updatePhaseLabel() {
        const labelEl = $('phase-label');
        if (labelEl) {
            const key = 'phase.' + state.currentPhase;
            labelEl.textContent = t(key, { phase: state.currentPhase });
        }
    }

    function updateStatusBar(key) {
        const statusEl = $('status-bar');
        if (statusEl && key) {
            statusEl.textContent = t(key);
            statusEl.classList.toggle('error', key === 'status.error');
        }
    }

    // ============================================
    // Transitions & Animations
    // ============================================

    function playPhaseTransition(phase) {
        const overlay = $('phase-overlay');
        if (!overlay) return;

        overlay.classList.remove('hidden');

        if (isNightPhase(phase)) {
            overlay.style.background = 'rgba(0, 0, 20, 0.95)';
        } else if (phase === 'day' || phase.startsWith('vote')) {
            overlay.style.background = 'rgba(255, 200, 100, 0.4)';
        } else {
            overlay.style.background = 'rgba(0, 0, 20, 0.9)';
        }

        const textEl = overlay.querySelector('.phase-overlay__text');
        if (textEl) {
            textEl.textContent = t('phase.' + phase, { phase });
        }

        setTimeout(() => {
            overlay.classList.add('hidden');
        }, 2000);
    }

    // ============================================
    // Error Handling
    // ============================================

    function showError(message) {
        const errorEl = $('error-message');
        if (errorEl) {
            errorEl.textContent = message;
            errorEl.classList.remove('hidden');
            setTimeout(() => errorEl.classList.add('hidden'), 5000);
        }
    }

    // ============================================
    // Game Actions (send to server)
    // ============================================

    function startGame() {
        const playerNames = state.players.map(p => p.name);
        if (playerNames.length < 5) {
            showError(t('setup.error_min_players'));
            return;
        }

        const totalRoles = Object.values(state.roles).reduce((a, b) => a + b, 0);
        if (totalRoles !== playerNames.length) {
            showError(t('setup.error_role_mismatch', {
                roles: totalRoles,
                players: playerNames.length
            }));
            return;
        }

        sendMessage('start_game', {
            player_names: playerNames,
            role_config: {
                villagers: state.roles.villagers,
                werewolves: state.roles.werewolves,
                seers: state.roles.seers,
            }
        });
    }

    function confirmRoleSeen() {
        sendMessage('confirm_role_seen', {});
    }

    function selectTarget(targetId) {
        sendMessage('select_target', { target_id: targetId });
    }

    function submitNightAction(actionType, targetId) {
        sendMessage('night_action', {
            action_type: actionType,
            target_id: targetId
        });
    }

    function skipAction() {
        sendMessage('skip_action', {});
    }

    function nextPhase() {
        sendMessage('next_phase', {});
    }

    function beginVote() {
        sendMessage('begin_vote', {});
    }

    function submitVote(voterId, targetId) {
        sendMessage('submit_vote', {
            voter_id: voterId,
            target_id: targetId
        });
    }

    function resolveVote() {
        sendMessage('resolve_votes', {});
    }

    function eliminatePlayer(playerId, cause) {
        sendMessage('eliminate_player', {
            player_id: playerId,
            cause: cause || 'village_vote'
        });
    }

    function resetGame() {
        sendMessage('reset', {});
        state.gameOver = false;
        state.winner = null;
        state.currentPhase = 'setup';
        state.round = 0;
        state.players = [];
        state.deadTonight = [];
        state.seerReveals = [];
    }

    // ============================================
    // Debug Actions
    // ============================================

    function debugNextPhase() {
        sendMessage('next_phase', {});
    }

    function debugBeginVote() {
        sendMessage('begin_vote', {});
    }

    function debugResolveVotes() {
        sendMessage('resolve_votes', {});
    }

    function debugWolfKill(targetId) {
        submitNightAction('wolf_kill', targetId);
    }

    function debugSeerInvestigate(targetId) {
        submitNightAction('seer_investigate', targetId);
    }

    function debugEliminate(playerId) {
        eliminatePlayer(playerId, 'village_vote');
    }

    // ============================================
    // Public API
    // ============================================

    function init(options = {}) {
        views = options.views || {};

        createConnection();

        if (options.onStateUpdate) {
            onStateUpdate = options.onStateUpdate;
        }
        if (options.onLog) {
            onLog = options.onLog;
        }

        debugLog('[Core] Initialized', 'info');
        return {
            getState,
            startGame,
            confirmRoleSeen,
            selectTarget,
            submitNightAction,
            skipAction,
            nextPhase,
            beginVote,
            submitVote,
            resolveVote,
            eliminatePlayer,
            resetGame,
            debugNextPhase,
            debugBeginVote,
            debugResolveVotes,
            debugWolfKill,
            debugSeerInvestigate,
            debugEliminate,
        };
    }

    function getState() {
        return {
            phase: state.currentPhase,
            round: state.round,
            players: state.players,
            winner: state.winner,
            language: state.language,
            revealIndex: state.revealIndex,
            revealTotal: state.revealTotal,
            nextRevealPlayer: state.nextRevealPlayer,
            eliminatedThisRound: state.eliminatedThisRound,
            voteTallies: state.voteTallies,
            votesCast: state.votesCast,
            aliveVoterCount: state.aliveVoterCount,
            currentNightRole: state.currentNightRole,
            currentTargetId: state.currentTargetId,
            nightActions: state.nightActions,
            nightActionsCompleted: state.nightActionsCompleted,
            deadTonight: state.deadTonight,
            gameOver: state.gameOver,
            connected: state.connected,
        };
    }

    return {
        init,
        getState,
        getRawState: () => ({ ...state }),
        startGame,
        confirmRoleSeen,
        selectTarget,
        submitNightAction,
        skipAction,
        nextPhase,
        beginVote,
        submitVote,
        resolveVote,
        eliminatePlayer,
        resetGame,
        debugNextPhase,
        debugBeginVote,
        debugResolveVotes,
        debugWolfKill,
        debugSeerInvestigate,
        debugEliminate,
        updateDebugButtons: null,
    };
})();

// Global alias for game.html compatibility
window.LoupGarouCore = LoupGarouCore;