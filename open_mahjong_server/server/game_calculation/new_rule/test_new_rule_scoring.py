from __future__ import annotations

from pathlib import Path
import sys

SERVER_ROOT = Path(__file__).resolve().parents[3]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from server.game_calculation.new_rule.scoring import HandContext, score_hand


def assert_has(result, fan_id: str, points: int | None = None) -> None:
    assert fan_id in result.fan_ids, (fan_id, result)
    if points is not None:
        assert result.points == points, result


def assert_not_has(result, fan_id: str) -> None:
    assert fan_id not in result.fan_ids, (fan_id, result)


def test_pinfu_all_sequences() -> None:
    result = score_hand(HandContext([11, 12, 13, 14, 15, 16, 22, 23, 24, 36, 37, 38, 41, 41]))
    assert_has(result, "pinfu")


def test_seven_pairs_repeated_pair() -> None:
    result = score_hand(HandContext([11, 11, 11, 11, 22, 22, 23, 23, 34, 34, 35, 35, 41, 41]))
    assert_has(result, "seven_pairs")


def test_thirteen_orphans_not_mixed_terminals() -> None:
    result = score_hand(HandContext([11, 19, 21, 29, 31, 39, 41, 42, 43, 44, 45, 46, 47, 47]))
    assert_has(result, "thirteen_orphans", 20)
    assert_not_has(result, "mixed_terminals")


def test_true_nine_gates_requires_pre_win_shape() -> None:
    pre = [11, 11, 11, 12, 13, 14, 15, 16, 17, 18, 19, 19, 19]
    result = score_hand(HandContext(pre + [15], winning_tile=15, pre_win_tiles=pre))
    assert_has(result, "nine_gates", 20)

    loose = score_hand(HandContext(pre + [15], winning_tile=15))
    assert_not_has(loose, "nine_gates")
    assert_has(loose, "full_flush")


def test_dragon_row_upgrade() -> None:
    result = score_hand(HandContext([45, 45, 45, 46, 46, 46, 11, 12, 13, 21, 22, 23, 31, 31]))
    assert_has(result, "two_dragon_triplets")
    assert_not_has(result, "red_dragon")
    assert_not_has(result, "green_dragon")


def test_single_dragon_triplets() -> None:
    red = score_hand(HandContext([45, 45, 45, 11, 12, 13, 21, 22, 23, 31, 32, 33, 41, 41]))
    assert_has(red, "red_dragon")

    white = score_hand(HandContext([46, 46, 46, 11, 12, 13, 21, 22, 23, 31, 32, 33, 41, 41]))
    assert_has(white, "white_dragon")
    assert_not_has(white, "green_dragon")

    green = score_hand(HandContext([47, 47, 47, 11, 12, 13, 21, 22, 23, 31, 32, 33, 41, 41]))
    assert_has(green, "green_dragon")
    assert_not_has(green, "white_dragon")


def test_two_two_suit_triplets_can_repeat() -> None:
    result = score_hand(HandContext([12, 12, 12, 22, 22, 22, 15, 15, 15, 35, 35, 35, 27, 27]))
    assert result.fan_ids.count("two_suit_triplets") == 2, result


def test_small_three_suit_triplets_and_disjoint_two_suit_triplets_both_score() -> None:
    result = score_hand(HandContext([11, 11, 11, 21, 21, 21, 12, 12, 12, 22, 22, 22, 31, 31]))
    assert_has(result, "small_three_suit_triplets")
    assert result.fan_ids.count("two_suit_triplets") == 1, result


def test_two_consecutive_triplets_can_repeat() -> None:
    result = score_hand(HandContext([12, 12, 12, 13, 13, 13, 27, 27, 27, 28, 28, 28, 35, 35]))
    assert result.fan_ids.count("two_consecutive_triplets") == 2, result


def test_four_identical_cannot_be_standard_pair_or_triplet() -> None:
    result = score_hand(HandContext([11, 11, 11, 11, 22, 23, 24, 32, 33, 34, 36, 37, 38, 45]))
    assert result.points == 0, result


def test_kong_count_from_declared_melds() -> None:
    result = score_hand(HandContext([11, 12, 13, 21, 22, 23, 31, 31], meld_codes=["g45", "G46"]))
    assert_has(result, "two_kongs")


