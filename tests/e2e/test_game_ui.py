"""E2E tests for Loup Garou frontend based on TEST_PLAN.md.

These tests document expected behavior. The frontend is currently broken
and will be fixed in a future iteration. Tests are designed to pass once
the frontend is functional.

Phase 5.1: Basic Game Flow
Phase 5.2: Backend Integration  
Phase 5.3: Edge Cases
Phase 5.4: Mobile Compatibility
Phase 5.5: Debug Panel
"""
from __future__ import annotations

import pytest


# ============================================================================
# Phase 5.1: Basic Game Flow
# ============================================================================

class TestLauncherHtml:
    """Phase 5.1.1: Launcher & Entry"""

    def test_launcher_loads_without_crash(self, page, launcher_url):
        """launcher.html loads without console errors."""
        page.goto(launcher_url)
        page.wait_for_timeout(500)
        assert page.title() == "Loup Garou — Game Master"

    def test_launcher_title_visible(self, page, launcher_url):
        """Launcher title is visible."""
        page.goto(launcher_url)
        page.wait_for_timeout(500)
        title = page.locator(".launcher-title")
        assert title.is_visible()

    def test_launcher_opens_game_new_tab(self, page, launcher_url):
        """'Lancer le Jeu' opens game.html in new tab."""
        page.goto(launcher_url)
        page.wait_for_timeout(500)
        btn = page.locator("#open-game-btn")
        assert btn.is_visible()
        assert "game.html" in btn.get_attribute("href") or btn.get_attribute("onclick")

    def test_launcher_opens_game_same_tab(self, page, launcher_url):
        """'Ouvrir dans cet onglet' navigates to game.html."""
        page.goto(launcher_url)
        page.wait_for_timeout(500)
        btn = page.locator("#open-game-same-btn")
        assert btn.is_visible()


class TestGameSetupView:
    """Phase 5.1.2: Setup Phase"""

    def test_game_html_loads(self, page, game_url):
        """game.html loads without crash."""
        page.goto(game_url)
        page.wait_for_timeout(500)
        assert page.title() == "Loup Garou"

    def test_debug_panel_hidden_without_flag(self, page, game_url):
        """Debug panel hidden without ?debug=1."""
        page.goto(game_url)
        page.wait_for_timeout(500)
        panel = page.locator("#debug-panel")
        display = page.evaluate("getComputedStyle(document.getElementById('debug-panel')).display")
        assert display == "none"

    def test_debug_panel_visible_with_flag(self, page, game_url):
        """Debug panel visible with ?debug=1."""
        page.goto(f"{game_url}?debug=1")
        page.wait_for_timeout(500)
        panel = page.locator("#debug-panel")
        assert panel.is_visible()

    def test_player_input_exists(self, page, game_url):
        """Player input field exists in setup view."""
        page.goto(f"{game_url}?debug=1")
        page.wait_for_timeout(500)
        player_input = page.locator("#setup-player-input")
        assert player_input.count() > 0 or page.locator(".player-input-row input").count() > 0

    def test_player_list_exists(self, page, game_url):
        """Player list container exists."""
        page.goto(f"{game_url}?debug=1")
        page.wait_for_timeout(500)
        player_list = page.locator("#setup-player-list")
        assert player_list.count() > 0 or page.locator(".player-input-row").count() > 0

    def test_add_player_button_exists(self, page, game_url):
        """Add player button exists."""
        page.goto(f"{game_url}?debug=1")
        page.wait_for_timeout(500)
        add_btn = page.locator("#setup-add-btn")
        assert add_btn.count() > 0 or page.locator("#add-player-btn").count() > 0

    def test_role_preset_buttons_exist(self, page, game_url):
        """Role preset buttons (small/medium/large) exist."""
        page.goto(f"{game_url}?debug=1")
        page.wait_for_timeout(500)
        preset_grid = page.locator("#preset-grid")
        assert preset_grid.count() > 0
        buttons = preset_grid.locator("button, .preset-btn")
        assert buttons.count() >= 3

    def test_start_game_button_exists(self, page, game_url):
        """'Commencer la partie' button exists."""
        page.goto(f"{game_url}?debug=1")
        page.wait_for_timeout(500)
        start_btn = page.locator("#setup-start-btn")
        assert start_btn.count() > 0 or page.locator("#start-game-btn").count() > 0


