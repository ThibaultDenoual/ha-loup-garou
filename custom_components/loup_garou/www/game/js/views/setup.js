import { t, roleName } from '../i18n.js';

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
    inp.addEventListener('input', e => { _names[i] = e.target.value; _validate(); });

    const del = document.createElement('button');
    del.className = 'ghost icon-btn';
    del.textContent = '✕';
    del.addEventListener('click', () => { _names.splice(i, 1); _renderPlayers(); _validate(); });

    row.append(inp, del);
    el.appendChild(row);
  });
}

function _renderRoles() {
  const el = document.getElementById('setup-role-slots');
  el.innerHTML = '';

  ROLE_ORDER.forEach(rid => {
    const cnt = _roleConfig[rid] || 0;
    const row = document.createElement('div');
    row.className = 'role-slot-row';

    const name = document.createElement('span');
    name.className = 'role-slot-name';
    name.textContent = roleName(rid);

    const dec = document.createElement('button');
    dec.className = 'secondary icon-btn role-slot-btn';
    dec.textContent = '−';
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
    inc.addEventListener('click', () => {
      _roleConfig[rid] = (_roleConfig[rid] || 0) + 1;
      _updateRoleRow(row, rid);
      _validate();
    });

    row.append(name, dec, count, inc);
    el.appendChild(row);
  });
}

function _updateRoleRow(row, rid) {
  row.querySelector('[data-rid]').textContent = _roleConfig[rid] || 0;
  _updateTotalLabel();
}

function _updateTotalLabel() {
  const total = Object.values(_roleConfig).reduce((a, b) => a + b, 0);
  const el = document.getElementById('role-total-label');
  if (el) el.textContent = `${total} / ${_names.length}`;
}

function _validate() {
  const total = Object.values(_roleConfig).reduce((a, b) => a + b, 0);
  const ok = _names.length >= 3
    && total === _names.length
    && _names.every(n => n.trim());
  document.getElementById('btn-start-game').disabled = !ok;
  _updateTotalLabel();
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
