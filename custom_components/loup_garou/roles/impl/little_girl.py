"""Little Girl role — passive; she spies on the wolves at the table, not in the app."""
from ..base import BaseRole, EliminateDecision, RoleContext


class LittleGirl(BaseRole):
    id = "little_girl"
    team = "village"
    night_priority = 99
    has_night_action = False
    # She peeks during the wolves' turn in real life. The app only tells her so
    # in her role description; neither the engine nor the browser plays it.