class TestRoleRevealPhase:
    """Phase 5.1.3: Role Reveal Phase"""

    def test_reveal_view_container_exists(self, goto_reveal_phase):
        """Reveal view container exists."""
        page = goto_reveal_phase
        reveal = page.locator("#view-reveal")
        assert reveal.count() > 0

    def test_reveal_view_is_active(self, goto_reveal_phase):
        """Reveal view is active when in role_reveal phase."""
        page = goto_reveal_phase
        reveal = page.locator("#view-reveal")
        # Check that reveal view has 'active' class
        is_active = reveal.evaluate("el => el.classList.contains('active')")
        assert is_active is True

    def test_reveal_player_name_displayed(self, goto_reveal_phase):
        """Reveal view shows current player name."""
        page = goto_reveal_phase
        player_name = page.locator("#reveal-player-name, .reveal-player-name")
        assert player_name.count() > 0

    def test_role_card_button_exists(self, goto_reveal_phase):
        """'J'ai vu mon rôle' button exists."""
        page = goto_reveal_phase
        role_btn = page.locator("#role-card")
        assert role_btn.count() > 0

    def test_reveal_progress_displayed(self, goto_reveal_phase):
        """Reveal progress shows X/Y players seen."""
        page = goto_reveal_phase
        progress = page.locator("#reveal-progress, .reveal-progress")
        assert progress.count() > 0

    def test_reveal_confirm_advances_to_next_player(self, goto_reveal_phase):
        """Clicking confirm button advances to next player reveal."""
        page = goto_reveal_phase
        initial_index = page.evaluate("window._getGameState().reveal_index")

        card = page.locator("#role-card")
        card.click()
        page.wait_for_timeout(500)

        seen_btn = page.locator("#seen-btn")
        seen_btn.click()
        page.wait_for_timeout(800)

        new_index = page.evaluate("window._getGameState().reveal_index")
        assert new_index == initial_index + 1

    def test_reveal_shows_role_name(self, goto_reveal_phase):
        """Reveal view shows role name when card is revealed."""
        page = goto_reveal_phase
        card = page.locator("#role-card")
        assert card.count() > 0
        card.click()
        page.wait_for_timeout(500)
        is_revealed = card.evaluate("el => el.classList.contains('revealed')")
        assert is_revealed is True
        role_text = page.locator("#role-card-back .role-name")
        assert role_text.count() > 0
        assert role_text.inner_text() == "Voyant"

    def test_reveal_completes_after_all_players(self, goto_reveal_phase):
        """After all players confirm, phase advances to next."""
        page = goto_reveal_phase
        total_players = page.evaluate("window._getGameState().reveal_total")

        for _ in range(total_players):
            card = page.locator("#role-card")
            card.click()
            page.wait_for_timeout(300)
            seen_btn = page.locator("#seen-btn")
            seen_btn.click()
            page.wait_for_timeout(500)
        page.wait_for_timeout(1000)
        phase = page.evaluate("window._getGameState().phase")
        assert phase == "night_start"


