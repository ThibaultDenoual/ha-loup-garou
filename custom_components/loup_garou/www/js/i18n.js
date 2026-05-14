/**
 * i18n.js - Internationalization Module
 *
 * Handles translations for the Loup Garou UI.
 * Supports lazy-loaded language files.
 */

const LoupGarouI18n = (function() {
    'use strict';

    // ============================================
    // State
    // ============================================

    let translations = {};
    let currentLang = 'fr';
    const availableLangs = ['fr', 'en'];

    // ============================================
    // Translation Data (Embedded for simplicity)
    // ============================================

    const embeddedTranslations = {
        fr: {
            // General
            'app.title': 'Loup Garou',
            'status.connecting': 'Connexion en cours...',
            'status.connected': 'Connecté',
            'status.error': 'Erreur de connexion',
            'status.waiting_setup': 'En attente de configuration',
            'status.game_in_progress': 'Partie en cours',

            // Setup
            'setup.title': 'Configuration de la partie',
            'setup.players_label': 'Joueurs',
            'setup.players_min': '{{count}}/5 min',
            'setup.add_player_placeholder': 'Nom du joueur',
            'setup.add_player_button': 'Ajouter',
            'setup.roles_label': 'Distribution des rôles',
            'setup.villagers': 'Villageois',
            'setup.werewolves': 'Loups',
            'setup.seers': 'Voyante',
            'setup.start_button': 'Commencer la partie',
            'setup.error_min_players': 'Il faut au moins 5 joueurs pour commencer',
            'setup.error_role_mismatch': 'Le nombre de rôles ({{roles}}) doit correspondre au nombre de joueurs ({{players}})',
            'setup.players_empty': 'Aucun joueur ajouté',

            // Phases
            'phase.setup': 'Configuration',
            'phase.role_reveal': 'Distribution des rôles',
            'phase.night_start': 'Nuit - Le village s\'endort',
            'phase.night_seer_wake': 'Nuit - Réveil de la Voyante',
            'phase.night_seer_act': 'Nuit - La Voyante observe',
            'phase.night_seer_sleep': 'Nuit - La Voyante se rendort',
            'phase.night_wolf_wake': 'Nuit - Réveil des Loups',
            'phase.night_wolf_act': 'Nuit - Les Loups choisissent leur victime',
            'phase.night_wolf_sleep': 'Nuit - Les Loups se rendorment',
            'phase.day': 'Jour',
            'phase.vote': 'Vote',
            'phase.discussion': 'Discussion',
            'phase.game_over': 'Fin de partie',

            // Role Reveal
            'reveal.banner': '{{player}} doit voir son rôle',
            'reveal.progress': '{{current}}/{{total}}',
            'reveal.confirm_button': 'J\'ai vu mon rôle',

            // Night Actions
            'night.seer_turn': 'Tour de la {{role}}',
            'night.wolf_turn': 'Tour des {{role}}',
            'night.seer_action': 'observer le joueur choisi',
            'night.wolf_action': 'tuer le joueur choisi',
            'night.skip': 'Passer (ne rien faire)',
            'night.continue': 'Continuer',
            'night.seer_investigate': 'Observer le joueur choisi',
            'night.start_night': 'Commencer la nuit',
            'night.hint_select': 'Sélectionnez un joueur pour l\'observer',
            'night.hint_select_kill': 'Sélectionnez un joueur (non-loup) pour le tuer',
            'night.hint_wait': 'Attendez...',
            'night.hint_wait_wake': 'Attendez que la scène se termine...',
            'actions.investigate_result': '{{name}} est {{allegiance}}',
            'actions.investigate_wolf': 'un Loup-Garou',
            'actions.investigate_not_wolf': 'pas un Loup-Garou',
            'day.no_deaths': 'Miraculeusement, personne n\'est mort cette nuit.',
            'night.hint_select_kill': 'Sélectionnez un joueur (non-loup) pour le tuer',
            'night.hint_wait': 'Attendez...',
            'night.hint_wait_wake': 'Attendez que la scène se termine...',

            // Day Actions
            'day.start_vote': 'Commencer le vote',
            'day.skip_vote': 'Passer (sans vote)',
            'day.skip_to_night': 'Commencer la nuit',

            // Vote
            'vote.start': 'Commencer le vote',
            'vote.resolve': 'Terminer le vote',
            'vote.cast': 'Votes: {{count}}/{{total}}',

            // Game Over
            'game_over.wolves_win': 'Les Loups-Garous ont gagné !',
            'game_over.villagers_win': 'Le Village a gagné !',
            'game_over.new_game': 'Nouvelle partie',

            // Debug Panel
            'debug.title': 'Panneau de test',
            'debug.navigation': 'Navigation',
            'debug.elimination': 'Élimination',
            'debug.night_action': 'Action nuit',
            'debug.log': 'Log',

            // Roles
            'role.villager': 'Villageois',
            'role.werewolf': 'Loup-Garou',
            'role.seer': 'Voyante',
            'role.doctor': 'Docteur',
            'role.hunter': 'Chasseur',
            'role.witch': 'Sorcière',
            'role.cupid': 'Cupidon',
            'role.serial_killer': 'Tueur en série',
            'role.jester': 'Bouffon',
        },

        en: {
            // General
            'app.title': 'Werewolf',
            'status.connecting': 'Connecting...',
            'status.connected': 'Connected',
            'status.error': 'Connection error',
            'status.waiting_setup': 'Waiting for setup',
            'status.game_in_progress': 'Game in progress',

            // Setup
            'setup.title': 'Game Configuration',
            'setup.players_label': 'Players',
            'setup.players_min': '{{count}}/5 min',
            'setup.add_player_placeholder': 'Player name',
            'setup.add_player_button': 'Add',
            'setup.roles_label': 'Role Distribution',
            'setup.villagers': 'Villagers',
            'setup.werewolves': 'Werewolves',
            'setup.seers': 'Seer',
            'setup.start_button': 'Start Game',
            'setup.error_min_players': 'At least 5 players required',
            'setup.error_role_mismatch': 'Role count ({{roles}}) must match player count ({{players}})',

            // Phases
            'phase.setup': 'Setup',
            'phase.role_reveal': 'Role Distribution',
            'phase.night_start': 'Night - Village sleeps',
            'phase.night_seer_wake': 'Night - Seer Awakens',
            'phase.night_seer_act': 'Night - Seer Observes',
            'phase.night_seer_sleep': 'Night - Seer Sleeps',
            'phase.night_wolf_wake': 'Night - Wolves Awake',
            'phase.night_wolf_act': 'Night - Wolves Choose Victim',
            'phase.night_wolf_sleep': 'Night - Wolves Sleep',
            'phase.day': 'Day',
            'phase.vote': 'Vote',
            'phase.discussion': 'Discussion',
            'phase.game_over': 'Game Over',

            // Role Reveal
            'reveal.banner': '{{player}} doit voir son rôle',
            'reveal.progress': '{{current}}/{{total}}',
            'reveal.confirm_button': 'I\'ve seen my role',

            // Night Actions
            'night.seer_turn': '{{role}}\'s Turn',
            'night.wolf_turn': '{{role}}\'s Turn',
            'night.seer_action': 'Observe chosen player',
            'night.wolf_action': 'Kill chosen player',
            'night.skip': 'Skip (do nothing)',
            'night.continue': 'Continue',
            'night.seer_investigate': 'Observe chosen player',
            'night.start_night': 'Start Night',
            'night.hint_select': 'Select a player to observe',
            'night.hint_select_kill': 'Select a player (non-wolf) to kill',
            'night.hint_wait': 'Please wait...',
            'night.hint_wait_wake': 'Wait for scene to end...',
            'actions.investigate_result': '{{name}} is {{allegiance}}',
            'actions.investigate_wolf': 'a Werewolf',
            'actions.investigate_not_wolf': 'not a Werewolf',
            'day.no_deaths': 'Miraculously, no one died last night.',

            // Day Actions
            'day.start_vote': 'Start Vote',
            'day.skip_vote': 'Skip (no vote)',
            'day.skip_to_night': 'Start Night',

            // Vote
            'vote.start': 'Start Vote',
            'vote.resolve': 'End Vote',
            'vote.cast': 'Votes: {{count}}/{{total}}',

            // Game Over
            'game_over.wolves_win': 'The Werewolves Win!',
            'game_over.villagers_win': 'The Village Wins!',
            'game_over.new_game': 'New Game',

            // Debug Panel
            'debug.title': 'Debug Panel',
            'debug.navigation': 'Navigation',
            'debug.elimination': 'Elimination',
            'debug.night_action': 'Night Action',
            'debug.log': 'Log',

            // Roles
            'role.villager': 'Villager',
            'role.werewolf': 'Werewolf',
            'role.seer': 'Seer',
            'role.doctor': 'Doctor',
            'role.hunter': 'Hunter',
            'role.witch': 'Witch',
            'role.cupid': 'Cupid',
            'role.serial_killer': 'Serial Killer',
            'role.jester': 'Jester',
        }
    };

    // ============================================
    // Functions
    // ============================================

    /**
     * Set the current language
     * @param {string} lang - Language code (e.g., 'fr', 'en')
     */
    function setLanguage(lang) {
        if (availableLangs.includes(lang)) {
            currentLang = lang;
            translations = embeddedTranslations[lang];
        }
    }

    /**
     * Get the current language
     * @returns {string} Current language code
     */
    function getLanguage() {
        return currentLang;
    }

    /**
     * Get available languages
     * @returns {string[]} Array of language codes
     */
    function getAvailableLanguages() {
        return [...availableLangs];
    }

    /**
     * Translation function
     * @param {string} key - Translation key
     * @param {Object|undefined} params - Interpolation parameters
     * @returns {string} Translated string or key as fallback
     */
    function t(key, params) {
        let text = translations[key] || embeddedTranslations.fr[key] || key;

        if (params) {
            Object.keys(params).forEach(param => {
                text = text.replace(new RegExp('\\{' + param + '\\}', 'g'), params[param]);
            });
        }

        return text;
    }

    /**
     * Check if a translation key exists
     * @param {string} key - Translation key
     * @returns {boolean}
     */
    function hasKey(key) {
        return translations[key] !== undefined || embeddedTranslations.fr[key] !== undefined;
    }

    /**
     * Detect browser language
     * @returns {string} Detected language code
     */
    function detectLanguage() {
        const browserLang = navigator.language.split('-')[0];
        return availableLangs.includes(browserLang) ? browserLang : 'fr';
    }

    // ============================================
    // Initialize
    // ============================================

    // Auto-detect language on load
    setLanguage(detectLanguage());

    // ============================================
    // Public API
    // ============================================

    return {
        setLanguage,
        getLanguage,
        getAvailableLanguages,
        t,
        hasKey,
        detectLanguage,
        translations: embeddedTranslations
    };
})();

// Export for ES modules (if supported)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = LoupGarouI18n;
}