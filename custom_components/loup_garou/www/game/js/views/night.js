import { translate } from '../i18n.js';
import { h, $ } from '../dom.js';
import { isPack, teamOf } from '../roles.js';
import { avatar, sprite } from '../sprites.js';
import { choiceGrid } from '../ui.js';

let _send;
let _getState;

// The waking role and what its player has picked so far.
let _role = null;
let _picked = [];
let _witch = null;   // { id, save, poison } while the witch is up

export function init(send, getState) {
  _send = send;
  _getState = getState;

  $('sleep-moon').replaceChildren(sprite('moon', 12));
  $('sleep-moon').firstChild.classList.add('bob');
  $('witch-save-icon').replaceChildren(sprite('potion_heal', 4));
  $('witch-poison-icon').replaceChildren(sprite('potion_poison', 4));

  $('btn-na-skip').addEventListener('click', _onSkip);
  $('btn-na-confirm').addEventListener('click', _onConfirm);
  $('btn-seer-ack').addEventListener('click', () => {
    _send('submit_pending_action', { role: 'seer', action: {} });
  });
  $('witch-save-btn').addEventListener('click', _toggleSave);
  $('witch-poison-btn').addEventListener('click', _togglePoison);
}

// ── Public API ────────────────────────────────────────────────────────────────

export function showSleeping() {
  _role = null;
  _picked = [];
  _witch = null;
  translate($('night-heading'), 'ui.night.heading', { n: _getState().night_number });
  _setSection('sleeping');
}

export function onWake(data) {
  _role = data.role;
  _picked = [];
  _witch = null;

  if (data.result) _showSeerResult(data.result);
  else if (data.player_id && data.role === 'hunter') _showHunter(data.player_id);
  else _showAction(data);
}

export function onSleep() {
  showSleeping();
}

// ── Sections ──────────────────────────────────────────────────────────────────

function _setSection(which) {
  $('night-sleeping').hidden = which !== 'sleeping';
  $('night-action').hidden = which !== 'action';
  $('night-seer').hidden = which !== 'seer';
  $('btn-seer-ack').hidden = which !== 'seer';
  $('btn-na-confirm').hidden = which !== 'action';
  if (which !== 'action') $('btn-na-skip').hidden = true;
}

// Resets the action panel for a role: heading, prompt, buttons.
function _prepareAction(role, promptKey, { skip = true, confirmKey = 'ui.night.confirm' } = {}) {
  $('na-sprite').replaceChildren(sprite(role, 5));
  translate($('na-role-name'), `role.${role}.name`);
  translate($('na-prompt'), promptKey);
  $('na-victim').hidden = true;
  $('na-witch-potions').hidden = true;
  $('na-status').hidden = true;
  $('na-grid').replaceChildren();
  $('btn-na-skip').hidden = !skip;
  const confirm = $('btn-na-confirm');
  translate(confirm, confirmKey);
  confirm.className = role === 'hunter' ? 'btn btn-danger' : 'btn btn-primary';
  confirm.disabled = true;
}

function _status(key, vars) {
  const el = $('na-status');
  el.hidden = false;
  translate(el, key, vars);
}

function _alive() {
  return _getState().players.filter(p => p.alive);
}

// Single-pick grid that enables confirm once someone is chosen.
function _singleGrid(players, variant = 'pick') {
  $('na-grid').replaceChildren(choiceGrid(players, {
    variant,
    onChange: picked => { _picked = picked; $('btn-na-confirm').disabled = !picked.length; },
  }));
}

function _showAction(data) {
  const role = data.role;
  _prepareAction(role, `role.${role}.action_prompt`);
  const alive = _alive();

  if (role === 'witch') {
    _showWitch(data, alive);
  } else if (role === 'cupid') {
    _status('ui.night.cupid_count', { count: 0 });
    $('na-grid').replaceChildren(choiceGrid(alive, {
      max: 2,
      variant: 'love',
      onChange: picked => {
        _picked = picked;
        _status('ui.night.cupid_count', { count: picked.length });
        $('btn-na-confirm').disabled = picked.length !== 2;
      },
    }));
  } else if (role === 'werewolf' || role === 'alpha_wolf') {
    const prey = alive.filter(p => !isPack(p.role_id));
    if (!prey.length && role === 'alpha_wolf') {
      _status('ui.night.no_targets');
      $('btn-na-confirm').disabled = false;
    } else {
      _singleGrid(prey, 'wolf');
    }
  } else {
    _singleGrid(alive);
  }

  _setSection('action');
}

