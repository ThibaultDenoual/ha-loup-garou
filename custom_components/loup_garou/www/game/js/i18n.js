let _locale = {};

export async function loadLocale(lang) {
  const r = await fetch(`/loup_garou/locales/${lang}.json`);
  _locale = await r.json();
}

export function t(key, vars = {}) {
  const s = _locale[key];
  if (!s) return key;

  return s.replace(/\{(\w+)\}/g, (_, k) =>
    Object.hasOwn(vars, k)
      ? escHtml(String(vars[k]))
      : `{${k}}`
  );
}

export const roleName = id => t(`role.${id}.name`) || id;
export const roleDesc = id => t(`role.${id}.description`) || '';
export const roleTeam = id => t(`role.${id}.team`) || '';
