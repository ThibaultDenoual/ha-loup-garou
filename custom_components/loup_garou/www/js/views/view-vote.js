/**
 * view-vote.js - Vote View Module
 *
 * Handles voting phase:
 * - Player selection for vote
 * - Vote cast counter
 * - Resolve vote button
 */

const ViewVote = (function() {
    'use strict';

    const { $, $$, escapeHtml, animateOnce } = LoupGarouUtils;
    const { t } = LoupGarouI18n;

    let selectedTarget = null;

    function getContainer() { return $('view-vote'); }
    function getPlayerGrid() { return $('vote-player-grid'); }
    function getCounter() { return $('vote-counter'); }
    function getResolveBtn() { return $('vote-resolve-btn'); }

    function render(state) {
        selectedTarget = null;
        const grid = getPlayerGrid();
        const counter = getCounter();
        const players = state?.players || [];
        const tallies = state?.voteTallies || {};
        const votesCast = state?.votesCast || 0;
        const aliveVoters = state?.aliveVoterCount || 0;

        if (counter) {
            counter.textContent = t('vote.cast', { count: votesCast, total: aliveVoters });
        }

        if (grid) {
            grid.innerHTML = players.map(p => {
                if (!p.alive) {
                    return `<div class="player-card eliminated">
                        <div class="player-card__name">${escapeHtml(p.name)}</div>
                        <i class="fas fa-skull player-card__icon"></i>
                    </div>`;
                }

                const votes = tallies[p.id || p.name] || 0;
                const classes = ['player-card'];
                if (votes > 0) classes.push('selected');

                return `<div class="${classes.join(' ')}" onclick="ViewVote.castVote('${escapeHtml(p.id || p.name)}')">
                    <div class="player-card__name">${escapeHtml(p.name)}</div>
                    ${votes > 0 ? `<div class="player-card__target" style="font-size:12px;color:var(--color-accent-warning);">${votes} vote${votes > 1 ? 's' : ''}</div>` : ''}
                </div>`;
            }).join('');
        }
    }

    function castVote(targetId) {
        selectedTarget = targetId;
        const state = LoupGarouCore.getState();
        const voterId = state.players.find(p => p.alive && p.role === 'villager')?.id || state.players[0]?.id;
        if (!voterId) return;

        LoupGarouCore.submitVote(voterId, targetId);
    }

    function handleResolve() {
        LoupGarouCore.resolveVote();
    }

    function show(state) {
        const container = getContainer();
        if (container) {
            container.classList.remove('hidden');
            animateOnce(container, 'animate-fade-in');
        }
        render(state || LoupGarouCore.getState());

        const btn = getResolveBtn();
        if (btn) {
            btn.classList.remove('hidden');
            btn.onclick = handleResolve;
        }
    }

    function hide() {
        const container = getContainer();
        if (container) container.classList.add('hidden');
    }

    return { show, hide, render, castVote, handleResolve };
})();

window.ViewVote = ViewVote;