import { ref, setLanguage, storedLanguage, translate } from './i18n.js';
import { h, $ } from './dom.js';
import { connect, send } from './ws.js';
import * as tts from './tts.js';
import { ROLE_ORDER } from './roles.js';
import { sprite } from './sprites.js';
import { mountScenery, setConnection, setTime } from './ui.js';

let _cfg = {};
let _speakers = [];
// Lights picker state — selection is a Set of entity_ids so entity-list
// refreshes never drop the user's picks. Available lights are normalized
// to {entity_id, name, area, state} (backend sends objects; old string[]
// payloads still work).
let _lights = [];
let _picked = new Set();
let _filter = '';

// ── Tabs ─────────────────────────────────────────────────────────────────────

function initTabs() {
  const tabs = [...document.querySelectorAll('[role="tab"]')];
  const select = tab => {
    tabs.forEach(t => {
      const on = t === tab;
      t.setAttribute('aria-selected', String(on));
      t.tabIndex = on ? 0 : -1;
      $(t.getAttribute('aria-controls')).hidden = !on;
    });
  };
  tabs.forEach((tab, i) => {
    tab.addEventListener('click', () => select(tab));
    tab.addEventListener('keydown', e => {
      const step = { ArrowRight: 1, ArrowLeft: -1 }[e.key];
      const jump = { Home: 0, End: tabs.length - 1 }[e.key];
      if (step === undefined && jump === undefined) return;
      e.preventDefault();
      const next = tabs[jump ?? (i + step + tabs.length) % tabs.length];
      select(next);
      next.focus();
    });
  });
}

function renderRoleReference() {
  $('role-ref').replaceChildren(...ROLE_ORDER.map(id =>
    h('div', { class: 'role-row' },
      sprite(id, 3),
      h('span', { class: 'role-name', i18n: `role.${id}.name` }),
      h('span', { class: 'role-desc', i18n: `role.${id}.description` }))));
}

// ── Config form ──────────────────────────────────────────────────────────────

const audioSource = () => $('cfg-audio-source');
const audioOutput = () => $('cfg-audio-output');

function applyAudioVisibility() {
  const isHa = audioOutput().value === 'ha';
  $('cfg-ha-fields').hidden = !isHa;
  $('cfg-tts-engine-group').hidden = !(isHa && audioSource().value === 'tts');
}

function renderSpeakers() {
  const sel = $('cfg-speaker');
  const ids = ['', ..._speakers];
  sel.replaceChildren(...ids.map(id => (id
    ? h('option', { value: id, text: id })
    : h('option', { value: '', i18n: 'launcher.config.speaker_none' }))));
  sel.value = _cfg.speaker || '';
}

function renderSummary() {
  const items = [];
  if (_cfg.language) {
    items.push(['launcher.summary.language', { language: ref(`launcher.lang.${_cfg.language}`) }]);
  }
  if (_cfg.audio_output === 'ha') {
    items.push(_cfg.speaker
      ? ['launcher.summary.voice_ha', { speaker: _cfg.speaker }]
      : ['launcher.summary.voice_ha_none']);
  } else {
    items.push(['launcher.summary.voice_browser']);
  }
  items.push(_picked.size
    ? ['launcher.summary.lights', { count: _picked.size }]
    : ['launcher.summary.no_lights']);
  $('config-summary').replaceChildren(...items.map(i => h('li', { i18n: i })));
}

function applyConfig(cfg) {
  _cfg = cfg;
  audioSource().value = cfg.audio_source || 'tts';
  audioOutput().value = cfg.audio_output || 'browser';
  applyAudioVisibility();
  $('cfg-tts-engine').value = cfg.tts_engine || '';
  $('cfg-language').value = cfg.language || 'fr';
  _picked = new Set(cfg.lights || []);
  renderSpeakers();
  renderLights();
  renderSummary();
  if (cfg.language) setLanguage(cfg.language);
  if (cfg.version) translate($('version-footer'), 'ui.app.version', { version: cfg.version });
}