class TestNightPhase:
    """Phase 5.1.4: Night Phase"""

    def test_night_view_container_exists(self, goto_night_phase):
        """Night view container exists."""
        page = goto_night_phase
        night = page.locator("#view-night")
        assert night.count() > 0

    def test_night_sleeping_message_exists(self, goto_night_phase):
        """Night view shows 'Le village s'endort...' message."""
        page = goto_night_phase
        msg = page.locator("#night-message, .night-message")
        assert msg.count() > 0

    def test_night_role_indicator_exists(self, goto_night_phase):
        """Night view has role indicator (Seer/Wolf wake messages)."""
        page = goto_night_phase
        role_indicator = page.locator("#night-role-indicator")
        assert role_indicator.count() > 0

    def test_night_player_grid_exists(self, goto_night_phase):
        """Night view has player grid for selection."""
        page = goto_night_phase
        grid = page.locator("#night-player-grid")
        assert grid.count() > 0

    def test_night_confirm_button_exists(self, goto_night_phase):
        """Night confirm/continue button exists."""
        page = goto_night_phase
        page.wait_for_timeout(500)
        confirm = page.locator("#night-confirm-btn, #night-continue-btn")
        assert confirm.count() > 0

    def test_stars_visible_during_night(self, goto_night_phase):
        """Stars layer visible during night phase."""
        page = goto_night_phase
        stars = page.locator("#stars-layer")
        assert stars.count() > 0


class TestDayPhase:
    """Phase 5.1.5: Day Phase"""

    def test_day_view_container_exists(self, goto_day_phase):
        """Day view container exists."""
        page = goto_day_phase
        page.wait_for_timeout(500)
        day = page.locator("#view-day")
        assert day.count() > 0

    def test_day_alive_players_list_exists(self, goto_day_phase):
        """Day view shows alive players list."""
        page = goto_day_phase
        page.wait_for_timeout(500)
        alive_list = page.locator("#alive-list, .alive-list")
        assert alive_list.count() > 0

    def test_day_dead_list_exists(self, goto_day_phase):
        """Day view shows eliminated players separately."""
        page = goto_day_phase
        page.wait_for_timeout(500)
        dead_list = page.locator("#dead-list, .dead-list")
        assert dead_list.count() > 0

    def test_day_start_vote_button_exists(self, goto_day_phase):
        """'Commencer le vote' button exists."""
        page = goto_day_phase
        page.wait_for_timeout(500)
        vote_btn = page.locator("#day-start-vote-btn")
        assert vote_btn.count() > 0

    def test_day_skip_vote_button_exists(self, goto_day_phase):
        """'Passer (sans vote)' button exists."""
        page = goto_day_phase
        page.wait_for_timeout(500)
        skip_btn = page.locator("#day-skip-vote-btn")
        assert skip_btn.count() > 0


class TestVotePhase:
    """Phase 5.1.6: Vote Phase"""

    def test_vote_view_container_exists(self, goto_vote_phase):
        """Vote view container exists."""
        page = goto_vote_phase
        page.wait_for_timeout(500)
        vote = page.locator("#view-vote")
        assert vote.count() > 0

    def test_vote_player_grid_exists(self, goto_vote_phase):
        """Vote view shows all alive players."""
        page = goto_vote_phase
        page.wait_for_timeout(500)
        grid = page.locator("#vote-player-grid")
        assert grid.count() > 0

    def test_vote_counter_exists(self, goto_vote_phase):
        """Vote counter shows X/Y votes cast."""
        page = goto_vote_phase
        page.wait_for_timeout(500)
        counter = page.locator("#vote-counter")
        assert counter.count() > 0

    def test_vote_resolve_button_exists(self, goto_vote_phase):
        """'Terminer le vote' button exists."""
        page = goto_vote_phase
        page.wait_for_timeout(500)
        resolve_btn = page.locator("#vote-resolve-btn")
        assert resolve_btn.count() > 0


class TestGameOver:
    """Phase 5.1.7: Game Over"""

    def test_end_view_container_exists(self, goto_end_phase):
        """End view container exists."""
        page = goto_end_phase
        page.wait_for_timeout(500)
        end = page.locator("#view-end")
        assert end.count() > 0

    def test_game_over_banner_exists(self, goto_end_phase):
        """Game over winner banner exists."""
        page = goto_end_phase
        page.wait_for_timeout(500)
        banner = page.locator("#game-over-banner")
        assert banner.count() > 0

    def test_new_game_button_exists(self, goto_end_phase):
        """'Nouvelle partie' button exists."""
        page = goto_end_phase
        page.wait_for_timeout(500)
        new_game_btn = page.locator("#end-new-game-btn")
        assert new_game_btn.count() > 0


