let _locale = {};

export async function loadLocale(lang) {
  const r = await fetch(`/loup_garou/locales/${lang}.json`);
  _locale = await r.json();
}

export function t(key, vars = {}) {
  let s = _locale[key] || '';
  for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, String(v));
  return s || key;
}

export const roleName = id => t(`role.${id}.name`) || id;
export const roleDesc = id => t(`role.${id}.description`) || '';
export const roleTeam = id => t(`role.${id}.team`) || '';
