import { translate } from '../i18n.js';
import { h, $ } from '../dom.js';
import { teamOf } from '../roles.js';
import { avatar, sprite } from '../sprites.js';
import { choiceGrid } from '../ui.js';

let _answer;
let _getState;

// The open prompt and what its player has picked so far.
let _prompt = null;
let _pickName = null;
let _picked = [];
let _witch = null;   // { victims, save, poison } while the witch is up

export function init(answer, getState) {
  _answer = answer;
  _getState = getState;

  $('sleep-moon').replaceChildren(sprite('moon', 12));
  $('sleep-moon').firstChild.classList.add('bob');
  $('witch-save-icon').replaceChildren(sprite('potion_heal', 4));
  $('witch-poison-icon').replaceChildren(sprite('potion_poison', 4));

  $('btn-na-skip').addEventListener('click', () => _answer());
  $('btn-na-confirm').addEventListener('click', _onConfirm);
  $('btn-seer-ack').addEventListener('click', () => _answer());
  $('witch-save-btn').addEventListener('click', _toggleSave);
  $('witch-poison-btn').addEventListener('click', _togglePoison);
}

// ── Public API ────────────────────────────────────────────────────────────────

// No prompt means the village sleeps: the narrator is speaking, or no one is up.
export function render(prompt) {
  _prompt = prompt;
  _picked = [];
  _pickName = null;
  _witch = null;

  if (!prompt) {
    translate($('night-heading'), 'ui.night.heading', { n: _getState().night });
    _setSection('sleeping');
  } else if (prompt.kind === 'seer_result') {
    _showSeerResult(prompt.info);
  } else if (prompt.role === 'witch') {
    _showWitch(prompt);
  } else {
    _showPick(prompt);
  }
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

function _playersIn(options) {
  return _getState().players.filter(p => options.includes(p.id));
}

const GRID_VARIANT = { werewolf: 'wolf', hunter: 'wolf', cupid: 'love' };
const PROMPT_KEY = {
  hunter_shot: 'role.hunter.death_prompt',
  sheriff_election: 'role.sheriff.election_prompt',
};

// A prompt with one pick: the core says who can be chosen and how many.
function _showPick(prompt) {
  const { role, kind, picks } = prompt;
  const [name, pick] = Object.entries(picks)[0];
  _pickName = name;
  const max = Math.max(...pick.counts);
  const legal = n => pick.counts.includes(n);

  _prepareAction(role, PROMPT_KEY[kind] || `role.${role}.action_prompt`, {
    skip: legal(0) && pick.options.length > 0,
    confirmKey: kind === 'hunter_shot' ? 'role.hunter.shoot_confirm' : 'ui.night.confirm',
  });

  if (!pick.options.length) {
    _status('ui.night.no_targets');
    $('btn-na-confirm').disabled = false;
  } else {
    if (role === 'cupid') _status('ui.night.cupid_count', { count: 0 });
    $('na-grid').replaceChildren(choiceGrid(_playersIn(pick.options), {
      max,
      variant: GRID_VARIANT[role] || 'pick',
      onChange: picked => {
        _picked = picked;
        if (role === 'cupid') _status('ui.night.cupid_count', { count: picked.length });
        $('btn-na-confirm').disabled = !(picked.length && legal(picked.length));
      },
    }));
  }
  _setSection('action');
}

function _showWitch(prompt) {
  const { picks, info } = prompt;
  _prepareAction('witch', 'role.witch.action_prompt');
  _witch = {
    victims: info.victims,
    canSave: picks.save_target.options.length > 0,
    canPoison: picks.poison_target.options.length > 0,
    save: false,
    poison: false,
  };

  const box = $('na-victim');
  box.hidden = false;
  if (info.victims.length) {
    box.replaceChildren(
      sprite('skull', 4),
      h('div', {},
        h('div', { class: 'dim small', i18n: 'role.witch.victim_label' }),
        h('div', { class: 'player-name', text: info.victims.map(p => p.name).join(', ') })));
  } else {
    box.replaceChildren(h('p', { i18n: 'ui.night.witch_no_victim' }));
  }

  const save = $('witch-save-btn');
  save.disabled = !_witch.canSave;
  translate($('witch-save-label'), info.save_used ? 'ui.night.witch_used' : 'ui.night.witch_save');
  const poison = $('witch-poison-btn');
  poison.disabled = !_witch.canPoison;
  translate($('witch-poison-label'), _witch.canPoison ? 'ui.night.witch_poison' : 'ui.night.witch_used');
  _syncPotions();

  $('na-witch-potions').hidden = false;
  // The witch may always confirm: no potion is a valid choice.
  $('btn-na-confirm').disabled = false;
  _setSection('action');
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
  $('na-grid').replaceChildren(choiceGrid(_playersIn(_prompt.picks.poison_target.options), {
    variant: 'poison',
    onChange: picked => { _picked = picked; },
  }));
}

function _showSeerResult({ name, role_id: roleId }) {
  $('seer-sprite').replaceChildren(sprite('seer', 5));
  $('seer-avatar').replaceChildren(avatar(name, 8));
  $('seer-name').textContent = name;
  const roleEl = $('seer-role');
  translate(roleEl, `role.${roleId}.name`);
  roleEl.className = `role-big team-${teamOf(roleId)}`;
  _setSection('seer');
  $('btn-seer-ack').focus();
}

// ── Buttons ───────────────────────────────────────────────────────────────────

function _onConfirm() {
  if (!_prompt) return;
  if (_witch) {
    _answer({
      save_target: _witch.save ? _witch.victims[0].id : null,
      poison_target: _witch.poison ? _picked[0] ?? null : null,
    });
  } else {
    _answer({ [_pickName]: _picked });
  }
}
