/**
 * view-night.js - Night View Module
 *
 * Handles night phase:
 * - Seer turn (observe players)
 * - Werewolf turn (select victim)
 * - Continue/skip button
 * - Seer result display
 */

const ViewNight = (function() {
    'use strict';

    const { $, $$, escapeHtml, animateOnce } = LoupGarouUtils;
    const { t } = LoupGarouI18n;

    let selectedTarget = null;

    function getContainer() { return $('view-night'); }
    function getPlayerGrid() { return $('night-player-grid'); }
    function getHint() { return $('night-action-hint'); }
    function getContinueBtn() { return $('night-continue-btn'); }
    function getRoleIndicator() { return $('night-role-indicator'); }
    function getSeerResult() { return $('seer-result'); }

    function render(state) {
        selectedTarget = null;
        const grid = getPlayerGrid();
        const hint = getHint();
        const btn = getContinueBtn();
        const indicator = getRoleIndicator();

        const phase = state?.phase || 'night_start';
        const nightRole = state?.currentNightRole;
        const players = state?.players || [];
        const targetId = state?.currentTargetId;
        const nightActions = state?.nightActions || {};

        // Role indicator
        if (indicator) {
            if (nightRole === 'seer') {
                indicator.classList.remove('hidden');
                indicator.className = 'night-role-indicator seer';
                indicator.textContent = t('night.seer_turn', { role: t('role.seer') });
            } else if (nightRole === 'werewolf') {
                indicator.classList.remove('hidden');
                indicator.className = 'night-role-indicator werewolf';
                indicator.textContent = t('night.wolf_turn', { role: t('role.werewolf') });
            } else {
                indicator.classList.add('hidden');
            }
        }

        // Hint
        if (hint) {
            if (nightRole === 'seer') {
                hint.textContent = t('night.hint_select');
            } else if (nightRole === 'werewolf') {
                hint.textContent = t('night.hint_select_kill');
            } else if (phase === 'night_start' || phase.includes('wake') || phase.includes('sleep')) {
                hint.textContent = t('night.hint_wait_wake');
            } else {
                hint.textContent = t('night.hint_wait');
            }
        }

        // Player grid
        if (grid) {
            const canSelect = nightRole && (phase === 'night_seer_act' || phase === 'night_wolf_act');
            const showRole = nightRole === 'werewolf';

            grid.innerHTML = players.map(p => {
                if (!p.alive) {
                    return `<div class="player-card eliminated">
                        <div class="player-card__name">${escapeHtml(p.name)}</div>
                        <i class="fas fa-skull player-card__icon"></i>
                    </div>`;
                }

                const classes = ['player-card'];
                if (nightRole === 'werewolf') classes.push('wolf');
                if (nightRole === 'seer') classes.push('seer');
                if (p.id === targetId || p.name === targetId) classes.push('selected');

                const onclick = canSelect
                    ? `onclick="ViewNight.selectTarget('${escapeHtml(p.id || p.name)}')"`
                    : '';

                return `<div class="${classes.join(' ')}" ${onclick}>
                    <div class="player-card__name">${escapeHtml(p.name)}</div>
                    ${(p.id === targetId || p.name === targetId) ? '<i class="fas fa-crosshairs player-card__target"></i>' : ''}
                </div>`;
            }).join('');
        }

        // Continue button
        if (btn) {
            if (nightRole && (phase === 'night_seer_act' || phase === 'night_wolf_act')) {
                btn.classList.remove('hidden');
                btn.textContent = selectedTarget ? t('night.continue') : t('night.skip');
            } else if (phase === 'night_start') {
                btn.classList.remove('hidden');
                btn.textContent = t('night.start_night');
            } else {
                btn.classList.add('hidden');
            }
        }

        // Seer result
        const seerResultEl = getSeerResult();
        if (seerResultEl && nightActions.seerResult !== null) {
            seerResultEl.classList.remove('hidden');
            const isWolf = nightActions.seerResult === 'werewolf';
            seerResultEl.innerHTML = `<div class="card animate-slide-up" style="border-left: 4px solid var(--color-seer);">
                <h3>${t('night.seer_investigate')}</h3>
                <p>${t('actions.investigate_result', {
                    name: nightActions.seerTargetId || '?',
                    allegiance: isWolf ? t('actions.investigate_wolf') : t('actions.investigate_not_wolf')
                })}</p>
            </div>`;
        } else if (seerResultEl) {
            seerResultEl.classList.add('hidden');
        }
    }

    function selectTarget(playerId) {
        selectedTarget = playerId;
        LoupGarouCore.selectTarget(playerId);

        $$('.player-card').forEach(card => {
            const name = card.querySelector('.player-card__name')?.textContent;
            const id = card.dataset.playerId;
            if (id === playerId || name === playerId) {
                card.classList.add('selected');
                if (!card.querySelector('.player-card__target')) {
                    card.innerHTML += '<i class="fas fa-crosshairs player-card__target"></i>';
                }
            } else {
                card.classList.remove('selected');
                const icon = card.querySelector('.player-card__target');
                if (icon) icon.remove();
            }
        });

        const btn = getContinueBtn();
        if (btn) btn.textContent = t('night.continue');
    }

    function handleContinue() {
        const state = LoupGarouCore.getState();
        const nightRole = state.currentNightRole;
        const phase = state.phase;

        if (phase === 'night_start') {
            LoupGarouCore.nextPhase();
            return;
        }

        if (selectedTarget) {
            if (nightRole === 'seer') {
                LoupGarouCore.submitNightAction('seer_investigate', selectedTarget);
            } else if (nightRole === 'werewolf') {
                LoupGarouCore.submitNightAction('wolf_kill', selectedTarget);
            }
        } else {
            LoupGarouCore.skipAction();
        }
    }

    function show(state) {
        const container = getContainer();
        if (container) {
            container.classList.remove('hidden');
            animateOnce(container, 'animate-fade-in');
        }
        render(state || LoupGarouCore.getState());

        const btn = getContinueBtn();
        if (btn) btn.onclick = handleContinue;
    }

    function hide() {
        const container = getContainer();
        if (container) container.classList.add('hidden');
    }

    return { show, hide, render, selectTarget, handleContinue };
})();

window.ViewNight = ViewNight;