from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .presentation_profile import PresentationProfile
from .win_continuation import WinContinuationPolicy


@dataclass(frozen=True)
class RuleComposition:
    """Independently replaceable Mahjong rule modules.

    A future blood-battle Guobiao state can keep Guobiao action/scoring modules
    and replace only ``hand_flow`` plus the matching presentation profile.
    """

    actions: Any
    settlement: Any
    hand_flow: WinContinuationPolicy
    presentation: PresentationProfile
