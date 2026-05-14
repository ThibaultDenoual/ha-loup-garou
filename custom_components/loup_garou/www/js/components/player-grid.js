/**
 * player-grid.js - Player Grid Component
 *
 * Renders the player grid with selection, role indicators, and status.
 */

const PlayerGrid = (function() {
    'use strict';

    const { $, escapeHtml, createElement } = LoupGarouUtils;
    const { t } = LoupGarouI18n;

    // ============================================
    // Constants
    // ============================================

    const ROLE_ICONS = {
        werewolf: 'fa-wolf',
        wolf: 'fa-wolf',
        seer: 'fa-crystal-ball',
    };

    const ROLE_COLORS = {
        werewolf: 'var(--color-werewolf)',
        wolf: 'var(--color-werewolf)',
        seer: 'var(--color-seer)',
    };

    // ============================================
    // State
    // ============================================

    let currentTarget = null;
    let onTargetSelect = null;

    // ============================================
    // Render Functions
    // ============================================

    /**
     * Render the player grid
     * @param {Array} players - Array of player objects
     * @param {Object} options - Rendering options
     * @param {boolean} options.canSelect - Whether players can be selected
     * @param {string|null} options.targetId - Currently selected target ID
     * @param {boolean} options.showRole - Whether to show role (for wolves)
     * @param {Function} options.onSelect - Callback when player is selected
     * @returns {string} HTML string
     */
    function render(players, options = {}) {
        const {
            canSelect = false,
            targetId = null,
            showRole = false,
            onSelect = null
        } = options;

        currentTarget = targetId;
        onTargetSelect = onSelect;

        if (!players || players.length === 0) {
            return '<p class="text-center text-muted">' + t('game.no_players') + '</p>';
        }

        return players.map(player => {
            const classes = ['player-card'];
            const dataAttrs = {};

            // Add status classes
            if (!player.alive) {
                classes.push('eliminated');
            }

            // Add role-based styling
            const roleKey = player.role?.toLowerCase() || player.role_key?.toLowerCase();
            if (roleKey === 'werewolf' || roleKey === 'wolf') {
                classes.push('wolf');
            } else if (roleKey === 'seer') {
                classes.push('seer');
            }

            // Selected state
            if (player.id === targetId || player.name === targetId) {
                classes.push('selected');
            }

            // Build HTML
            const classStr = classes.join(' ');
            const dataStr = Object.entries(dataAttrs)
                .map(([k, v]) => `data-${k}="${escapeHtml(v)}"`)
                .join(' ');

            const onclickAttr = canSelect && player.alive !== false
                ? `onclick="PlayerGrid.selectPlayer('${escapeHtml(player.id || player.name)}')"`
                : '';

            const iconHtml = !player.alive
                ? '<i class="fas fa-skull player-card__icon"></i>'
                : '';

            const targetIconHtml = (player.id === targetId || player.name === targetId)
                ? '<i class="fas fa-crosshairs player-card__target" style="color:var(--color-accent-warning);"></i>'
                : '';

            return `
                <div class="${classStr}" ${dataStr} ${onclickAttr}>
                    <div class="player-card__name">${escapeHtml(player.name)}</div>
                    ${iconHtml}
                    ${targetIconHtml}
                </div>
            `;
        }).join('');
    }

    /**
     * Render player tags for setup list
     * @param {Array} players - Array of player names
     * @param {Function} onRemove - Callback when remove is clicked
     * @returns {string} HTML string
     */
    function renderTags(players, onRemove = null) {
        return players.map((name, index) => `
            <div class="player-tag">
                ${escapeHtml(name)}
                <button class="player-tag__remove" onclick="${onRemove ? `PlayerGrid.removePlayer(${index})` : `PlayerGrid._defaultRemove(${index})`}">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `).join('');
    }

    // ============================================
    // Player Management
    // ============================================

    /**
     * Select a player
     * @param {string} playerId - Player ID or name
     */
    function selectPlayer(playerId) {
        currentTarget = playerId;
        if (onTargetSelect) {
            onTargetSelect(playerId);
        }

        // Update UI
        $$('.player-card').forEach(card => {
            const name = card.querySelector('.player-card__name')?.textContent;
            const id = card.dataset.playerId;

            if (id === playerId || name === playerId) {
                card.classList.add('selected');
                // Add crosshairs icon
                if (!card.querySelector('.player-card__target')) {
                    card.innerHTML += '<i class="fas fa-crosshairs player-card__target" style="color:var(--color-accent-warning);"></i>';
                }
            } else {
                card.classList.remove('selected');
                const targetIcon = card.querySelector('.player-card__target');
                if (targetIcon) targetIcon.remove();
            }
        });
    }

    /**
     * Clear selection
     */
    function clearSelection() {
        currentTarget = null;
        $$('.player-card').forEach(card => {
            card.classList.remove('selected');
            const targetIcon = card.querySelector('.player-card__target');
            if (targetIcon) targetIcon.remove();
        });
    }

    /**
     * Get current selected player
     * @returns {string|null}
     */
    function getSelectedPlayer() {
        return currentTarget;
    }

    /**
     * Remove player by index (default handler)
     * @param {number} index
     */
    function _defaultRemove(index) {
        // Override this by setting onRemove when calling renderTags
        console.warn('No remove handler set for player tags');
    }

    /**
     * Highlight dead players
     * @param {Array} deadPlayerIds - IDs of dead players
     */
    function markDead(deadPlayerIds) {
        $$('.player-card').forEach(card => {
            const name = card.querySelector('.player-card__name')?.textContent;
            if (deadPlayerIds.includes(name)) {
                card.classList.add('eliminated');
                card.classList.remove('selected');
            }
        });
    }

    // ============================================
    // Public API
    // ============================================

    return {
        render,
        renderTags,
        selectPlayer,
        clearSelection,
        getSelectedPlayer,
        markDead,
        removePlayer: _defaultRemove,
    };
})();