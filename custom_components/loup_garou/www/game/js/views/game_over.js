import { t, roleName } from '../i18n.js';

let _send;
let _getState;
let _onRestart;

export function init(send, getState, onRestart) {
  _send = send;
  _getState = getState;
  _onRestart = onRestart;

  document.getElementById('btn-restart').addEventListener('click', () => {
    if (_onRestart) _onRestart();
  });
}

export function render() {
  const state = _getState();

  const msgs = {
    wolves:  'phase.game_over.wolves_win',
    village: 'phase.game_over.village_win',
    lovers:  'phase.game_over.lovers_win',
  };
  const msgKey = msgs[state.winner] || 'phase.game_over.village_win';
  document.getElementById('go-msg').textContent = t(msgKey);

  const banner = document.getElementById('go-banner');
  banner.className = `winner-banner ${state.winner || 'village'}`;

  const grid = document.getElementById('go-grid');
  grid.innerHTML = '';
  state.players.forEach(p => {
    const card = document.createElement('div');
    card.className = 'player-card' + (p.alive ? '' : ' dead');
    const dot = _teamDot(p.role_id);
    card.innerHTML = `
      <div class="player-name">${p.name}</div>
      <div class="player-role">${dot}${roleName(p.role_id)}</div>`;
    grid.appendChild(card);
  });
}

function _teamDot(roleId) {
  const wolves = ['werewolf', 'alpha_wolf', 'minion'];
  const lovers = ['cupid'];
  let color = 'var(--sage)';
  if (wolves.includes(roleId)) color = 'var(--blood-bright)';
  else if (lovers.includes(roleId)) color = 'var(--rose)';
  return `<span class="player-team-dot" style="background:${color}"></span>`;
}