def test_wind_row_upgrades_to_small_four_winds() -> None:
    result = score_hand(HandContext([41, 41, 41, 42, 42, 42, 43, 43, 43, 11, 12, 13, 44, 44]))
    assert_has(result, "small_four_winds", 20)
    assert_not_has(result, "big_three_winds")


def test_wind_row_lower_patterns() -> None:
    two = score_hand(HandContext([41, 41, 41, 42, 42, 42, 11, 12, 13, 21, 22, 23, 31, 31]))
    assert_has(two, "two_wind_triplets")

    small_three = score_hand(HandContext([41, 41, 41, 42, 42, 42, 43, 43, 11, 12, 13, 21, 22, 23]))
    assert_has(small_three, "small_three_winds")

    big_three = score_hand(HandContext([41, 41, 41, 42, 42, 42, 43, 43, 43, 11, 12, 13, 21, 21]))
    assert_has(big_three, "big_three_winds")


def test_big_four_winds() -> None:
    result = score_hand(HandContext([41, 41, 41, 42, 42, 42, 43, 43, 43, 44, 44, 44, 11, 11]))
    assert_has(result, "big_four_winds", 20)


def test_big_three_dragons() -> None:
    result = score_hand(HandContext([45, 45, 45, 46, 46, 46, 47, 47, 47, 11, 12, 13, 21, 21]))
    assert_has(result, "big_three_dragons", 20)


def test_small_three_dragons() -> None:
    result = score_hand(HandContext([45, 45, 45, 46, 46, 46, 47, 47, 11, 12, 13, 21, 22, 23]))
    assert_has(result, "small_three_dragons")


def test_terminal_honor_row_outside_and_pure_outside() -> None:
    mixed = score_hand(HandContext([11, 12, 13, 27, 28, 29, 31, 31, 31, 41, 41, 41, 19, 19]))
    assert_has(mixed, "mixed_outside_hand")

    pure = score_hand(HandContext([11, 12, 13, 17, 18, 19, 21, 21, 21, 39, 39, 39, 11, 11]))
    assert_has(pure, "pure_outside_hand")


def test_full_straight() -> None:
    result = score_hand(HandContext([11, 12, 13, 14, 15, 16, 17, 18, 19, 22, 23, 24, 31, 31]))
    assert_has(result, "full_straight")


def test_all_simples_and_closed_hand() -> None:
    result = score_hand(HandContext([12, 13, 14, 14, 15, 16, 22, 23, 24, 36, 37, 38, 28, 28]))
    assert_has(result, "all_simples")
    assert_has(result, "closed_hand")


def test_mixed_and_pure_terminals_with_seven_pairs() -> None:
    mixed = score_hand(HandContext([11, 11, 19, 19, 21, 21, 29, 29, 41, 41, 42, 42, 45, 45]))
    assert_has(mixed, "mixed_terminals")
    assert_has(mixed, "seven_pairs")

    pure = score_hand(HandContext([11, 11, 11, 11, 19, 19, 21, 21, 29, 29, 31, 31, 39, 39]))
    assert_has(pure, "pure_terminals", 20)
    assert_has(pure, "seven_pairs")


def test_half_flush_full_flush_all_honors() -> None:
    half = score_hand(HandContext([11, 12, 13, 14, 15, 16, 17, 18, 19, 41, 41, 45, 45, 45]))
    assert_has(half, "half_flush")

    full = score_hand(HandContext([11, 12, 13, 14, 15, 16, 17, 18, 19, 11, 11, 11, 19, 19]))
    assert_has(full, "full_flush")

    honors = score_hand(HandContext([41, 41, 41, 42, 42, 42, 43, 43, 43, 45, 45, 45, 47, 47]))
    assert_has(honors, "all_honors", 20)


def test_three_suit_number_patterns() -> None:
    small = score_hand(HandContext([15, 15, 15, 25, 25, 25, 35, 35, 11, 12, 13, 27, 28, 29]))
    assert_has(small, "small_three_suit_triplets")

    all_three = score_hand(HandContext([17, 17, 17, 27, 27, 27, 37, 37, 37, 11, 12, 13, 41, 41]))
    assert_has(all_three, "three_suit_triplets")

    chow = score_hand(HandContext([12, 13, 14, 22, 23, 24, 32, 33, 34, 45, 45, 45, 11, 11]))
    assert_has(chow, "mixed_triple_chow")


