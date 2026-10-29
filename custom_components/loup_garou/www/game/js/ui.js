import { has, translate, translateAttr } from './i18n.js';
import { h, $ } from './dom.js';
import { avatar, sprite, skyline, starField } from './sprites.js';
import { teamOf } from './roles.js';

const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// ── Scenery ──────────────────────────────────────────────────────────────────

export function mountScenery() {
  const stars = h('div', { class: 'stars twinkle', 'aria-hidden': 'true' });
  stars.style.boxShadow = starField();
  document.body.prepend(stars);
  document.querySelectorAll('.dock').forEach(dock => dock.prepend(skyline()));
}

// night | day | dusk. The first call sets the palette silently; later
// changes play the sky wipe.
export function setTime(time) {
  const body = document.body;
  if (body.dataset.time === time) return;
  const first = !body.dataset.time;
  body.dataset.time = time;
  const icon = $('time-icon');
  if (icon) icon.replaceChildren(sprite(time === 'day' ? 'sun' : 'moon', 3));
  if (first || reducedMotion()) return;
  const wipe = h('div', { class: 'time-wipe', 'aria-hidden': 'true' },
    Array.from({ length: 8 }, (_, i) => {
      const band = h('i');
      band.style.animationDelay = `${i * 40}ms`;
      return band;
    }));
  document.body.append(wipe);
  setTimeout(() => wipe.remove(), 1000);
}

// ── Status bar ───────────────────────────────────────────────────────────────

const PHASES = ['setup', 'role_reveal', 'night', 'day', 'vote', 'game_over'];

export function setPhase(phase) {
  translate($('st-phase'), `ui.phase.${phase}`);
  const current = PHASES.indexOf(phase);
  $('phase-track').querySelectorAll('i').forEach((step, i) => {
    step.dataset.state = i < current ? 'done' : i === current ? 'current' : 'todo';
  });
}

export function buildTrack() {
  const track = $('phase-track');
  translateAttr(track, 'aria-label', 'ui.phase.track');
  track.replaceChildren(...PHASES.map(() => h('i')));
}

// status: connecting | connected | reconnecting | open_from_ha
export function setConnection(el, status, keyPrefix = 'ui.ws') {
  el.classList.toggle('connected', status === 'connected');
  translate(el.querySelector('.conn-text'), `${keyPrefix}.${status}`);
}

// ── Toast ────────────────────────────────────────────────────────────────────

export function toast(key, vars, ms = 4000) {
  const el = $('toast');
  translate(el, key, vars);
  el.hidden = false;
  clearTimeout(el._timer);
  el._timer = setTimeout(() => { el.hidden = true; }, ms);
}

// Server errors carry a code; show its translation, never the raw English msg.
export function toastError(msg) {
  const key = `ui.error.${msg.code}`;
  toast(has(key) ? key : 'ui.error.generic');
}

// ── Players ──────────────────────────────────────────────────────────────────

// showRole: true, or a predicate per player, to print the role under the name.
export function playerCard(player, { selectable = false, showRole = false } = {}) {
  const reveal = typeof showRole === 'function' ? showRole(player) : showRole;
  const roleLine = reveal
    ? h('span', { class: `player-role team-${teamOf(player.role_id)}`, i18n: `role.${player.role_id}.name` })
    : null;
  const card = h(selectable ? 'button' : 'div', {
    class: 'player-card' + (player.alive ? '' : ' dead'),
    type: selectable ? 'button' : null,
    'aria-pressed': selectable ? 'false' : null,
    data: { playerId: player.id },
  },
    h('span', { class: 'avatar' }, player.alive ? avatar(player.name, 4) : sprite('skull', 3)),
    h('span', { class: 'who' },
      h('span', { class: 'player-name', text: player.name }),
      roleLine,
      player.alive ? null : h('span', { class: 'sr-only', i18n: 'ui.player.dead' })),
  );
  return card;
}

export function playerGrid(players, opts) {
  return h('div', { class: 'player-grid' }, players.map(p => playerCard(p, opts)));
}

// Selectable grid. max = 1 behaves like a radio group that can be cleared;
// max > 1 lets up to max cards be pressed. variant colours the selection.
export function choiceGrid(players, { max = 1, variant = 'pick', onChange }) {
  const picked = [];
  const grid = h('div', { class: 'player-grid' });
  const sync = () => grid.querySelectorAll('.player-card').forEach(card => {
    card.setAttribute('aria-pressed', String(picked.includes(card.dataset.playerId)));
  });
  players.forEach(p => {
    const card = playerCard(p, { selectable: true });
    card.dataset.variant = variant;
    card.addEventListener('click', () => {
      const at = picked.indexOf(p.id);
      if (at >= 0) picked.splice(at, 1);
      else if (max === 1) picked.splice(0, picked.length, p.id);
      else if (picked.length < max) picked.push(p.id);
      else return;
      sync();
      onChange([...picked]);
    });
    grid.append(card);
  });
  return grid;
}
