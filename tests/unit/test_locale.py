"""Tests for locale JSON files — structure and key completeness."""
import json
from pathlib import Path
import pytest

LOCALES_DIR = Path(__file__).parent.parent.parent / "custom_components" / "loup_garou" / "locales"
LANGUAGES = ["fr", "en"]
REQUIRED_KEYS = [
    "_meta",
    "phase.night.start",
    "phase.day.start_with_death",
    "phase.day.start_no_death",
    "phase.vote.start",
    "phase.vote.tie",
    "phase.game_over.wolves_win",
    "phase.game_over.village_win",
    "phase.game_over.lovers_win",
    "role.villager.name",
    "role.werewolf.name",
    "role.werewolf.wake",
    "role.werewolf.sleep",
    "role.seer.name",
    "role.witch.name",
    "role.cupid.name",
    "role.hunter.name",
    "role.elder.name",
    "role.scapegoat.name",
    "role.little_girl.name",
    "role.alpha_wolf.name",
    "role.minion.name",
    "role.sheriff.name",
    "elimination.wolf_kill",
    "elimination.village_vote",
    "elimination.hunter_shot",
    "elimination.lover_grief",
    "ui.setup.start_game",
    "ui.reveal.tap_to_reveal",
    "ui.vote.confirm",
]


@pytest.fixture(params=LANGUAGES)
def locale(request):
    lang = request.param
    path = LOCALES_DIR / f"{lang}.json"
    with open(path) as f:
        return json.load(f)


def test_locale_is_valid_json(locale):
    assert isinstance(locale, dict)


def test_locale_has_meta(locale):
    assert "_meta" in locale
    assert "language" in locale["_meta"]


@pytest.mark.parametrize("key", REQUIRED_KEYS)
def test_required_key_present(locale, key):
    assert key in locale, f"Missing key: {key}"


def test_no_empty_values(locale):
    for key, value in locale.items():
        if key == "_meta":
            continue
        if isinstance(value, str):
            assert value.strip(), f"Empty string for key: {key}"


def test_fr_and_en_have_same_keys():
    fr_path = LOCALES_DIR / "fr.json"
    en_path = LOCALES_DIR / "en.json"
    with open(fr_path) as f:
        fr = json.load(f)
    with open(en_path) as f:
        en = json.load(f)
    assert set(fr.keys()) == set(en.keys()), (
        f"Key mismatch: FR-only={set(fr)-set(en)}, EN-only={set(en)-set(fr)}"
    )