def test_closed_opening_row_context_flags() -> None:
    base = [11, 12, 13, 21, 22, 23, 31, 32, 33, 45, 45, 45, 41, 41]
    heavenly = score_hand(HandContext(base, heavenly_win=True))
    assert_has(heavenly, "heavenly_win", 20)
    assert_not_has(heavenly, "closed_hand")

    earthly = score_hand(HandContext(base, earthly_win=True))
    assert_has(earthly, "earthly_win", 20)


def test_last_tile_and_kong_win_context_flags() -> None:
    base = [11, 12, 13, 21, 22, 23, 31, 32, 33, 45, 45, 45, 41, 41]
    result = score_hand(HandContext(base, haitei=True, rinshan=True))
    assert_has(result, "haitei")
    assert_has(result, "rinshan")

    robbed = score_hand(HandContext(base, win_source="rob_kong", chankan=True))
    assert_has(robbed, "chankan")

    discard_final = score_hand(HandContext(base, win_source="discard", houtei=True))
    assert_has(discard_final, "houtei")


def test_concealed_triplet_row_self_draw_and_discard_pair_wait() -> None:
    self_draw = score_hand(HandContext(
        [11, 11, 11, 22, 22, 22, 33, 33, 33, 41, 41, 41, 15, 15],
        winning_tile=41,
        win_source="self_draw",
    ))
    assert_has(self_draw, "four_concealed_triplets", 20)

    pair_wait = score_hand(HandContext(
        [11, 11, 11, 22, 22, 22, 33, 33, 33, 41, 41, 41, 15, 15],
        winning_tile=15,
        win_source="discard",
    ))
    assert_has(pair_wait, "four_concealed_triplets", 20)

    triplet_wait = score_hand(HandContext(
        [11, 11, 11, 22, 22, 22, 33, 33, 33, 41, 41, 41, 15, 15],
        winning_tile=41,
        win_source="discard",
    ))
    assert_has(triplet_wait, "three_concealed_triplets")
    assert_not_has(triplet_wait, "four_concealed_triplets")


def test_all_triplets_and_two_concealed_triplets() -> None:
    all_triplets = score_hand(HandContext([11, 11, 11, 22, 22, 22, 33, 33, 33, 41, 41, 41, 15, 15]))
    assert_has(all_triplets, "all_triplets")

    two_concealed = score_hand(HandContext([11, 11, 11, 22, 22, 22, 33, 34, 35, 36, 37, 38, 41, 41]))
    assert_has(two_concealed, "two_concealed_triplets")


def test_consecutive_triplet_row_upgrades() -> None:
    three = score_hand(HandContext([12, 12, 12, 13, 13, 13, 14, 14, 14, 27, 28, 29, 41, 41]))
    assert_has(three, "three_consecutive_triplets")
    assert_not_has(three, "two_consecutive_triplets")

    four = score_hand(HandContext([12, 12, 12, 13, 13, 13, 14, 14, 14, 15, 15, 15, 41, 41]))
    assert_has(four, "four_consecutive_triplets", 20)


def test_identical_sequence_row_upgrades() -> None:
    one = score_hand(HandContext([12, 13, 14, 12, 13, 14, 25, 26, 27, 37, 38, 39, 41, 41]))
    assert_has(one, "pure_double_chow")

    twice = score_hand(HandContext([12, 13, 14, 12, 13, 14, 25, 26, 27, 25, 26, 27, 41, 41]))
    assert_has(twice, "twice_pure_double_chow")

    triple = score_hand(HandContext([27, 28, 29, 41, 41], meld_codes=["s12", "s12", "s12"]))
    assert_has(triple, "pure_triple_chow")

    quad = score_hand(HandContext([41, 41], meld_codes=["s12", "s12", "s12", "s12"]))
    assert_has(quad, "pure_quadruple_chow", 20)


def test_kong_count_row_upgrades() -> None:
    one = score_hand(HandContext([11, 12, 13, 21, 22, 23, 31, 31, 32, 33, 34], meld_codes=["g45"]))
    assert_has(one, "one_kong")

    three = score_hand(HandContext([11, 12, 13, 31, 31], meld_codes=["g45", "G46", "g47"]))
    assert_has(three, "three_kongs")

    four = score_hand(HandContext([31, 31], meld_codes=["g11", "G21", "g45", "G46"]))
    assert_has(four, "four_kongs", 20)


