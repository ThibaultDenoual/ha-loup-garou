"""
roles.py — Werewolf game role definitions.

Design rules:
• Roles never import from engine.py (no circular deps).
• All user-facing strings come from i18n.t() — no hardcoded literals.
• Night-action *resolution* logic lives in action_resolver.py, not here.
  Roles only *produce* NightAction objects; the resolver interprets them.
• The wolf pack coordination is encapsulated in WerewolfPackCoordinator.
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from game_state import GameState, Player


# ─────────────────────────────────────────────
#  NightAction — shared data structure
# ─────────────────────────────────────────────

@dataclass
class NightAction:
    actor: "Player"
    action_type: str
    target: Optional["Player"] = None
    metadata: dict = field(default_factory=dict)

    def __repr__(self) -> str:
        tgt = self.target.name if self.target else "—"
        return f"<NightAction {self.action_type} by {self.actor.name} -> {tgt}>"


# ─────────────────────────────────────────────
#  Base Role
# ─────────────────────────────────────────────

class Role(ABC):
    role_key: str = "Unknown"
    team: str = "village"
    night_priority: int = 50
    has_night_action: bool = False

    def __init__(self, player: "Player"):
        self.player = player

    @property
    def name(self) -> str:
        return self.role_key

    @property
    def description(self) -> str:
        return f"Role: {self.role_key}"

    def act(self, state: "GameState") -> Optional[NightAction]:
        return None

    def on_death(self, state: "GameState") -> Optional[str]:
        return None

    def on_day_start(self, state: "GameState") -> Optional[str]:
        return None

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} [{self.team}]>"


# ─────────────────────────────────────────────
#  Village roles
# ─────────────────────────────────────────────

class Villager(Role):
    role_key = "Villager"
    team = "village"


class Seer(Role):
    role_key = "Seer"
    team = "village"
    night_priority = 10
    has_night_action = True

    def act(self, state: "GameState") -> Optional[NightAction]:
        candidates = [p for p in state.alive_players if p is not self.player]
        if not candidates:
            return None
        target = state.io.choose_target(
            self.player, candidates,
            prompt=f"{self.player.name}, choose a player to investigate:",
        )
        return NightAction(actor=self.player, action_type="investigate", target=target)


class Doctor(Role):
    role_key = "Doctor"
    team = "village"
    night_priority = 20
    has_night_action = True

    def __init__(self, player: "Player"):
        super().__init__(player)
        self.self_heals_left: int = 1

    def act(self, state: "GameState") -> Optional[NightAction]:
        candidates = list(state.alive_players)
        if self.self_heals_left == 0:
            candidates = [p for p in candidates if p is not self.player]
        if not candidates:
            return None
        target = state.io.choose_target(
            self.player, candidates,
            prompt=f"{self.player.name}, choose a player to protect:",
        )
        if target is self.player:
            self.self_heals_left -= 1
        return NightAction(actor=self.player, action_type="protect", target=target)


class Bodyguard(Role):
    role_key = "Bodyguard"
    team = "village"
    night_priority = 15
    has_night_action = True

    def act(self, state: "GameState") -> Optional[NightAction]:
        candidates = [p for p in state.alive_players if p is not self.player]
        if not candidates:
            return None
        target = state.io.choose_target(
            self.player, candidates,
            prompt=f"{self.player.name}, choose a player to guard:",
        )
        return NightAction(
            actor=self.player, action_type="protect", target=target,
            metadata={"bodyguard": True},
        )


class Hunter(Role):
    role_key = "Hunter"
    team = "village"

    def on_death(self, state: "GameState") -> Optional[str]:
        candidates = list(state.alive_players)
        if not candidates:
            return None
        state.io.announce(f"{self.player.name} takes aim before dying...")
        target = state.io.choose_target(
            self.player, candidates,
            prompt=f"{self.player.name}, choose your final target:",
        )
        state.schedule_death(target, cause="hunter's arrow")
        return f"{self.player.name} fires their final shot at {target.name}!"


class Witch(Role):
    role_key = "Witch"
    team = "village"
    night_priority = 25
    has_night_action = True

    def __init__(self, player: "Player"):
        super().__init__(player)
        self.heal_potion: bool = True
        self.poison_potion: bool = True

    def act(self, state: "GameState") -> Optional[NightAction]:
        attacked = list(state.tonight_attacked)

        if self.heal_potion and attacked:
            victim = attacked[0]
            if state.io.yes_no(self.player, f"Witch! {victim.name} was attacked. Use your heal potion?"):
                self.heal_potion = False
                return NightAction(
                    actor=self.player, action_type="protect",
                    target=victim, metadata={"witch_heal": True},
                )

        if self.poison_potion:
            if state.io.yes_no(self.player, "Witch! Use your poison potion?"):
                candidates = [p for p in state.alive_players if p is not self.player]
                target = state.io.choose_target(
                    self.player, candidates,
                    prompt="Choose a player to poison:",
                )
                self.poison_potion = False
                return NightAction(
                    actor=self.player, action_type="kill",
                    target=target, metadata={"witch_poison": True},
                )

        return None


class Cupid(Role):
    role_key = "Cupid"
    team = "village"
    night_priority = 5
    has_night_action = True

    def __init__(self, player: "Player"):
        super().__init__(player)
        self.used: bool = False

    def act(self, state: "GameState") -> Optional[NightAction]:
        if self.used or state.round_number > 1:
            return None
        state.io.announce(f"{self.player.name} surveys the village for love...")
        candidates = list(state.alive_players)
        lover1 = state.io.choose_target(
            self.player, candidates,
            prompt="Choose the first lover:",
        )
        lover2 = state.io.choose_target(
            self.player, [p for p in candidates if p is not lover1],
            prompt="Choose the second lover:",
        )
        state.link_lovers(lover1, lover2)
        self.used = True
        return NightAction(
            actor=self.player, action_type="none",
            metadata={"lovers": (lover1, lover2)},
        )


# ─────────────────────────────────────────────
#  Werewolf roles
# ─────────────────────────────────────────────

class Werewolf(Role):
    role_key = "Werewolf"
    team = "werewolf"
    night_priority = 30
    has_night_action = True

    def act(self, state: "GameState") -> Optional[NightAction]:
        return None


class AlphaWolf(Role):
    role_key = "Alpha Wolf"
    team = "werewolf"
    night_priority = 28
    has_night_action = True

    def __init__(self, player: "Player"):
        super().__init__(player)
        self.convert_used: bool = False

    def act(self, state: "GameState") -> Optional[NightAction]:
        if self.convert_used:
            return None
        if not state.io.yes_no(self.player, "Alpha Wolf! Use your power to convert a villager?"):
            return None
        candidates = [
            p for p in state.alive_players
            if p.role.team == "village" and p is not self.player
        ]
        if not candidates:
            return None
        target = state.io.choose_target(
            self.player, candidates,
            prompt="Choose a villager to convert:",
        )
        self.convert_used = True
        return NightAction(actor=self.player, action_type="convert", target=target)


class Minion(Role):
    role_key = "Minion"
    team = "werewolf"


# ─────────────────────────────────────────────
#  Solo roles
# ─────────────────────────────────────────────

class SerialKiller(Role):
    role_key = "Serial Killer"
    team = "solo"
    night_priority = 35
    has_night_action = True

    def act(self, state: "GameState") -> Optional[NightAction]:
        candidates = [p for p in state.alive_players if p is not self.player]
        if not candidates:
            return None
        target = state.io.choose_target(
            self.player, candidates,
            prompt=f"Serial Killer {self.player.name}, choose your victim:",
        )
        return NightAction(
            actor=self.player, action_type="kill",
            target=target, metadata={"serial_killer": True},
        )


class Jester(Role):
    role_key = "Jester"
    team = "solo"

    def on_death(self, state: "GameState") -> Optional[str]:
        if state.current_elimination_cause == "vote":
            state.declare_solo_winner(self.player)
            return f"🎭 {self.player.name} wins! They were voted out and laughed their way to victory!"
        return None


# ─────────────────────────────────────────────
#  Wolf pack coordination
# ─────────────────────────────────────────────

class WerewolfPackCoordinator:
    @staticmethod
    def coordinate(state: "GameState") -> Optional[NightAction]:
        wolves = state.werewolves
        if not wolves:
            return None

        candidates = [p for p in state.alive_players if p.role.team != "werewolf"]
        if not candidates:
            return None

        state.io.separator("🐺 WEREWOLVES CONVENE")
        state.io.announce(f"Werewolves awake: {', '.join(w.name for w in wolves)}")

        if any(a.action_type == "convert" for a in state.tonight_actions):
            state.io.announce("The Alpha Wolf has chosen to convert — no kill tonight.")
            return None

        target = state.io.choose_target(
            wolves[0], candidates,
            prompt="Werewolves, choose your victim:",
        )
        state.tonight_attacked.append(target)
        state.io.announce(f"The pack has chosen... {target.name} will be hunted.")
        return NightAction(actor=wolves[0], action_type="kill", target=target)


# ─────────────────────────────────────────────
#  Registries
# ─────────────────────────────────────────────

ROLE_REGISTRY: dict[str, type[Role]] = {
    "Villager": Villager,
    "Seer": Seer,
    "Doctor": Doctor,
    "Bodyguard": Bodyguard,
    "Hunter": Hunter,
    "Witch": Witch,
    "Cupid": Cupid,
    "Werewolf": Werewolf,
    "Alpha Wolf": AlphaWolf,
    "Minion": Minion,
    "Serial Killer": SerialKiller,
    "Jester": Jester,
}

PRESETS: dict[str, list[str]] = {
    "small": ["Werewolf", "Seer", "Doctor",
              "Villager", "Villager", "Villager"],
    "medium": ["Werewolf", "Werewolf", "Alpha Wolf",
               "Seer", "Doctor", "Witch", "Hunter",
               "Villager", "Villager"],
    "large": ["Werewolf", "Werewolf", "Alpha Wolf", "Minion",
              "Seer", "Doctor", "Bodyguard", "Witch", "Hunter", "Cupid",
              "Villager", "Villager", "Villager"],
    "chaos": ["Werewolf", "Werewolf", "Serial Killer", "Jester",
              "Seer", "Doctor", "Witch",
              "Villager", "Villager", "Villager"],
}