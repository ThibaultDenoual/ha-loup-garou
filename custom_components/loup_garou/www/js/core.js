/* ═══════════════════════════════════════════
   LOUP GAROU — Core
   Entry point, state management, WS routing
   ═══════════════════════════════════════════ */

const LoupGarouCore = (() => {
  const { qs, setHTML, setText, showToast, createWebSocket, debugLog, addClass, removeClass, createStars } = LoupGarouUtils;
  const { t, setLanguage, getRoleTeam } = LoupGarouI18n;

  // ── State ──
  let _ws     = null;
  let _state  = null;  // Last known game state from server
  let _views  = {};
  let _debugLogFetchTimer = null;
  let _lastBackendLogCount = 0;

  // ── Phase → view mapping ──
  const PHASE_VIEW_MAP = {
    'setup':            'setup',
    'role_reveal':      'reveal',
    'night_start':      'night',
    'night_seer_wake':  'night',
    'night_seer_act':   'night',
    'night_seer_sleep': 'night',
    'night_wolf_wake':  'night',
    'night_wolf_act':   'night',
    'night_wolf_sleep': 'night',
    'day_start':        'day',
    'day':              'day',
    'discussion':       'day',
    'vote':             'vote',
    'resolve_day':      'day',
    'game_over':        'end',
  };

  /* ──────────────────────────────────────────
     INIT
     ────────────────────────────────────────── */
  function init() {
    _setupViews();
    _setupWS();
    _setupStars();
    _showView('setup');
    _renderSetupView();
  }

  function _setupViews() {
    _views = {
      setup:  ViewSetup,
      reveal: ViewReveal,
      night:  ViewNight,
      day:    ViewDay,
      vote:   ViewVote,
      end:    ViewEnd,
    };
  }

  function _setupStars() {
    const starsEl = qs('#stars-layer');
    if (starsEl) LoupGarouUtils.createStars(starsEl, 70);
  }

  /* ──────────────────────────────────────────
     WEBSOCKET
     ────────────────────────────────────────── */
  function _setupWS() {
    _ws = createWebSocket('/loup_garou/ws', {
      onMessage: _handleMessage,
      onOpen:    _onWsOpen,
      onClose:   _onWsClose,
      onStatus:  _updateWsStatus,
    });
  }

  function _onWsOpen() {
    // Request current state on connect
    _ws.send({ type: 'get_state' });
    // Start polling for backend debug logs
    _startDebugLogPoll();
  }

  function _startDebugLogPoll() {
    if (_debugLogFetchTimer) clearInterval(_debugLogFetchTimer);
    _debugLogFetchTimer = setInterval(() => {
      if (_ws && _ws.isConnected()) {
        _ws.send({ type: 'get_debug_log' });
      }
    }, 2000);
  }

  function _onWsClose() { /* reconnect handled by utils */ }

  function _updateWsStatus(status) {
    const dot = qs('#ws-status');
    if (!dot) return;
    dot.className = `ws-status ${status}`;
    const label = qs('#ws-label');
    if (label) label.textContent = t(`app.${status}`) || status;
  }

  function _send(msg) {
    if (!_ws.isConnected()) {
      showToast(t('app.disconnected'), { type: 'error' });
      return false;
    }
    return _ws.send(msg);
  }

  /* ──────────────────────────────────────────
     MESSAGE HANDLER
     ────────────────────────────────────────── */
  function _handleMessage(msg) {
    debugLog('WS message', msg);

    if (msg.type === 'error') {
      showToast(msg.message || 'Erreur serveur', { type: 'error' });
      return;
    }

    if (msg.type === 'state') {
      _applyState(msg.data);
      return;
    }

    if (msg.type === 'debug_log') {
      _handleDebugLog(msg.data);
      return;
    }
  }

  function _handleDebugLog(logs) {
    if (!logs || !Array.isArray(logs)) return;
    // Only show new logs
    if (logs.length > _lastBackendLogCount) {
      const newLogs = logs.slice(_lastBackendLogCount);
      for (const entry of newLogs) {
        const type = entry.level === 'error' ? 'error' : entry.level === 'warn' ? 'warn' : '';
        if (typeof window.logMsg === 'function') {
          window.logMsg(`[BACKEND] ${entry.message}`, type);
        }
      }
      _lastBackendLogCount = logs.length;
    }
  }

  function _applyState(newState) {
    if (!newState) return;
    const prevPhase = _state ? _state.phase : null;
    _state = newState;

    // Sync language
    if (_state.language) {
      setLanguage(_state.language);
    }

    // Update header info
    _updateHeader();

    // Update debug buttons
    if (typeof window.updateDebugButtons === 'function') {
      window.updateDebugButtons(_state.players);
    }

    // Route to correct view
    _renderCurrentView(prevPhase);
  }

  /* ──────────────────────────────────────────
     VIEW ROUTING
     ────────────────────────────────────────── */
  function _showView(viewName) {
    // Hide all views
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));

    const el = qs(`#view-${viewName}`);
    if (el) el.classList.add('active');

    // Body phase class for ambient
    document.body.className = document.body.className.replace(/phase-\w+/g, '').trim();
    const phaseClass = {
      setup:  'phase-setup',
      reveal: 'phase-night',
      night:  'phase-night',
      day:    'phase-day',
      vote:   'phase-vote',
      end:    'phase-gameover',
    }[viewName];
    if (phaseClass) document.body.classList.add(phaseClass);

    // Stars visible at night
    const starsEl = qs('#stars-layer');
    if (starsEl) {
      if (viewName === 'night' || viewName === 'reveal') {
        starsEl.classList.add('visible');
      } else {
        starsEl.classList.remove('visible');
      }
    }
  }

  function _renderCurrentView(prevPhase) {
    if (!_state) return;
    const phase    = _state.phase || 'setup';
    const viewName = PHASE_VIEW_MAP[phase] || 'setup';

    _showView(viewName);

    switch (viewName) {
      case 'setup':
        _renderSetupView();
        break;
      case 'reveal':
        _renderRevealView();
        break;
      case 'night':
        _renderNightView();
        break;
      case 'day':
        _renderDayView();
        break;
      case 'vote':
        _renderVoteView();
        break;
      case 'end':
        _renderEndView();
        break;
    }
  }

  /* ──────────────────────────────────────────
     HEADER
     ────────────────────────────────────────── */
  function _updateHeader() {
    if (!_state) return;
    const roundEl = qs('#header-round');
    if (roundEl && _state.round > 0) {
      roundEl.textContent = `${t('common.round')} ${_state.round}`;
    }
    const aliveEl = qs('#header-alive');
    if (aliveEl && _state.alive_count != null) {
      aliveEl.textContent = `${_state.alive_count} ${t('common.alive').toLowerCase()}`;
    }
  }

  /* ──────────────────────────────────────────
     SETUP VIEW
     ────────────────────────────────────────── */
  function _renderSetupView() {
    ViewSetup.render({
      language: _state ? _state.language : 'fr',
      onStart: (payload) => {
        _send({ type: 'start_game', ...payload });
      }
    });
  }

  /* ──────────────────────────────────────────
     REVEAL VIEW
     ────────────────────────────────────────── */
  function _renderRevealView() {
    ViewReveal.render(_state, {
      onConfirm: (playerId) => {
        _send({ type: 'confirm_role_seen', player_id: playerId });
      }
    });
  }

  /* ──────────────────────────────────────────
     NIGHT VIEW
     ────────────────────────────────────────── */
  function _renderNightView() {
    const phase = _state.phase || '';
    ViewNight.render(_state, {
      onNextPhase: () => {
        _send({ type: 'next_phase' });
      },
      onAction: (actionType, targetId) => {
        _send({ type: 'night_action', action_type: actionType, target_id: targetId });
      },
      onSkip: (actionType) => {
        _send({ type: 'skip_action', action_type: actionType });
      }
    });
  }

  /* ──────────────────────────────────────────
     DAY VIEW
     ────────────────────────────────────────── */
  function _renderDayView() {
    ViewDay.render(_state, {
      onGoVote: () => {
        _send({ type: 'begin_vote' });
      },
      onSkipVote: () => {
        _send({ type: 'next_phase' });
      }
    });
  }

  /* ──────────────────────────────────────────
     VOTE VIEW
     ────────────────────────────────────────── */
  function _renderVoteView() {
    ViewVote.render(_state, {
      onVote: (voterId, targetId) => {
        _send({ type: 'submit_vote', voter_id: voterId, target_id: targetId });
      },
      onResolve: () => {
        _send({ type: 'resolve_votes' });
      },
      onCancel: () => {
        _send({ type: 'next_phase' });
      }
    });
  }