function applyEntities(entities) {
  _speakers = entities.speakers || [];
  _lights = (entities.lights || []).map(e => (typeof e === 'string'
    ? { entity_id: e, name: e, area: null, state: null }
    : {
      entity_id: e.entity_id || e.id || '',
      name: e.name || e.entity_id || e.id || '',
      area: e.area || null,
      state: e.state || null,
    })).filter(e => e.entity_id);
  renderSpeakers();
  renderLights();
}

function feedback(id, key, tone) {
  const el = $(id);
  if (!key) { el.textContent = ''; el.removeAttribute('data-i18n'); return; }
  translate(el, key);
  el.dataset.tone = tone || '';
}

// ── Lights picker ────────────────────────────────────────────────────────────

const lightLabel = e => (e.name && e.name !== e.entity_id ? e.name : e.entity_id);

function filteredLights() {
  const q = _filter.trim().toLowerCase();
  if (!q) return _lights;
  return _lights.filter(e =>
    (e.name || '').toLowerCase().includes(q)
    || e.entity_id.toLowerCase().includes(q)
    || (e.area || '').toLowerCase().includes(q));
}

function pickedChanged() {
  _cfg.lights = [..._picked];
  renderLights();
  renderSummary();
}

function renderLights() {
  // Selected lights that HA no longer reports stay as chips and are saved.
  const known = new Map(_lights.map(e => [e.entity_id, e]));
  $('cfg-lights-chips').replaceChildren(...[..._picked].map(id => {
    const e = known.get(id) || { entity_id: id, name: id };
    return h('span', { class: 'chip' },
      h('span', { title: id, text: lightLabel(e) }),
      h('button', {
        type: 'button',
        i18nLabel: ['ui.config.lights_remove', { name: lightLabel(e) }],
        on: { click: ev => { ev.stopPropagation(); _picked.delete(id); pickedChanged(); } },
      }, sprite('cross', 2)));
  }));
  $('cfg-lights-placeholder').hidden = _picked.size > 0;
  translate($('cfg-lights-count'), 'ui.config.lights_selected', { n: _picked.size });

  const rows = filteredLights();
  const list = $('cfg-lights-list');
  if (!rows.length) {
    list.replaceChildren(h('li', {
      class: 'lights-empty',
      i18n: _lights.length ? 'ui.config.lights_no_results' : 'ui.config.lights_empty',
    }));
    return;
  }
  list.replaceChildren(...rows.map(e => {
    const on = _picked.has(e.entity_id);
    const unavail = e.state === 'unavailable' || e.state === 'unknown';
    return h('li', {},
      h('button', {
        type: 'button',
        class: 'lights-opt' + (unavail ? ' unavail' : ''),
        role: 'option',
        'aria-selected': String(on),
        on: {
          click: () => {
            if (_picked.has(e.entity_id)) _picked.delete(e.entity_id);
            else _picked.add(e.entity_id);
            pickedChanged();
          },
        },
      },
        h('span', { class: 'box' }),
        h('span', {},
          h('span', { text: lightLabel(e) }),
          h('span', { class: 'eid', text: e.entity_id })),
        e.area ? h('span', { class: 'area', text: e.area }) : null));
  }));
}

function initLightsPicker() {
  const field = $('cfg-lights-field');
  const panel = $('cfg-lights-panel');
  const search = $('cfg-lights-search');
  const setOpen = open => {
    panel.hidden = !open;
    field.setAttribute('aria-expanded', String(open));
    if (open) search.focus();
  };
  field.addEventListener('click', () => setOpen(panel.hidden));
  field.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setOpen(panel.hidden); }
  });
  document.addEventListener('click', e => {
    if (!panel.hidden && !$('lights-picker').contains(e.target)) setOpen(false);
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && !panel.hidden) { setOpen(false); field.focus(); }
  });
  search.addEventListener('input', () => { _filter = search.value; renderLights(); });
  $('cfg-lights-all').addEventListener('click', () => {
    filteredLights().forEach(e => _picked.add(e.entity_id));
    pickedChanged();
  });
  $('cfg-lights-clear').addEventListener('click', () => {
    // Clear only the filtered rows when a search is active, else everything.
    if (_filter.trim()) filteredLights().forEach(e => _picked.delete(e.entity_id));
    else _picked.clear();
    pickedChanged();
  });
}

