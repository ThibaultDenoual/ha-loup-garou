"""Public roles (#78): dealing, and the voice clips that announce deaths by them."""
from __future__ import annotations

import random

import pytest

from loup_garou import public_roles, voice
from loup_garou.const import STATIC_AUDIO_MAP
from loup_garou.game_engine import GameEngine
from loup_garou.setup_rules import InvalidSetup, check_players


@pytest.mark.parametrize("count", [0, 3, 10])
def test_up_to_ten_players_get_distinct_trades(count):
    roles = public_roles.deal(count, random.Random(1))
    assert len(roles) == len(set(roles)) == count
    assert set(roles) <= set(public_roles.TRADES)


def test_past_ten_players_apprentices_follow_trades_in_play():
    roles = public_roles.deal(14, random.Random(2))
    apprentices = [r for r in roles if r.endswith(public_roles.APPRENTICE)]
    assert len(apprentices) == 4 and len(set(roles)) == 14
    for a in apprentices:
        assert a.removesuffix(public_roles.APPRENTICE) in roles


def test_more_than_twenty_players_cannot_be_dealt():
    assert len(public_roles.deal(20)) == 20
    with pytest.raises(ValueError):
        public_roles.deal(21)


def test_the_server_refuses_more_than_twenty_players():
    with pytest.raises(InvalidSetup) as err:
        check_players([f"P{i}" for i in range(21)])
    assert err.value.reason == "too_many"


async def test_every_player_gets_a_public_role_shown_in_snapshots():
    engine = GameEngine(rng=random.Random(3))
    await engine.start_game(["A", "B", "C"], ["werewolf", "villager", "seer"])
    publics = [p["public_role"] for p in engine.snapshot()["players"]]
    assert len(set(publics)) == 3 and all(publics)
    # Public, unlike the secret role.
    assert all("role_id" not in p for p in engine.snapshot()["players"])


def test_every_public_role_and_spoken_role_has_a_clip():
    for p in public_roles.ALL:
        assert f"public.{p}.spoken" in STATIC_AUDIO_MAP


def test_voice_urls_only_accept_known_clips():
    assert voice.parse("fr", "part_victim+public_baker+part_was+spoken_seer.mp3") == [
        "part_victim", "public_baker", "part_was", "spoken_seer",
    ]
    for lang, name in [
        ("de", "part_victim.mp3"),            # unknown language
        ("fr", "part_victim"),                # no .mp3
        ("fr", "part_victim+nope.mp3"),       # unknown clip
        ("fr", "../game/index.html.mp3"),     # path tricks
        ("fr", "+".join(["part_was"] * 7) + ".mp3"),  # too many parts
    ]:
        assert voice.parse(lang, name) is None


def test_joined_clip_is_the_parts_one_after_the_other():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2] / "custom_components/loup_garou/www/audio"
    parts = ("part_victim", "public_baker")
    joined = voice.join(root, "en", parts)
    assert joined == b"".join((root / "en" / f"{p}.mp3").read_bytes() for p in parts)
