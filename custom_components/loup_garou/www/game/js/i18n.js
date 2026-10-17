let _locale = {};
let _language = null;

export async function loadLocale(lang) {
  const language = ['en', 'fr'].includes(lang) ? lang : 'fr';
  if (_language === language) return language;

  const r = await fetch(`/loup_garou/locales/${language}.json`);
  if (!r.ok) throw new Error(`Could not load ${language} locale`);
  _locale = await r.json();
  _language = language;
  document.documentElement.lang = language;
  applyTranslations();
  return language;
}

export function currentLanguage() {
  return _language;
}

export function applyTranslations(root = document) {
  root.querySelectorAll('[data-i18n]').forEach(el => {
    el.textContent = t(el.dataset.i18n);
  });
  root.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    el.setAttribute('placeholder', t(el.dataset.i18nPlaceholder));
  });
  root.querySelectorAll('[data-i18n-aria-label]').forEach(el => {
    el.setAttribute('aria-label', t(el.dataset.i18nAriaLabel));
  });
}

export function t(key, vars = {}) {
  let s = _locale[key] || '';
  for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, String(v));
  return s || key;
}

export const roleName = id => t(`role.${id}.name`) || id;
export const roleDesc = id => t(`role.${id}.description`) || '';
export const roleTeam = id => t(`role.${id}.team`) || '';
