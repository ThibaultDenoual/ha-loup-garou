import { t, roleName } from '../i18n.js';

let _send;
let _getState;
let _toast;

let _nightRole = null;
let _naSelected = null;
let _witchSaveTarget = null;
let _witchPoisonTarget = null;
let _witchSaveAvail = true;
let _witchPoisonAvail = true;
let _witchId = null;
let _cupidLovers = [];

const ROLE_HALOS = {
  werewolf:    'rgba(139,26,26,0.6)',
  alpha_wolf:  'rgba(139,26,26,0.6)',
  seer:        'rgba(122,61,154,0.6)',
  witch:       'rgba(122,61,154,0.6)',
  cupid:       'rgba(138,48,80,0.6)',
  hunter:      'rgba(212,134,42,0.6)',
};

export function init(send, getState, toast) {
  _send = send;
  _getState = getState;
  _toast = toast;

  document.getElementById('btn-na-skip').addEventListener('click', _onSkip);
  document.getElementById('btn-na-confirm').addEventListener('click', _onConfirm);
  document.getElementById('btn-seer-ack').addEventListener('click', () => {
    _send('submit_pending_action', { role: 'seer', action: {} });
  });
}

// ── Public API ────────────────────────────────────────────────────────────────

export function showSleeping(sleepText) {
  _setSection('sleeping');
  _setHalo(null);
  document.getElementById('sleep-text').textContent = sleepText || t('ui.night.title');
}

export function onWake(data) {
  const role = data.role;
  _nightRole = role;
  _setHalo(ROLE_HALOS[role] || null);

  if (data.result) {
    _showSeerResult(data);
    return;
  }

  if (data.player_id && role === 'hunter') {
    _showHunterAction(data);
    return;
  }

  _showNightAction(data);
}

export function onSleep() {
  _nightRole = null;
  _naSelected = null;
  _witchSaveTarget = null;
  _witchPoisonTarget = null;
  _cupidLovers = [];
  showSleeping();
}

// ── Section switching ─────────────────────────────────────────────────────────

function _setSection(which) {
  document.getElementById('night-sleeping').style.display = which === 'sleeping' ? '' : 'none';
  document.getElementById('night-action').style.display  = which === 'action'   ? '' : 'none';
  document.getElementById('night-seer').style.display    = which === 'seer'     ? '' : 'none';
}

function _setHalo(color) {
  document.getElementById('view-night').style.setProperty('--role-halo', color || 'transparent');
}

// ── Artifact helpers ──────────────────────────────────────────────────────────

function _flash(type) {
  const el = document.createElement('div');
  el.className = `role-flash flash-${type}`;
  document.body.appendChild(el);
  // Remove after animation completes
  el.addEventListener('animationend', () => el.remove(), { once: true });
}

function _showArtifact(html) {
  const el = document.getElementById('role-artifact');
  el.innerHTML = html;
  el.style.display = '';
}

function _hideArtifact() {
  const el = document.getElementById('role-artifact');
  el.style.display = 'none';
  el.innerHTML = '';
}

function _seerOrbActivate() {
  const orb = document.getElementById('seer-orb');
  if (orb) orb.classList.add('active');
}

// ── Night action views ────────────────────────────────────────────────────────

function _showNightAction(data) {
  const role = data.role;
  _naSelected = null;
  _cupidLovers = [];

  _hideArtifact();

  document.getElementById('na-role-name').textContent = roleName(role);
  document.getElementById('na-prompt').textContent = t(`role.${role}.action_prompt`);
  document.getElementById('na-victim').style.display = 'none';
  document.getElementById('na-witch-potions').style.display = 'none';

  const skip = document.getElementById('btn-na-skip');
  skip.style.display = '';

  const confirm = document.getElementById('btn-na-confirm');
  confirm.disabled = true;
  confirm.className = 'primary';
  confirm.textContent = t('ui.vote.confirm') || 'Confirmer';

  const state = _getState();
  const alive = state.players.filter(p => p.alive);

  if (role === 'witch') {
    _renderWitch(data, alive);
  } else if (role === 'cupid') {
    _renderCupid(alive);
  } else if (role === 'alpha_wolf') {
    _renderAlphaWolf(alive);
  } else if (role === 'seer') {
    _showArtifact(`
      <div class="seer-orb-wrap">
        <div class="seer-orb" id="seer-orb"></div>
      </div>`);
    _renderTargetGrid(alive, 'selected', (pid) => {
      _naSelected = pid;
      confirm.disabled = false;
      _seerOrbActivate();
    });
  } else if (role === 'werewolf') {
    _renderTargetGrid(alive.filter(p => !['werewolf', 'alpha_wolf'].includes(p.role_id)), 'wolf-locked', (pid) => {
      _naSelected = pid;
      confirm.disabled = false;
    });
  } else {
    _renderTargetGrid(alive, 'selected', (pid) => {
      _naSelected = pid;
      confirm.disabled = false;
    });
  }

  _setSection('action');
}

