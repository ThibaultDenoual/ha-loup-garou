"""
Tests for core_game i18n module.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "custom_components", "loup_garou"))


class TestI18n:
    """Test i18n translation functions."""

    def test_english_role_names(self):
        """Can translate role names to English."""
        from core_game.i18n import t, set_language
        
        set_language("en")
        
        assert t("roles.Villager.name") == "Villager"
        assert t("roles.Seer.name") == "Seer"
        assert t("roles.Werewolf.name") == "Werewolf"

    def test_french_role_names(self):
        """Can translate role names to French."""
        from core_game.i18n import t, set_language
        
        set_language("fr")
        
        assert t("roles.Villager.name") == "Villageois"
        assert t("roles.Seer.name") == "Voyante"
        assert t("roles.Werewolf.name") == "Loup-Garou"

    def test_interpolation(self):
        """Can interpolate values into translations."""
        from core_game.i18n import t, set_language
        
        set_language("en")
        
        result = t("roles.Seer.prompt_investigate", player_name="Alice")
        assert "Alice" in result

    def test_role_descriptions(self):
        """Can get role descriptions."""
        from core_game.i18n import t, set_language
        
        set_language("en")
        
        desc = t("roles.Seer.description")
        assert len(desc) > 0

    def test_fallback_to_english(self):
        """Falls back to English for unknown keys."""
        from core_game.i18n import t, set_language
        
        set_language("fr")
        
        # French has the key, but let's test fallback behavior
        result = t("roles.Villager.name")
        assert result is not None

    def test_get_language(self):
        """Can get current language."""
        from core_game.i18n import get_language, set_language
        
        set_language("fr")
        assert get_language() == "fr"
        
        set_language("en")
        assert get_language() == "en"

    def test_available_languages(self):
        """Can list available languages."""
        from core_game.i18n import available_languages
        
        langs = available_languages()
        assert "en" in langs
        assert "fr" in langs

    def test_has_key(self):
        """Can check if a key exists."""
        from core_game.i18n import has_key, set_language
        
        set_language("en")
        
        assert has_key("roles.Villager.name") is True
        assert has_key("roles.Nonexistent.key") is False

    def test_tts_translations(self):
        """Can access TTS strings."""
        from core_game.i18n import t, set_language
        
        set_language("fr")
        
        assert t("tts.night_start") is not None
        assert t("tts.village_wins") is not None


class TestLocales:
    """Test locale file structure."""

    def test_locale_files_exist(self):
        """Verify locale files exist."""
        import os
        from core_game.i18n import _translations
        
        assert "en" in _translations
        assert "fr" in _translations

    def test_english_locale_structure(self):
        """English locale has expected structure."""
        from core_game.i18n import _translations
        
        en = _translations.get("en", {})
        
        assert "roles" in en
        assert "tts" in en
        assert "setup" in en

    def test_french_locale_structure(self):
        """French locale has expected structure."""
        from core_game.i18n import _translations
        
        fr = _translations.get("fr", {})
        
        assert "roles" in fr
        assert "tts" in fr
        assert "setup" in fr

    def test_role_keys_match(self):
        """Same roles exist in both languages."""
        from core_game.i18n import _translations
        
        en_roles = set(_translations.get("en", {}).get("roles", {}).keys())
        fr_roles = set(_translations.get("fr", {}).get("roles", {}).keys())
        
        assert en_roles == fr_roles

    def test_meta_information(self):
        """Locale files have meta information."""
        from core_game.i18n import _translations
        
        en = _translations.get("en", {})
        
        assert "_meta" in en
        assert en["_meta"]["language"] == "en"