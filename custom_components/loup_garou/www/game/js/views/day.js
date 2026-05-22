import { t, roleName } from '../i18n.js';

let _send;
let _getState;

export function init(send, getState) {
  _send = send;
  _getState = getState;

  document.getElementById('btn-day-vote').addEventListener('click', () => _send('begin_vote'));
  document.getElementById('btn-day-night').addEventListener('click', () => _send('begin_night'));
}

export function render(nightDeaths) {
  const state = _getState();
  document.getElementById('day-night-num').textContent = state.night_number;

  _renderAnnouncement(nightDeaths);
  _renderGrid();
}

function _renderAnnouncement(deaths) {
  const el = document.getElementById('day-announcement');
  if (!deaths || deaths.length === 0) {
    el.textContent = t('phase.day.start_no_death');
    el.className = 'day-announcement';
    return;
  }

  el.className = 'day-announcement deaths';

  if (deaths.length === 1) {
    const d = deaths[0];
    const article = _genderArticle(d.role);
    el.textContent = t('phase.day.start_with_death', {
      name: d.name,
      article,
      role: roleName(d.role),
    });
  } else {
    const names = deaths.map(d => d.name).join(', ');
    el.textContent = t('phase.day.start_multi_death', { names });
  }
}

function _renderGrid() {
  const state = _getState();
  const grid = document.getElementById('day-grid');
  grid.innerHTML = '';
  state.players.forEach(p => {
    const card = document.createElement('div');
    card.className = 'player-card' + (p.alive ? '' : ' dead');
    card.innerHTML = `
      <div class="player-name">${p.name}</div>
      <div class="player-role">${p.alive ? '' : roleName(p.role_id)}</div>`;
    grid.appendChild(card);
  });
}

export function updateGrid() {
  _renderGrid();
}

// French grammatical gender approximation for role articles
function _genderArticle(roleId) {
  const feminine = ['seer', 'witch', 'little_girl'];
  return feminine.includes(roleId) ? 'une' : 'un';
}