function _showSeerResult(data) {
  const state = _getState();
  const player = state.players.find(p => p.id === data.result.player_id);
  const name = player ? player.name : '?';
  const roleId = data.result.role_id;
  const isWolf = ['werewolf', 'alpha_wolf'].includes(roleId);

  document.getElementById('seer-name').textContent = name;

  const roleEl = document.getElementById('seer-role');
  roleEl.textContent = roleName(roleId);
  roleEl.className = 'night-result-role ' + (isWolf ? 'team-wolf' : 'team-village');

  // Apply reveal animation on the result box
  const box = document.querySelector('#night-seer .night-result');
  if (box) {
    box.classList.remove('seer-reveal');
    void box.offsetWidth; // force reflow to restart animation
    box.classList.add('seer-reveal');
  }

  document.getElementById('btn-seer-ack').textContent = t('ui.reveal.seen') || 'Compris';
  _setSection('seer');
}

function _showHunterAction(data) {
  const hunterId = data.player_id;
  _naSelected = null;

  _hideArtifact();

  document.getElementById('na-role-name').textContent = roleName('hunter');
  document.getElementById('na-prompt').textContent = t('role.hunter.death_prompt');
  document.getElementById('na-victim').style.display = 'none';
  document.getElementById('na-witch-potions').style.display = 'none';
  document.getElementById('btn-na-skip').style.display = 'none';

  const confirm = document.getElementById('btn-na-confirm');
  confirm.disabled = true;
  confirm.className = 'primary hunter-aim';
  confirm.textContent = '🔫 Tirer';

  const state = _getState();
  const targets = state.players.filter(p => p.alive && p.id !== hunterId);
  _renderTargetGrid(targets, 'selected', (pid) => {
    _naSelected = pid;
    confirm.disabled = false;
  });

  _setSection('action');
}

// ── Grid renderers ────────────────────────────────────────────────────────────

function _renderTargetGrid(players, selectionClass, onSelect) {
  const grid = document.getElementById('na-grid');
  grid.innerHTML = '';
  players.forEach(p => {
    const card = _makePlayerCard(p, () => {
      grid.querySelectorAll('.player-card').forEach(c => {
        c.classList.remove('selected', 'wolf-locked', 'lover-pick');
      });
      card.classList.add('selected');
      if (selectionClass !== 'selected') card.classList.add(selectionClass);
      onSelect(p.id);
    });
    grid.appendChild(card);
  });
}

function _renderWitch(data, alive) {
  _witchId = data.witch_id || null;
  _witchSaveAvail = data.witch_save_available !== false;
  _witchPoisonAvail = data.witch_poison_available !== false;
  _witchSaveTarget = null;
  _witchPoisonTarget = null;

  const victims = data.pending_kill_players || [];

  if (victims.length) {
    const victimBox = document.getElementById('na-victim');
    victimBox.style.display = '';
    victimBox.innerHTML = `<strong>Victime cette nuit :</strong> ${victims.map(p => p.name).join(', ')}`;
  }

  const witchBox = document.getElementById('na-witch-potions');
  witchBox.style.display = '';

  const grid = document.getElementById('na-grid');

  const saveBtn = document.getElementById('witch-save-btn');
  const poisonBtn = document.getElementById('witch-poison-btn');

  if (_witchSaveAvail && victims.length) {
    saveBtn.disabled = false;
    saveBtn.onclick = () => {
      if (_witchSaveTarget) {
        _witchSaveTarget = null;
        saveBtn.classList.remove('active');
      } else {
        _witchSaveTarget = victims[0].id;
        saveBtn.classList.add('active');
      }
    };
  } else {
    saveBtn.disabled = true;
    saveBtn.classList.remove('active');
  }

  if (_witchPoisonAvail) {
    poisonBtn.disabled = false;
    poisonBtn.onclick = () => {
      if (poisonBtn.classList.contains('active')) {
        poisonBtn.classList.remove('active');
        _witchPoisonTarget = null;
        grid.innerHTML = '';
      } else {
        poisonBtn.classList.add('active');
        const excludeIds = victims.map(v => v.id);
        _renderPoisonGrid(alive.filter(p => !excludeIds.includes(p.id)));
      }
    };
  } else {
    poisonBtn.disabled = true;
    poisonBtn.classList.remove('active');
  }

  document.getElementById('btn-na-confirm').disabled = false;
  document.getElementById('btn-na-skip').style.display = '';
}

