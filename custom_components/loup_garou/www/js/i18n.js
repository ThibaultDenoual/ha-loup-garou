/* ═══════════════════════════════════════════
   LOUP GAROU — i18n
   Uses external locales.js
   ═══════════════════════════════════════════ */

const LoupGarouI18n = (() => {
  // Translations are loaded from locales.js (LoupGarouLocales)
  let _lang = 'fr';

  function setLanguage(lang) {
    if (LoupGarouLocales[lang]) {
      _lang = lang;
    }
  }

  function getLanguage() { return _lang; }

  function t(key, vars = {}) {
    const parts = key.split('.');
    let val = LoupGarouLocales[_lang];
    for (const part of parts) {
      if (val == null) break;
      val = val[part];
    }
    if (val == null) {
      // Fallback to EN
      val = LoupGarouLocales['en'];
      for (const part of parts) {
        if (val == null) break;
        val = val[part];
      }
    }
    if (val == null) return key;
    if (typeof val !== 'string') return key;
    // Interpolate {varName}
    return val.replace(/\{(\w+)\}/g, (_, k) => (vars[k] != null ? vars[k] : `{${k}}`));
  }

  function getRoleName(roleKey) {
    return t(`roles.${roleKey}.name`) || roleKey;
  }

  function getRoleDesc(roleKey) {
    return t(`roles.${roleKey}.desc`) || '';
  }

  function getRoleColor(roleKey) {
    const colors = {
      'Werewolf':      'var(--color-wolf)',
      'Alpha Wolf':    'var(--color-wolf)',
      'Minion':        'var(--color-wolf)',
      'Seer':          'var(--color-seer)',
      'Doctor':        'var(--color-doctor)',
      'Bodyguard':     'var(--color-hunter)',
      'Hunter':        'var(--color-hunter)',
      'Witch':         'var(--color-witch)',
      'Cupid':         'var(--color-jester)',
      'Villager':      'var(--color-village)',
      'Serial Killer': 'var(--color-serial)',
      'Jester':        'var(--color-jester)',
    };
    return colors[roleKey] || 'var(--color-pale)';
  }

  function getRoleGlow(roleKey) {
    const glows = {
      'Werewolf':   'var(--color-wolf-glow)',
      'Alpha Wolf': 'var(--color-wolf-glow)',
      'Minion':     'var(--color-wolf-glow)',
      'Seer':       'var(--color-seer-glow)',
    };
    return glows[roleKey] || 'rgba(255,255,255,0.15)';
  }

  function getRoleTeam(roleKey) {
    const teams = {
      'Werewolf': 'wolf', 'Alpha Wolf': 'wolf', 'Minion': 'wolf',
      'Serial Killer': 'solo', 'Jester': 'solo',
    };
    return teams[roleKey] || 'village';
  }

  function getRoleSymbol(roleKey) {
    const symbols = {
      'Werewolf':      '🐺',
      'Alpha Wolf':    '🐺',
      'Minion':        '🩸',
      'Seer':          '🔮',
      'Doctor':        '💊',
      'Bodyguard':     '🛡️',
      'Hunter':        '🏹',
      'Witch':         '🧪',
      'Cupid':         '💘',
      'Villager':      '🏡',
      'Serial Killer': '🔪',
      'Jester':        '🎭',
    };
    return symbols[roleKey] || '❓';
  }

  function getTeamLabel(team) {
    if (team === 'wolf')    return t('reveal.team_wolf');
    if (team === 'solo')    return t('reveal.team_solo');
    return t('reveal.team_village');
  }

  return {
    setLanguage,
    getLanguage,
    t,
    getRoleName,
    getRoleDesc,
    getRoleColor,
    getRoleGlow,
    getRoleTeam,
    getRoleSymbol,
    getTeamLabel
  };
})();

// Export for module systems
if (typeof module !== 'undefined') module.exports = LoupGarouI18n;