/* ──────────────────────────────────────────
      END VIEW
      ────────────────────────────────────────── */
  function _renderEndView() {
    ViewEnd.render(_state, {
      onPlayAgain: () => {
        _send({ type: 'reset' });
      }
    });
  }

  /* ──────────────────────────────────────────
     DEBUG ACTIONS
     ────────────────────────────────────────── */
  function resetGame() {
    _send({ type: 'reset' });
  }

  function debugNextPhase() {
    _send({ type: 'next_phase' });
  }

  function debugBeginVote() {
    _send({ type: 'begin_vote' });
  }

  function debugResolveVotes() {
    _send({ type: 'resolve_votes' });
  }

  function debugWolfKill(targetId) {
    _send({ type: 'night_action', action_type: 'werewolf_kill', target_id: targetId });
    debugNextPhase();
  }

  function debugSeerInvestigate(targetId) {
    _send({ type: 'night_action', action_type: 'seer_investigate', target_id: targetId });
    debugNextPhase();
  }

  function debugEliminate(playerId) {
    _send({ type: 'eliminate_player', player_id: playerId });
  }

  function debugTestTts(message) {
    _send({ type: 'test_tts', message: message || 'Test de la synthèse vocale' });
  }

/* ──────────────────────────────────────────
      PUBLIC
      ────────────────────────────────────────── */
  return {
    init,
    resetGame,
    debugNextPhase,
    debugBeginVote,
    debugResolveVotes,
    debugWolfKill,
    debugSeerInvestigate,
    debugEliminate,
    debugTestTts,
    get ws() { return _ws; },
  };
})();

// Boot on DOM ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', LoupGarouCore.init);
} else {
  LoupGarouCore.init();
}
