from __future__ import annotations

from collections import Counter
from pathlib import Path
import sys

SERVER_ROOT = Path(__file__).resolve().parents[3]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from server.gamestate.game_jiandan import JiandanGameState


def _empty_round() -> JiandanGameState:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
        player.combination_tiles = []
        player.combination_mask = []
    return game


def test_wall_is_136_tiles_without_flowers() -> None:
    game = JiandanGameState()
    game.initialize_round()
    all_tiles = [tile for player in game.player_list for tile in player.hand_tiles]
    all_tiles.extend(game.tiles_list)

    assert len(all_tiles) == 136
    assert all(tile < 50 for tile in all_tiles)
    assert set(Counter(all_tiles).values()) == {4}
    assert len(game.player_list[game.dealer_index].hand_tiles) == 14
    assert all(
        len(player.hand_tiles) == 13
        for index, player in enumerate(game.player_list)
        if index != game.dealer_index
    )


def test_fixed_dealer_rotation() -> None:
    game = JiandanGameState()
    assert [game.advance_dealer_after_round() for _ in range(4)] == [1, 2, 3, 0]


def test_first_marked_winner_ends_hand_and_late_winner_is_ignored() -> None:
    game = JiandanGameState()
    game.initialize_round()

    game.mark_player_hu(1, {"points": 8})
    game.mark_player_hu(2, {"points": 12})

    assert game.game_status == "END"
    assert game.ended_by == "win"
    assert game.hu_count == 1
    assert game.player_list[1].is_hu is True
    assert game.player_list[2].is_hu is False
    assert [settlement["winner"] for settlement in game.deferred_hu_settlements] == [1]


def test_wall_exhaustion_ends_hand_without_winner() -> None:
    game = JiandanGameState()
    game.initialize_round()
    game.tiles_list.clear()

    assert game.should_end_hand() is True
    assert game.hu_count == 0


def test_discard_response_uses_head_bump_first_legal_winner() -> None:
    game = _empty_round()
    game.tiles_list = [33, 34]
    game.player_list[0].hand_tiles = [15]
    game.player_list[1].waiting_tiles = {15}
    game.player_list[2].waiting_tiles = {15}

    tile = game.record_discard(0, 15)
    result = game.resolve_discard_win_responses(
        0,
        tile,
        {2: "hu", 1: "hu"},
        {1: {"points": 6}, 2: {"points": 8}},
    )

    assert result["winners"] == [1]
    assert result["ended"] is True
    assert result["drawn_tile"] is None
    assert game.player_list[1].is_hu is True
    assert game.player_list[2].is_hu is False
    assert [settlement["winner"] for settlement in game.deferred_hu_settlements] == [1]


def test_discard_response_can_pass_nearer_seat_then_accept_next_winner() -> None:
    game = _empty_round()
    game.player_list[0].hand_tiles = [15]
    game.player_list[1].waiting_tiles = {15}
    game.player_list[2].waiting_tiles = {15}

    tile = game.record_discard(0, 15)
    result = game.resolve_discard_win_responses(
        0,
        tile,
        {1: "pass", 2: "hu", 3: "pass"},
        {2: {"points": 8}},
    )

    assert result["passed"] == [1]
    assert result["winners"] == [2]
    assert not game.can_win_by_discard(1, 15)
    assert game.game_status == "END"


def test_discard_win_scores_only_discarder_and_ends_hand() -> None:
    game = _empty_round()
    game.player_list[0].hand_tiles = [45]
    game.player_list[1].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 41, 41, 45, 45]
    game.player_list[1].waiting_tiles = {45}

    tile = game.record_discard(0, 45)
    result = game.resolve_discard_win_responses(0, tile, {1: "hu"})
    settlement = game.deferred_hu_settlements[0]

    assert result["winners"] == [1]
    assert settlement["points"] == 8
    assert settlement["score_changes"] == [-48, 48, 0, 0]
    assert game.game_status == "END"