function _showWitch(data, alive) {
  const victims = data.pending_kill_players || [];
  _witch = {
    id: data.witch_id || null,
    victims,
    alive,
    canSave: data.witch_save_available !== false && victims.length > 0,
    canPoison: data.witch_poison_available !== false,
    save: false,
    poison: false,
  };

  const box = $('na-victim');
  box.hidden = false;
  if (victims.length) {
    box.replaceChildren(
      sprite('skull', 4),
      h('div', {},
        h('div', { class: 'dim small', i18n: 'role.witch.victim_label' }),
        h('div', { class: 'player-name', text: victims.map(p => p.name).join(', ') })));
  } else {
    box.replaceChildren(h('p', { i18n: 'ui.night.witch_no_victim' }));
  }

  const save = $('witch-save-btn');
  save.disabled = !_witch.canSave;
  translate($('witch-save-label'),
    data.witch_save_available === false ? 'ui.night.witch_used' : 'ui.night.witch_save');
  const poison = $('witch-poison-btn');
  poison.disabled = !_witch.canPoison;
  translate($('witch-poison-label'), _witch.canPoison ? 'ui.night.witch_poison' : 'ui.night.witch_used');
  _syncPotions();

  $('na-witch-potions').hidden = false;
  // The witch may always confirm: no potion is a valid choice.
  $('btn-na-confirm').disabled = false;
}

function _syncPotions() {
  for (const [id, on] of [['witch-save-btn', _witch.save], ['witch-poison-btn', _witch.poison]]) {
    const btn = $(id);
    btn.setAttribute('aria-pressed', String(on));
    btn.classList.toggle('active', on);
  }
}

function _toggleSave() {
  if (!_witch?.canSave) return;
  _witch.save = !_witch.save;
  _syncPotions();
}

function _togglePoison() {
  if (!_witch?.canPoison) return;
  _witch.poison = !_witch.poison;
  _picked = [];
  _syncPotions();
  if (!_witch.poison) {
    $('na-grid').replaceChildren();
    return;
  }
  const victimIds = _witch.victims.map(v => v.id);
  $('na-grid').replaceChildren(choiceGrid(_witch.alive.filter(p => !victimIds.includes(p.id)), {
    variant: 'poison',
    onChange: picked => { _picked = picked; },
  }));
}

function _showSeerResult(result) {
  const player = _getState().players.find(p => p.id === result.player_id);
  const name = player ? player.name : '?';
  $('seer-sprite').replaceChildren(sprite('seer', 5));
  $('seer-avatar').replaceChildren(avatar(name, 8));
  $('seer-name').textContent = name;
  const roleEl = $('seer-role');
  translate(roleEl, `role.${result.role_id}.name`);
  roleEl.className = `role-big team-${teamOf(result.role_id)}`;
  _setSection('seer');
  $('btn-seer-ack').focus();
}

function _showHunter(hunterId) {
  _prepareAction('hunter', 'role.hunter.death_prompt', {
    skip: false,
    confirmKey: 'role.hunter.shoot_confirm',
  });
  _singleGrid(_alive().filter(p => p.id !== hunterId), 'wolf');
  _setSection('action');
}

// ── Button handlers ───────────────────────────────────────────────────────────

function _submit(action) {
  _send('submit_night_action', { role: _role, action });
}

function _onSkip() {
  if (!_role) return;
  if (_role === 'witch') _submit({ player_id: _witch?.id ?? null });
  else if (_role === 'cupid') _submit({ lovers: [] });
  else _submit({});
}

function _onConfirm() {
  if (!_role) return;
  const [target] = _picked;

  switch (_role) {
    case 'witch':
      _submit({
        player_id: _witch.id,
        save_target: _witch.save ? _witch.victims[0].id : null,
        poison_target: _witch.poison ? target ?? null : null,
      });
      break;
    case 'cupid':
      _submit({ lovers: _picked });
      break;
    case 'hunter':
      if (target) _send('submit_pending_action', { role: 'hunter', action: { target } });
      break;
    case 'alpha_wolf':
      _submit(target ? { convert_target: target } : {});
      break;
    default:
      if (target) _submit({ target });
  }
}
