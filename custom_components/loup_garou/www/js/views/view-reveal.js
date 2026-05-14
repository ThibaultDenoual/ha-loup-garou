/**
 * view-reveal.js - Role Reveal View Module
 *
 * Handles individual role reveal phase:
 * - Sequential player role display
 * - "I saw my role" confirmation button
 * - Progress tracking
 */

const ViewReveal = (function() {
    'use strict';

    const { $, escapeHtml, animateOnce } = LoupGarouUtils;
    const { t } = LoupGarouI18n;

    function getContainer() { return $('view-reveal'); }
    function getBanner() { return $('reveal-banner-text'); }
    function getProgress() { return $('reveal-progress'); }
    function getConfirmBtn() { return $('reveal-confirm-btn'); }

    function render(state) {
        const container = getContainer();
        if (!container) return;

        const index = state?.revealIndex || 0;
        const total = state?.revealTotal || state?.players?.length || 0;
        const nextPlayer = state?.nextRevealPlayer || state?.players?.[index]?.name || 'Player ' + (index + 1);

        const banner = getBanner();
        if (banner) {
            banner.textContent = t('reveal.banner', { player: nextPlayer });
        }

        const progress = getProgress();
        if (progress) {
            progress.textContent = t('reveal.progress', { current: index + 1, total });
        }
    }

    function show(state) {
        const container = getContainer();
        if (container) {
            container.classList.remove('hidden');
            animateOnce(container, 'animate-fade-in');
        }
        render(state);

        const btn = getConfirmBtn();
        if (btn) {
            btn.classList.remove('hidden');
            btn.onclick = function() {
                LoupGarouCore.confirmRoleSeen();
            };
        }
    }

    function hide() {
        const container = getContainer();
        if (container) container.classList.add('hidden');
        const btn = getConfirmBtn();
        if (btn) btn.classList.add('hidden');
    }

    return { show, hide, render };
})();

window.ViewReveal = ViewReveal;