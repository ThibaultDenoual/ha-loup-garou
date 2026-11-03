"""The console plays through the same prompts as the browser."""
from __future__ import annotations

from loup_garou.console.console_runner import ConsoleRunner


async def test_console_plays_a_whole_game_from_stdin(monkeypatch, capsys):
    inputs = iter([
        "Wolf", "Ann", "Bea", "",                 # players
        "werewolf", "villager", "villager",       # roles
        "", "", "",                               # one reveal each
        "nobody",                                 # illegal: asked again
        "p1",                                     # the wolf's kill ends the game
    ])
    monkeypatch.setattr("builtins.input", lambda *_: next(inputs))

    runner = ConsoleRunner(language="en")
    await runner.run()

    assert runner._engine.get_public_state()["winner"] == "wolves"
    assert list(inputs) == []
    out = capsys.readouterr().out
    assert "wolves" in out.lower() or "werewol" in out.lower()
