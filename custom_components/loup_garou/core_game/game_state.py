"""
game_state.py — Pure data: players, lovers, deaths, night bookkeeping.

GameState is the single source of truth passed into every role's act().
It never drives logic — that belongs to the engine and state machine.

Includes serialization support for HA storage.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from roles import Role, NightAction


# ─────────────────────────────────────────────
#  Player
# ─────────────────────────────────────────────

@dataclass
class Player:
    name: str
    role: "Role"
    alive: bool = True
    lover: Optional["Player"] = None
    silenced: bool = False

    def __repr__(self):
        status = "alive" if self.alive else "dead"
        return f"<Player {self.name!r} [{self.role.name}] {status}>"

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return isinstance(other, Player) and self.name == other.name

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "role": self.role.name,
            "alive": self.alive,
            "silenced": self.silenced,
            "has_lover": self.lover is not None,
        }

    @classmethod
    def from_dict(cls, data: dict, role_registry: dict) -> "Player":
        player = cls(
            name=data["name"],
            role=role_registry.get(data["role"], role_registry["Villager"])(None),
            alive=data.get("alive", True),
            silenced=data.get("silenced", False),
        )
        return player


# ─────────────────────────────────────────────
#  GameState
# ─────────────────────────────────────────────

class GameState:
    """
    Snapshot of the entire game world.

    The engine mutates this object; roles read it to make decisions.
    """

    def __init__(self, players: list[Player] = None, io=None):
        self.players: list[Player] = players or []
        self.io = io

        self.round_number: int = 0
        self.phase: str = "setup"

        self.tonight_attacked: list[Player] = []
        self.tonight_protected: list[Player] = []
        self.pending_deaths: list[tuple[Player, str]] = []
        self.tonight_actions: list["NightAction"] = []

        self.current_elimination_cause: str = ""

        self.winner: Optional[str] = None
        self.solo_winner: Optional[Player] = None

        self.event_log: list[str] = []

    # ── Convenience properties ────────────────

    @property
    def alive_players(self) -> list[Player]:
        return [p for p in self.players if p.alive]

    @property
    def dead_players(self) -> list[Player]:
        return [p for p in self.players if not p.alive]

    @property
    def werewolves(self) -> list[Player]:
        return [p for p in self.alive_players if p.role.team == "werewolf"]

    @property
    def villagers(self) -> list[Player]:
        return [p for p in self.alive_players if p.role.team == "village"]

    # ── Mutation helpers ─────────────────────

    def reset_night_state(self):
        self.tonight_attacked = []
        self.tonight_protected = []
        self.pending_deaths = []
        self.tonight_actions = []

    def schedule_death(self, player: Player, cause: str = "unknown"):
        if (player, cause) not in self.pending_deaths:
            self.pending_deaths.append((player, cause))

    def link_lovers(self, p1: Player, p2: Player):
        p1.lover = p2
        p2.lover = p1
        self.log(f"💘 {p1.name} and {p2.name} are now bound by love.")

    def declare_solo_winner(self, player: Player):
        self.solo_winner = player
        self.winner = player.name

    def log(self, message: str):
        self.event_log.append(f"[R{self.round_number}|{self.phase}] {message}")

    def is_game_over(self) -> bool:
        return self.winner is not None

    # ── Win-condition checks ─────────────────

    def check_win_conditions(self) -> Optional[str]:
        if self.winner:
            return self.winner

        alive = self.alive_players
        wolves = [p for p in alive if p.role.team == "werewolf"]
        village = [p for p in alive if p.role.team in ("village", "solo")]
        sk = [p for p in alive if p.role.name == "Serial Killer"]

        if len(alive) == 1 and sk:
            self.winner = sk[0].name
            return self.winner

        if wolves and len(wolves) >= len(village):
            self.winner = "werewolf"
            return self.winner

        if not wolves:
            self.winner = "village"
            return self.winner

        return None

    # ── Serialization for HA ────────────────

    def to_dict(self) -> dict:
        return {
            "players": [self._player_to_dict(p) for p in self.players],
            "round_number": self.round_number,
            "phase": self.phase,
            "winner": self.winner,
            "event_log": self.event_log,
        }

    def _player_to_dict(self, player: Player) -> dict:
        return {
            "name": player.name,
            "role": player.role.name,
            "alive": player.alive,
            "silenced": player.silenced,
            "has_lover": player.lover is not None,
        }

    @classmethod
    def from_dict(cls, data: dict, role_registry: dict) -> "GameState":
        state = cls()
        state.round_number = data.get("round_number", 0)
        state.phase = data.get("phase", "setup")
        state.winner = data.get("winner")
        state.event_log = data.get("event_log", [])

        state.players = []
        for pd in data.get("players", []):
            role_name = pd.get("role", "Villager")
            role_class = role_registry.get(role_name, role_registry["Villager"])
            player = Player(
                name=pd["name"],
                role=role_class(None),
                alive=pd.get("alive", True),
                silenced=pd.get("silenced", False),
            )
            state.players.append(player)

        return state