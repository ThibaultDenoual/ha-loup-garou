/* ═══════════════════════════════════════════
   LOUP GAROU — ViewReveal
   Private role reveal with card flip
   ═══════════════════════════════════════════ */

const ViewReveal = (() => {
  const { qs, setHTML, escapeHtml, showToast } = LoupGarouUtils;
  const { t, getRoleName, getRoleDesc, getRoleColor, getRoleGlow, getRoleSymbol, getTeamLabel, getRoleTeam } = LoupGarouI18n;

  let _state = null;
  let _revealed = false;
  let _onConfirm = null;

  function render(state, opts = {}) {
    _state = state;
    _revealed = false;
    if (opts.onConfirm) _onConfirm = opts.onConfirm;

    const container = qs('#view-reveal');
    if (!container) return;

    const revealIndex  = state.reveal_index || 0;
    const revealTotal  = state.reveal_total || state.players.length;
    const nextPlayer   = state.next_reveal_player;
    const playerName   = nextPlayer ? escapeHtml(nextPlayer.name) : '…';

    // Progress dots
    const dotsHtml = Array.from({ length: revealTotal }, (_, i) => {
      let cls = 'reveal-dot';
      if (i < revealIndex) cls += ' done';
      else if (i === revealIndex) cls += ' current';
      return `<div class="${cls}"></div>`;
    }).join('');

  setHTML(container, `
    <div class="reveal-screen">

      <!-- Progress -->
      <div class="reveal-progress">${dotsHtml}</div>

      <!-- Player -->
      <div class="reveal-header">
        <div class="reveal-player-name">${playerName}</div>
        <div class="reveal-instruction">
          ${escapeHtml(t('reveal.instruction', { name: playerName }))}
        </div>
      </div>

      <!-- Card -->
      <div class="reveal-card-wrap">
        <div class="role-card" id="role-card" aria-label="${t('reveal.tap_to_reveal')}">
          <div class="role-card__inner">

            <div class="role-card__face role-card__front">
              <div class="cover-symbol">🌕</div>
              <div class="role-card__hint">
                ${escapeHtml(t('reveal.tap_to_reveal'))}
              </div>
            </div>

            <div class="role-card__face role-card__back" id="role-card-back"></div>

          </div>
        </div>
      </div>

      <!-- Confirm -->
      <div class="reveal-actions">
        <button class="btn btn-primary btn-lg hidden" id="seen-btn">
          ${escapeHtml(t('reveal.seen'))}
        </button>
      </div>

      <!-- Footer -->
      <div class="reveal-footer">
        ${escapeHtml(
          t('reveal.progress', {
            current: revealIndex + 1,
            total: revealTotal
          })
        )}
      </div>

    </div>
  `);

    _attachEvents(nextPlayer);
  }

  function _fillRoleBack(player) {
    const back = qs('#role-card-back');
    if (!back || !player || !player.role) return;

    const roleKey = player.role;
    const color   = getRoleColor(roleKey);
    const glow    = getRoleGlow(roleKey);
    const symbol  = getRoleSymbol(roleKey);
    const name    = getRoleName(roleKey);
    const desc    = getRoleDesc(roleKey);
    const team    = getRoleTeam(roleKey);
    const teamLabel = getTeamLabel(team);

    back.style.setProperty('--role-color', color);
    back.style.setProperty('--role-glow', glow);

    back.innerHTML = `
      <div class="role-symbol">${symbol}</div>
      <div class="role-name">${escapeHtml(name)}</div>
      <div class="role-team">${escapeHtml(teamLabel)}</div>
      <div style="margin-top:var(--sp-4); font-size:var(--text-xs); color:var(--color-ash); text-align:center; line-height:var(--leading-snug); padding:0 var(--sp-2)">
        ${escapeHtml(desc)}
      </div>
    `;
  }

  function _attachEvents(player) {
    const card    = qs('#role-card');
    const seenBtn = qs('#seen-btn');

    if (!card) return;

    card.addEventListener('click', () => {
      if (!_revealed) {
        // Reveal
        _fillRoleBack(player);
        card.classList.add('revealed');
        _revealed = true;
        if (seenBtn) seenBtn.classList.remove('hidden');
      } else {
        // Hide again
        card.classList.remove('revealed');
        _revealed = false;
        if (seenBtn) seenBtn.classList.add('hidden');
      }
    });

    if (seenBtn) {
      seenBtn.addEventListener('click', () => {
        if (!_revealed) {
          showToast(t('reveal.tap_to_reveal'));
          return;
        }
        if (_onConfirm && player) {
          _onConfirm(player.id);
        }
      });
    }
  }

  function _show() {
    const el = qs('#view-reveal');
    if (el) el.classList.add('active');
  }

  function _hide() {
    const el = qs('#view-reveal');
    if (el) el.classList.remove('active');
  }

  return { render };
})();

if (typeof module !== 'undefined') module.exports = ViewReveal;
