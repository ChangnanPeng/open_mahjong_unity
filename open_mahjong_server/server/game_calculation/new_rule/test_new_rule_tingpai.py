from __future__ import annotations

from pathlib import Path
import sys

SERVER_ROOT = Path(__file__).resolve().parents[3]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from server.game_calculation.new_rule import tingpai_check
from server.game_calculation.new_rule.tiles import ORPHANS


def test_standard_hand_single_wait() -> None:
    waits = tingpai_check([11, 12, 13, 21, 22, 23, 31, 32, 33, 45, 45, 45, 41])
    assert 41 in waits, waits


def test_seven_pairs_wait() -> None:
    waits = tingpai_check([11, 11, 22, 22, 23, 23, 34, 34, 35, 35, 41, 41, 45])
    assert 45 in waits, waits


def test_thirteen_orphans_waits_any_orphan_pair() -> None:
    waits = tingpai_check([11, 19, 21, 29, 31, 39, 41, 42, 43, 44, 45, 46, 47])
    assert waits == set(ORPHANS), waits


def test_four_copy_limit_is_respected() -> None:
    waits = tingpai_check([11, 11, 11, 11, 21, 22, 23, 31, 32, 33, 45, 45, 45])
    assert 11 not in waits, waits


def test_zero_point_standard_wait_is_allowed() -> None:
    waits = tingpai_check([13, 14, 15, 24, 25, 26, 36, 37, 38, 41], ["k12"])
    assert 41 in waits, waits


def run() -> None:
    tests = [
        test_standard_hand_single_wait,
        test_seven_pairs_wait,
        test_thirteen_orphans_waits_any_orphan_pair,
        test_four_copy_limit_is_respected,
        test_zero_point_standard_wait_is_allowed,
    ]
    for test in tests:
        test()
    print(f"new_rule tingpai smoke tests ok: {len(tests)} tests")


if __name__ == "__main__":
    run()
