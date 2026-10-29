import { translate } from '../i18n.js';
import { $ } from '../dom.js';
import { sprite } from '../sprites.js';
import { playerGrid } from '../ui.js';

const WINNERS = {
  wolves:  { key: 'phase.game_over.wolves_win', sprite: 'werewolf' },
  village: { key: 'phase.game_over.village_win', sprite: 'villager' },
  lovers:  { key: 'phase.game_over.lovers_win', sprite: 'heart' },
};

let _getState;

export function init(getState, onRestart) {
  _getState = getState;
  $('btn-restart').addEventListener('click', onRestart);
}

export function render() {
  const state = _getState();
  const winner = WINNERS[state.winner] ? state.winner : 'village';
  $('go-banner').dataset.winner = winner;
  $('go-sprite').replaceChildren(sprite(WINNERS[winner].sprite, 8));
  translate($('go-msg'), WINNERS[winner].key);
  $('go-grid').replaceChildren(playerGrid(state.players, { showRole: true }));
}
