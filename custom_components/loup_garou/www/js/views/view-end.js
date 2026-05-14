/**
 * view-end.js - Game Over View Module
 *
 * Handles game end:
 * - Winner announcement (wolves vs villagers)
 * - Final role reveal
 * - New game button
 */

const ViewEnd = (function() {
    'use strict';

    const { $, $$, escapeHtml, animateOnce } = LoupGarouUtils;
    const { t } = LoupGarouI18n;

    function getContainer() { return $('view-end'); }
    function getBanner() { return $('game-over-banner'); }
    function getNewGameBtn() { return $('end-new-game-btn'); }

    function render(state) {
        const banner = getBanner();
        if (!banner) return;

        const winner = state?.winner;
        const isWolvesWin = winner === 'werewolf' || winner === 'wolves';
        const isVillagersWin = winner === 'village' || winner === 'villagers';

        banner.className = 'game-over-banner';

        if (isWolvesWin) {
            banner.classList.add('wolves');
            banner.innerHTML = `
                <span class="game-over-banner__icon">
                    <i class="fas fa-moon"></i>
                </span>
                <h1>${t('game_over.wolves_win')}</h1>
                <p class="text-muted">Les Loups-Garous ont devore le village...</p>
            `;
        } else if (isVillagersWin) {
            banner.classList.add('villagers');
            banner.innerHTML = `
                <span class="game-over-banner__icon">
                    <i class="fas fa-sun"></i>
                </span>
                <h1>${t('game_over.villagers_win')}</h1>
                <p class="text-muted">Le village a survécu a la menace !</p>
            `;
        } else {
            banner.innerHTML = `
                <span class="game-over-banner__icon">
                    <i class="fas fa-trophy"></i>
                </span>
                <h1>Fin de partie</h1>
                <p class="text-muted">${winner || ''}</p>
            `;
        }

        const btn = getNewGameBtn();
        if (btn) btn.textContent = t('game_over.new_game');
    }

    function show(state) {
        const container = getContainer();
        if (container) {
            container.classList.remove('hidden');
            animateOnce(container, 'animate-fade-in');
        }
        render(state || LoupGarouCore.getState());

        const btn = getNewGameBtn();
        if (btn) {
            btn.classList.remove('hidden');
            btn.onclick = function() {
                LoupGarouCore.resetGame();
            };
        }
    }

    function hide() {
        const container = getContainer();
        if (container) container.classList.add('hidden');
    }

    return { show, hide, render };
})();

window.ViewEnd = ViewEnd;