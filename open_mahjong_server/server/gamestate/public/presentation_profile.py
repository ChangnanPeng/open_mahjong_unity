from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .win_continuation import WinContinuationPolicy


@dataclass(frozen=True)
class PresentationProfile:
    """Server-declared presentation capabilities consumed by generic clients."""

    winner_exit_animation: bool
    defer_win_details: bool
    result_sequence: str
    win_tile_to_buhua: bool = False
    score_display_multiplier: int = 1
    draw_slot_win_tile: bool = False
    complete_discard_before_ron: bool = False
    concealed_win_tile: bool = False
    preserve_win_animation_on_resume: bool = False

    @classmethod
    def for_win_continuation(
        cls,
        flow: WinContinuationPolicy,
        *,
        score_display_multiplier: int = 1,
        draw_slot_win_tile: bool = False,
        complete_discard_before_ron: bool = False,
        concealed_win_tile: bool = False,
        preserve_win_animation_on_resume: bool = False,
        win_tile_to_buhua: bool = False,
        winner_result_sequence: bool | None = None,
        defer_win_details: bool | None = None,
    ) -> "PresentationProfile":
        continuous = flow.winners_exit_hand
        if winner_result_sequence is None:
            winner_result_sequence = continuous
        if defer_win_details is None:
            defer_win_details = continuous
        return cls(
            winner_exit_animation=continuous,
            defer_win_details=defer_win_details,
            result_sequence="winner_sequence" if winner_result_sequence else "single",
            win_tile_to_buhua=win_tile_to_buhua,
            score_display_multiplier=score_display_multiplier,
            draw_slot_win_tile=draw_slot_win_tile,
            complete_discard_before_ron=complete_discard_before_ron,
            concealed_win_tile=concealed_win_tile,
            preserve_win_animation_on_resume=preserve_win_animation_on_resume,
        )

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)
