import { translate } from '../i18n.js';
import { h, $ } from '../dom.js';
import { ROLE_ORDER, roleNameRef } from '../roles.js';
import { avatar, sprite } from '../sprites.js';

const MIN_PLAYERS = 3;
const MAX_NAME = 20;

let _send;
// Kept across games so the same group can replay without retyping.
let _names = [];
let _roleConfig = {};

export function init(send) {
  _send = send;

  $('btn-add-player').addEventListener('click', () => {
    _names.push('');
    _renderPlayers();
    _validate();
    $('setup-player-list').querySelector('.player-row:last-child input').focus();
  });
  $('btn-start-game').addEventListener('click', _startGame);

  _renderPlayers();
  _renderRoles();
  _validate();
}

export function reset() {
  _renderPlayers();
  _renderRoles();
  _validate();
}

const _assigned = () => Object.values(_roleConfig).reduce((a, b) => a + b, 0);

function _renderPlayers() {
  $('setup-player-list').replaceChildren(..._names.map((name, i) => {
    const face = h('span', { class: 'avatar' }, avatar(name, 4));
    const input = h('input', {
      class: 'field',
      type: 'text',
      maxlength: MAX_NAME + 5,
      autocomplete: 'off',
      i18nPlaceholder: 'ui.setup.player_name_placeholder',
      on: {
        input: e => {
          _names[i] = e.target.value;
          face.replaceChildren(avatar(e.target.value, 4));
          _validate();
        },
      },
    });
    input.value = name;
    const remove = h('button', {
      type: 'button',
      class: 'btn btn-icon',
      i18nLabel: 'ui.setup.remove_player',
      on: { click: () => { _names.splice(i, 1); _renderPlayers(); _validate(); } },
    }, sprite('cross', 2));
    return h('div', { class: 'player-row' }, face, input, remove);
  }));
}

function _renderRoles() {
  $('setup-role-slots').replaceChildren(...ROLE_ORDER.map(rid => {
    const count = h('span', { class: 'role-slot-count', 'aria-live': 'polite' });
    const less = h('button', {
      type: 'button',
      class: 'btn btn-icon',
      i18nLabel: ['ui.setup.role_less', { role: roleNameRef(rid) }],
      on: { click: () => _bump(rid, -1) },
    }, sprite('minus', 2));
    const more = h('button', {
      type: 'button',
      class: 'btn btn-icon',
      i18nLabel: ['ui.setup.role_more', { role: roleNameRef(rid) }],
      on: { click: () => _bump(rid, 1) },
    }, sprite('plus', 2));
    return h('div', { class: 'role-slot-row', data: { roleId: rid } },
      sprite(rid, 3),
      h('div', {},
        h('div', { class: 'role-slot-name', i18n: `role.${rid}.name` }),
        h('div', { class: 'role-slot-desc', i18n: `role.${rid}.description` })),
      h('div', { class: 'stepper' }, less, count, more));
  }));
}

function _bump(rid, delta) {
  _roleConfig[rid] = Math.max(0, (_roleConfig[rid] || 0) + delta);
  _validate();
}

// Returns the first unmet condition as a locale key (+ vars), or null.
function _problem() {
  const names = _names.map(n => n.trim());
  if (names.length < MIN_PLAYERS) return ['ui.setup.hint.need_players'];
  if (names.some(n => !n)) return ['ui.setup.hint.empty_name'];
  if (names.some(n => n.length > MAX_NAME)) return ['ui.setup.hint.long_name'];
  if (names.some(n => /[{}]/.test(n))) return ['ui.setup.hint.bad_chars'];
  if (new Set(names.map(n => n.toLowerCase())).size !== names.length) return ['ui.setup.hint.duplicate'];
  const gap = names.length - _assigned();
  if (gap > 0) return ['ui.setup.hint.roles_short', { count: gap }];
  if (gap < 0) return ['ui.setup.hint.roles_over', { count: -gap }];
  return null;
}

function _validate() {
  const assigned = _assigned();
  const players = _names.length;

  document.querySelectorAll('#setup-role-slots .role-slot-row').forEach(row => {
    const n = _roleConfig[row.dataset.roleId] || 0;
    row.dataset.count = n;
    row.querySelector('.role-slot-count').textContent = n;
    const [less, more] = row.querySelectorAll('button');
    less.disabled = n === 0;
    more.disabled = assigned >= players;
  });

  translate($('role-total-label'), 'ui.setup.role_count', { assigned, players });

  const problem = _problem();
  const hint = $('setup-hint');
  translate(hint, ...(problem || ['ui.setup.hint.ready']));
  hint.dataset.ok = String(!problem);
  $('btn-start-game').disabled = Boolean(problem);
}

function _startGame() {
  const roles = ROLE_ORDER.flatMap(rid => Array(_roleConfig[rid] || 0).fill(rid));
  // Fisher-Yates shuffle
  for (let i = roles.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [roles[i], roles[j]] = [roles[j], roles[i]];
  }
  _send('start_game', { players: _names.map(n => n.trim()), roles });
}
