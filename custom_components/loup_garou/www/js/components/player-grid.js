/* ═══════════════════════════════════════════
   LOUP GAROU — PlayerGrid Component
   Renders interactive player cards grid
   ═══════════════════════════════════════════ */

const PlayerGrid = (() => {
  const { createElement, escapeHtml, getInitials, stringToColor, addClass, removeClass } = LoupGarouUtils;
  const { getRoleColor, getRoleSymbol, getRoleName, getRoleTeam } = LoupGarouI18n;

  let _container = null;
  let _players = [];
  let _selectedId = null;
  let _selectable = false;
  let _showRoles = false;
  let _onSelect = null;
  let _highlightTeam = null; // 'wolf' | 'village' | null

  /* ── Build a single player card ── */
  function _buildCard(player) {
    const isAlive = player.alive !== false;
    const isSelected = player.id === _selectedId;
    const roleKey = player.role || null;
    const roleColor = roleKey ? getRoleColor(roleKey) : 'var(--color-mist)';
    const roleTeam  = roleKey ? getRoleTeam(roleKey)  : 'village';
    const initials  = getInitials(player.name);
    const avatarBg  = stringToColor(player.name);

    const dimmed = _highlightTeam && roleKey && roleTeam !== _highlightTeam;

    const card = createElement('div', {
      class: [
        'player-card',
        _selectable && isAlive ? 'selectable' : '',
        isSelected ? 'selected' : '',
        !isAlive ? 'dead' : '',
        dimmed ? 'dimmed' : ''
      ].filter(Boolean).join(' '),
      dataset: { playerId: player.id },
      style: { '--role-color': roleColor }
    });

    // Avatar
    const avatar = createElement('div', {
      class: 'player-avatar',
      style: { borderColor: isAlive ? roleColor : 'rgba(255,255,255,0.08)' }
    });

    if (roleKey && _showRoles) {
      avatar.textContent = getRoleSymbol(roleKey);
      avatar.style.fontSize = 'var(--text-xl)';
    } else {
      avatar.textContent = initials;
      avatar.style.color = avatarBg;
    }

    card.appendChild(avatar);

    // Name
    const nameEl = createElement('div', { class: 'player-name' }, [
      escapeHtml(player.name)
    ]);
    card.appendChild(nameEl);

    // Role badge (if visible)
    if (_showRoles && roleKey) {
      const badge = createElement('div', {
        class: 'player-role-badge',
        style: { color: roleColor }
      }, [getRoleName(roleKey)]);
      card.appendChild(badge);
    }

    // Vote count badge
    if (player.votes != null && player.votes > 0) {
      const voteBadge = createElement('div', {
        class: 'badge badge-wolf',
        style: { position: 'absolute', top: '6px', right: '6px', fontSize: 'var(--text-xs)' }
      }, [`${player.votes} ✗`]);
      card.style.position = 'relative';
      card.appendChild(voteBadge);
    }

    // Click handler
    if (_selectable && isAlive && _onSelect) {
      card.addEventListener('click', () => {
        _selectedId = player.id;
        render();
        _onSelect(player.id, player);
      });
    }

    return card;
  }

  /* ── Public: render grid into container ── */
  function render(players, opts = {}) {
    if (players !== undefined) _players = players;
    if (opts.container !== undefined) _container = opts.container;
    if (opts.selectable !== undefined) _selectable = opts.selectable;
    if (opts.showRoles !== undefined) _showRoles = opts.showRoles;
    if (opts.onSelect !== undefined) _onSelect = opts.onSelect;
    if (opts.selectedId !== undefined) _selectedId = opts.selectedId;
    if (opts.highlightTeam !== undefined) _highlightTeam = opts.highlightTeam;
    if (opts.clearSelection) _selectedId = null;

    if (!_container) return;

    // Clear and rebuild
    while (_container.firstChild) _container.removeChild(_container.firstChild);

    for (const player of _players) {
      _container.appendChild(_buildCard(player));
    }

    // Stagger animation
    _container.querySelectorAll('.player-card').forEach((card, i) => {
      card.style.animationDelay = `${i * 60}ms`;
      card.style.animation = `fade-up var(--duration-slow) var(--ease-out) both`;
    });
  }

  /* ── Public: select a player programmatically ── */
  function selectPlayer(id) {
    _selectedId = id;
    if (!_container) return;
    _container.querySelectorAll('.player-card').forEach(card => {
      const isThis = card.dataset.playerId === String(id);
      card.classList.toggle('selected', isThis);
    });
  }

  /* ── Public: mark player as dead with animation ── */
  function markDead(id) {
    if (!_container) return;
    const card = _container.querySelector(`[data-player-id="${id}"]`);
    if (!card) return;
    card.classList.add('dying');
    setTimeout(() => {
      card.classList.remove('dying');
      card.classList.add('dead');
    }, 1200);
  }

  /* ── Public: update vote tallies ── */
  function updateVotes(tallies) {
    // tallies: { playerId: count }
    if (!_container) return;
    _container.querySelectorAll('.player-card').forEach(card => {
      const id = card.dataset.playerId;
      const count = tallies[id] || 0;
      let badge = card.querySelector('.vote-badge');
      if (count > 0) {
        if (!badge) {
          badge = createElement('div', {
            class: 'badge badge-wolf vote-badge',
            style: { position: 'absolute', top: '6px', right: '6px', fontSize: 'var(--text-xs)' }
          });
          card.style.position = 'relative';
          card.appendChild(badge);
          card.classList.add('vote-registered');
          setTimeout(() => card.classList.remove('vote-registered'), 400);
        }
        badge.textContent = `${count} ✗`;
      } else if (badge) {
        badge.remove();
      }
    });
  }

  /* ── Public: clear selection ── */
  function clearSelection() {
    _selectedId = null;
    if (!_container) return;
    _container.querySelectorAll('.player-card.selected').forEach(c => c.classList.remove('selected'));
  }

  /* ── Public: get selected ID ── */
  function getSelected() { return _selectedId; }

  return { render, selectPlayer, markDead, updateVotes, clearSelection, getSelected };
})();

if (typeof module !== 'undefined') module.exports = PlayerGrid;
