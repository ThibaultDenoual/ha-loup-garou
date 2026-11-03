import { translate } from '../i18n.js';
import { $ } from '../dom.js';
import { choiceGrid } from '../ui.js';

let _answer;
let _getState;
let _selected = null;

export function init(answer, getState) {
  _answer = answer;
  _getState = getState;

  $('btn-vote-confirm').addEventListener('click', _onConfirm);
}

// One prompt per voter: the ballots themselves are kept by the core.
export function render(prompt) {
  _selected = null;
  $('btn-vote-confirm').disabled = true;
  $('vote-wait').hidden = Boolean(prompt);
  $('vote-ballot').hidden = !prompt;
  $('btn-vote-confirm').hidden = !prompt;
  if (!prompt) return;

  const { players } = _getState();
  const voter = players.find(p => p.id === prompt.actor);
  $('vote-voter-name').textContent = voter ? voter.name : '?';
  const { done, total } = prompt.info;
  translate($('vote-progress'), 'ui.vote.progress', { done, total });

  const { options } = prompt.picks.target;
  $('vote-grid').replaceChildren(choiceGrid(players.filter(p => options.includes(p.id)), {
    variant: 'wolf',
    onChange: ([picked]) => {
      _selected = picked || null;
      $('btn-vote-confirm').disabled = !_selected;
    },
  }));
  window.scrollTo(0, 0);
}

function _onConfirm() {
  if (_selected) _answer({ target: _selected });
}
