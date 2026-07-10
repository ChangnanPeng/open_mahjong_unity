"""New rule game-state skeleton.

The first version is intentionally small and script-testable. It does not yet
wire into room creation, WebSocket broadcasting, or database persistence.
"""

from .NewRuleGameState import NewRuleGameState, NewRulePlayer
from .action_check import NewRuleActionPolicy
from .settlement import NewRuleSettlementPolicy

__all__ = ["NewRuleGameState", "NewRulePlayer", "NewRuleActionPolicy", "NewRuleSettlementPolicy"]
