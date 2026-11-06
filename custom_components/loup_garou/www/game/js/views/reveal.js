import { translate } from '../i18n.js';
import { $ } from '../dom.js';
import { teamOf } from '../roles.js';
import { sprite } from '../sprites.js';

// Matches the .reveal-card transition in pixel.css, plus a frame of margin.
const FLIP_MS = 650;

let _answer;
let _getState;
let _prompt = null;

export function init(answer, getState) {
  _answer = answer;
  _getState = getState;
  $('reveal-emblem').replaceChildren(..._scalable(sprite('full_moon', 3)));

  const card = $('reveal-card');
  card.addEventListener('click', _flip);
  card.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); _flip(); }
  });
  $('btn-reveal-seen').addEventListener('click', _onSeen);
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

// Size each sprite in --sprite-unit steps (one sprite pixel), so the CSS can
// shrink the medallion on short screens and keep the pixels square.
function _scalable(...sprites) {
  for (const svg of sprites) {
    const [, , w, h] = svg.getAttribute('viewBox').split(' ').map(Number);
    svg.style.width = `calc(var(--sprite-unit) * ${w})`;
    svg.style.height = `calc(var(--sprite-unit) * ${h})`;
  }
  return sprites;
}

export function render(prompt) {
  _prompt = prompt;
  if (!prompt) return;
  const { role_id: roleId, done, total } = prompt.info;
  const player = _getState().players.find(p => p.id === prompt.actor);
  // The narrator sets the scene once, while the first player takes the phone.
  $('reveal-intro').hidden = done !== 1;
  $('reveal-player-label').textContent = player ? player.name : '?';
  translate($('reveal-progress'), 'ui.reveal.progress', { done, total });

  // The card is face-down here, so loading the next role cannot leak it.
  $('reveal-card').querySelector('.card-back').dataset.team = teamOf(roleId);
  $('reveal-sprite').replaceChildren(..._scalable(sprite('full_moon', 4), sprite(roleId, 4)));
  translate($('reveal-role-name'), `role.${roleId}.name`);
  translate($('reveal-team'), `role.${roleId}.team`);
  translate($('reveal-role-desc'), `role.${roleId}.description`);
  _setFaces(false);
  $('reveal-card').focus();
}

function _flip() {
  if (!_prompt || $('reveal-card').classList.contains('flipped')) return;
  _setFaces(true);
  $('btn-reveal-seen').focus();
}

function _onSeen() {
  // Flip face-down first; the next player's role loads only once the
  // current one is hidden.
  _setFaces(false);
  $('btn-reveal-seen').hidden = true;
  setTimeout(() => _answer(), FLIP_MS);
}
