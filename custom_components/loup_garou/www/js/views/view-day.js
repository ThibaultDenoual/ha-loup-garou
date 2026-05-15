/* ═══════════════════════════════════════════
   LOUP GAROU — ViewDay
   Dawn: deaths announcement + discussion phase
   ═══════════════════════════════════════════ */

const ViewDay = (() => {
  const { qs, setHTML, escapeHtml, createElement } = LoupGarouUtils;
  const { t, getRoleName, getRoleSymbol } = LoupGarouI18n;

  let _state = null;
  let _callbacks = {};

  function render(state, opts = {}) {
    _state = state;
    _callbacks = opts;

    const container = qs('#view-day');
    if (!container) return;

    const phase   = state.phase || 'day';
    const round   = state.round || 1;
    const players = state.players || [];
    const alive   = players.filter(p => p.alive);
    const dead    = players.filter(p => !p.alive);
    const eliminated = state.eliminated_this_round || [];

    const isDiscussion = phase === 'discussion' || phase === 'day_start' || phase === 'day';

    setHTML(container, `
      <div class="view__header">
        <h2 class="view__title">${escapeHtml(t('day.title'))}</h2>
        <p class="view__subtitle">${escapeHtml(t('day.subtitle', { n: round }))}</p>
      </div>

      <div class="view__body">
        <div style="display:flex; flex-direction:column; gap:var(--sp-6)">

          <!-- Deaths announcement -->
          <div id="deaths-section"></div>

          <!-- Alive player count -->
          <div class="flex gap-4 items-center" style="flex-wrap:wrap">
            <div class="status-item" style="color:var(--color-village)">
              <div class="status-dot"></div>
              <span class="status-count">${alive.length}</span>
              <span style="font-size:var(--text-xs); color:var(--color-ash); letter-spacing:var(--tracking-wide); text-transform:uppercase">${escapeHtml(t('common.alive'))}</span>
            </div>
            <div class="status-item" style="color:var(--color-wolf)">
              <div class="status-dot"></div>
              <span class="status-count">${dead.length}</span>
              <span style="font-size:var(--text-xs); color:var(--color-ash); letter-spacing:var(--tracking-wide); text-transform:uppercase">${escapeHtml(t('common.dead'))}</span>
            </div>
          </div>

          ${isDiscussion ? `
          <!-- Players grid -->
          <div>
            <div style="font-family:var(--font-display); font-size:var(--text-xs); letter-spacing:var(--tracking-widest); text-transform:uppercase; color:var(--color-mist); margin-bottom:var(--sp-3)">
              ${escapeHtml(t('day.discussion'))} — ${escapeHtml(t('day.discussion_subtitle'))}
            </div>
            <div class="players-grid" id="day-player-grid"></div>
          </div>` : ''}

        </div>
      </div>

      <div class="view__footer">
        <button class="btn btn-ghost" id="skip-vote-btn">
          ${escapeHtml(t('day.skip_vote'))}
        </button>
        <button class="btn btn-primary btn-lg" id="go-vote-btn">
          ${escapeHtml(t('day.go_to_vote'))}
        </button>
      </div>
    `);

    // Render deaths
    _renderDeaths(eliminated, players);

    // Render player grid
    if (isDiscussion) {
      _renderPlayerGrid(players);
    }

    // Footer events
    const goVoteBtn = qs('#go-vote-btn');
    if (goVoteBtn) {
      goVoteBtn.addEventListener('click', () => {
        if (_callbacks.onGoVote) _callbacks.onGoVote();
      });
    }

    const skipVoteBtn = qs('#skip-vote-btn');
    if (skipVoteBtn) {
      skipVoteBtn.addEventListener('click', () => {
        if (_callbacks.onSkipVote) _callbacks.onSkipVote();
      });
    }
  }

  function _renderDeaths(eliminatedIds, allPlayers) {
    const section = qs('#deaths-section');
    if (!section) return;

    if (!eliminatedIds || eliminatedIds.length === 0) {
      section.innerHTML = `
        <div class="card" style="text-align:center; padding:var(--sp-5)">
          <div style="font-size:1.5rem; margin-bottom:var(--sp-3)">🌅</div>
          <div style="font-family:var(--font-display); color:var(--color-pale)">${escapeHtml(t('day.no_deaths'))}</div>
        </div>
      `;
      return;
    }

    const deathsHtml = eliminatedIds.map(id => {
      const player = allPlayers.find(p => p.id === id);
      if (!player) return '';
      const roleLabel = player.role ? getRoleName(player.role) : t('common.unknown');
      const symbol    = player.role ? getRoleSymbol(player.role) : '❓';
      return `
        <div class="death-entry">
          <div class="death-cross">✝</div>
          <div style="flex:1">
            <div class="death-name">${escapeHtml(player.name)}</div>
            <div class="death-cause">${escapeHtml(t('day.death_by_wolves'))}</div>
          </div>
          <div style="font-size:1.4rem">${symbol}</div>
          <div class="badge badge-muted">${escapeHtml(roleLabel)}</div>
        </div>
      `;
    }).join('');

    section.innerHTML = `
      <div class="deaths-announcement">
        <div class="deaths-announcement__title">🌅 ${escapeHtml(t('day.deaths_title'))}</div>
        ${deathsHtml}
      </div>
    `;
  }

  function _renderPlayerGrid(players) {
    const grid = qs('#day-player-grid');
    if (!grid) return;

    players.forEach(player => {
      const card = createElement('div', {
        class: `player-card ${!player.alive ? 'dead' : ''}`,
        dataset: { playerId: player.id }
      });

      const avatar = createElement('div', { class: 'player-avatar' });
      avatar.textContent = LoupGarouUtils.getInitials(player.name);
      avatar.style.color = LoupGarouUtils.stringToColor(player.name);

      const nameEl = createElement('div', { class: 'player-name' }, [escapeHtml(player.name)]);

      // Show role if dead (revealed)
      if (!player.alive && player.role) {
        const roleEl = createElement('div', {
          class: 'player-role-badge',
          style: { color: 'var(--color-mist)' }
        }, [`${getRoleSymbol(player.role)} ${getRoleName(player.role)}`]);
        card.appendChild(avatar);
        card.appendChild(nameEl);
        card.appendChild(roleEl);
      } else {
        card.appendChild(avatar);
        card.appendChild(nameEl);
      }

      grid.appendChild(card);
    });
  }

  function show() {
    const el = qs('#view-day');
    if (el) el.classList.add('active');
  }

  function hide() {
    const el = qs('#view-day');
    if (el) el.classList.remove('active');
  }

  return { render };
})();

if (typeof module !== 'undefined') module.exports = ViewDay;
