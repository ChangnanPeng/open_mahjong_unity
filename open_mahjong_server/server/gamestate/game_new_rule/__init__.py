"""New rule game-state skeleton.

The first version is intentionally small and script-testable. It does not yet
wire into room creation, WebSocket broadcasting, or database persistence.
"""

from .NewRuleGameState import NewRuleGameState, NewRulePlayer

__all__ = ["NewRuleGameState", "NewRulePlayer"]
