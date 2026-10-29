import { setLanguage, storedLanguage, translate } from './i18n.js';
import { $ } from './dom.js';
import { connect, send } from './ws.js';
import * as tts from './tts.js';
import * as ui from './ui.js';
import * as setup from './views/setup.js';
import * as reveal from './views/reveal.js';
import * as night from './views/night.js';
import * as day from './views/day.js';
import * as vote from './views/vote.js';
import * as gameOver from './views/game_over.js';

// ── Global state ──────────────────────────────────────────────────────────────

let _state = { phase: 'setup', players: [], night_number: 0, winner: null };
let _nightDeaths = [];   // player_eliminated events accumulated during night

function getState() { return _state; }

// The palette follows the game clock; the vote happens at dusk.
const TIME_OF = {
  setup: 'night', role_reveal: 'night', night: 'night', day: 'day', vote: 'dusk',
};
const WINNER_TIME = { wolves: 'night', village: 'day', lovers: 'dusk' };

// ── View routing ───────────────────────────────────────────────────────────────

function showView(id) {
  document.querySelectorAll('.view').forEach(v => { v.hidden = v.id !== `view-${id}`; });
  window.scrollTo(0, 0);
}

function currentView() {
  const el = document.querySelector('.view:not([hidden])');
  return el ? el.id : null;
}

// ── Message handling ───────────────────────────────────────────────────────────

function handleMessage(msg) {
  switch (msg.type) {
    case 'state':             onState(msg.state); break;
    case 'night_role_wake':   onNightRoleWake(msg.data); break;
    case 'night_role_sleep':  night.onSleep(msg.data); break;
    case 'player_eliminated': onPlayerEliminated(msg.data); break;
    case 'narrate':           tts.speak(msg.data.text, msg.data.lang, msg.data.audio_url ?? null); break;
    case 'config':            onConfig(msg.config || {}); break;
    case 'error':             ui.toastError(msg); break;
  }
}

function onState(newState) {
  _state = newState;
  const phase = newState.phase;
  ui.setPhase(phase);
  ui.setTime(phase === 'game_over' ? WINNER_TIME[newState.winner] || 'day' : TIME_OF[phase] || 'night');

  const view = currentView();

  switch (phase) {
    case 'role_reveal':
      // Guard: only transition once; ignore subsequent state msgs with same phase
      if (view !== 'view-reveal') {
        showView('reveal');
        reveal.start(newState.players);
      }
      break;

    case 'night':
      // Don't interrupt an active night action view
      if (view !== 'view-night') {
        _nightDeaths = [];
        showView('night');
        night.showSleeping();
      }
      break;

    case 'day':
      // Guard: PHASE_CHANGED(day) and DAY_STARTED both broadcast state — only render once.
      if (view !== 'view-day') {
        showView('day');
        day.render(_nightDeaths);
        _nightDeaths = [];
      }
      break;

    case 'vote':
      if (view !== 'view-vote') {
        showView('vote');
        vote.start();
      }
      break;

    case 'game_over':
      showView('game-over');
      gameOver.render();
      break;

    case 'setup':
      if (view !== 'view-setup') showView('setup');
      break;
  }
}

function onNightRoleWake(data) {
  // The server enriches night_role_wake events (see game_server.py wire_events)
  // data.result    → seer revealed a player (needs acknowledgement via submit_pending_action)
  // data.player_id → hunter must shoot (can happen by day, after a vote)
  // otherwise      → regular night role action (submit_night_action)
  if (currentView() !== 'view-night') showView('night');
  night.onWake(data);
}

function onPlayerEliminated(data) {
  // Accumulate night deaths for the day announcement
  if (_state.phase === 'night') _nightDeaths.push(data);

  const p = _state.players.find(pl => pl.id === data.player_id);
  if (p) p.alive = false;

  const view = currentView();
  if (view === 'view-day') day.updateGrid();
  if (view === 'view-vote') vote.updateGrid();
}

function onConfig(cfg) {
  if (cfg.language) setLanguage(cfg.language);
  if (cfg.version) translate($('version-footer'), 'ui.app.version', { version: cfg.version });
}

// ── Init ───────────────────────────────────────────────────────────────────────

async function init() {
  // Last known language first; the server's configured one follows via get_config.
  await setLanguage(storedLanguage() || document.documentElement.lang);

  ui.mountScenery();
  ui.buildTrack();
  ui.setPhase('setup');
  ui.setTime('night');

  tts.init(send);
  setup.init(send);
  reveal.init(send);
  night.init(send, getState);
  day.init(send, getState);
  vote.init(send, getState);
  gameOver.init(getState, () => {
    reveal.reset();
    setup.reset();
    showView('setup');
    ui.setPhase('setup');
    ui.setTime('night');
  });

  const status = $('ws-status');
  connect({
    onMessage: handleMessage,
    onReady: () => { send('get_config'); send('get_state'); },
    onStatus: s => ui.setConnection(status, s),
  });

  showView('setup');
}

init();