function _renderPoisonGrid(players) {
  const grid = document.getElementById('na-grid');
  grid.innerHTML = '';
  players.forEach(p => {
    const card = _makePlayerCard(p, () => {
      grid.querySelectorAll('.player-card').forEach(c => c.classList.remove('selected', 'wolf-locked', 'lover-pick', 'targeted'));
      card.classList.add('targeted');
      _witchPoisonTarget = p.id;
    });
    grid.appendChild(card);
  });
}

function _renderCupid(alive) {
  const grid = document.getElementById('na-grid');
  grid.innerHTML = '';
  const confirm = document.getElementById('btn-na-confirm');

  alive.forEach(p => {
    const card = _makePlayerCard(p, () => {
      if (_cupidLovers.includes(p.id)) {
        _cupidLovers = _cupidLovers.filter(id => id !== p.id);
        card.classList.remove('selected', 'lover-pick');
      } else if (_cupidLovers.length < 2) {
        _cupidLovers.push(p.id);
        card.classList.add('selected', 'lover-pick');
      }
      confirm.disabled = _cupidLovers.length !== 2;
    });
    grid.appendChild(card);
  });
}

function _renderAlphaWolf(alive) {
  const grid = document.getElementById('na-grid');
  grid.innerHTML = '';
  const confirm = document.getElementById('btn-na-confirm');

  const targets = alive.filter(p => !['werewolf', 'alpha_wolf'].includes(p.role_id));
  if (targets.length === 0) {
    confirm.disabled = false;
    return;
  }

  targets.forEach(p => {
    const card = _makePlayerCard(p, () => {
      grid.querySelectorAll('.player-card').forEach(c => c.classList.remove('selected'));
      card.classList.add('selected');
      _naSelected = p.id;
    });
    grid.appendChild(card);
  });
}

// ── Button handlers ────────────────────────────────────────────────────────────

function _onSkip() {
  if (_nightRole === 'witch') {
    _send('submit_night_action', { role: 'witch', action: { player_id: _witchId } });
  } else if (_nightRole === 'cupid') {
    _send('submit_night_action', { role: 'cupid', action: { lovers: [] } });
  } else if (_nightRole === 'alpha_wolf') {
    _send('submit_night_action', { role: 'alpha_wolf', action: {} });
  } else if (_nightRole) {
    _send('submit_night_action', { role: _nightRole, action: {} });
  }
}

function _onConfirm() {
  if (!_nightRole) return;

  if (_nightRole === 'witch') {
    _send('submit_night_action', {
      role: 'witch',
      action: {
        player_id: _witchId,
        save_target: _witchSaveTarget || null,
        poison_target: _witchPoisonTarget || null,
      },
    });
    return;
  }

  if (_nightRole === 'cupid') {
    _send('submit_night_action', { role: 'cupid', action: { lovers: _cupidLovers } });
    return;
  }

  if (_nightRole === 'hunter') {
    if (_naSelected) {
      _flash('hunter');
      _send('submit_pending_action', { role: 'hunter', action: { target: _naSelected } });
    }
    return;
  }

  if (_nightRole === 'alpha_wolf') {
    _send('submit_night_action', {
      role: 'alpha_wolf',
      action: _naSelected ? { convert_target: _naSelected } : {},
    });
    return;
  }

  if (_naSelected) {
    if (_nightRole === 'werewolf') _flash('wolf');
    _send('submit_night_action', { role: _nightRole, action: { target: _naSelected } });
  }
}

function _makePlayerCard(player, onClick) {
  const card = document.createElement('div');
  card.className = 'player-card';
  card.innerHTML = `
    <div class="player-name">${player.name}</div>
    <div class="player-role"></div>`;
  card.addEventListener('click', onClick);
  return card;
}
