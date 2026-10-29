// Every visible string goes through this module. Elements remember the key
// they were translated with (data-i18n*), so a language switch is one pass
// over the DOM instead of a re-render of every view.

const SUPPORTED = ['fr', 'en'];
const FALLBACK = 'fr';
const STORAGE_KEY = 'loup_garou.lang';

// data-i18n-<suffix> → attribute it fills.
const ATTRS = {
  placeholder: 'placeholder',
  'aria-label': 'aria-label',
  title: 'title',
};

let _lang = null;
let _strings = {};
let _loading = null;
const _listeners = new Set();

export function currentLanguage() { return _lang; }

export function storedLanguage() {
  try { return localStorage.getItem(STORAGE_KEY); } catch { return null; }
}

function normalize(lang) {
  return SUPPORTED.includes(lang) ? lang : FALLBACK;
}

export async function setLanguage(lang) {
  lang = normalize(lang);
  if (lang === _lang) return;
  const token = {};
  _loading = token;
  const r = await fetch(`/loup_garou/locales/${lang}.json`);
  const strings = await r.json();
  if (_loading !== token) return;  // a newer request won
  _strings = strings;
  _lang = lang;
  document.documentElement.lang = lang;
  try { localStorage.setItem(STORAGE_KEY, lang); } catch { /* private mode */ }
  applyTranslations(document);
  _listeners.forEach(fn => fn(lang));
}

export function onLanguageChange(fn) { _listeners.add(fn); }

export function has(key) { return typeof _strings[key] === 'string'; }

// A var may itself be a reference to another key: { t: 'role.seer.name' }.
export const ref = (key, vars) => ({ t: key, vars });

function resolve(value) {
  if (value && typeof value === 'object' && 't' in value) return t(value.t, value.vars);
  return String(value);
}

export function t(key, vars = {}) {
  const s = _strings[key];
  if (typeof s !== 'string') return key;
  return s.replace(/\{(\w+)\}/g, (match, k) => (Object.hasOwn(vars, k) ? resolve(vars[k]) : match));
}

function store(el, name, key, vars) {
  el.setAttribute(name, key);
  if (vars) el.setAttribute(`${name}-vars`, JSON.stringify(vars));
  else el.removeAttribute(`${name}-vars`);
}

function readVars(el, name) {
  const raw = el.getAttribute(`${name}-vars`);
  return raw ? JSON.parse(raw) : {};
}

// Sets el's text from key and keeps it translated on language change.
export function translate(el, key, vars) {
  store(el, 'data-i18n', key, vars);
  el.textContent = t(key, vars);
  return el;
}

export function translateAttr(el, attr, key, vars) {
  store(el, `data-i18n-${attr}`, key, vars);
  el.setAttribute(ATTRS[attr], t(key, vars));
  return el;
}

export function applyTranslations(root) {
  const scope = root.querySelectorAll ? root : document;
  scope.querySelectorAll('[data-i18n]').forEach(el => {
    el.textContent = t(el.getAttribute('data-i18n'), readVars(el, 'data-i18n'));
  });
  for (const [suffix, attr] of Object.entries(ATTRS)) {
    const name = `data-i18n-${suffix}`;
    scope.querySelectorAll(`[${name}]`).forEach(el => {
      el.setAttribute(attr, t(el.getAttribute(name), readVars(el, name)));
    });
  }
}
