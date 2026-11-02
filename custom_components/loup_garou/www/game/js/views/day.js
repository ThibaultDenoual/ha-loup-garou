import { translate } from '../i18n.js';
import { h, $ } from '../dom.js';
import { articleRef, roleNameRef } from '../roles.js';
import { sprite } from '../sprites.js';
import { playerGrid } from '../ui.js';

let _answer;
let _getState;

export function init(answer, getState) {
  _answer = answer;
  _getState = getState;

  $('btn-day-vote').addEventListener('click', () => _answer({ next: 'vote' }));
  $('btn-day-night').addEventListener('click', () => _answer({ next: 'night' }));
}

// The buttons are what the core offers; without a prompt the narrator is speaking.
export function render(prompt) {
  const { night, news } = _getState();
  translate($('day-heading'), 'ui.day.heading', { n: night });
  _renderAnnouncement(news);
  _updateGrid();

  const options = prompt ? prompt.picks.next.options : [];
  $('btn-day-vote').hidden = !options.includes('vote');
  $('btn-day-night').hidden = !options.includes('night');
  $('day-wait').hidden = Boolean(prompt);
}

function _announcementKey({ source, deaths, tie }) {
  if (deaths.length > 1) return ['phase.day.start_multi_death', { names: deaths.map(d => d.name).join(', ') }];
  if (deaths.length === 1) {
    const [d] = deaths;
    return [source === 'vote' ? 'phase.vote.result' : 'phase.day.start_with_death', {
      name: d.name,
      article: articleRef(d.role),
      role: roleNameRef(d.role),
    }];
  }
  return [tie ? 'phase.vote.tie' : 'phase.day.start_no_death'];
}

function _renderAnnouncement(news) {
  const text = h('p');
  translate(text, ..._announcementKey(news));
  $('day-announcement').replaceChildren(sprite(news.deaths.length ? 'skull' : 'sun', 4), text);
}

function _updateGrid() {
  const players = _getState().players;
  translate($('day-alive'), 'ui.day.alive_count', { count: players.filter(p => p.alive).length });
  // Dead players' roles are public knowledge.
  $('day-grid').replaceChildren(playerGrid(players, { showRole: p => !p.alive }));
}
