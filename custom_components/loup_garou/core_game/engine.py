"""
engine.py — The Werewolf game engine.

Uses the `transitions` library to model the game as a Hierarchical State Machine:

  SETUP
    └─► NIGHT
          ├─ night_roles     (Cupid, Seer, Doctor, etc. act in priority order)
          ├─ werewolf_kill   (wolves choose a victim)
          └─► RESOLVE_NIGHT  (apply kills, protections, conversions)
                └─► DAY
                      ├─ discussion
                      ├─ vote
                      └─► RESOLVE_DAY
                            └─► (NIGHT | END)

Each state has on_enter / on_exit callbacks.
Transitions carry guards (conditions) so invalid triggers are silently ignored.
"""

from __future__ import annotations

import random
import time
from abc import ABC, abstractmethod
from typing import Optional

from transitions import Machine, MachineError

from .game_state import GameState, Player
from .io_interface import IOInterface, ConsoleIO
from .roles import (
    Role, NightAction, ROLE_REGISTRY,
    Werewolf, AlphaWolf, Minion, WerewolfPackCoordinator,
)


# ─────────────────────────────────────────────
#  States & Transitions
# ─────────────────────────────────────────────

STATES = [
    "setup",
    "night_start",
    "night_actions",
    "resolve_night",
    "day_start",
    "discussion",
    "vote",
    "resolve_day",
    "game_over",
]

TRANSITIONS = [
    {"trigger": "begin_game", "source": "setup", "dest": "night_start"},
    {"trigger": "start_night", "source": "night_start", "dest": "night_actions"},
    {"trigger": "resolve", "source": "night_actions", "dest": "resolve_night"},
    {"trigger": "dawn", "source": "resolve_night", "dest": "day_start"},
    {"trigger": "open_day", "source": "day_start", "dest": "discussion"},
    {"trigger": "call_vote", "source": "discussion", "dest": "vote"},
    {"trigger": "tally", "source": "vote", "dest": "resolve_day"},
    {"trigger": "next_round", "source": "resolve_day", "dest": "night_start",
     "conditions": "game_continues"},
    {"trigger": "end_game", "source": "resolve_day", "dest": "game_over",
     "conditions": "game_is_over"},
    {"trigger": "end_game", "source": "resolve_night", "dest": "game_over",
     "conditions": "game_is_over"},
    {"trigger": "end_game", "source": "discussion", "dest": "game_over",
     "conditions": "game_is_over"},
]


# ─────────────────────────────────────────────
#  GameEngine
# ─────────────────────────────────────────────