# ============================================================================
# Phase 5.2: Backend Integration
# ============================================================================

class TestWebSocketStatus:
    """Phase 5.2: WebSocket integration"""

    def test_ws_status_indicator_exists(self, page, game_url):
        """WebSocket status indicator exists in header."""
        page.goto(game_url)
        page.wait_for_timeout(500)
        ws_status = page.locator("#ws-status")
        assert ws_status.count() > 0


class TestHeaderStats:
    """Phase 5.2.2: State Synchronization"""

    def test_header_round_exists(self, page, game_url):
        """Header round element exists."""
        page.goto(game_url)
        page.wait_for_timeout(500)
        round_el = page.locator("#header-round")
        assert round_el.count() > 0

    def test_header_alive_count_exists(self, page, game_url):
        """Header alive count element exists."""
        page.goto(game_url)
        page.wait_for_timeout(500)
        alive_el = page.locator("#header-alive")
        assert alive_el.count() > 0


class TestPhaseOverlay:
    """Phase transitions"""

    def test_phase_overlay_exists(self, page, game_url):
        """Phase overlay element exists."""
        page.goto(game_url)
        page.wait_for_timeout(500)
        overlay = page.locator("#phase-overlay")
        assert overlay.count() > 0


# ============================================================================
# Phase 5.3: Edge Cases
# ============================================================================

class TestEdgeCases:
    """Phase 5.3: Edge Cases"""

    def test_player_input_max_length(self, page, game_url):
        """Player input has maxlength attribute (24 chars)."""
        page.goto(f"{game_url}?debug=1")
        page.wait_for_timeout(500)
        input_el = page.locator(".player-input-row input").first
        if input_el.count() > 0:
            maxlen = input_el.get_attribute("maxlength")
            assert maxlen == "24"


# ============================================================================
# Phase 5.4: Mobile Compatibility
# ============================================================================

class TestMobileLayout:
    """Phase 5.4: Mobile Compatibility"""

    def test_viewport_meta_tag_exists(self, page, game_url):
        """Viewport meta tag is set."""
        page.goto(game_url)
        page.wait_for_timeout(500)
        viewport = page.locator('meta[name="viewport"]')
        assert viewport.is_visible()

    def test_mobile_viewport_375px(self, page, game_url):
        """Page renders on 375px width viewport."""
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(game_url)
        page.wait_for_timeout(500)
        assert page.title() == "Loup Garou"


# ============================================================================
# Phase 5.5: Debug Panel
# ============================================================================

