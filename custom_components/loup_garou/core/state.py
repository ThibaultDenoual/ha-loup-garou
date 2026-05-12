"""Game state data models for Loup Garou."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict


@dataclass
class Player:
    """A participant in the game."""
    id: str
    name: str
    role: str
    alive: bool = True
    role_seen: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Player":
        return cls(**data)


@dataclass
class NightActions:
    """Tracks which night actions have been submitted this round."""
    wolf_victim_id: str | None = None
    seer_target_id: str | None = None
    seer_result: str | None = None
    completed_roles: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "NightActions":
        return cls(**data)


@dataclass
class GameState:
    """Complete snapshot of the game at a point in time."""
    phase: str = "setup"
    round: int = 0
    players: list[Player] = field(default_factory=list)
    night_actions: NightActions = field(default_factory=NightActions)
    vote_tallies: dict[str, list[str]] = field(default_factory=dict)
    eliminated_this_round: list[str] = field(default_factory=list)
    current_target_id: str | None = None
    reveal_order: list[str] = field(default_factory=list)
    reveal_index: int = 0
    winner: str | None = None
    language: str = "fr"
    delay_seconds: float = 2.0

    def to_dict(self) -> dict:
        return {
            "phase": self.phase,
            "round": self.round,
            "players": [p.to_dict() for p in self.players],
            "night_actions": self.night_actions.to_dict(),
            "vote_tallies": self.vote_tallies,
            "eliminated_this_round": self.eliminated_this_round,
            "reveal_order": self.reveal_order,
            "reveal_index": self.reveal_index,
            "winner": self.winner,
            "language": self.language,
            "delay_seconds": self.delay_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GameState":
        state = cls()
        state.phase = data.get("phase", "setup")
        state.round = data.get("round", 0)
        state.players = [Player.from_dict(p) for p in data.get("players", [])]
        na = data.get("night_actions", {})
        state.night_actions = NightActions.from_dict(na) if na else NightActions()
        state.vote_tallies = data.get("vote_tallies", {})
        state.eliminated_this_round = data.get("eliminated_this_round", [])
        state.reveal_order = data.get("reveal_order", [])
        state.reveal_index = data.get("reveal_index", 0)
        state.winner = data.get("winner")
        state.language = data.get("language", "fr")
        state.delay_seconds = data.get("delay_seconds", 2.0)
        return state