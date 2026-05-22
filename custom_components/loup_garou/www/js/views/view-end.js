/* ═══════════════════════════════════════════
   LOUP GAROU — ViewEnd
   Game over screen with winner reveal
   ═══════════════════════════════════════════ */

const ViewEnd = (() => {
  const { qs, setHTML, escapeHtml } = LoupGarouUtils;
  const { t, getRoleName, getRoleSymbol, getRoleColor, getRoleTeam } = LoupGarouI18n;

  let _callbacks = {};

  function render(state, opts = {}) {
    _callbacks = opts;

    const container = qs('#view-end');
    if (!container) return;

    const winner    = state.winner || 'village';
    const players   = state.players || [];
    const round     = state.round || 1;

    const isWolves  = winner === 'wolves' || winner === 'werewolves';
    const isSolo    = winner === 'solo';
    const soloWinner = state.solo_winner_name;

    // Set class for ambient
    container.className = container.className
      .replace(/\b(wolves|village|solo)-win\b/g, '').trim()
      .replace('active', '').trim();
    if (isWolves) container.classList.add('wolves-win');
    else if (isSolo) container.classList.add('solo-win');
    else container.classList.add('village-win');
    container.classList.add('active');

    // Winner info
    let winnerTitle = '';
    let emblemCls   = '';
    let emblemIcon  = '';

    if (isWolves) {
      winnerTitle = t('end.wolves_win');
      emblemCls   = 'wolves';
      emblemIcon  = '🐺';
    } else if (isSolo && soloWinner) {
      winnerTitle = t('end.solo_win', { name: soloWinner });
      emblemCls   = 'wolves';
      emblemIcon  = '🎭';
    } else {
      winnerTitle = t('end.village_win');
      emblemCls   = 'village';
      emblemIcon  = '🏡';
    }

    // Survivors and fallen
    const alive = players.filter(p => p.alive);
    const dead  = players.filter(p => !p.alive);

    const survivorListHtml = alive.map(p => {
      const roleKey   = p.role;
      const roleColor = roleKey ? getRoleColor(roleKey) : 'var(--color-mist)';
      const symbol    = roleKey ? getRoleSymbol(roleKey) : '❓';
      const roleName  = roleKey ? getRoleName(roleKey)   : t('common.unknown');
      return `
        <div class="survivor-entry">
          <div style="font-size:1.4rem">${symbol}</div>
          <div style="flex:1">
            <div style="font-family:var(--font-display); font-size:var(--text-sm); color:var(--color-white)">${escapeHtml(p.name)}</div>
            <div style="font-size:var(--text-xs); color:${roleColor}; letter-spacing:var(--tracking-wide); text-transform:uppercase">${escapeHtml(roleName)}</div>
          </div>
        </div>
      `;
    }).join('') || `<div style="color:var(--color-mist); font-size:var(--text-sm)">${t('common.unknown')}</div>`;

    const fallenListHtml = dead.map(p => {
      const roleKey   = p.role;
      const symbol    = roleKey ? getRoleSymbol(roleKey) : '❓';
      const roleName  = roleKey ? getRoleName(roleKey)   : t('common.unknown');
      return `
        <div class="survivor-entry" style="opacity:0.55">
          <div style="font-size:1.2rem">✝</div>
          <div style="flex:1">
            <div style="font-family:var(--font-display); font-size:var(--text-sm); color:var(--color-pale)">${escapeHtml(p.name)}</div>
            <div style="font-size:var(--text-xs); color:var(--color-ash); letter-spacing:var(--tracking-wide); text-transform:uppercase">${escapeHtml(roleName)} ${symbol}</div>
          </div>
        </div>
      `;
    }).join('');

    setHTML(container, `
      <!-- Winner emblem -->
      <div class="winner-emblem ${emblemCls}">
        ${emblemIcon}
      </div>

      <!-- Title -->
      <div>
        <h2 class="winner-title ${emblemCls}">${escapeHtml(winnerTitle)}</h2>
        <div style="font-size:var(--text-sm); color:var(--color-ash); margin-top:var(--sp-2)">
          ${escapeHtml(t('end.rounds_played', { n: round }))}
        </div>
      </div>

      <!-- Survivors -->
      <div style="width:100%; max-width:360px">
        <div style="font-family:var(--font-display); font-size:var(--text-xs); letter-spacing:var(--tracking-widest); text-transform:uppercase; color:var(--color-ash); margin-bottom:var(--sp-3)">
          ${escapeHtml(t('end.survivors'))} (${alive.length})
        </div>
        <div class="survivor-list">
          ${survivorListHtml}
        </div>
      </div>

      ${dead.length > 0 ? `
      <!-- Fallen -->
      <div style="width:100%; max-width:360px">
        <div style="font-family:var(--font-display); font-size:var(--text-xs); letter-spacing:var(--tracking-widest); text-transform:uppercase; color:var(--color-ash); margin-bottom:var(--sp-3)">
          ${escapeHtml(t('end.fallen'))} (${dead.length})
        </div>
        <div class="fallen-list">
          ${fallenListHtml}
        </div>
      </div>` : ''}

      <!-- Actions -->
      <div style="display:flex; gap:var(--sp-4); flex-wrap:wrap; justify-content:center">
        <button class="btn btn-primary btn-xl" id="play-again-btn">
          ${escapeHtml(t('end.play_again'))}
        </button>
      </div>
    `);

    // Events
    const playAgainBtn = qs('#play-again-btn');
    if (playAgainBtn) {
      playAgainBtn.addEventListener('click', () => {
        if (_callbacks.onPlayAgain) _callbacks.onPlayAgain();
      });
    }
  }

  function show() {
    const el = qs('#view-end');
    if (el) el.classList.add('active');
  }

  function hide() {
    const el = qs('#view-end');
    if (el) el.classList.remove('active');
  }

  return { render };
})();

if (typeof module !== 'undefined') module.exports = ViewEnd;
