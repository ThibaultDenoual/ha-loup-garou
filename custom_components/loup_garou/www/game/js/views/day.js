import { translate } from '../i18n.js';
import { h, $ } from '../dom.js';
import { articleRef, roleNameRef } from '../roles.js';
import { sprite } from '../sprites.js';
import { playerGrid } from '../ui.js';

let _send;
let _getState;

export function init(send, getState) {
  _send = send;
  _getState = getState;

  $('btn-day-vote').addEventListener('click', () => _send('begin_vote'));
  $('btn-day-night').addEventListener('click', () => _send('begin_night'));
}

export function render(nightDeaths) {
  translate($('day-heading'), 'ui.day.heading', { n: _getState().night_number });
  _renderAnnouncement(nightDeaths || []);
  updateGrid();
}

function _renderAnnouncement(deaths) {
  const text = h('p');
  if (deaths.length === 0) {
    translate(text, 'phase.day.start_no_death');
  } else if (deaths.length === 1) {
    const d = deaths[0];
    translate(text, 'phase.day.start_with_death', {
      name: d.name,
      article: articleRef(d.role),
      role: roleNameRef(d.role),
    });
  } else {
    translate(text, 'phase.day.start_multi_death', { names: deaths.map(d => d.name).join(', ') });
  }
  $('day-announcement').replaceChildren(sprite(deaths.length ? 'skull' : 'sun', 4), text);
}

export function updateGrid() {
  const players = _getState().players;
  translate($('day-alive'), 'ui.day.alive_count', { count: players.filter(p => p.alive).length });
  // Dead players' roles are public knowledge.
  $('day-grid').replaceChildren(playerGrid(players, { showRole: p => !p.alive }));
}