class GameEngine:
    """
    Synchronous game engine orchestrating all game phases via FSM.

    Public API:
        engine = GameEngine(player_names, role_names=["Werewolf", "Seer", "Doctor", "Villager"])
        engine.run()
    """

    def __init__(
        self,
        player_names: list[str],
        role_names: list[str],
        io: Optional[IOInterface] = None,
        seed: Optional[int] = None,
        events: Optional["GameEvents"] = None,
    ):
        if seed is not None:
            random.seed(seed)

        self.io: IOInterface = io or ConsoleIO()
        self._events = events
        self._pending_solo_death: Optional[tuple[Player, str]] = None

        if len(role_names) != len(player_names):
            raise ValueError(
                f"Role count ({len(role_names)}) must match player count ({len(player_names)})"
            )

        shuffled_roles = role_names[:]
        random.shuffle(shuffled_roles)
        players = [
            Player(name=name, role=ROLE_REGISTRY[rname](None))
            for name, rname in zip(player_names, shuffled_roles)
        ]
        for p in players:
            p.role.player = p

        self.state = GameState(players, self.io)

        self.machine = Machine(
            model=self,
            states=STATES,
            transitions=TRANSITIONS,
            initial="setup",
            ignore_invalid_triggers=True,
            auto_transitions=False,
            model_attribute="_fsm_state",
        )

    # ─────────────────────────────────────────
    #  Guards
    # ─────────────────────────────────────────

    def game_continues(self) -> bool:
        return not self.state.is_game_over()

    def game_is_over(self) -> bool:
        return self.state.is_game_over()

    # ─────────────────────────────────────────
    #  Main loop
    # ─────────────────────────────────────────

    def run(self):
        self._setup_phase()
        self.begin_game()

        while self._fsm_state not in ("game_over",):
            s = self._fsm_state

            if s == "night_start":
                self._enter_night_start()
                self.start_night()

            elif s == "night_actions":
                self._run_night_actions()
                self.resolve()

            elif s == "resolve_night":
                self._resolve_night()
                if not self.game_is_over():
                    self.dawn()
                else:
                    self.end_game()

            elif s == "day_start":
                self._enter_day_start()
                self.open_day()

            elif s == "discussion":
                self._run_discussion()
                if not self.game_is_over():
                    self.call_vote()
                else:
                    self.end_game()

            elif s == "vote":
                self._run_vote()
                self.tally()

            elif s == "resolve_day":
                self._resolve_day()
                self.state.check_win_conditions()
                if self.game_is_over():
                    self.end_game()
                else:
                    self.next_round()

        self._game_over_phase()

    # ─────────────────────────────────────────
    #  Phase handlers
    # ─────────────────────────────────────────

    def _setup_phase(self):
        self.io.separator("🐺 WEREWOLF 🐺")
        self.io.announce("Welcome to Werewolf!\n")
        self._reveal_roles_privately()

    def _reveal_roles_privately(self):
        self.io.announce("Each player will now privately learn their role.\n")
        gs = self.state

        wolf_players = [p for p in gs.players if p.role.team == "werewolf"]
        wolf_names = ", ".join(p.name for p in wolf_players
                               if not isinstance(p.role, Minion))

        for p in gs.players:
            msg_lines = [
                f"You are the {p.role.name}.",
                f"Description: {p.role.description}",
                f"Team: {p.role.team.upper()}",
            ]
            if p.role.team == "werewolf" or isinstance(p.role, Minion):
                msg_lines.append(f"Pack members: {wolf_names or '(none)'}")
            self.io.private(p, "\n     ".join(msg_lines))

    def _enter_night_start(self):
        gs = self.state
        gs.round_number += 1
        gs.phase = "night"
        gs.reset_night_state()
        self.io.separator(f"NIGHT {gs.round_number}")
        self.io.announce("The village falls into an uneasy sleep...")

        for p in gs.alive_players:
            msg = p.role.on_day_start(gs)
            if msg:
                self.io.announce(f"  ℹ️  {msg}")

        if self._events:
            self._events.on_phase_changed("day_start", "night_start")

    def _run_night_actions(self):
        gs = self.state

        actors: list[Player] = sorted(
            [p for p in gs.alive_players if p.role.has_night_action],
            key=lambda p: p.role.night_priority
        )

        if gs.werewolves:
            action = WerewolfPackCoordinator.coordinate(gs)
            if action:
                gs.tonight_actions.append(action)
                if self._events:
                    self._events.on_role_acting(action.actor, "werewolf_kill")

        for p in actors:
            if p.role.team == "werewolf" and isinstance(p.role, Werewolf):
                continue
            if isinstance(p.role, AlphaWolf):
                action = p.role.act(gs)
                if action:
                    gs.tonight_actions.append(action)
                    if self._events:
                        self._events.on_role_acting(p, action.action_type)
                continue

            action = p.role.act(gs)
            if action:
                gs.tonight_actions.append(action)
                if self._events:
                    self._events.on_role_acting(p, action.action_type)

    def _resolve_night(self):
        gs = self.state
        gs.phase = "resolve_night"

        kills: dict[Player, list[str]] = {}
        protections: set[Player] = set()
        conversions: list[NightAction] = []
        investigations: list[NightAction] = []

        for action in gs.tonight_actions:
            if action.action_type == "kill":
                kills.setdefault(action.target, []).append(action.actor.name)
            elif action.action_type == "protect":
                protections.add(action.target)
            elif action.action_type == "convert":
                conversions.append(action)
            elif action.action_type == "investigate":
                investigations.append(action)

        for conv in conversions:
            self._apply_conversion(conv)

        for inv in investigations:
            team = inv.target.role.team
            readable = "a Werewolf" if team == "werewolf" else "not a Werewolf"
            self.io.private(
                inv.actor,
                f"Your vision reveals: {inv.target.name} is {readable}."
            )

        for target, killer_names in kills.items():
            if target in protections:
                gs.log(f"{target.name} was protected from harm.")
                continue
            gs.schedule_death(target, cause=" & ".join(killer_names))

        for action in gs.tonight_actions:
            if action.action_type == "protect" and action.metadata.get("bodyguard"):
                bg = action.actor
                if action.target in kills and action.target not in protections:
                    gs.pending_deaths = [(p, c) for p, c in gs.pending_deaths
                                        if p is not action.target]
                    gs.schedule_death(bg, cause="protecting " + action.target.name)

        deaths_this_night = []
        for player, cause in list(gs.pending_deaths):
            self._kill_player(player, cause)
            deaths_this_night.append((player, cause))

        self.io.announce("\n☽ The night draws to a close...")
        time.sleep(0.5)

        self.io.separator(f"DAY {gs.round_number}")
        self.io.announce("Dawn breaks over the village.")
        self._announce_deaths(deaths_this_night)

        gs.check_win_conditions()

        if self._events:
            self._events.on_night_resolved(deaths_this_night, protections)

    def _apply_conversion(self, action: NightAction):
        gs = self.state
        target = action.target
        if not target.alive:
            return
        old_role_name = target.role.name
        new_role = Werewolf(target)
        target.role = new_role
        gs.log(f"🔄 {target.name} was converted from {old_role_name} to Werewolf!")
        self.io.private(
            target,
            f"You have been bitten by the Alpha Wolf! You are now a WEREWOLF.\n"
            f"Work with the pack to devour the village."
        )

    def _enter_day_start(self):
        gs = self.state
        gs.phase = "day"

    def _run_discussion(self):
        gs = self.state
        self.io.announce(
            "  Discuss among yourselves. Who do you suspect?\n"
            "  (In a real game, players would now talk openly for several minutes.)\n"
        )
        self.io.separator("Alive Players")
        for p in gs.alive_players:
            print(f"    • {p.name}")
        self.io.pause("\n  (Press Enter when discussion is over...)")
        gs.check_win_conditions()

    def _run_vote(self):
        gs = self.state
        gs.phase = "vote"
        voters = gs.alive_players
        candidates = gs.alive_players[:]
        self._last_vote_tally = self.io.get_votes(voters, candidates)

    def _resolve_day(self):
        gs = self.state
        gs.phase = "resolve_day"
        tally = self._last_vote_tally

        if not tally or max(tally.values(), default=0) == 0:
            self.io.announce("  No votes cast. The village fails to reach a decision.")
            return

        max_votes = max(tally.values())
        top = [p for p, v in tally.items() if v == max_votes]

        if len(top) > 1:
            self.io.announce(
                f"  It's a tie between: {', '.join(p.name for p in top)}.\n"
                "  No execution today — the village is divided."
            )
            return

        condemned = top[0]
        gs.current_elimination_cause = "vote"
        self.io.announce(
            f"\n⚖️ The village has spoken. {condemned.name} is condemned with {max_votes} vote(s)."
        )
        self._kill_player(condemned, cause="village vote")

        for player, cause in list(gs.pending_deaths):
            if player is not condemned:
                self._kill_player(player, cause)

        gs.check_win_conditions()

    def _game_over_phase(self):
        gs = self.state
        gs.phase = "end"
        winner_name = gs.winner or "nobody"
        self.io.separator("🏆 GAME OVER 🏆")
        if winner_name == "village":
            self.io.announce("🎉 The VILLAGE wins! The werewolves have been vanquished!")
        elif winner_name == "werewolf":
            self.io.announce("🐺 The WEREWOLVES win! They have devoured the village!")
        else:
            self.io.announce(f"🎭 {winner_name.upper()} wins!")
        self.io.announce("\nFinal roles:")
        for p in gs.players:
            status = "alive" if p.alive else "💀"
            self.io.announce(f"    {status}  {p.name:15s} → {p.role.name}")
        self.io.separator()

        if self._events:
            self._events.on_game_over(gs.winner)

    # ─────────────────────────────────────────
    #  Death resolution
    # ─────────────────────────────────────────

    def _kill_player(self, player: Player, cause: str):
        gs = self.state
        if not player.alive:
            return

        player.alive = False
        gs.log(f"☠ {player.name} ({player.role.name}) died from {cause}.")

        death_msg = player.role.on_death(gs)
        if death_msg:
            self.io.announce(f"  {death_msg}")

        if player.lover and player.lover.alive:
            lover = player.lover
            self.io.announce(
                f"  💔 {lover.name} cannot bear the loss of their beloved {player.name}...\n"
                f"     They die of a broken heart."
            )
            self._kill_player(lover, cause="broken heart")

        newly_queued = [(p, c) for p, c in gs.pending_deaths if p.alive and p is not player]
        for p, c in newly_queued:
            self._kill_player(p, c)

        if self._events:
            self._events.on_player_eliminated(player, cause)

    def _announce_deaths(self, deaths: list[tuple[Player, str]]):
        if not deaths:
            self.io.announce("  ☀️ A miracle! No one died last night. The village sighs with relief.")
            return
        for player, cause in deaths:
            self.io.announce(f"  💀 {player.name} was found dead — killed by {cause}.")
            self.io.announce(f"     They were the {player.role.name}.")

    # ─────────────────────────────────────────
    #  Helpers
    # ─────────────────────────────────────────


# ─────────────────────────────────────────────
#  GameEvents — for external effects (HA hooks)
# ─────────────────────────────────────────────

class GameEvents(ABC):
    """Abstract interface for game events that external systems can hook into."""

    @abstractmethod
    def on_phase_changed(self, old_phase: str, new_phase: str) -> None:
        """Called when the game phase changes."""

    @abstractmethod
    def on_night_resolved(
        self,
        deaths: list[tuple[Player, str]],
        protections: set[Player]
    ) -> None:
        """Called after night actions are resolved."""

    @abstractmethod
    def on_player_eliminated(self, player: Player, cause: str) -> None:
        """Called when a player is eliminated."""

    @abstractmethod
    def on_game_over(self, winner: Optional[str]) -> None:
        """Called when the game ends."""

    @abstractmethod
    def on_role_acting(self, player: "Player", action_type: str) -> None:
        """Called when a role is about to act during night phase."""