def test_standard_shape_can_win_with_zero_points() -> None:
    result = score_hand(HandContext([13, 14, 15, 24, 25, 26, 36, 37, 38, 41, 41], meld_codes=["k12"]))
    assert result.is_win is True
    assert result.points == 0
    assert result.raw_points == 0
    assert result.fan_ids == ()
    assert result.decomposition is not None


def test_incomplete_shape_is_not_a_win() -> None:
    result = score_hand(HandContext([11, 12, 13, 21, 22, 23, 31, 32, 33, 41, 42, 43, 45, 46]))
    assert result.is_win is False
    assert result.points == 0
    assert result.fan_ids == ()
    assert result.decomposition is None


def test_best_decomposition_prefers_high_scoring_standard_shape_over_seven_pairs() -> None:
    result = score_hand(HandContext([11, 11, 12, 12, 13, 13, 14, 14, 15, 15, 16, 16, 17, 17]))
    assert result.is_win is True
    assert_has(result, "twice_pure_double_chow")
    assert_has(result, "full_flush")
    assert_has(result, "pinfu")
    assert_not_has(result, "seven_pairs")
    assert result.decomposition is not None


def test_best_decomposition_prefers_triplet_chain_over_sequence_shape() -> None:
    result = score_hand(HandContext([11, 11, 11, 12, 12, 12, 13, 13, 13, 14, 14, 14, 15, 15]))
    assert result.is_win is True
    assert_has(result, "four_consecutive_triplets", 20)
    assert_has(result, "all_triplets")
    assert_not_has(result, "pure_triple_chow")
    assert result.decomposition is not None


def test_best_decomposition_keeps_special_top_score_when_standard_shape_exists() -> None:
    pre = [11, 11, 11, 12, 13, 14, 15, 16, 17, 18, 19, 19, 19]
    result = score_hand(HandContext(pre + [15], winning_tile=15, pre_win_tiles=pre))
    assert_has(result, "nine_gates", 20)
    assert_not_has(result, "full_flush")
    assert result.decomposition is None


def run() -> None:
    tests = [
        test_pinfu_all_sequences,
        test_seven_pairs_repeated_pair,
        test_thirteen_orphans_not_mixed_terminals,
        test_true_nine_gates_requires_pre_win_shape,
        test_dragon_row_upgrade,
        test_single_dragon_triplets,
        test_two_two_suit_triplets_can_repeat,
        test_small_three_suit_triplets_and_disjoint_two_suit_triplets_both_score,
        test_two_consecutive_triplets_can_repeat,
        test_four_identical_cannot_be_standard_pair_or_triplet,
        test_kong_count_from_declared_melds,
        test_wind_row_upgrades_to_small_four_winds,
        test_wind_row_lower_patterns,
        test_big_four_winds,
        test_big_three_dragons,
        test_small_three_dragons,
        test_terminal_honor_row_outside_and_pure_outside,
        test_full_straight,
        test_all_simples_and_closed_hand,
        test_mixed_and_pure_terminals_with_seven_pairs,
        test_half_flush_full_flush_all_honors,
        test_three_suit_number_patterns,
        test_closed_opening_row_context_flags,
        test_last_tile_and_kong_win_context_flags,
        test_concealed_triplet_row_self_draw_and_discard_pair_wait,
        test_all_triplets_and_two_concealed_triplets,
        test_consecutive_triplet_row_upgrades,
        test_identical_sequence_row_upgrades,
        test_kong_count_row_upgrades,
        test_standard_shape_can_win_with_zero_points,
        test_incomplete_shape_is_not_a_win,
        test_best_decomposition_prefers_high_scoring_standard_shape_over_seven_pairs,
        test_best_decomposition_prefers_triplet_chain_over_sequence_shape,
        test_best_decomposition_keeps_special_top_score_when_standard_shape_exists,
    ]
    for test in tests:
        test()
    print(f"new_rule scoring smoke tests ok: {len(tests)} tests")


if __name__ == "__main__":
    run()
