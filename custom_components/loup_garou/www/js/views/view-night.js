/* ═══════════════════════════════════════════
   LOUP GAROU — ViewNight
   Night phase: Seer investigation + Wolf kill
   ═══════════════════════════════════════════ */

const ViewNight = (() => {
  const { qs, setHTML, escapeHtml, showToast, createElement, addClass, removeClass } = LoupGarouUtils;
  const { t, getRoleColor } = LoupGarouI18n;

  let _state   = null;
  let _callbacks = {};
  let _selectedTarget = null;

  /* ── MAIN RENDER ── */
  function render(state, opts = {}) {
    _state = state;
    _callbacks = opts;
    _selectedTarget = null;

    const container = qs('#view-night');
    if (!container) return;

    const phase  = state.phase || '';
    const round  = state.round || 1;
    const players = state.players || [];
    const alive   = players.filter(p => p.alive);

    // Determine sub-phase
    const isSeer  = phase === 'night_seer_act';
    const isWolf  = phase === 'night_wolf_act';
    const isSeerWake = phase === 'night_seer_wake';
    const isWolfWake = phase === 'night_wolf_wake';
    const isNightStart = ['night_start', 'night_seer_sleep', 'night_wolf_sleep'].includes(phase);

    // Body class for ambient lighting
    container.className = container.className.replace(/\b(seer|wolf)-phase\b/g, '').trim();
    if (isSeer) container.classList.add('seer-phase');
    if (isWolf) container.classList.add('wolf-phase');

    // Title
    let phaseLabel = t('night.title');
    let subLabel   = t('night.subtitle', { n: round });
    let roleLabel  = '';
    let instruction = '';
    let roleIndicatorCls = '';

    if (isSeer) {
      roleLabel = t('night.phase_seer');
      instruction = t('night.seer_instruction');
      roleIndicatorCls = 'seer-indicator';
    } else if (isWolf) {
      roleLabel = t('night.phase_wolves');
      instruction = t('night.wolves_instruction');
      roleIndicatorCls = 'wolf-indicator';
    } else if (isSeerWake) {
      instruction = t('night.seer_wake');
    } else if (isWolfWake) {
      instruction = t('night.wolves_wake');
    } else if (isNightStart) {
      instruction = t('night.village_sleeps');
    }

    // Seer result (if available)
    const seerResult = state.seer_result_pending;
    const nightActionsCompleted = state.night_actions_completed;

    setHTML(container, `
      <div class="view__header">
        <div style="display:flex; align-items:center; justify-content:space-between; width:100%; max-width:900px; margin:0 auto; padding: 0 var(--sp-6); box-sizing:border-box">
          <div>
            <h2 class="view__title" style="text-align:left">${escapeHtml(phaseLabel)}</h2>
            <p class="view__subtitle" style="text-align:left">${escapeHtml(subLabel)}</p>
          </div>
          ${roleLabel ? `
          <div class="night-role-indicator ${roleIndicatorCls}">
            <span>${isSeer ? '🔮' : '🐺'}</span>
            <span>${escapeHtml(roleLabel)}</span>
          </div>` : ''}
        </div>
      </div>

      <div class="view__body">
        <div class="stagger-children" style="display:flex; flex-direction:column; gap:var(--sp-5)">

          ${instruction ? `
          <div style="text-align:center; color:var(--color-ash); font-size:var(--text-sm); letter-spacing:var(--tracking-wide); padding:var(--sp-3) 0">
            ${escapeHtml(instruction)}
          </div>` : ''}

          ${(isSeer || isWolf) ? `
          <div>
            <div style="font-family:var(--font-display); font-size:var(--text-xs); letter-spacing:var(--tracking-widest); text-transform:uppercase; color:var(--color-mist); margin-bottom:var(--sp-3)">
              ${escapeHtml(t('night.select_target'))}
            </div>
            <div class="players-grid" id="night-player-grid"></div>
          </div>` : ''}

          ${isNightStart ? `
          <div style="text-align:center; padding:var(--sp-8) 0">
            <div style="font-size:3rem; margin-bottom:var(--sp-4); animation:twinkle 3s ease-in-out infinite">🌕</div>
            <div style="font-family:var(--font-display); font-size:var(--text-2xl); color:var(--color-pale); letter-spacing:var(--tracking-wide)">${escapeHtml(t('night.village_sleeps'))}</div>
          </div>` : ''}

        </div>
      </div>

      <div class="view__footer" id="night-footer">
      </div>
    `);

    // Render player grid for action phases
    if (isSeer || isWolf) {
      _renderPlayerGrid(alive, isSeer, isWolf, state);
    }

    // Render footer buttons
    _renderFooter(phase, isSeer, isWolf, isSeerWake, isWolfWake, isNightStart, state);

    // Auto-advance from night_start to seer wake after brief delay (allows TTS to start)
    if (phase === 'night_start' && _callbacks.onNextPhase) {
      setTimeout(() => {
        _callbacks.onNextPhase();
      }, 800);
    }

    // Auto-advance from seer wake to seer act (seamless transition)
    if ((isSeerWake || isWolfWake) && _callbacks.onNextPhase) {
      setTimeout(() => {
        _callbacks.onNextPhase();
      }, 600);
    }

    // Show seer result if available
    if (seerResult && isSeer) {
      _showSeerResult(seerResult);
    }
  }

  function _renderPlayerGrid(alivePlayers, isSeer, isWolf, state) {
    const grid = qs('#night-player-grid');
    if (!grid) return;

    // Filter candidates:
    // Seer: exclude self (if known), show all alive except seer
    // Wolf: exclude wolves themselves
    const phase = state.phase;
    let candidates = alivePlayers;

    alivePlayers.forEach(player => {
      const card = createElement('div', {
        class: 'player-card selectable',
        style: { '--role-color': isSeer ? 'var(--color-seer)' : 'var(--color-wolf)' },
        dataset: { playerId: player.id }
      });

      // Avatar
      const avatar = createElement('div', { class: 'player-avatar' });
      avatar.textContent = LoupGarouUtils.getInitials(player.name);
      avatar.style.color = LoupGarouUtils.stringToColor(player.name);
      card.appendChild(avatar);

      const nameEl = createElement('div', { class: 'player-name' }, [escapeHtml(player.name)]);
      card.appendChild(nameEl);

      card.addEventListener('click', () => {
        // Deselect previous
        grid.querySelectorAll('.player-card.selected').forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');
        _selectedTarget = player.id;

        // Update confirm button
        const confirmBtn = qs('#night-confirm-btn');
        if (confirmBtn) {
          confirmBtn.disabled = false;
          confirmBtn.classList.remove('btn-secondary');
          if (isSeer) confirmBtn.classList.add('btn-seer');
          else confirmBtn.classList.add('btn-primary');
        }
      });

      grid.appendChild(card);
    });
  }

  function _renderFooter(phase, isSeer, isWolf, isSeerWake, isWolfWake, isNightStart, state) {
    const footer = qs('#night-footer');
    if (!footer) return;
    setHTML(footer, '');

    if (isSeerWake || isWolfWake) {
      const nextBtn = createElement('button', { class: 'btn btn-primary btn-lg', id: 'night-next-btn' }, [
        escapeHtml(t('common.continue'))
      ]);
      nextBtn.addEventListener('click', () => {
        if (_callbacks.onNextPhase) _callbacks.onNextPhase();
      });
      footer.appendChild(nextBtn);
      return;
    }

    if (isNightStart) {
      // Just a continue button
      const nextBtn = createElement('button', { class: 'btn btn-primary btn-lg', id: 'night-next-btn' }, [
        escapeHtml(t('night.next_phase'))
      ]);
      nextBtn.addEventListener('click', () => {
        if (_callbacks.onNextPhase) _callbacks.onNextPhase();
      });
      footer.appendChild(nextBtn);
      return;
    }

    if (isSeer || isWolf) {
      const skipBtn = createElement('button', { class: 'btn btn-ghost' }, [
        escapeHtml(isWolf ? t('night.wolves_skip') : t('common.skip'))
      ]);
      skipBtn.addEventListener('click', () => {
        if (_callbacks.onSkip) _callbacks.onSkip(isSeer ? 'seer_investigate' : 'wolf_kill');
      });

      const confirmBtn = createElement('button', {
        class: 'btn btn-secondary btn-lg',
        id: 'night-confirm-btn',
        disabled: true
      }, [escapeHtml(t('night.action_confirm'))]);
      confirmBtn.setAttribute('disabled', 'true');

      confirmBtn.addEventListener('click', () => {
        if (!_selectedTarget) {
          showToast(t('night.select_target'));
          return;
        }
        const actionType = isSeer ? 'seer_investigate' : 'wolf_kill';
        if (_callbacks.onAction) {
          _callbacks.onAction(actionType, _selectedTarget);
        }
      });

      footer.appendChild(skipBtn);
      footer.appendChild(confirmBtn);
      return;
    }

    // Sleep phases — next
    const nextBtn = createElement('button', { class: 'btn btn-primary btn-lg', id: 'night-next-btn' }, [
      escapeHtml(t('night.next_phase'))
    ]);
    nextBtn.addEventListener('click', () => {
      if (_callbacks.onNextPhase) _callbacks.onNextPhase();
    });
    footer.appendChild(nextBtn);
  }

  function _showSeerResult(result) {
    const body = qs('#view-night .view__body');
    if (!body) return;

    const isWolf = result === 'wolf' || result === 'werewolf';
    const resultDiv = createElement('div', {
      class: `seer-result-reveal ${isWolf ? 'is-wolf' : 'is-village'}`
    });
    resultDiv.innerHTML = isWolf
      ? `<div style="font-family:var(--font-display); font-size:var(--text-xl)">${t('night.seer_result_wolf')}</div>`
      : `<div style="font-family:var(--font-display); font-size:var(--text-xl)">${t('night.seer_result_village')}</div>`;

    body.appendChild(resultDiv);
  }

  return { render };
})();

if (typeof module !== 'undefined') module.exports = ViewNight;
