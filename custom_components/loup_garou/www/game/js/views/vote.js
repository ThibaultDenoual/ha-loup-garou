import { translate } from '../i18n.js';
import { $ } from '../dom.js';
import { choiceGrid } from '../ui.js';

let _send;
let _getState;

// Ballots collected so far (voter id → target id) and who still has to vote.
let _votes = {};
let _queue = [];
let _selected = null;

export function init(send, getState) {
  _send = send;
  _getState = getState;

  $('btn-vote-confirm').addEventListener('click', _onConfirm);
}

export function start() {
  _votes = {};
  _queue = _getState().players.filter(p => p.alive).map(p => p.id);
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
  const voter = state.players.find(p => p.id === _queue[0]);
  $('vote-voter-name').textContent = voter ? voter.name : '?';

  const done = Object.keys(_votes).length;
  const total = done + _queue.length;
  translate($('vote-progress'), 'ui.vote.progress', { done, total });

  _renderGrid(_queue[0]);
}

function _renderGrid(voterId) {
  _selected = null;
  $('btn-vote-confirm').disabled = true;
  const targets = _getState().players.filter(p => p.alive && p.id !== voterId);
  $('vote-grid').replaceChildren(choiceGrid(targets, {
    variant: 'wolf',
    onChange: ([picked]) => {
      _selected = picked || null;
      $('btn-vote-confirm').disabled = !_selected;
    },
  }));
}

function _onConfirm() {
  if (!_selected) return;
  const voterId = _queue.shift();
  _votes[voterId] = _selected;
  _renderCurrent();
  window.scrollTo(0, 0);
}