// ── Demo ─────────────────────────────────────────────────────────────────────

function setDemoRunning(running, key, tone) {
  $('btn-run-demo').disabled = running;
  $('btn-stop-demo').disabled = !running;
  $('demo-preset').disabled = running;
  if (key) feedback('demo-log', key, tone);
}

function renderPresets(presets) {
  $('demo-preset').replaceChildren(...presets.map(p => h('option', { value: p.key, i18n: p.label_key })));
}

// ── Messages ─────────────────────────────────────────────────────────────────

let _savePending = false;

function handleMessage(msg) {
  switch (msg.type) {
    case 'config':
      applyConfig(msg.config || {});
      if (_savePending) {
        _savePending = false;
        feedback('save-feedback', 'launcher.config.saved', 'ok');
        setTimeout(() => feedback('save-feedback', null), 3000);
      }
      break;
    case 'entities': applyEntities(msg.data || {}); break;
    case 'demo_presets': renderPresets(msg.presets || []); break;
    case 'demo_started': setDemoRunning(true, 'demo.running'); break;
    case 'demo_step': feedback('demo-log', `demo.step.${msg.data.step}`); break;
    case 'demo_finished': setDemoRunning(false, 'demo.finished', 'ok'); break;
    case 'demo_stopped': setDemoRunning(false, 'demo.stopped'); break;
    case 'demo_error': setDemoRunning(false, 'demo.failed', 'error'); break;
    case 'demo_rejected': setDemoRunning(false, `demo.rejected.${msg.data.reason}`, 'error'); break;
    // "Test the narration" and demos speak through this page in browser mode.
    case 'narrate': tts.speak(msg.data.text, msg.data.lang, msg.data.audio_url ?? null); break;
    case 'test_audio_done':
      $('btn-test-audio').disabled = false;
      feedback('test-audio-feedback', 'launcher.config.test_audio_done', 'ok');
      setTimeout(() => feedback('test-audio-feedback', null), 3000);
      break;
  }
}

function initActions() {
  audioSource().addEventListener('change', applyAudioVisibility);
  audioOutput().addEventListener('change', applyAudioVisibility);

  $('btn-test-audio').addEventListener('click', () => {
    $('btn-test-audio').disabled = true;
    feedback('test-audio-feedback', 'launcher.config.test_audio_running');
    send('test_audio');
  });

  $('btn-save-config').addEventListener('click', () => {
    _savePending = true;
    send('save_config', {
      audio_source: audioSource().value,
      audio_output: audioOutput().value,
      speaker: $('cfg-speaker').value,
      lights: [..._picked],
      language: $('cfg-language').value,
      tts_engine: $('cfg-tts-engine').value,
    });
  });

  $('btn-run-demo').addEventListener('click', () => {
    const preset = $('demo-preset').value;
    if (!preset) return;
    setDemoRunning(true, 'demo.running');
    send('run_demo', { preset });
  });
  $('btn-stop-demo').addEventListener('click', () => send('stop_demo'));
}

// ── Init ─────────────────────────────────────────────────────────────────────

async function init() {
  await setLanguage(storedLanguage() || document.documentElement.lang);
  mountScenery();
  setTime('night');
  $('play-art').replaceChildren(sprite('werewolf', 8));

  initTabs();
  renderRoleReference();
  initLightsPicker();
  initActions();
  applyAudioVisibility();
  renderSpeakers();
  renderLights();
  $('config-summary').replaceChildren(h('li', { i18n: 'launcher.summary.loading' }));

  tts.init(send);
  connect({
    onMessage: handleMessage,
    onReady: () => { send('get_config'); send('get_entities'); send('get_demos'); },
    onStatus: s => {
      setConnection($('ha-connection'), s, 'launcher.connection');
      if (s === 'open_from_ha') feedback('save-feedback', 'ui.ws.open_from_ha', 'error');
    },
  });
}

init();
