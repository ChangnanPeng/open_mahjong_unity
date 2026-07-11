from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping, Optional


class HandEndMode(str, Enum):
    """When a hand stops after confirmed wins.

    This is deliberately independent from scoring and ron selection. A rule can
    therefore combine (for example) second-winner continuation with any scoring
    system or with either head-bump or multi-ron action resolution.
    """

    FIRST_WIN = "first_win"
    SECOND_WIN = "second_win"
    THIRD_WIN = "third_win"

    @property
    def winner_target(self) -> int:
        return {
            HandEndMode.FIRST_WIN: 1,
            HandEndMode.SECOND_WIN: 2,
            HandEndMode.THIRD_WIN: 3,
        }[self]


@dataclass(frozen=True)
class WinContinuationPolicy:
    """Reusable winner-exit flow policy for four-player Mahjong hands."""

    mode: HandEndMode = HandEndMode.THIRD_WIN

    @classmethod
    def from_room_data(
        cls,
        room_data: Mapping[str, Any],
        *,
        default: HandEndMode = HandEndMode.THIRD_WIN,
    ) -> "WinContinuationPolicy":
        raw_mode = room_data.get("hand_end_mode")
        if raw_mode is not None:
            try:
                return cls(HandEndMode(str(raw_mode)))
            except ValueError as exc:
                allowed = ", ".join(mode.value for mode in HandEndMode)
                raise ValueError(f"hand_end_mode must be one of: {allowed}") from exc

        return cls(default)

    @property
    def winner_target(self) -> int:
        return self.mode.winner_target

    @property
    def winners_exit_hand(self) -> bool:
        return self.winner_target > 1

    def should_end(self, winner_count: int, wall_tiles: int, dead_wall_count: int = 0) -> bool:
        return winner_count >= self.winner_target or wall_tiles <= dead_wall_count

    @staticmethod
    def next_active_index(players: Iterable[Any], from_index: int) -> Optional[int]:
        indexed_players = {int(player.player_index): player for player in players}
        player_count = len(indexed_players)
        if player_count == 0:
            return None
        index = from_index
        for _ in range(player_count):
            index = (index + 1) % player_count
            player = indexed_players.get(index)
            if player is not None and not bool(getattr(player, "is_hu", False)):
                return index
        return None

    def to_payload(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "winner_target": self.winner_target,
            "winners_exit_hand": self.winners_exit_hand,
        }
