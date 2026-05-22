/**
 * view-day.js - Day View Module
 *
 * Handles day phase:
 * - Display dead players from last night
 * - Player grid
 * - Start vote / skip buttons
 */

const ViewDay = (function() {
    'use strict';

    const { $, $$, escapeHtml, animateOnce } = LoupGarouUtils;
    const { t } = LoupGarouI18n;

    function getContainer() { return $('view-day'); }
    function getDeadList() { return $('dead-list'); }
    function getPlayerGrid() { return $('day-player-grid'); }
    function getStartVoteBtn() { return $('day-start-vote-btn'); }
    function getSkipBtn() { return $('day-skip-btn'); }

    function render(state) {
        const deadList = getDeadList();
        const grid = getPlayerGrid();

        const players = state?.players || [];
        const deadTonight = state?.eliminatedThisRound || [];

        if (deadList) {
            if (deadTonight.length > 0) {
                deadList.innerHTML = deadTonight.map(name => `
                    <div class="player-tag eliminated">
                        <i class="fas fa-skull" style="margin-right: 8px;"></i>
                        <span>${escapeHtml(name)}</span>
                    </div>
                `).join('');
            } else {
                deadList.innerHTML = `<p class="text-muted text-center" style="padding: var(--spacing-md);">
                    ${t('day.no_deaths') || 'Miraculeusement, personne n\'est mort cette nuit.'}
                </p>`;
            }
        }

        if (grid) {
            grid.innerHTML = players.map(p => {
                const classes = ['player-card'];
                if (!p.alive) {
                    classes.push('eliminated');
                    return `<div class="${classes.join(' ')}">
                        <div class="player-card__name">${escapeHtml(p.name)}</div>
                        <i class="fas fa-skull player-card__icon"></i>
                    </div>`;
                }
                return `<div class="${classes.join(' ')}">
                    <div class="player-card__name">${escapeHtml(p.name)}</div>
                </div>`;
            }).join('');
        }
    }

    function show(state) {
        const container = getContainer();
        if (container) {
            container.classList.remove('hidden');
            animateOnce(container, 'animate-fade-in');
        }
        render(state || LoupGarouCore.getState());

        const voteBtn = getStartVoteBtn();
        if (voteBtn) {
            voteBtn.classList.remove('hidden');
            voteBtn.onclick = function() {
                LoupGarouCore.beginVote();
            };
        }

        const skipBtn = getSkipBtn();
        if (skipBtn) {
            skipBtn.classList.remove('hidden');
            skipBtn.onclick = function() {
                LoupGarouCore.nextPhase();
            };
        }
    }

    function hide() {
        const container = getContainer();
        if (container) container.classList.add('hidden');
    }

    return { show, hide, render };
})();

window.ViewDay = ViewDay;