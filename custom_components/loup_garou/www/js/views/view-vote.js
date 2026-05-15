/* ═══════════════════════════════════════════
   LOUP GAROU — ViewVote
   Village voting phase
   ═══════════════════════════════════════════ */

const ViewVote = (() => {
  const { qs, setHTML, escapeHtml, createElement, showToast } = LoupGarouUtils;
  const { t, getRoleName, getRoleSymbol } = LoupGarouI18n;

  let _state = null;
  let _callbacks = {};
  let _selectedVoter = null;
  let _selectedTarget = null;

  function render(state, opts = {}) {
    _state = state;
    _callbacks = opts;
    _selectedVoter = null;
    _selectedTarget = null;

    const container = qs('#view-vote');
    if (!container) return;

    const players     = state.players || [];
    const alive       = players.filter(p => p.alive);
    const votesCast   = state.votes_cast || 0;
    const totalVoters = state.alive_voter_count || alive.length;
    const tallies     = state.vote_tallies_count || {};

    setHTML(container, `
      <div class="view__header">
        <h2 class="view__title">${escapeHtml(t('vote.title'))}</h2>
        <p class="view__subtitle">${escapeHtml(t('vote.subtitle'))}</p>
      </div>

      <div class="view__body">
        <div style="display:flex; flex-direction:column; gap:var(--sp-6)">

          <!-- Progress -->
          <div class="flex items-center justify-between">
            <div style="font-size:var(--text-sm); color:var(--color-ash)">
              ${escapeHtml(t('vote.votes_cast', { n: votesCast, total: totalVoters }))}
            </div>
            <div class="vote-bar" style="width:200px">
              <div class="vote-bar-fill" style="width:${totalVoters > 0 ? Math.round(votesCast/totalVoters*100) : 0}%"></div>
            </div>
          </div>

          <!-- Two-step vote: pick voter → pick target -->
          <div id="vote-step-1" class="${_selectedVoter ? 'hidden' : ''}">
            <div style="font-family:var(--font-display); font-size:var(--text-xs); letter-spacing:var(--tracking-widest); text-transform:uppercase; color:var(--color-mist); margin-bottom:var(--sp-3)">
              1 — ${escapeHtml(t('vote.instruction'))}
            </div>
            <div class="players-grid" id="voter-grid"></div>
          </div>

          <div id="vote-step-2" class="${!_selectedVoter ? 'hidden' : ''}">
            <div style="display:flex; align-items:center; gap:var(--sp-3); margin-bottom:var(--sp-3)">
              <button class="btn btn-ghost btn-sm" id="back-voter-btn">← ${escapeHtml(t('common.back'))}</button>
              <div style="font-family:var(--font-display); font-size:var(--text-xs); letter-spacing:var(--tracking-widest); text-transform:uppercase; color:var(--color-mist)">
                2 — ${escapeHtml(t('vote.vote_for'))} :
                <span style="color:var(--color-white)" id="voter-label"></span>
              </div>
            </div>
            <div class="players-grid" id="target-grid"></div>
          </div>

          <!-- Vote tally -->
          <div class="card">
            <div class="card__title">${escapeHtml(t('vote.tallies'))}</div>
            <div class="vote-tallies" id="vote-tallies"></div>
          </div>

        </div>
      </div>

      <div class="view__footer">
        <button class="btn btn-ghost" id="cancel-vote-btn">
          ${escapeHtml(t('vote.cancel_vote'))}
        </button>
        <button class="btn btn-primary btn-lg" id="resolve-vote-btn">
          ${escapeHtml(t('vote.resolve'))}
        </button>
      </div>
    `);

    _renderVoterGrid(alive, tallies);
    _renderTallies(players, tallies);
    _attachFooterEvents();
  }

  function _renderVoterGrid(alive, tallies) {
    const grid = qs('#voter-grid');
    if (!grid) return;

    alive.forEach(player => {
      const hasVoted = Object.values(tallies || {}).some(arr =>
        Array.isArray(arr) ? arr.includes(player.id) : false
      ) || (tallies && tallies[player.id] !== undefined && false); // vote_tallies_count doesn't include voter IDs

      const card = createElement('div', {
        class: `player-card selectable${hasVoted ? ' opacity-50' : ''}`,
        style: { '--role-color': 'var(--color-wolf)', opacity: hasVoted ? '0.5' : '1' },
        dataset: { playerId: player.id }
      });

      const avatar = createElement('div', { class: 'player-avatar' });
      avatar.textContent = LoupGarouUtils.getInitials(player.name);
      avatar.style.color = LoupGarouUtils.stringToColor(player.name);
      card.appendChild(avatar);
      card.appendChild(createElement('div', { class: 'player-name' }, [escapeHtml(player.name)]));

      card.addEventListener('click', () => {
        _selectedVoter = player.id;
        // Update voter label
        const label = qs('#voter-label');
        if (label) label.textContent = player.name;
        // Show step 2
        const step1 = qs('#vote-step-1');
        const step2 = qs('#vote-step-2');
        if (step1) step1.classList.add('hidden');
        if (step2) step2.classList.remove('hidden');
        _renderTargetGrid(qs('#target-grid'), _state.players.filter(p => p.alive && p.id !== player.id));
      });

      grid.appendChild(card);
    });
  }

  function _renderTargetGrid(grid, candidates) {
    if (!grid) return;
    setHTML(grid, '');

    candidates.forEach(player => {
      const card = createElement('div', {
        class: 'player-card selectable',
        style: { '--role-color': 'var(--color-wolf)' },
        dataset: { playerId: player.id }
      });

      const avatar = createElement('div', { class: 'player-avatar' });
      avatar.textContent = LoupGarouUtils.getInitials(player.name);
      avatar.style.color = LoupGarouUtils.stringToColor(player.name);
      card.appendChild(avatar);
      card.appendChild(createElement('div', { class: 'player-name' }, [escapeHtml(player.name)]));

      card.addEventListener('click', () => {
        // Submit vote
        if (_callbacks.onVote && _selectedVoter) {
          _callbacks.onVote(_selectedVoter, player.id);
        }
        // Reset steps
        _selectedVoter = null;
        const step1 = qs('#vote-step-1');
        const step2 = qs('#vote-step-2');
        if (step1) step1.classList.remove('hidden');
        if (step2) step2.classList.add('hidden');
        showToast(`${player.name} 🗳️`);
      });

      grid.appendChild(card);
    });
  }

  function _renderTallies(players, tallies) {
    const container = qs('#vote-tallies');
    if (!container) return;
    setHTML(container, '');

    const maxVotes = Math.max(1, ...Object.values(tallies || {}).map(v => Number(v) || 0));

    const sorted = players
      .filter(p => p.alive)
      .sort((a, b) => ((tallies[b.id] || 0) - (tallies[a.id] || 0)));

    sorted.forEach(player => {
      const count = tallies[player.id] || 0;
      const pct   = Math.round(count / maxVotes * 100);

      const row = createElement('div', { class: 'vote-tally-row' });
      row.innerHTML = `
        <div class="vote-tally-name">${escapeHtml(player.name)}</div>
        <div class="vote-bar">
          <div class="vote-bar-fill" style="width:${pct}%"></div>
        </div>
        <div class="vote-count">${count || '–'}</div>
      `;
      container.appendChild(row);
    });

    if (sorted.length === 0) {
      container.innerHTML = `<div style="color:var(--color-mist); font-size:var(--text-sm)">${escapeHtml(t('vote.no_votes'))}</div>`;
    }
  }

  function _attachFooterEvents() {
    const resolveBtn = qs('#resolve-vote-btn');
    if (resolveBtn) {
      resolveBtn.addEventListener('click', () => {
        if (_callbacks.onResolve) _callbacks.onResolve();
      });
    }

    const cancelBtn = qs('#cancel-vote-btn');
    if (cancelBtn) {
      cancelBtn.addEventListener('click', () => {
        if (_callbacks.onCancel) _callbacks.onCancel();
      });
    }

    const backBtn = qs('#back-voter-btn');
    if (backBtn) {
      backBtn.addEventListener('click', () => {
        _selectedVoter = null;
        const step1 = qs('#vote-step-1');
        const step2 = qs('#vote-step-2');
        if (step1) step1.classList.remove('hidden');
        if (step2) step2.classList.add('hidden');
      });
    }
  }

  // Re-render tallies on update without full render
  function updateTallies(players, tallies) {
    const container = qs('#vote-tallies');
    if (container) _renderTallies(players, tallies);

    // Update progress bar
    const votesCast   = Object.values(tallies).reduce((a, b) => a + Number(b || 0), 0);
    const totalVoters = (players || []).filter(p => p.alive).length;
    const fill = qs('.vote-bar-fill');
    const label = qs('.view__body .flex .text-sm');
    if (fill) fill.style.width = `${totalVoters > 0 ? Math.round(votesCast/totalVoters*100) : 0}%`;
  }

  function show() {
    const el = qs('#view-vote');
    if (el) el.classList.add('active');
  }

  function hide() {
    const el = qs('#view-vote');
    if (el) el.classList.remove('active');
  }

  return { render, updateTallies };
})();

if (typeof module !== 'undefined') module.exports = ViewVote;
