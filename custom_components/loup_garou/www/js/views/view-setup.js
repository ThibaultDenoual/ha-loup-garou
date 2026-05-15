/* ═══════════════════════════════════════════
   LOUP GAROU — ViewSetup
   Game configuration, player names, roles
   ═══════════════════════════════════════════ */

const ViewSetup = (() => {
  const { qs, createElement, escapeHtml, showToast, setHTML, setText, hide, show, toggle, addClass, removeClass } = LoupGarouUtils;
  const { t, getRoleName, getRoleSymbol, getRoleColor } = LoupGarouI18n;

  const PRESETS = {
    small:  { name: 'small',  roles: { Villager:3, Werewolf:1, Seer:1, Doctor:1 } },
    medium: { name: 'medium', roles: { Villager:3, Werewolf:2, 'Alpha Wolf':1, Seer:1, Doctor:1, Witch:1 } },
    large:  { name: 'large',  roles: { Villager:3, Werewolf:2, 'Alpha Wolf':1, Minion:1, Seer:1, Doctor:1, Bodyguard:1, Witch:1, Hunter:1, Cupid:1 } },
    chaos:  { name: 'chaos',  roles: { Villager:3, Werewolf:2, 'Serial Killer':1, Jester:1, Seer:1, Doctor:1, Witch:1 } },
  };

  const ROLE_KEYS = [
    'Villager', 'Werewolf', 'Seer', 'Doctor', 'Hunter',
    'Witch', 'Bodyguard', 'Cupid', 'Alpha Wolf', 'Minion',
    'Serial Killer', 'Jester'
  ];

  let _players = ['', '', '', '', '', ''];
  let _roleConfig = { Villager: 3, Werewolf: 1, Seer: 1, Doctor: 1 };
  let _preset = 'small';
  let _language = 'fr';
  let _onStart = null;

  /* ── Render the view into #view-setup ── */
  function render(opts = {}) {
    if (opts.onStart) _onStart = opts.onStart;
    if (opts.language) _language = opts.language;

    const container = qs('#view-setup');
    if (!container) return;

    setHTML(container, `
      <div class="view__header">
        <h2 class="view__title">${escapeHtml(t('setup.title'))}</h2>
        <p class="view__subtitle">${escapeHtml(t('setup.subtitle'))}</p>
      </div>

      <div class="view__body">
        <div class="setup-grid stagger-children">

          <!-- Language -->
          <div class="card">
            <div class="card__title">${escapeHtml(t('setup.language'))}</div>
            <div class="flex gap-3">
              <button class="btn btn-sm ${_language === 'fr' ? 'btn-seer' : 'btn-secondary'}" id="lang-fr">🇫🇷 Français</button>
              <button class="btn btn-sm ${_language === 'en' ? 'btn-seer' : 'btn-secondary'}" id="lang-en">🇬🇧 English</button>
            </div>
          </div>

          <!-- Players -->
          <div class="card">
            <div class="card__title">${escapeHtml(t('setup.players_title'))}</div>
            <div class="players-input-list" id="players-list"></div>
            <div style="margin-top:var(--sp-4)">
              <button class="btn btn-ghost btn-sm" id="add-player-btn">+ ${escapeHtml(t('setup.add_player'))}</button>
            </div>
            <div style="margin-top:var(--sp-3); font-size:var(--text-xs); color:var(--color-ash); letter-spacing:var(--tracking-wide);" id="player-count-label"></div>
          </div>

          <!-- Preset selector -->
          <div class="card">
            <div class="card__title">${escapeHtml(t('setup.preset_title'))}</div>
            <div class="preset-grid" id="preset-grid"></div>
          </div>

          <!-- Custom roles -->
          <div class="card" id="custom-roles-card">
            <div class="card__title">${escapeHtml(t('setup.custom_roles'))}</div>
            <div class="role-config-grid" id="role-config-grid"></div>
          </div>

        </div>
      </div>

      <div class="view__footer">
        <button class="btn btn-primary btn-lg" id="start-game-btn">
          ${escapeHtml(t('setup.start_game'))}
        </button>
      </div>
    `);

    _renderPlayerList();
    _renderPresets();
    _renderRoleConfig();
    _attachEvents();
  }

  function _renderPlayerList() {
    const list = qs('#players-list');
    if (!list) return;
    setHTML(list, '');

    _players.forEach((name, i) => {
      const row = createElement('div', { class: 'player-input-row' });

      const num = createElement('span', { class: 'player-num' }, [`${i + 1}`]);

      const input = createElement('input', {
        class: 'input',
        type: 'text',
        placeholder: t('setup.player_placeholder'),
        value: name,
        'data-index': String(i),
        maxlength: '24'
      });
      input.value = name;
      input.addEventListener('input', e => {
        _players[i] = e.target.value;
        _updatePlayerCount();
      });

      const removeBtn = createElement('button', {
        class: 'btn btn-icon btn-ghost',
        title: t('setup.remove_player'),
        style: { color: 'var(--color-mist)' }
      }, ['×']);
      removeBtn.addEventListener('click', () => {
        if (_players.length <= 4) {
          showToast(t('setup.players_min', { n: 4 }), { type: 'error' });
          return;
        }
        _players.splice(i, 1);
        _renderPlayerList();
        _syncPresetToCount();
      });

      row.appendChild(num);
      row.appendChild(input);
      row.appendChild(removeBtn);
      list.appendChild(row);
    });

    _updatePlayerCount();
  }

  function _updatePlayerCount() {
    const el = qs('#player-count-label');
    if (el) el.textContent = t('setup.total', { n: _players.length });
  }

  function _renderPresets() {
    const grid = qs('#preset-grid');
    if (!grid) return;
    setHTML(grid, '');

    const detailKeys = {
      small: t('setup.preset_small_detail'),
      medium: t('setup.preset_medium_detail'),
      large: t('setup.preset_large_detail'),
      chaos: t('setup.preset_chaos_detail'),
    };

    for (const [key, preset] of Object.entries(PRESETS)) {
      const btn = createElement('button', {
        class: `preset-btn ${_preset === key ? 'active' : ''}`,
        'data-preset': key
      });
      btn.innerHTML = `
        <div class="preset-btn__name">${escapeHtml(t(`setup.preset_${key}`))}</div>
        <div class="preset-btn__detail">${escapeHtml(detailKeys[key] || '')}</div>
      `;
      btn.addEventListener('click', () => {
        _preset = key;
        _roleConfig = Object.assign({}, preset.roles);
        // Adjust player count to match preset total
        const total = Object.values(_roleConfig).reduce((a, b) => a + b, 0);
        while (_players.length < total) _players.push('');
        while (_players.length > total) _players.pop();
        _renderPlayerList();
        _renderPresets();
        _renderRoleConfig();
      });
      grid.appendChild(btn);
    }
  }

  function _renderRoleConfig() {
    const grid = qs('#role-config-grid');
    if (!grid) return;
    setHTML(grid, '');

    for (const roleKey of ROLE_KEYS) {
      const count = _roleConfig[roleKey] || 0;
      const color = getRoleColor(roleKey);
      const symbol = getRoleSymbol(roleKey);

      const item = createElement('div', { class: 'role-config-item' });
      item.innerHTML = `
        <div class="role-config-item__name" style="color:${color}">
          <span style="margin-right:var(--sp-2)">${symbol}</span>${escapeHtml(getRoleName(roleKey))}
        </div>
      `;

      const stepper = createElement('div', { class: 'number-stepper' });
      const minusBtn = createElement('button', { class: 'stepper-btn' }, ['−']);
      const valueEl  = createElement('div', { class: 'stepper-value' }, [String(count)]);
      const plusBtn  = createElement('button', { class: 'stepper-btn' }, ['+']);

      minusBtn.addEventListener('click', () => {
        if ((_roleConfig[roleKey] || 0) > 0) {
          _roleConfig[roleKey] = (_roleConfig[roleKey] || 0) - 1;
          valueEl.textContent = _roleConfig[roleKey];
          _preset = 'custom';
          _renderPresets();
          // Adjust players
          _syncPlayersToRoleTotal();
        }
      });

      plusBtn.addEventListener('click', () => {
        _roleConfig[roleKey] = (_roleConfig[roleKey] || 0) + 1;
        valueEl.textContent = _roleConfig[roleKey];
        _preset = 'custom';
        _renderPresets();
        _syncPlayersToRoleTotal();
      });

      stepper.appendChild(minusBtn);
      stepper.appendChild(valueEl);
      stepper.appendChild(plusBtn);
      item.appendChild(stepper);
      grid.appendChild(item);
    }
  }

  function _syncPlayersToRoleTotal() {
    const total = Object.values(_roleConfig).reduce((a, b) => a + b, 0);
    while (_players.length < total) _players.push('');
    while (_players.length > total) _players.pop();
    _renderPlayerList();
  }

  function _syncPresetToCount() {
    _renderPresets();
    _renderRoleConfig();
  }

  function _attachEvents() {
    const addBtn = qs('#add-player-btn');
    if (addBtn) {
      addBtn.addEventListener('click', () => {
        if (_players.length >= 20) {
          showToast('Maximum 20 joueurs', { type: 'error' });
          return;
        }
        _players.push('');
        _renderPlayerList();
      });
    }

    const langFr = qs('#lang-fr');
    const langEn = qs('#lang-en');
    if (langFr) langFr.addEventListener('click', () => {
      _language = 'fr';
      LoupGarouI18n.setLanguage('fr');
      render();
    });
    if (langEn) langEn.addEventListener('click', () => {
      _language = 'en';
      LoupGarouI18n.setLanguage('en');
      render();
    });

    const startBtn = qs('#start-game-btn');
    if (startBtn) {
      startBtn.addEventListener('click', () => {
        if (!_validate()) return;
        if (_onStart) {
          _onStart({
            player_names: _players.map(n => n.trim()),
            role_config: _buildRoleConfigPayload(),
            language: _language
          });
        }
      });
    }
  }

  function _validate() {
    const names = _players.map(n => n.trim()).filter(Boolean);
    if (names.length < 4) {
      showToast(t('setup.players_min', { n: 4 }), { type: 'error' });
      return false;
    }
    if (names.length !== _players.length) {
      showToast(t('setup.players_names'), { type: 'error' });
      return false;
    }
    const roleTotal = Object.values(_roleConfig).reduce((a, b) => a + b, 0);
    if (roleTotal !== _players.length) {
      showToast(t('setup.roles_mismatch', { n: _players.length }), { type: 'error' });
      return false;
    }
    return true;
  }

  function _buildRoleConfigPayload() {
    // Send preset name if applicable, else custom config
    if (_preset && _preset !== 'custom') {
      return { preset: _preset };
    }
    // Convert { RoleKey: count } → flat role name array
    const roles = [];
    for (const [key, count] of Object.entries(_roleConfig)) {
      for (let i = 0; i < count; i++) roles.push(key);
    }
    return { roles };
  }

  function _show() {
    const el = qs('#view-setup');
    if (el) el.classList.add('active');
  }

  function _hide() {
    const el = qs('#view-setup');
    if (el) el.classList.remove('active');
  }

  return { render, show: _show, hide: _hide };
})();

if (typeof module !== 'undefined') module.exports = ViewSetup;
