import { t, roleName } from '../i18n.js';

let _send;
let _getState;
let _onVoteDone;

let _votes = {};
let _queue = [];
let _selected = null;

export function init(send, getState, onVoteDone) {
  _send = send;
  _getState = getState;
  _onVoteDone = onVoteDone;

  document.getElementById('btn-vote-confirm').addEventListener('click', _onConfirm);
}

export function start() {
  const state = _getState();
  _votes = {};
  _queue = state.players.filter(p => p.alive).map(p => p.id);
  _selected = null;
  _renderCurrent();
}

export function updateGrid() {
  _renderGrid(_queue[0]);
}

function _renderCurrent() {
  if (!_queue.length) {
    _send('resolve_vote', { votes: _votes });
    return;
  }

  const state = _getState();
  const voterId = _queue[0];
  const voter = state.players.find(p => p.id === voterId);
  _selected = null;

  document.getElementById('vote-voter-name').textContent = voter ? voter.name : '?';

  const done = Object.keys(_votes).length;
  const total = state.players.filter(p => p.alive).length;
  document.getElementById('vote-progress').textContent = t('ui.vote.progress', { done, total });

  const confirm = document.getElementById('btn-vote-confirm');
  confirm.disabled = true;
  confirm.textContent = t('ui.vote.submit');

  _renderGrid(voterId);
}

function _renderGrid(excludeId) {
  const state = _getState();
  const grid = document.getElementById('vote-grid');
  grid.innerHTML = '';

  state.players.filter(p => p.alive && p.id !== excludeId).forEach(p => {
    const card = document.createElement('div');
    card.className = 'player-card';
    card.setAttribute('role', 'button');
    card.tabIndex = 0;
    card.setAttribute('aria-pressed', 'false');
    card.setAttribute('aria-label', `${t('ui.vote.instruction')}: ${p.name}`);
    const name = document.createElement('div');
    name.className = 'player-name';
    name.textContent = p.name;
    const role = document.createElement('div');
    role.className = 'player-role';
    card.append(name, role);
    const select = () => {
      grid.querySelectorAll('.player-card').forEach(c => {
        c.classList.remove('selected');
        c.setAttribute('aria-pressed', 'false');
      });
      card.classList.add('selected');
      card.setAttribute('aria-pressed', 'true');
      _selected = p.id;
      document.getElementById('btn-vote-confirm').disabled = false;
    };
    card.addEventListener('click', select);
    card.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); select(); }
    });
    grid.appendChild(card);
  });
}

function _onConfirm() {
  if (!_selected) return;
  const voterId = _queue.shift();
  _votes[voterId] = _selected;
  _selected = null;
  _renderCurrent();
}
