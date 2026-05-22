"""Scapegoat role — dies on vote tie instead of no one."""
from ..base import BaseRole, EliminateDecision, RoleContext


class Scapegoat(BaseRole):
    id = "scapegoat"
    team = "village"
    night_priority = 99
    has_night_action = False
    # Scapegoat elimination is triggered directly by resolve_vote() in the engine.
