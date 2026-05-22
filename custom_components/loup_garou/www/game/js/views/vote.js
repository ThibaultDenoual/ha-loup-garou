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
  document.getElementById('vote-progress').textContent = `${done} / ${total} votes`;

  const confirm = document.getElementById('btn-vote-confirm');
  confirm.disabled = true;
  confirm.textContent = t('ui.vote.confirm') || 'Voter';

  _renderGrid(voterId);
}

function _renderGrid(excludeId) {
  const state = _getState();
  const grid = document.getElementById('vote-grid');
  grid.innerHTML = '';

  state.players.filter(p => p.alive && p.id !== excludeId).forEach(p => {
    const card = document.createElement('div');
    card.className = 'player-card';
    card.innerHTML = `
      <div class="player-name">${p.name}</div>
      <div class="player-role"></div>`;
    card.addEventListener('click', () => {
      grid.querySelectorAll('.player-card').forEach(c => c.classList.remove('selected'));
      card.classList.add('selected');
      _selected = p.id;
      document.getElementById('btn-vote-confirm').disabled = false;
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
