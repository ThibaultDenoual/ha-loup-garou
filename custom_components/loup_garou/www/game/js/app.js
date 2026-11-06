import { setLanguage, storedLanguage, translate } from './i18n.js';
import { $ } from './dom.js';
import { connect, send } from './ws.js';
import * as tts from './tts.js';
import * as ui from './ui.js';
import { sprite } from './sprites.js';
import * as setup from './views/setup.js';
import * as reveal from './views/reveal.js';
import * as night from './views/night.js';
import * as day from './views/day.js';
import * as vote from './views/vote.js';
import * as gameOver from './views/game_over.js';

// ── Global state ──────────────────────────────────────────────────────────────

// The latest snapshot from the core. The page keeps no game state of its own.
let _state = { phase: 'setup', players: [], night: 0, winner: null, news: null, prompt: null };
let _renderedKey = null;

function getState() { return _state; }

function answer(fields = {}) {
  if (_state.prompt) send('answer', { prompt_id: _state.prompt.id, answer: fields });
}

// The palette follows the game clock; the vote happens at dusk.
const TIME_OF = {
  setup: 'night', role_reveal: 'night', night: 'night', day: 'day', vote: 'dusk',
};
const WINNER_TIME = { wolves: 'night', village: 'day', lovers: 'dusk' };

// Prompts played on the night screen, in whichever phase they open.
const NIGHT_PROMPTS = new Set(['night_action', 'seer_result', 'hunter_shot', 'sheriff_election']);

const VIEW_OF = {
  setup: 'setup', role_reveal: 'reveal', night: 'night', day: 'day', vote: 'vote', game_over: 'game-over',
};

// ── View routing ───────────────────────────────────────────────────────────────

function showView(id) {
  const view = `view-${id}`;
  if (currentView() === view) return;
  document.querySelectorAll('.view').forEach(v => { v.hidden = v.id !== view; });
  window.scrollTo(0, 0);
}

function currentView() {
  const el = document.querySelector('.view:not([hidden])');
  return el ? el.id : null;
}

// ── Message handling ───────────────────────────────────────────────────────────

function handleMessage(msg) {
  switch (msg.type) {
    case 'snapshot':  onSnapshot(msg.state); break;
    case 'narrate':   tts.speak(msg.data.text, msg.data.lang, msg.data.audio_url ?? null, msg.data.audio_seconds ?? null); break;
    case 'config':    onConfig(msg.config || {}); break;
    case 'error':     ui.toastError(msg); break;
  }
}

// Everything on screen comes from here: the snapshot says what the game is
// waiting for, and the view for it is drawn once per prompt.
function onSnapshot(snapshot) {
  _state = snapshot;
  const { phase, prompt, winner } = snapshot;
  ui.setPhase(phase);
  ui.setTime(phase === 'game_over' ? WINNER_TIME[winner] || 'day' : TIME_OF[phase] || 'night');
  // A finished game already offers "New game".
  $('btn-abandon').hidden = phase === 'setup' || phase === 'game_over';
  if ($('btn-abandon').hidden) closeAbandon();

  const key = `${phase}|${prompt ? prompt.id : ''}`;
  if (key === _renderedKey) return;
  _renderedKey = key;

  const nightPrompt = prompt && NIGHT_PROMPTS.has(prompt.kind);
  const view = nightPrompt ? 'night' : VIEW_OF[phase] || 'setup';
  const wasSetup = currentView() === 'view-setup';
  showView(view);

  switch (view) {
    case 'setup':     if (!wasSetup) setup.reset(); break;
    case 'reveal':    reveal.render(prompt); break;
    case 'night':     night.render(prompt); break;
    case 'day':       day.render(prompt); break;
    case 'vote':      vote.render(prompt); break;
    case 'game-over': gameOver.render(); break;
  }
}

// ── Quit ───────────────────────────────────────────────────────────────────────

// Quitting ends the game for everyone, so it asks first. Keep playing is the
// safe choice and takes the focus.
function openAbandon() {
  $('abandon-sheet').hidden = false;
  $('btn-abandon-keep').focus();
}

function closeAbandon() {
  if ($('abandon-sheet').hidden) return;
  $('abandon-sheet').hidden = true;
  if (!$('btn-abandon').hidden) $('btn-abandon').focus();
}

function initAbandon() {
  $('abandon-icon').replaceChildren(sprite('door', 2));
  $('btn-abandon').addEventListener('click', openAbandon);
  $('btn-abandon-keep').addEventListener('click', closeAbandon);
  $('btn-abandon-confirm').addEventListener('click', () => {
    closeAbandon();
    send('abandon_game');
  });
  $('abandon-sheet').addEventListener('click', e => {
    if (e.target === $('abandon-sheet')) closeAbandon();
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeAbandon();
  });
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
  reveal.init(answer, getState);
  night.init(answer, getState);
  day.init(answer, getState);
  vote.init(answer, getState);
  gameOver.init(answer, getState);

  initAbandon();

  const status = $('ws-status');
  connect({
    onMessage: handleMessage,
    onReady: () => {
      // A reconnect redraws the open prompt: an answer may have been lost.
      _renderedKey = null;
      send('get_config');
      send('get_state');
    },
    onStatus: s => ui.setConnection(status, s),
  });

  showView('setup');
}

init();
