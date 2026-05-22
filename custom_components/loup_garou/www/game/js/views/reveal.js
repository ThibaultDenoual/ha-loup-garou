import { t, roleName, roleDesc } from '../i18n.js';

let _send;
let _players = [];
let _idx = 0;
let _active = false;   // guard: prevent re-entry if multiple state msgs arrive

const ROLE_TEAMS = {
  werewolf: 'wolf', alpha_wolf: 'wolf', minion: 'wolf',
  seer: 'village', hunter: 'village', elder: 'village', villager: 'village',
  scapegoat: 'village', little_girl: 'village', witch: 'village',
  cupid: 'lovers',
};

function _teamClass(roleId) {
  const t = ROLE_TEAMS[roleId];
  if (t === 'wolf') return 'team-wolf';
  if (t === 'lovers') return 'team-lovers';
  return 'team-village';
}

function _teamLabel(roleId) {
  const t = ROLE_TEAMS[roleId];
  if (t === 'wolf') return 'Loups';
  if (t === 'lovers') return 'Amoureux';
  return 'Village';
}

export function init(send) {
  _send = send;

  document.getElementById('reveal-card').addEventListener('click', _onCardClick);
  document.getElementById('btn-reveal-seen').addEventListener('click', _onSeen);
}

export function start(players) {
  if (_active) return;  // already showing — ignore duplicate state messages
  _active = true;
  _players = players;
  _idx = 0;
  _showCurrent();
}

export function reset() {
  _active = false;
}

function _showCurrent() {
  if (_idx >= _players.length) {
    _active = false;
    _send('begin_night');
    return;
  }

  const p = _players[_idx];
  document.getElementById('reveal-player-label').textContent = p.name;

  const card = document.getElementById('reveal-card');
  card.classList.remove('flipped');

  const front = card.querySelector('.card-front');
  front.innerHTML = `<span class="reveal-tap">${t('ui.reveal.tap_to_reveal')}</span>`;

  const back = card.querySelector('.card-back');
  back.className = `card-face card-back ${_teamClass(p.role_id)}`;
  back.innerHTML = `
    <div class="reveal-role-name">${roleName(p.role_id)}</div>
    <div class="reveal-role-desc">${roleDesc(p.role_id)}</div>
    <span class="reveal-team-badge">${_teamLabel(p.role_id)}</span>`;

  document.getElementById('btn-reveal-seen').style.display = 'none';
  document.getElementById('btn-reveal-seen').textContent = t('ui.reveal.seen');
}

function _onCardClick() {
  const card = document.getElementById('reveal-card');
  if (card.classList.contains('flipped')) return;
  card.classList.add('flipped');
  document.getElementById('btn-reveal-seen').style.display = '';
}

function _onSeen() {
  _idx++;
  _showCurrent();
}
