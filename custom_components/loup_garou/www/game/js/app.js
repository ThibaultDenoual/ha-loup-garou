import { loadLocale, t } from './i18n.js';
import { connect, send } from './ws.js';
import * as tts from './tts.js';
import * as setup from './views/setup.js';
import * as reveal from './views/reveal.js';
import * as night from './views/night.js';
import * as day from './views/day.js';
import * as vote from './views/vote.js';
import * as gameOver from './views/game_over.js';

// ── Global state ──────────────────────────────────────────────────────────────

let _state = { phase: 'setup', players: [], night_number: 0, winner: null };
let _nightDeaths = [];   // player_eliminated events accumulated during night
let _voteDeath = null;   // player eliminated by vote (for next-day announcement)
const _activeViews = new Set(); // which view is currently showing

function getState() { return _state; }

// ── View routing ───────────────────────────────────────────────────────────────

function showView(id) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  const el = document.getElementById(`view-${id}`);
  if (el) el.classList.add('active');
}

function currentView() {
  const el = document.querySelector('.view.active');
  return el ? el.id : null;
}

// ── Toast ──────────────────────────────────────────────────────────────────────

function toast(msg, type = '', ms = 3000) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = 'show' + (type ? ` toast-${type}` : '');
  clearTimeout(el._timer);
  el._timer = setTimeout(() => el.classList.remove('show', `toast-${type}`), ms);
}

// ── Status bar ─────────────────────────────────────────────────────────────────

function updatePhaseLabel(phase) {
  const el = document.getElementById('st-phase');
  if (!el) return;
  const labels = {
    setup: 'Configuration',
    role_reveal: 'Révélation',
    night: 'Nuit',
    day: 'Jour',
    vote: 'Vote',
    game_over: 'Fin de partie',
  };
  el.textContent = labels[phase] || phase;
  el.className = `phase-${phase}` || '';
}

// ── Message handling ───────────────────────────────────────────────────────────

function handleMessage(msg) {
  switch (msg.type) {
    case 'state':            onState(msg.state);              break;
    case 'night_role_wake':  onNightRoleWake(msg.data);       break;
    case 'night_role_sleep': onNightRoleSleep(msg.data);      break;
    case 'player_eliminated': onPlayerEliminated(msg.data);   break;
    case 'narrate':          tts.speak(msg.data.text, msg.data.lang); break;
    case 'error':            toast('⚠ ' + msg.msg, 'death');  break;
  }
}

function onState(newState) {
  const prevPhase = _state.phase;
  _state = newState;
  updatePhaseLabel(newState.phase);

  const view = currentView();

  switch (newState.phase) {
    case 'role_reveal':
      // Guard: only transition once; ignore subsequent state msgs with same phase
      if (view !== 'view-reveal') {
        showView('reveal');
        reveal.start(newState.players);
      }
      break;

    case 'night':
      // Don't interrupt an active night action view
      if (!view || !view.startsWith('view-night')) {
        _nightDeaths = [];
        showView('night');
        night.showSleeping();
      }
      break;

    case 'day':
      // Guard: PHASE_CHANGED(day) and DAY_STARTED both broadcast state — only render once.
      if (currentView() !== 'view-day') {
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
  // data.player_id → hunter must shoot (hunter's on_before_eliminate interrupt)
  // otherwise      → regular night role action (submit_night_action)
  night.onWake(data);
}

function onNightRoleSleep(data) {
  night.onSleep(data);
  // If phase transitioned (game over / day) during night, server will broadcast state
  // which drives the view transition. We stay in night-sleep until that state arrives.
}

function onPlayerEliminated(data) {
  // Accumulate night deaths for the day announcement
  if (_state.phase === 'night') {
    _nightDeaths.push(data);
  }

  // Update alive status in local state
  const p = _state.players.find(pl => pl.id === data.player_id);
  if (p) p.alive = false;

  // Refresh grids if currently visible
  const view = currentView();
  if (view === 'view-day')  day.updateGrid();
  if (view === 'view-vote') vote.updateGrid();
}

// ── Init ───────────────────────────────────────────────────────────────────────

async function init() {
  const lang = document.documentElement.lang || 'fr';
  await loadLocale(lang);

  // Wire up all view modules
  tts.init(send);
  setup.init(send);
  reveal.init(send);
  night.init(send, getState, toast);
  day.init(send, getState);
  vote.init(send, getState);
  gameOver.init(send, getState, () => {
    reveal.reset();
    setup.reset();
    showView('setup');
  });

  connect(handleMessage, () => {
    // On reconnect, request fresh state
    send('get_state');
  });

  showView('setup');
}

init();

// Starfield canvas
(function () {
  const canvas = document.getElementById('bg-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let W, H, stars = [], shootingStar = null, shootTimer = 0;

  function resize() {
    W = canvas.width  = window.innerWidth;
    H = canvas.height = window.innerHeight;
  }
  function mkStars() {
    stars = [];
    const n = Math.floor(W * H / 6500);
    for (let i = 0; i < n; i++) stars.push({
      x: Math.random() * W, y: Math.random() * H,
      r: Math.random() * 1.1 + 0.25,
      a: Math.random() * 0.55 + 0.1,
      sp: Math.random() * 0.007 + 0.002,
      ph: Math.random() * Math.PI * 2,
    });
  }
  let t2 = 0;
  function draw() {
    ctx.clearRect(0, 0, W, H);
    t2 += 0.016;
    for (const s of stars) {
      const a = s.a * (0.45 + 0.55 * Math.sin(t2 * s.sp * 60 + s.ph));
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(215,205,245,${a})`;
      ctx.fill();
    }
    shootTimer -= 0.016;
    if (shootTimer <= 0) {
      shootTimer = 8 + Math.random() * 14;
      shootingStar = {
        x: Math.random() * W * 0.7, y: Math.random() * H * 0.4,
        len: 90 + Math.random() * 80, speed: 6 + Math.random() * 4,
        alpha: 0.8, life: 1,
      };
    }
    if (shootingStar) {
      const s = shootingStar;
      s.x += s.speed; s.y += s.speed * 0.45; s.life -= 0.03;
      s.alpha = Math.max(0, s.life);
      const grd = ctx.createLinearGradient(s.x, s.y, s.x - s.len, s.y - s.len * 0.45);
      grd.addColorStop(0, `rgba(230,210,100,${s.alpha})`);
      grd.addColorStop(1, 'rgba(230,210,100,0)');
      ctx.beginPath();
      ctx.moveTo(s.x, s.y);
      ctx.lineTo(s.x - s.len, s.y - s.len * 0.45);
      ctx.strokeStyle = grd; ctx.lineWidth = 1.5; ctx.stroke();
      if (s.life <= 0) shootingStar = null;
    }
    requestAnimationFrame(draw);
  }
  resize(); mkStars(); draw();
  window.addEventListener('resize', () => { resize(); mkStars(); });
})();
