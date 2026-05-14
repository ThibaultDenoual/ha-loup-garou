/**
 * view-setup.js - Setup View Module
 *
 * Handles game configuration UI:
 * - Player list management (local, server confirms)
 * - Role configuration
 * - Start game
 */

const ViewSetup = (function() {
    'use strict';

    const { $, $$, createElement, escapeHtml, animateOnce } = LoupGarouUtils;
    const { t } = LoupGarouI18n;

    const players = [];
    const roles = { villagers: 3, werewolves: 1, seers: 1 };

    // ============================================
    // DOM References
    // ============================================

    function getContainer() { return $('view-setup'); }
    function getPlayerInput() { return $('setup-player-input'); }
    function getPlayerList() { return $('setup-player-list'); }
    function getStartButton() { return $('setup-start-btn'); }
    function getErrorEl() { return $('setup-error'); }

    // ============================================
    // Player Management
    // ============================================

    function addPlayer(name) {
        if (!name || name.trim() === '') return false;
        if (players.length >= 12) return false;
        if (players.some(p => p.name.toLowerCase() === name.trim().toLowerCase())) {
            shakeInput();
            return false;
        }

        const id = 'player_' + Date.now() + '_' + Math.random().toString(36).slice(2);
        players.push({ id, name: name.trim(), alive: true });
        renderPlayerList();
        updateStartButton();
        clearInput();
        return true;
    }

    function removePlayer(index) {
        if (index < 0 || index >= players.length) return;
        players.splice(index, 1);
        renderPlayerList();
        updateStartButton();
    }

    function clearInput() {
        const input = getPlayerInput();
        if (input) input.value = '';
    }

    function shakeInput() {
        const input = getPlayerInput();
        if (!input) return;
        input.classList.add('shake');
        setTimeout(() => input.classList.remove('shake'), 500);
    }

    // ============================================
    // Role Configuration
    // ============================================

    function adjustRole(role, delta) {
        roles[role] = Math.max(0, (roles[role] || 0) + delta);
        renderRoleConfig();
        updateStartButton();
    }

    // ============================================
    // Rendering
    // ============================================

    function renderPlayerList() {
        const container = getPlayerList();
        if (!container) return;

        if (players.length === 0) {
            container.innerHTML = '<p class="text-center text-muted">' + t('setup.players_empty', { count: 0 }) + '</p>';
            return;
        }

        container.innerHTML = players.map((p, index) => `
            <div class="player-tag animate-slide-up">
                <span>${escapeHtml(p.name)}</span>
                <button class="player-tag__remove" onclick="ViewSetup.removePlayer(${index})">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `).join('');
    }

    function renderRoleConfig() {
        const container = $('role-config');
        if (!container) return;

        container.innerHTML = `
            <div class="role-config-grid">
                <div class="role-config-item">
                    <span class="role-config-item__icon role-config-item__icon--villager">
                        <i class="fas fa-user"></i>
                    </span>
                    <div class="form-group">
                        <label class="form-label">${t('setup.villagers')}</label>
                        <div style="display:flex;gap:8px;justify-content:center;align-items:center;">
                            <button class="btn btn-sm btn-secondary" onclick="ViewSetup.adjustRole('villagers', -1)">
                                <i class="fas fa-minus"></i>
                            </button>
                            <span>${roles.villagers}</span>
                            <button class="btn btn-sm btn-secondary" onclick="ViewSetup.adjustRole('villagers', 1)">
                                <i class="fas fa-plus"></i>
                            </button>
                        </div>
                    </div>
                </div>
                <div class="role-config-item">
                    <span class="role-config-item__icon role-config-item__icon--wolf">
                        <i class="fas fa-moon"></i>
                    </span>
                    <div class="form-group">
                        <label class="form-label">${t('setup.werewolves')}</label>
                        <div style="display:flex;gap:8px;justify-content:center;align-items:center;">
                            <button class="btn btn-sm btn-secondary" onclick="ViewSetup.adjustRole('werewolves', -1)">
                                <i class="fas fa-minus"></i>
                            </button>
                            <span>${roles.werewolves}</span>
                            <button class="btn btn-sm btn-secondary" onclick="ViewSetup.adjustRole('werewolves', 1)">
                                <i class="fas fa-plus"></i>
                            </button>
                        </div>
                    </div>
                </div>
                <div class="role-config-item">
                    <span class="role-config-item__icon role-config-item__icon--seer">
                        <i class="fas fa-eye"></i>
                    </span>
                    <div class="form-group">
                        <label class="form-label">${t('setup.seers')}</label>
                        <div style="display:flex;gap:8px;justify-content:center;align-items:center;">
                            <button class="btn btn-sm btn-secondary" onclick="ViewSetup.adjustRole('seers', -1)">
                                <i class="fas fa-minus"></i>
                            </button>
                            <span>${roles.seers}</span>
                            <button class="btn btn-sm btn-secondary" onclick="ViewSetup.adjustRole('seers', 1)">
                                <i class="fas fa-plus"></i>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    function updateStartButton() {
        const btn = getStartButton();
        if (!btn) return;

        const totalRoles = roles.villagers + roles.werewolves + roles.seers;
        const count = players.length;

        if (count < 5) {
            btn.disabled = true;
            btn.textContent = t('setup.players_min', { count });
            btn.classList.remove('btn-primary');
            btn.classList.add('btn-secondary');
        } else if (totalRoles !== count) {
            btn.disabled = true;
            btn.textContent = t('setup.error_role_mismatch', { roles: totalRoles, players: count });
            btn.classList.remove('btn-primary');
            btn.classList.add('btn-danger');
        } else {
            btn.disabled = false;
            btn.textContent = t('setup.start_button');
            btn.classList.add('btn-primary');
            btn.classList.remove('btn-danger', 'btn-secondary');
        }
    }

    function showError(message) {
        const errorEl = getErrorEl();
        if (errorEl) {
            errorEl.textContent = message;
            errorEl.classList.remove('hidden');
            setTimeout(() => errorEl.classList.add('hidden'), 3000);
        }
    }

    // ============================================
    // Visibility
    // ============================================

    function show(state) {
        const container = getContainer();
        if (container) {
            container.classList.remove('hidden');
            animateOnce(container, 'animate-fade-in');
        }
        renderRoleConfig();
        renderPlayerList();
        updateStartButton();

        const input = getPlayerInput();
        if (input) {
            input.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    const name = input.value.trim();
                    if (addPlayer(name)) {
                        input.value = '';
                    }
                }
            });
        }

        const addBtn = $('setup-add-btn');
        if (addBtn) {
            addBtn.onclick = function() {
                const name = getPlayerInput()?.value.trim();
                if (name) addPlayer(name);
            };
        }

        const startBtn = getStartButton();
        if (startBtn) {
            startBtn.onclick = function() {
                const totalRoles = roles.villagers + roles.werewolves + roles.seers;
                if (players.length < 5) {
                    showError(t('setup.error_min_players'));
                    return;
                }
                if (totalRoles !== players.length) {
                    showError(t('setup.error_role_mismatch', { roles: totalRoles, players: players.length }));
                    return;
                }
                LoupGarouCore.startGame();
            };
        }
    }

    function hide() {
        const container = getContainer();
        if (container) container.classList.add('hidden');
    }

    // ============================================
    // Public API
    // ============================================

    return {
        show,
        hide,
        addPlayer,
        removePlayer,
        adjustRole,
        getPlayers: () => [...players],
    };
})();

window.ViewSetup = ViewSetup;