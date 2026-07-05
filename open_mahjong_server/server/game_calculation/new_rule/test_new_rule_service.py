from __future__ import annotations

from pathlib import Path
import sys

SERVER_ROOT = Path(__file__).resolve().parents[3]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from server.game_calculation.game_calculation_service import GameCalculationService


def test_service_basic_score() -> None:
    service = GameCalculationService()
    points, fan_names = service.NewRule_hepai_check(
        [45, 45, 45, 46, 46, 46, 47, 47, 47, 11, 12, 13, 21, 21],
        [],
        ["自摸"],
        21,
    )
    assert points == 20, (points, fan_names)
    assert "大三元" in fan_names, fan_names


def test_service_detail_fan_ids_and_context() -> None:
    service = GameCalculationService()
    detail = service.NewRule_hepai_detail(
        [11, 12, 13, 21, 22, 23, 31, 32, 33, 45, 45, 45, 41, 41],
        [],
        ["自摸"],
        41,
        {"haitei": True, "rinshan": True},
    )
    assert detail["points"] >= 1, detail
    assert "haitei" in detail["fan_ids"], detail
    assert "rinshan" in detail["fan_ids"], detail


def test_service_tingpai_check() -> None:
    service = GameCalculationService()
    waits = service.NewRule_tingpai_check(
        [11, 12, 13, 21, 22, 23, 31, 32, 33, 45, 45, 45, 41],
        [],
    )
    assert 41 in waits, waits


def test_service_detail_allows_zero_point_standard_win() -> None:
    service = GameCalculationService()
    detail = service.NewRule_hepai_detail(
        [13, 14, 15, 24, 25, 26, 36, 37, 38, 41, 41],
        ["k12"],
        ["自摸"],
        41,
    )
    assert detail["is_win"] is True, detail
    assert detail["points"] == 0, detail
    assert detail["fan_ids"] == [], detail


def test_service_detail_applies_repeatable_row_rule() -> None:
    service = GameCalculationService()
    detail = service.NewRule_hepai_detail(
        [11, 11, 11, 21, 21, 21, 12, 12, 12, 22, 22, 22, 31, 31],
        [],
        ["自摸"],
        31,
    )
    assert "small_three_suit_triplets" in detail["fan_ids"], detail
    assert "two_suit_triplets" not in detail["fan_ids"], detail


def run() -> None:
    tests = [
        test_service_basic_score,
        test_service_detail_fan_ids_and_context,
        test_service_tingpai_check,
        test_service_detail_allows_zero_point_standard_win,
        test_service_detail_applies_repeatable_row_rule,
    ]
    for test in tests:
        test()
    print(f"new_rule service smoke tests ok: {len(tests)} tests")


if __name__ == "__main__":
    run()
