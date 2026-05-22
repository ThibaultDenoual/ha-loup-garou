"""Little Girl role — passive, may spy on wolves (UI-only mechanic)."""
from ..base import BaseRole, EliminateDecision, RoleContext


class LittleGirl(BaseRole):
    id = "little_girl"
    team = "village"
    night_priority = 99
    has_night_action = False
    # Spying mechanic is handled entirely in the UI — no engine interaction needed.