def test_self_draw_win_scores_all_opponents_and_ends_hand() -> None:
    game = _empty_round()
    game.opening_action_taken = True
    game.opening_flow_interrupted = True
    game.player_list[0].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 45, 45, 45, 15, 15]

    window = game.apply_turn_action(0, "hu_self", tile=15)
    settlement = game.deferred_hu_settlements[0]

    assert window["status"] == "END"
    assert settlement["points"] == 5
    assert settlement["score_changes"] == [30, -10, -10, -10]
    assert game.hu_count == 1


def test_zero_point_standard_win_is_preserved() -> None:
    game = _empty_round()
    game.player_list[0].hand_tiles = [41]

    game.record_self_draw_win(
        0,
        41,
        {
            "is_win": True,
            "points": 0,
            "raw_points": 0,
            "fan_ids": [],
            "fan_names": [],
            "score_changes": [0, 0, 0, 0],
        },
    )

    settlement = game.deferred_hu_settlements[0]
    assert settlement["points"] == 0
    assert settlement["fan_ids"] == []
    assert game.game_status == "END"


def test_no_win_response_allows_normal_claim_priority() -> None:
    game = _empty_round()
    game.tiles_list = [33]
    game.player_list[0].hand_tiles = [15]
    game.player_list[1].hand_tiles = [13, 14, 22]
    game.player_list[2].hand_tiles = [15, 15, 31]

    tile = game.record_discard(0, 15)
    window = game.continue_after_discard_responses(
        0,
        tile,
        {1: "pass", 2: "pass"},
        {1: "chi_left", 2: "peng"},
    )

    claim = window["claim_result"]
    assert window["status"] == "onlycut_after_action"
    assert claim["claimant"] == 2
    assert claim["action"] == "peng"
    assert claim["meld_code"] == "k15"
    assert game.player_list[2].hand_tiles == [31]


def test_concealed_kong_draws_supplement_and_keeps_private_meld() -> None:
    game = _empty_round()
    game.tiles_list = [33, 34]
    game.player_list[0].hand_tiles = [15, 15, 15, 15, 41]

    result = game.declare_concealed_kong(0, 15)

    assert result["meld_code"] == "G15"
    assert result["public_meld_code"] == "G0"
    assert result["drawn_tile"] == 33
    assert game.player_list[0].hand_tiles == [41, 33]
    assert game.player_list[0].combination_tiles == ["G15"]
    assert game.player_list[0].combination_mask == [[2, 15, 2, 15, 2, 15, 2, 15]]


def test_added_kong_without_robbery_upgrades_and_draws() -> None:
    game = _empty_round()
    game.tiles_list = [33, 34]
    game.player_list[0].hand_tiles = [15, 41]
    game.player_list[0].combination_tiles = ["k15"]
    game.player_list[0].combination_mask = [[1, 15, 0, 15, 0, 15]]
    game.player_list[2].waiting_tiles = {15}

    game.attempt_added_kong(0, 15)
    result = game.resolve_added_kong_responses(0, 15, {2: "pass"})

    assert result["robbed"] is False
    assert result["drawn_tile"] == 33
    assert result["meld_code"] == "g15"
    assert game.player_list[0].hand_tiles == [41, 33]
    assert game.player_list[0].combination_tiles == ["g15"]
    assert not game.can_win_by_discard(2, 15)


def test_robbing_kong_uses_first_winner_and_ends_without_draw() -> None:
    game = _empty_round()
    game.tiles_list = [33, 34]
    game.player_list[0].hand_tiles = [15, 41]
    game.player_list[0].combination_tiles = ["k15"]
    game.player_list[1].waiting_tiles = {15}
    game.player_list[2].waiting_tiles = {15}

    game.attempt_added_kong(0, 15)
    result = game.resolve_added_kong_responses(
        0,
        15,
        {2: "hu", 1: "hu"},
        {1: {"points": 6}, 2: {"points": 8}},
    )

    assert result["robbed"] is True
    assert result["winners"] == [1]
    assert result["ended"] is True
    assert result["drawn_tile"] is None
    assert game.player_list[0].hand_tiles == [41]
    assert game.player_list[0].combination_tiles == ["k15"]
    assert game.player_list[2].is_hu is False