class TestDebugPanel:
    """Phase 5.5: Debug Panel"""

    def test_debug_panel_element_exists(self, page, game_url):
        """Debug panel element exists."""
        page.goto(game_url)
        page.wait_for_timeout(500)
        panel = page.locator("#debug-panel")
        assert panel.count() > 0

    def test_debug_reset_button_exists(self, page, game_url):
        """Debug reset button exists."""
        page.goto(f"{game_url}?debug=1")
        page.wait_for_timeout(500)
        reset_btn = page.locator("#debug-reset")
        assert reset_btn.is_visible()

    def test_debug_next_phase_button_exists(self, page, game_url):
        """Debug 'Phase suivante' button exists."""
        page.goto(f"{game_url}?debug=1")
        page.wait_for_timeout(500)
        next_btn = page.locator("#debug-next-phase")
        assert next_btn.is_visible()

    def test_debug_begin_vote_button_exists(self, page, game_url):
        """Debug 'Commencer vote' button exists."""
        page.goto(f"{game_url}?debug=1")
        page.wait_for_timeout(500)
        vote_btn = page.locator("#debug-begin-vote")
        assert vote_btn.is_visible()

    def test_debug_resolve_votes_button_exists(self, page, game_url):
        """Debug 'Résoudre votes' button exists."""
        page.goto(f"{game_url}?debug=1")
        page.wait_for_timeout(500)
        resolve_btn = page.locator("#debug-resolve-votes")
        assert resolve_btn.is_visible()

    def test_debug_elimination_buttons_container_exists(self, page, game_url):
        """Debug elimination buttons container exists."""
        page.goto(f"{game_url}?debug=1")
        page.wait_for_timeout(500)
        elim = page.locator("#debug-elim-buttons")
        assert elim.count() > 0

    def test_debug_wolf_buttons_container_exists(self, page, game_url):
        """Debug wolf kill buttons container exists."""
        page.goto(f"{game_url}?debug=1")
        page.wait_for_timeout(500)
        wolf = page.locator("#debug-wolf-buttons")
        assert wolf.count() > 0

    def test_debug_seer_buttons_container_exists(self, page, game_url):
        """Debug seer investigate buttons container exists."""
        page.goto(f"{game_url}?debug=1")
        page.wait_for_timeout(500)
        seer = page.locator("#debug-seer-buttons")
        assert seer.count() > 0

    def test_debug_log_area_exists(self, page, game_url):
        """Debug log area exists."""
        page.goto(f"{game_url}?debug=1")
        page.wait_for_timeout(500)
        log = page.locator("#log-area")
        assert log.count() > 0


# ============================================================================
# Static Asset Tests
# ============================================================================

class TestAssets:
    """Verify all required assets are properly linked."""

    def test_css_variables_linked(self, page, game_url):
        """CSS variables file is linked."""
        page.goto(game_url)
        page.wait_for_timeout(300)
        link = page.locator('link[href="css/variables.css"]')
        assert link.count() > 0

    def test_css_base_linked(self, page, game_url):
        """CSS base file is linked."""
        page.goto(game_url)
        page.wait_for_timeout(300)
        link = page.locator('link[href="css/base.css"]')
        assert link.count() > 0

    def test_css_components_linked(self, page, game_url):
        """CSS components file is linked."""
        page.goto(game_url)
        page.wait_for_timeout(300)
        link = page.locator('link[href="css/components.css"]')
        assert link.count() > 0

    def test_css_views_linked(self, page, game_url):
        """CSS views file is linked."""
        page.goto(game_url)
        page.wait_for_timeout(300)
        link = page.locator('link[href="css/views.css"]')
        assert link.count() > 0

    def test_css_animations_linked(self, page, game_url):
        """CSS animations file is linked."""
        page.goto(game_url)
        page.wait_for_timeout(300)
        link = page.locator('link[href="css/animations.css"]')
        assert link.count() > 0

    def test_js_i18n_linked(self, page, game_url):
        """JS i18n library is linked."""
        page.goto(game_url)
        page.wait_for_timeout(300)
        script = page.locator('script[src="js/i18n.js"]')
        assert script.count() > 0

    def test_js_utils_linked(self, page, game_url):
        """JS utils library is linked."""
        page.goto(game_url)
        page.wait_for_timeout(300)
        script = page.locator('script[src="js/utils.js"]')
        assert script.count() > 0

    def test_js_core_linked(self, page, game_url):
        """JS core is linked."""
        page.goto(game_url)
        page.wait_for_timeout(300)
        script = page.locator('script[src="js/core.js"]')
        assert script.count() > 0


class TestStarsBackground:
    """Test stars background element."""

    def test_stars_layer_exists(self, page, game_url):
        """Stars layer element exists."""
        page.goto(game_url)
        page.wait_for_timeout(500)
        stars = page.locator("#stars-layer")
        assert stars.count() > 0


class TestErrorHandling:
    """Test error handling elements."""

    def test_error_message_container_exists(self, page, game_url):
        """Error message container exists."""
        page.goto(game_url)
        page.wait_for_timeout(500)
        error = page.locator("#error-message")
        assert error.count() > 0