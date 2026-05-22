"""Sheriff role — elected; vote counts double."""
from ..base import BaseRole, EliminateDecision, RoleContext


class Sheriff(BaseRole):
    id = "sheriff"
    team = "village"
    night_priority = 99
    has_night_action = False
    # The Sheriff flag ("sheriff") is set via elect_sheriff(player_id) or
    # a dedicated vote in the server. Double-vote weight is applied in engine.resolve_vote().