def test_action_results_emit_one_final_result_per_viewer() -> None:
    game = _empty_round()
    game.player_list[0].hand_tiles = [41]
    game.player_list[1].waiting_tiles = {41}
    tile = game.record_discard(0, 41)
    window = {
        "status": "waiting_action_after_cut",
        "player": 0,
        "tile": tile,
        "actions": {1: ["hu", "pass"]},
    }

    next_window = game.apply_action_results(
        window,
        {1: {"action_type": "hu"}},
        settlements={1: {"points": 8, "fan_ids": ["pinfu"], "score_changes": [-48, 48, 0, 0]}},
    )

    result_payloads = [
        payload
        for payload in game.outbound_payloads
        if payload.get("type") == "gamestate/jiandan/show_result"
    ]
    assert next_window["status"] == "END"
    assert len(result_payloads) == 4
    assert [payload["player_index"] for payload in result_payloads] == [0, 1, 2, 3]
    assert all(payload["show_result_info"]["hepai_player_index"] == 1 for payload in result_payloads)
    assert not any("defer_score_settlement" in payload["show_result_info"] for payload in result_payloads)


def test_deferred_scores_are_applied_once() -> None:
    game = JiandanGameState()
    game.deferred_hu_settlements = [
        {"winner": 1, "points": 8, "score_changes": [-48, 48, 0, 0]}
    ]

    game.apply_deferred_score_changes()
    game.apply_deferred_score_changes()

    assert [player.score for player in game.player_list] == [-48, 48, 0, 0]
    assert [player.score_history for player in game.player_list] == [["-48"], ["+48"], ["0"], ["0"]]


def test_persist_game_record_uses_rule_local_adapter() -> None:
    class FakeDatabase:
        def __init__(self) -> None:
            self.calls = []

        def store_jiandan_game_record(self, *args):
            self.calls.append(args)
            return "record-id"

    game = JiandanGameState()
    game.db_manager = FakeDatabase()
    game.game_record = {"game_title": {"rule": "jiandan"}}

    assert game.persist_game_record() == "record-id"
    assert len(game.db_manager.calls) == 1
    assert game.db_manager.calls[0][0] is game.game_record


def test_result_ready_timeout_is_single_panel_duration() -> None:
    game = JiandanGameState()
    game.mark_player_hu(0, {"points": 8})

    assert game.estimated_round_result_ready_timeout() == 12.0


def run() -> None:
    tests = [
        test_wall_is_136_tiles_without_flowers,
        test_fixed_dealer_rotation,
        test_first_marked_winner_ends_hand_and_late_winner_is_ignored,
        test_wall_exhaustion_ends_hand_without_winner,
        test_discard_response_uses_head_bump_first_legal_winner,
        test_discard_response_can_pass_nearer_seat_then_accept_next_winner,
        test_discard_win_scores_only_discarder_and_ends_hand,
        test_self_draw_win_scores_all_opponents_and_ends_hand,
        test_zero_point_standard_win_is_preserved,
        test_no_win_response_allows_normal_claim_priority,
        test_concealed_kong_draws_supplement_and_keeps_private_meld,
        test_added_kong_without_robbery_upgrades_and_draws,
        test_robbing_kong_uses_first_winner_and_ends_without_draw,
        test_action_results_emit_one_final_result_per_viewer,
        test_deferred_scores_are_applied_once,
        test_persist_game_record_uses_rule_local_adapter,
        test_result_ready_timeout_is_single_panel_duration,
    ]
    for test in tests:
        test()
    print(f"jiandan gamestate tests ok: {len(tests)} tests")


if __name__ == "__main__":
    run()
