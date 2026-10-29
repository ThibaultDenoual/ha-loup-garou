import { translate } from '../i18n.js';
import { $ } from '../dom.js';
import { teamOf } from '../roles.js';
import { sprite } from '../sprites.js';

// Matches the .reveal-card transition in pixel.css, plus a frame of margin.
const FLIP_MS = 650;

let _send;
let _players = [];
let _idx = 0;
let _active = false;   // guard: prevent re-entry if multiple state msgs arrive

export function init(send) {
  _send = send;
  $('reveal-emblem').replaceChildren(sprite('moon', 8));

  const card = $('reveal-card');
  card.addEventListener('click', _flip);
  card.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); _flip(); }
  });
  $('btn-reveal-seen').addEventListener('click', _onSeen);
}

export function start(players) {
  if (_active) return;  // already showing — ignore duplicate state messages
  _active = true;
  _players = players;
  _idx = 0;
  _showCurrent();
}

export function reset() {
  _active = false;
}

function _setFaces(flipped) {
  const card = $('reveal-card');
  card.classList.toggle('flipped', flipped);
  card.setAttribute('aria-pressed', String(flipped));
  const [front, back] = card.querySelectorAll('.card-face');
  // The face turned away must be invisible to screen readers too.
  front.setAttribute('aria-hidden', String(flipped));
  front.inert = flipped;
  back.setAttribute('aria-hidden', String(!flipped));
  back.inert = !flipped;
  $('btn-reveal-seen').hidden = !flipped;
}

function _showCurrent() {
  if (_idx >= _players.length) {
    _active = false;
    _send('begin_night');
    return;
  }

  const p = _players[_idx];
  $('reveal-player-label').textContent = p.name;
  translate($('reveal-progress'), 'ui.reveal.progress', { done: _idx + 1, total: _players.length });

  // The card is face-down here, so loading the next role cannot leak it.
  $('reveal-card').querySelector('.card-back').dataset.team = teamOf(p.role_id);
  $('reveal-sprite').replaceChildren(sprite(p.role_id, 10));
  translate($('reveal-role-name'), `role.${p.role_id}.name`);
  translate($('reveal-team'), `role.${p.role_id}.team`);
  translate($('reveal-role-desc'), `role.${p.role_id}.description`);
  _setFaces(false);
  $('reveal-card').focus();
}

function _flip() {
  if ($('reveal-card').classList.contains('flipped')) return;
  _setFaces(true);
  $('btn-reveal-seen').focus();
}

function _onSeen() {
  // Flip face-down first; the next player's role loads only once the
  // current one is hidden.
  _setFaces(false);
  $('btn-reveal-seen').hidden = true;
  setTimeout(() => {
    _idx++;
    _showCurrent();
  }, FLIP_MS);
}
