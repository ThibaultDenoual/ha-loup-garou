import { t, roleName, roleDesc } from '../i18n.js';

const ROLE_ORDER = [
  'villager', 'werewolf', 'seer', 'hunter', 'elder', 'scapegoat',
  'little_girl', 'witch', 'cupid', 'alpha_wolf', 'minion', 'sheriff',
];

let _send;
let _names = [];
let _roleConfig = {};

export function init(send) {
  _send = send;

  document.getElementById('btn-add-player').addEventListener('click', () => {
    _names.push('');
    _renderPlayers();
    _validate();
  });

  document.getElementById('btn-start-game').addEventListener('click', _startGame);

  _renderPlayers();
  _renderRoles();
  _validate();
}

export function reset() {
  _names = [];
  _roleConfig = {};
  _renderPlayers();
  _renderRoles();
  _validate();
}

function _renderPlayers() {
  const el = document.getElementById('setup-player-list');
  el.innerHTML = '';
  _names.forEach((name, i) => {
    const row = document.createElement('div');
    row.className = 'player-row';

    const inp = document.createElement('input');
    inp.type = 'text';
    inp.value = name;
    inp.placeholder = t('ui.setup.player_name_placeholder');
    inp.setAttribute('aria-label', `${t('ui.setup.player_name_placeholder')} ${i + 1}`);
    inp.maxLength = 28;
    inp.autocomplete = 'off';
    inp.addEventListener('input', e => { _names[i] = e.target.value; _validate(); });

    const del = document.createElement('button');
    del.className = 'ghost icon-btn';
    del.textContent = '✕';
    del.setAttribute('aria-label', t('ui.setup.remove_player'));
    del.title = t('ui.setup.remove_player');
    del.addEventListener('click', () => { _names.splice(i, 1); _renderPlayers(); _validate(); });

    row.append(inp, del);
    el.appendChild(row);
  });
  const playerCount = document.getElementById('player-count');
  if (playerCount) {
    const key = _names.length === 1 ? 'ui.setup.player_count_one' : 'ui.setup.player_count';
    playerCount.textContent = t(key, { count: _names.length });
  }
}

function _renderRoles() {
  const el = document.getElementById('setup-role-slots');
  el.innerHTML = '';

  ROLE_ORDER.forEach(rid => {
    const cnt = _roleConfig[rid] || 0;
    const row = document.createElement('div');
    row.className = 'role-slot-row';
    row.dataset.roleId = rid;

    const copy = document.createElement('div');
    copy.className = 'role-slot-copy';
    const name = document.createElement('span');
    name.className = 'role-slot-name';
    name.textContent = roleName(rid);
    const description = document.createElement('span');
    description.className = 'role-slot-description';
    description.textContent = roleDesc(rid);
    copy.append(name, description);

    const dec = document.createElement('button');
    dec.className = 'secondary icon-btn role-slot-btn';
    dec.textContent = '−';
    dec.setAttribute('aria-label', `${t('ui.setup.remove_role')} ${roleName(rid)}`);
    dec.addEventListener('click', () => {
      _roleConfig[rid] = Math.max(0, (_roleConfig[rid] || 0) - 1);
      _updateRoleRow(row, rid);
      _validate();
    });

    const count = document.createElement('span');
    count.className = 'role-slot-count';
    count.textContent = cnt;
    count.dataset.rid = rid;

    const inc = document.createElement('button');
    inc.className = 'secondary icon-btn role-slot-btn';
    inc.textContent = '+';
    inc.setAttribute('aria-label', `${t('ui.setup.add_role')} ${roleName(rid)}`);
    inc.addEventListener('click', () => {
      _roleConfig[rid] = (_roleConfig[rid] || 0) + 1;
      _updateRoleRow(row, rid);
      _validate();
    });

    row.append(copy, dec, count, inc);
    el.appendChild(row);
  });
}

function _updateRoleRow(row, rid) {
  const count = _roleConfig[rid] || 0;
  row.querySelector('[data-rid]').textContent = count;
  row.querySelector('.role-slot-btn:first-of-type').disabled = count === 0;
  _updateTotalLabel();
}

function _updateTotalLabel() {
  const total = Object.values(_roleConfig).reduce((a, b) => a + b, 0);
  const el = document.getElementById('role-total-label');
  if (el) el.textContent = t('ui.setup.roles_count', { assigned: total, players: _names.length });
  document.querySelectorAll('.role-slot-row').forEach(row => {
    const rid = row.dataset.roleId;
    const count = _roleConfig[rid] || 0;
    const buttons = row.querySelectorAll('.role-slot-btn');
    if (buttons[0]) buttons[0].disabled = count === 0;
    if (buttons[1]) buttons[1].disabled = total >= _names.length;
  });
}

function _validate() {
  const total = Object.values(_roleConfig).reduce((a, b) => a + b, 0);
  const hasDuplicateNames = new Set(_names.map(n => n.trim().toLocaleLowerCase()).filter(Boolean)).size !== _names.filter(n => n.trim()).length;
  const ok = _names.length >= 3
    && total === _names.length
    && _names.every(n => n.trim())
    && !hasDuplicateNames;
  document.getElementById('btn-start-game').disabled = !ok;
  const hint = document.getElementById('setup-hint');
  if (hint) {
    let message = 'ui.setup.minimum_players';
    if (_names.length >= 3 && _names.some(n => !n.trim())) message = 'ui.setup.fill_names';
    else if (hasDuplicateNames) message = 'ui.setup.unique_names';
    else if (total < _names.length) message = 'ui.setup.assign_roles';
    else if (total > _names.length) message = 'ui.setup.remove_extra_roles';
    else if (ok) message = 'ui.setup.ready';
    hint.textContent = t(message);
    hint.classList.toggle('ready', ok);
  }
  _updateTotalLabel();
}

export function updateLanguage() {
  _renderPlayers();
  _renderRoles();
  _validate();
}

function _startGame() {
  const roles = [];
  ROLE_ORDER.forEach(rid => {
    for (let i = 0; i < (_roleConfig[rid] || 0); i++) roles.push(rid);
  });
  // Fisher-Yates shuffle
  for (let i = roles.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [roles[i], roles[j]] = [roles[j], roles[i]];
  }
  _send('start_game', { players: _names.map(n => n.trim()), roles });
}
