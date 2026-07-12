from __future__ import annotations

import asyncio
from collections import Counter
from pathlib import Path
import sys
import time
from types import SimpleNamespace

SERVER_ROOT = Path(__file__).resolve().parents[3]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from server.gamestate.game_jiandan import JiandanGameState
from server.gamestate.game_jiandan.boardcast import final_settlement_payloads


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_json(self, payload: dict) -> None:
        self.sent.append(payload)


def test_wall_is_136_no_flowers_and_deal_shape() -> None:
    game = JiandanGameState()
    game.initialize_round()
    all_tiles = []
    for player in game.player_list:
        all_tiles.extend(player.hand_tiles)
    all_tiles.extend(game.tiles_list)

    assert len(all_tiles) == 136
    assert all(tile < 50 for tile in all_tiles)
    assert set(Counter(all_tiles).values()) == {4}
    assert len(game.player_list[game.dealer_index].hand_tiles) == 14
    for idx, player in enumerate(game.player_list):
        if idx != game.dealer_index:
            assert len(player.hand_tiles) == 13
    assert len(game.tiles_list) == 83


def test_fixed_dealer_rotation() -> None:
    game = JiandanGameState()
    assert game.dealer_index == 0
    assert game.advance_dealer_after_round() == 1
    assert game.advance_dealer_after_round() == 2
    assert game.advance_dealer_after_round() == 3
    assert game.advance_dealer_after_round() == 0


def test_third_winner_flow_end_conditions() -> None:
    game = JiandanGameState()
    game.initialize_round()
    game.mark_player_hu(0, {"points": 8})
    assert game.game_status != "END"
    game.mark_player_hu(1, {"points": 8})
    assert game.game_status != "END"
    game.mark_player_hu(2, {"points": 8})
    assert game.game_status == "END"
    assert game.ended_by == "win"
    assert [p.hu_order for p in game.player_list[:3]] == [1, 2, 3]
    assert [rec["winner"] for rec in game.deferred_hu_settlements] == [0, 1, 2]


def test_wall_exhaustion_ends_hand() -> None:
    game = JiandanGameState()
    game.initialize_round()
    game.tiles_list.clear()
    assert game.should_end_hand()


def test_next_active_skips_winners() -> None:
    game = JiandanGameState()
    game.initialize_round()
    game.mark_player_hu(1)
    assert game.next_active_index(0) == 2
    game.mark_player_hu(2)
    assert game.next_active_index(0) == 3


def test_discard_win_lockout_helpers() -> None:
    game = JiandanGameState()
    game.add_discard_win_lockout(0, 15)
    assert not game.can_win_by_discard(0, 15)
    assert game.can_win_by_discard(0, 16)
    game.clear_lockout_on_discard(0, 19)
    assert game.can_win_by_discard(0, 15)
    assert not game.can_win_by_discard(0, 19)


def test_discard_pass_lockout_clears_and_restarts_on_own_discard() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
    game.player_list[1].waiting_tiles = {15, 16}
    game.player_list[1].hand_tiles = [16, 21, 22, 23]

    game.record_discard_win_pass(1, 15)
    assert not game.can_win_by_discard(1, 15)
    assert game.can_win_by_discard(1, 16)

    game.record_discard(1, 16)
    assert game.can_win_by_discard(1, 15)
    assert not game.can_win_by_discard(1, 16)


def test_discard_win_defers_settlement_and_next_draw_skips_winner() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
    game.tiles_list = [33, 34]
    game.player_list[0].hand_tiles = [15]
    game.player_list[2].waiting_tiles = {15}

    tile = game.record_discard(0, 15)
    game.record_discard_win(2, 0, tile, {"points": 8})
    drawn = game.draw_after_discard_resolution(0)

    assert game.player_list[2].is_hu
    assert game.deferred_hu_settlements == [
        {"source": "discard", "discarder": 0, "tile": 15, "points": 8, "winner": 2, "hu_order": 1}
    ]
    assert game.current_player_index == 1
    assert drawn == 33
    assert game.player_list[1].hand_tiles == [33]


def test_draw_after_discard_resolution_ends_on_empty_wall() -> None:
    game = JiandanGameState()
    game.initialize_round()
    game.tiles_list = []
    drawn = game.draw_after_discard_resolution(0)
    assert drawn is None
    assert game.game_status == "END"
    assert game.ended_by == "wall"


def test_resolve_discard_win_responses_allows_independent_multi_ron() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
    game.tiles_list = [33, 34]
    game.player_list[0].hand_tiles = [15]
    game.player_list[1].waiting_tiles = {15}
    game.player_list[2].waiting_tiles = {15}

    tile = game.record_discard(0, 15)
    result = game.resolve_discard_win_responses(
        0,
        tile,
        {1: "hu", 2: "hu", 3: "pass"},
        {1: {"points": 6}, 2: {"points": 8}},
    )

    assert result["winners"] == [1, 2]
    assert result["passed"] == [3]
    assert game.player_list[1].is_hu
    assert game.player_list[2].is_hu
    assert [record["winner"] for record in game.deferred_hu_settlements] == [1, 2]
    assert result["draw_player"] == 3
    assert result["drawn_tile"] == 33


def test_discard_win_continues_from_winner_next_seat_not_discarder_next_seat() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
    game.tiles_list = [33, 34]
    game.player_list[3].hand_tiles = [15]
    game.player_list[2].waiting_tiles = {15}

    tile = game.record_discard(3, 15)
    result = game.resolve_discard_win_responses(3, tile, {2: "hu"}, {2: {"points": 8}})

    assert result["winners"] == [2]
    assert result["draw_player"] == 3
    assert result["drawn_tile"] == 33
    assert game.current_player_index == 3
    assert game.player_list[3].hand_tiles == [33]


def test_discard_win_with_pass_locks_only_passing_non_winner() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
    game.tiles_list = [33, 34]
    game.player_list[0].hand_tiles = [15]
    game.player_list[1].waiting_tiles = {15}
    game.player_list[2].waiting_tiles = {15}

    tile = game.record_discard(0, 15)
    result = game.resolve_discard_win_responses(
        0,
        tile,
        {1: "hu", 2: "pass"},
        {1: {"points": 6}},
    )

    assert result["winners"] == [1]
    assert result["passed"] == [2]
    assert game.player_list[1].discard_win_lockout_tiles == set()
    assert game.player_list[2].discard_win_lockout_tiles == {15}


def test_resolve_discard_win_responses_ends_after_third_winner_without_draw() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
    game.tiles_list = [33]
    game.mark_player_hu(1)
    game.mark_player_hu(2)
    game.player_list[0].hand_tiles = [15]
    game.player_list[3].waiting_tiles = {15}

    tile = game.record_discard(0, 15)
    result = game.resolve_discard_win_responses(0, tile, {3: "hu"}, {3: {"points": 8}})

    assert result["winners"] == [3]
    assert result["draw_player"] is None
    assert result["drawn_tile"] is None
    assert result["ended"]
    assert game.game_status == "END"
    assert game.ended_by == "win"


def test_resolve_discard_win_responses_no_winner_only_records_passes() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
    game.tiles_list = [33]
    game.player_list[0].hand_tiles = [15]
    game.player_list[2].waiting_tiles = {15}

    tile = game.record_discard(0, 15)
    result = game.resolve_discard_win_responses(0, tile, {2: "pass"})

    assert result["winners"] == []
    assert result["passed"] == [2]
    assert not game.can_win_by_discard(2, 15)
    assert result["draw_player"] is None
    assert result["drawn_tile"] is None
    assert game.tiles_list == [33]


def test_resolve_discard_win_responses_rejects_locked_out_win() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
    game.player_list[0].hand_tiles = [15]
    game.player_list[2].waiting_tiles = {15}
    game.add_discard_win_lockout(2, 15)

    tile = game.record_discard(0, 15)
    try:
        game.resolve_discard_win_responses(0, tile, {2: "hu"})
    except ValueError:
        pass
    else:
        raise AssertionError("locked-out discard win should be rejected")


def test_resolve_discard_claim_prefers_peng_over_chi_and_forces_cut() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.combination_tiles = []
    game.player_list[0].hand_tiles = [15]
    game.player_list[1].hand_tiles = [13, 14, 22]
    game.player_list[2].hand_tiles = [15, 15, 31]

    tile = game.record_discard(0, 15)
    result = game.resolve_discard_claim_responses(0, tile, {1: "chi_left", 2: "peng"})

    assert result["claimed"]
    assert result["claimant"] == 2
    assert result["action"] == "peng"
    assert result["meld_code"] == "k15"
    assert result["combination_mask"] == [1, 15, 0, 15, 0, 15]
    assert game.player_list[2].hand_tiles == [31]
    assert game.player_list[2].combination_tiles == ["k15"]
    assert game.player_list[2].combination_mask == [[1, 15, 0, 15, 0, 15]]
    assert game.current_player_index == 2
    assert game.game_status == "onlycut_after_action"


def test_resolve_discard_claim_chi_only_from_fixed_next_seat() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.combination_tiles = []
    game.player_list[0].hand_tiles = [15]
    game.player_list[1].is_hu = True
    game.player_list[2].hand_tiles = [13, 14, 31]

    tile = game.record_discard(0, 15)
    result = game.resolve_discard_claim_responses(0, tile, {1: "chi_left", 2: "chi_left"})

    assert not result["claimed"]
    assert result["draw_player"] == 2
    assert result["drawn_tile"] is not None
    assert game.player_list[2].hand_tiles == [13, 14, 31, result["drawn_tile"]]


def test_resolve_discard_claim_chi_returns_unity_combination_mask() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.combination_tiles = []
        player.combination_mask = []
    game.player_list[0].hand_tiles = [15]
    game.player_list[1].hand_tiles = [16, 17, 31]

    tile = game.record_discard(0, 15)
    result = game.resolve_discard_claim_responses(0, tile, {1: "chi_right"})

    assert result["claimed"]
    assert result["claimant"] == 1
    assert result["action"] == "chi_right"
    assert result["meld_code"] == "s15"
    assert result["combination_mask"] == [1, 15, 0, 16, 0, 17]
    assert game.player_list[1].hand_tiles == [31]
    assert game.player_list[1].combination_tiles == ["s15"]
    assert game.player_list[1].combination_mask == [[1, 15, 0, 16, 0, 17]]


def test_resolve_discard_claim_gang_draws_supplement_tile() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.combination_tiles = []
    game.tiles_list = [33, 34]
    game.player_list[0].hand_tiles = [15]
    game.player_list[3].hand_tiles = [15, 15, 15, 41]

    tile = game.record_discard(0, 15)
    result = game.resolve_discard_claim_responses(0, tile, {3: "gang"})

    assert result["claimed"]
    assert result["claimant"] == 3
    assert result["meld_code"] == "g15"
    assert result["combination_mask"] == [1, 15, 0, 15, 0, 15, 0, 15]
    assert result["draw_player"] == 3
    assert result["drawn_tile"] == 33
    assert game.player_list[3].hand_tiles == [41, 33]
    assert game.player_list[3].combination_tiles == ["g15"]
    assert game.game_status == "waiting_hand_action"


def test_resolve_discard_claim_no_claim_draws_next_active_player() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.combination_tiles = []
    game.tiles_list = [33]
    game.player_list[0].hand_tiles = [15]

    tile = game.record_discard(0, 15)
    result = game.resolve_discard_claim_responses(0, tile, {2: "pass"})

    assert not result["claimed"]
    assert result["draw_player"] == 1
    assert result["drawn_tile"] == 33
    assert game.player_list[1].hand_tiles == [33]


def test_record_self_draw_win_defers_settlement() -> None:
    game = JiandanGameState()
    game.initialize_round()
    game.player_list[0].hand_tiles = [11, 12, 13, 41, 41]

    game.record_self_draw_win(0, 41, {"points": 6})

    assert game.player_list[0].is_hu
    assert game.deferred_hu_settlements == [
        {"source": "self_draw", "tile": 41, "points": 6, "winner": 0, "hu_order": 1}
    ]


def test_zero_point_win_with_empty_fans_is_preserved_in_deferred_settlement() -> None:
    game = JiandanGameState()
    game.initialize_round()
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

    assert game.player_list[0].is_hu
    assert game.deferred_hu_settlements == [
        {
            "source": "self_draw",
            "tile": 41,
            "is_win": True,
            "points": 0,
            "raw_points": 0,
            "fan_ids": [],
            "fan_names": [],
            "score_changes": [0, 0, 0, 0],
            "winner": 0,
            "hu_order": 1,
        }
    ]


def test_calculated_discard_win_settlement_scores_only_discarder() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
    game.player_list[0].hand_tiles = [45]
    game.player_list[1].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 41, 41, 45, 45]
    game.player_list[1].waiting_tiles = {45}

    tile = game.record_discard(0, 45)
    game.resolve_discard_win_responses(0, tile, {1: "hu"})
    settlement = game.deferred_hu_settlements[0]

    assert settlement["points"] == 8
    assert settlement["score_changes"] == [-48, 48, 0, 0]


def test_calculated_multi_ron_settlements_each_charge_discarder() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
    game.tiles_list = [33]
    game.player_list[0].hand_tiles = [45]
    game.player_list[1].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 41, 41, 45, 45]
    game.player_list[2].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 42, 42, 45, 45]
    game.player_list[1].waiting_tiles = {45}
    game.player_list[2].waiting_tiles = {45}

    tile = game.record_discard(0, 45)
    result = game.resolve_discard_win_responses(0, tile, {1: "hu", 2: "hu"})

    assert result["winners"] == [1, 2]
    assert [settlement["points"] for settlement in game.deferred_hu_settlements] == [8, 8]
    assert [settlement["score_changes"] for settlement in game.deferred_hu_settlements] == [
        [-48, 48, 0, 0],
        [-48, 0, 48, 0],
    ]


def test_calculated_self_draw_settlement_scores_remaining_non_winners() -> None:
    game = JiandanGameState()
    game.initialize_round()
    game.player_list[1].is_hu = True
    game.player_list[1].hu_order = 1
    game.hu_order_counter = 1
    game.opening_action_taken = True
    game.opening_flow_interrupted = True
    game.player_list[0].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 45, 45, 45, 15, 15]

    game.record_self_draw_win(0, 15)
    settlement = game.deferred_hu_settlements[0]

    assert settlement["points"] == 5
    assert settlement["score_changes"] == [30, 0, -15, -15]


def test_declare_concealed_kong_draws_supplement_and_hides_public_tile() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.combination_tiles = []
    game.tiles_list = [33, 34]
    game.player_list[0].hand_tiles = [15, 15, 15, 15, 41]

    result = game.declare_concealed_kong(0, 15)

    assert result["meld_code"] == "G15"
    assert result["public_meld_code"] == "G0"
    assert result["drawn_tile"] == 33
    assert game.player_list[0].hand_tiles == [41, 33]
    assert game.player_list[0].combination_tiles == ["G15"]
    assert game.player_list[0].combination_mask == [[2, 15, 2, 15, 2, 15, 2, 15]]
    assert result["combination_mask"] == [2, 15, 2, 15, 2, 15, 2, 15]
    assert game.game_status == "waiting_hand_action"


def test_added_kong_without_robbery_upgrades_triplet_and_draws_supplement() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
        player.combination_tiles = []
    game.tiles_list = [33, 34]
    game.player_list[0].hand_tiles = [15, 41]
    game.player_list[0].combination_tiles = ["k15"]
    game.player_list[0].combination_mask = [[1, 15, 0, 15, 0, 15]]
    game.player_list[2].waiting_tiles = {15}

    attempt = game.attempt_added_kong(0, 15)
    result = game.resolve_added_kong_responses(0, 15, {2: "pass"})

    assert attempt["next_status"] == "waiting_action_qianggang"
    assert not result["robbed"]
    assert result["passed"] == [2]
    assert result["meld_code"] == "g15"
    assert result["previous_meld_code"] == "k15"
    assert result["combination_mask"] == [3, 15, 1, 15, 0, 15, 0, 15]
    assert result["drawn_tile"] == 33
    assert game.player_list[0].hand_tiles == [41, 33]
    assert game.player_list[0].combination_tiles == ["g15"]
    assert game.player_list[0].combination_mask == [[3, 15, 1, 15, 0, 15, 0, 15]]
    assert not game.can_win_by_discard(2, 15)
    assert game.game_status == "waiting_hand_action"


def test_added_kong_robbed_does_not_upgrade_or_draw_supplement() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
        player.combination_tiles = []
    game.tiles_list = [33, 34]
    game.player_list[0].hand_tiles = [15, 41]
    game.player_list[0].combination_tiles = ["k15"]
    game.player_list[2].waiting_tiles = {15}

    game.attempt_added_kong(0, 15)
    result = game.resolve_added_kong_responses(0, 15, {2: "hu"}, {2: {"points": 8}})

    assert result["robbed"]
    assert result["winners"] == [2]
    assert game.player_list[2].is_hu
    assert game.deferred_hu_settlements == [
        {"source": "rob_kong", "kong_player": 0, "tile": 15, "points": 8, "winner": 2, "hu_order": 1}
    ]
    assert game.player_list[0].hand_tiles == [41]
    assert game.player_list[0].combination_tiles == ["k15"]
    assert result["draw_player"] == 3
    assert result["drawn_tile"] == 33
    assert game.player_list[3].hand_tiles == [33]


def test_added_kong_robbery_respects_same_tile_lockout() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
        player.combination_tiles = []
    game.player_list[0].hand_tiles = [15, 41]
    game.player_list[0].combination_tiles = ["k15"]
    game.player_list[2].waiting_tiles = {15}
    game.add_discard_win_lockout(2, 15)

    game.attempt_added_kong(0, 15)
    try:
        game.resolve_added_kong_responses(0, 15, {2: "hu"})
    except ValueError:
        pass
    else:
        raise AssertionError("locked-out robbing kong should be rejected")


def test_begin_hand_action_refreshes_waiting_from_pre_draw_tiles() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
    game.player_list[0].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 45, 45, 45, 41, 41]

    window = game.begin_hand_action(0)

    assert 41 in game.player_list[0].waiting_tiles
    assert "hu_self" in window["actions"][0], window


def test_apply_turn_cut_refreshes_waits_and_opens_discard_response_window() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
    game.player_list[0].hand_tiles = [41]
    game.player_list[2].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 45, 45, 45, 41]

    window = game.apply_turn_action(0, "cut", tile=41)

    assert window["status"] == "waiting_action_after_cut"
    assert "hu" in window["actions"][2], window
    assert game.player_list[0].discard_tiles == [41]


def test_apply_turn_self_draw_win_continues_to_next_player_draw() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
    game.tiles_list = [33, 34]
    game.player_list[0].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 45, 45, 45, 41, 41]

    window = game.apply_turn_action(0, "hu_self", tile=41, settlement={"points": 6})

    assert game.player_list[0].is_hu
    assert game.deferred_hu_settlements == [
        {"source": "self_draw", "tile": 41, "points": 6, "winner": 0, "hu_order": 1}
    ]
    assert window["player"] == 1
    assert window["drawn_tile"] == 33
    assert game.player_list[1].hand_tiles == [33]
    assert window["status"] == "waiting_hand_action"


def test_apply_action_results_self_draw_win_emits_deferred_show_result() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
    game.tiles_list = [33, 34]
    game.player_list[0].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 45, 45, 45, 41, 41]

    window = game.begin_hand_action(0)
    game.apply_action_results(
        window,
        {0: {"action_type": "hu_self", "target_tile": 41, "TileId": None, "cutIndex": -1, "cutClass": False}},
        settlements={0: {"points": 6}},
    )

    show_payloads = [
        payload
        for payload in game.outbound_payloads
        if payload.get("type") == "gamestate/jiandan/show_result"
    ]
    assert show_payloads
    assert show_payloads[0]["show_result_info"]["hepai_player_index"] == 0
    assert show_payloads[0]["show_result_info"]["hu_class"] == "hu_self"
    assert show_payloads[0]["show_result_info"]["hu_fan"] == []
    assert show_payloads[0]["show_result_info"]["suppress_hand_reveal"] is True
    assert show_payloads[0]["show_result_info"]["defer_score_settlement"] is True
    deal_payloads = [
        payload
        for payload in game.outbound_payloads
        if payload.get("type") == "gamestate/jiandan/do_action"
        and payload.get("do_action_info", {}).get("action_list") == ["deal_tile"]
        and payload.get("do_action_info", {}).get("action_player") == 1
    ]
    assert deal_payloads
    assert any(payload["do_action_info"]["deal_tile"] == 33 for payload in deal_payloads)


def test_apply_action_results_third_self_draw_win_with_zero_target_ends_hand() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
    game.tiles_list = [33, 34]
    game.player_list[0].is_hu = True
    game.player_list[1].is_hu = True
    game.hu_order_counter = 2
    game.deferred_hu_settlements = [
        {"source": "discard", "tile": 11, "winner": 0, "points": 8, "hu_order": 1},
        {"source": "discard", "tile": 12, "winner": 1, "points": 8, "hu_order": 2},
    ]
    game.player_list[2].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 45, 45, 45, 41, 41]

    window = game.begin_hand_action(2)
    next_window = game.apply_action_results(
        window,
        {2: {"action_type": "hu_self", "target_tile": 0, "TileId": None, "cutIndex": -1, "cutClass": False}},
        settlements={2: {"points": 6}},
    )

    assert next_window["status"] == "END"
    assert game.game_status == "END"
    assert game.player_list[2].is_hu
    assert game.deferred_hu_settlements[-1] == {
        "source": "self_draw",
        "tile": 41,
        "points": 6,
        "winner": 2,
        "hu_order": 3,
    }
    assert not any(
        payload.get("type") == "gamestate/jiandan/do_action"
        and payload.get("do_action_info", {}).get("action_list") == ["deal_tile"]
        for payload in game.outbound_payloads
    )
    terminal_tile_move_payloads = [
        payload
        for payload in game.outbound_payloads
        if payload.get("type") == "gamestate/jiandan/show_result"
        and payload.get("player_index") == 0
        and payload.get("show_result_info", {}).get("defer_score_settlement") is True
    ]
    assert len(terminal_tile_move_payloads) == 1
    assert terminal_tile_move_payloads[0]["show_result_info"]["hepai_player_index"] == 2
    assert terminal_tile_move_payloads[0]["show_result_info"]["hu_class"] == "hu_self"
    final_payloads = [
        payload
        for payload in game.outbound_payloads
        if payload.get("type") == "gamestate/jiandan/show_result"
        and payload.get("show_result_info", {}).get("liuju_step") == "settle_hu"
    ]
    assert len(final_payloads) == 4 * 3


def test_apply_turn_concealed_kong_returns_followup_hand_action_window() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
        player.combination_tiles = []
    game.tiles_list = [33, 34]
    game.player_list[0].hand_tiles = [15, 15, 15, 15, 41]

    window = game.apply_turn_action(0, "angang", tile=15)

    assert window["result"]["meld_code"] == "G15"
    assert window["result"]["public_meld_code"] == "G0"
    assert window["result"]["combination_mask"] == [2, 15, 2, 15, 2, 15, 2, 15]
    assert window["drawn_tile"] == 33
    assert game.player_list[0].hand_tiles == [41, 33]
    assert window["status"] == "waiting_hand_action"
    assert "cut" in window["actions"][0], window


def test_apply_action_results_concealed_kong_emits_mask_and_supplement_draw() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
        player.combination_tiles = []
        player.combination_mask = []
    game.tiles_list = [33, 34]
    game.player_list[0].hand_tiles = [15, 15, 15, 15, 41]

    window = game.begin_hand_action(0)
    next_window = game.apply_action_results(
        window,
        {0: {"action_type": "angang", "target_tile": 15, "TileId": None, "cutIndex": -1, "cutClass": False}},
    )

    assert next_window["status"] == "waiting_hand_action"
    action_payloads = [
        payload
        for payload in game.outbound_payloads
        if payload.get("type") == "gamestate/jiandan/do_action"
    ]
    angang_payload = next(
        payload for payload in action_payloads
        if payload["player_index"] == 0 and payload["do_action_info"]["action_list"] == ["angang"]
    )
    hidden_angang_payload = next(
        payload for payload in action_payloads
        if payload["player_index"] == 1 and payload["do_action_info"]["action_list"] == ["angang"]
    )
    gang_draw_payload = next(
        payload for payload in action_payloads
        if payload["player_index"] == 0 and payload["do_action_info"]["action_list"] == ["deal_gang_tile"]
    )

    assert angang_payload["do_action_info"]["combination_target"] == "G15"
    assert angang_payload["do_action_info"]["combination_mask"] == [2, 15, 2, 15, 2, 15, 2, 15]
    assert hidden_angang_payload["do_action_info"]["combination_target"] == "G0"
    assert hidden_angang_payload["do_action_info"]["combination_mask"] == [2, 0, 2, 0, 2, 0, 2, 0]
    assert gang_draw_payload["do_action_info"]["deal_tile"] == 33


def test_concealed_kong_supplement_self_draw_scores_rinshan() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
        player.combination_tiles = []
        player.combination_mask = []
    game.player_list[0].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 45, 45, 45, 41, 41]

    game.begin_hand_action(0, is_get_gang_tile=True)
    game.record_self_draw_win(0, 41)

    settlement = game.deferred_hu_settlements[-1]
    assert "rinshan" in settlement["fan_ids"], settlement


def test_opening_self_draw_context_scores_heavenly_and_earthly_win() -> None:
    heavenly = JiandanGameState()
    heavenly.initialize_round()
    for player in heavenly.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
    heavenly.player_list[0].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 45, 45, 45, 41, 41]

    heavenly.record_self_draw_win(0, 41)

    assert "heavenly_win" in heavenly.deferred_hu_settlements[-1]["fan_ids"]

    earthly = JiandanGameState()
    earthly.initialize_round()
    for player in earthly.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
    earthly.tiles_list = [41, 33]
    earthly.player_list[0].hand_tiles = [19]
    earthly.player_list[1].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 45, 45, 45, 41]
    earthly.record_discard(0, 19)
    drawn_tile = earthly.draw_after_discard_resolution(0)

    earthly.record_self_draw_win(1, drawn_tile)

    assert drawn_tile == 41
    assert "earthly_win" in earthly.deferred_hu_settlements[-1]["fan_ids"]


def test_last_tile_context_scores_haitei_and_houtei() -> None:
    haitei = JiandanGameState()
    haitei.initialize_round()
    for player in haitei.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
    haitei.tiles_list = []
    haitei.opening_action_taken = True
    haitei.player_list[1].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 45, 45, 45, 41, 41]

    haitei.record_self_draw_win(1, 41)

    assert "haitei" in haitei.deferred_hu_settlements[-1]["fan_ids"]

    houtei = JiandanGameState()
    houtei.initialize_round()
    for player in houtei.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
    houtei.tiles_list = []
    houtei.player_list[1].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 45, 45, 45, 41]

    houtei.record_discard_win(1, 0, 41)

    assert "houtei" in houtei.deferred_hu_settlements[-1]["fan_ids"]


def test_pre_win_context_scores_nine_gates_in_live_settlement() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
    pre = [11, 11, 11, 12, 13, 14, 15, 16, 17, 18, 19, 19, 19]
    game.player_list[1].hand_tiles = pre + [15]
    game.opening_flow_interrupted = True

    game.record_self_draw_win(1, 15)

    assert "nine_gates" in game.deferred_hu_settlements[-1]["fan_ids"]


def test_discard_win_pre_win_context_scores_nine_gates() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()

    game.player_list[1].hand_tiles = [11, 11, 11, 12, 13, 14, 15, 16, 17, 18, 19, 19, 19]
    game.player_list[1].waiting_tiles = {19}

    game.record_discard_win(1, 0, 19)

    settlement = game.deferred_hu_settlements[-1]
    assert "nine_gates" in settlement["fan_ids"]
    assert settlement["points"] == 20


def test_apply_turn_added_kong_opens_rob_kong_window() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
        player.combination_tiles = []
    game.player_list[0].hand_tiles = [15, 41]
    game.player_list[0].combination_tiles = ["k15"]
    game.player_list[2].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 45, 45, 45, 15]

    window = game.apply_turn_action(0, "jiagang", tile=15)

    assert window["status"] == "waiting_action_qianggang"
    assert "hu" in window["actions"][2], window
    assert game.player_list[0].combination_tiles == ["k15"]
    assert game.player_list[0].hand_tiles == [15, 41]


def test_apply_action_results_added_kong_pass_emits_meld_update_and_supplement_draw() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
        player.combination_tiles = []
        player.combination_mask = []
    game.tiles_list = [33, 34]
    game.player_list[0].hand_tiles = [15, 41]
    game.player_list[0].combination_tiles = ["k15"]
    game.player_list[0].combination_mask = [[1, 15, 0, 15, 0, 15]]

    kong_window = game.apply_turn_action(0, "jiagang", tile=15)
    next_window = game.apply_action_results(
        kong_window,
        {
            1: {"action_type": "pass"},
            2: {"action_type": "pass"},
            3: {"action_type": "pass"},
        },
    )

    assert next_window["status"] == "waiting_hand_action"
    action_payloads = [
        payload
        for payload in game.outbound_payloads
        if payload.get("type") == "gamestate/jiandan/do_action"
    ]
    jiagang_payload = next(
        payload for payload in action_payloads
        if payload["player_index"] == 0 and payload["do_action_info"]["action_list"] == ["jiagang"]
    )
    gang_draw_payload = next(
        payload for payload in action_payloads
        if payload["player_index"] == 0 and payload["do_action_info"]["action_list"] == ["deal_gang_tile"]
    )

    assert jiagang_payload["do_action_info"]["combination_target"] == "k15"
    assert jiagang_payload["do_action_info"]["combination_mask"] == [3, 15, 1, 15, 0, 15, 0, 15]
    assert gang_draw_payload["do_action_info"]["deal_tile"] == 33


def test_continue_after_discard_responses_multi_ron_returns_next_hand_window() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
    game.tiles_list = [33, 34]
    game.player_list[0].hand_tiles = [15]
    game.player_list[1].waiting_tiles = {15}
    game.player_list[2].waiting_tiles = {15}

    tile = game.record_discard(0, 15)
    window = game.continue_after_discard_responses(
        0,
        tile,
        {1: "hu", 2: "hu"},
        settlements={1: {"points": 6}, 2: {"points": 8}},
    )

    assert window["status"] == "waiting_hand_action"
    assert window["reason"] == "discard_win"
    assert window["player"] == 3
    assert window["drawn_tile"] == 33
    assert window["win_result"]["winners"] == [1, 2]


def test_apply_action_results_mid_multi_ron_marks_recycle_only_on_last_panel() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
    game.tiles_list = [33, 34]
    game.player_list[0].hand_tiles = [15]
    game.player_list[1].waiting_tiles = {15}
    game.player_list[2].waiting_tiles = {15}

    tile = game.record_discard(0, 15)
    window = {
        "status": "waiting_action_after_cut",
        "player": 0,
        "tile": tile,
        "actions": {1: ["hu", "pass"], 2: ["hu", "pass"]},
    }

    next_window = game.apply_action_results(
        window,
        {
            1: {"action_type": "hu"},
            2: {"action_type": "hu"},
        },
        settlements={1: {"points": 6, "score_changes": [-36, 36, 0, 0]}, 2: {"points": 8, "score_changes": [-48, 0, 48, 0]}},
    )

    assert next_window["status"] == "waiting_hand_action"
    panels = [
        payload
        for payload in game.outbound_payloads
        if payload.get("type") == "gamestate/jiandan/show_result"
        and payload.get("player_index") == 0
        and payload.get("show_result_info", {}).get("defer_score_settlement") is True
    ]
    assert [payload["show_result_info"]["hepai_player_index"] for payload in panels] == [1, 2]
    assert [payload["show_result_info"]["multi_ron"] for payload in panels] == [True, True]
    assert [payload["show_result_info"]["recycle_discard"] for payload in panels] == [False, True]
    viewer0_payloads = [
        payload
        for payload in game.outbound_payloads
        if payload.get("player_index") == 0
        or payload.get("type") == "gamestate/jiandan/_internal_mid_hand_hu_delay"
    ]
    delay_indexes = [
        i for i, payload in enumerate(viewer0_payloads)
        if payload.get("type") == "gamestate/jiandan/_internal_mid_hand_hu_delay"
    ]
    panel_indexes = [
        i for i, payload in enumerate(viewer0_payloads)
        if payload.get("type") == "gamestate/jiandan/show_result"
        and payload.get("show_result_info", {}).get("defer_score_settlement") is True
    ]
    assert len(delay_indexes) == 2
    assert panel_indexes[0] < delay_indexes[0] < panel_indexes[1] < delay_indexes[1]
    assert viewer0_payloads[delay_indexes[0]]["delay_seconds"] == 0.5


def test_apply_action_results_terminal_discard_win_emits_tile_move_then_final_settlement() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
    game.tiles_list = [33, 34]
    game.player_list[0].is_hu = True
    game.player_list[1].is_hu = True
    game.hu_order_counter = 2
    game.deferred_hu_settlements = [
        {"source": "self_draw", "tile": 11, "winner": 0, "points": 8, "hu_order": 1},
        {"source": "self_draw", "tile": 12, "winner": 1, "points": 8, "hu_order": 2},
    ]
    game.player_list[2].hand_tiles = [41]
    game.player_list[3].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 45, 45, 45, 41]
    game.player_list[3].waiting_tiles = {41}

    cut_tile = game.record_discard(2, 41)
    window = {
        "status": "waiting_action_after_cut",
        "player": 2,
        "tile": cut_tile,
        "actions": {3: ["hu", "pass"]},
    }
    next_window = game.apply_action_results(window, {3: {"action_type": "hu"}})

    assert next_window["status"] == "END"
    assert game.game_status == "END"
    assert game.player_list[3].is_hu
    assert game.deferred_hu_settlements[-1]["winner"] == 3
    assert game.deferred_hu_settlements[-1]["source"] == "discard"
    terminal_tile_move_payloads = [
        payload
        for payload in game.outbound_payloads
        if payload.get("type") == "gamestate/jiandan/show_result"
        and payload.get("player_index") == 0
        and payload.get("show_result_info", {}).get("defer_score_settlement") is True
    ]
    assert len(terminal_tile_move_payloads) == 1
    assert terminal_tile_move_payloads[0]["show_result_info"]["hepai_player_index"] == 3
    assert terminal_tile_move_payloads[0]["show_result_info"]["recycle_discard"] is True
    assert not any(
        payload.get("type") == "gamestate/jiandan/show_result"
        and payload.get("show_result_info", {}).get("defer_score_settlement") is True
        and payload.get("show_result_info", {}).get("hepai_player_index") in (0, 1)
        for payload in game.outbound_payloads
    )
    final_payloads = [
        payload
        for payload in game.outbound_payloads
        if payload.get("type") == "gamestate/jiandan/show_result"
        and payload.get("show_result_info", {}).get("liuju_step") == "settle_hu"
    ]
    assert len(final_payloads) == 4 * 3


def test_apply_action_results_terminal_multi_ron_emits_each_final_settlement() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
    game.tiles_list = [33, 34]
    game.player_list[0].is_hu = True
    game.hu_order_counter = 1
    game.deferred_hu_settlements = [
        {"source": "self_draw", "tile": 11, "winner": 0, "points": 8, "hu_order": 1},
    ]
    game.player_list[1].hand_tiles = [41]
    game.player_list[2].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 45, 45, 45, 41]
    game.player_list[2].waiting_tiles = {41}
    game.player_list[3].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 46, 46, 46, 41]
    game.player_list[3].waiting_tiles = {41}

    cut_tile = game.record_discard(1, 41)
    window = {
        "status": "waiting_action_after_cut",
        "player": 1,
        "tile": cut_tile,
        "actions": {2: ["hu", "pass"], 3: ["hu", "pass"]},
    }
    next_window = game.apply_action_results(
        window,
        {
            2: {"action_type": "hu"},
            3: {"action_type": "hu"},
        },
    )

    assert next_window["status"] == "END"
    assert [settlement["winner"] for settlement in game.deferred_hu_settlements] == [0, 2, 3]
    terminal_tile_move_payloads = [
        payload
        for payload in game.outbound_payloads
        if payload.get("type") == "gamestate/jiandan/show_result"
        and payload.get("player_index") == 0
        and payload.get("show_result_info", {}).get("defer_score_settlement") is True
    ]
    assert [payload["show_result_info"]["hepai_player_index"] for payload in terminal_tile_move_payloads] == [2, 3]
    assert [payload["show_result_info"]["multi_ron"] for payload in terminal_tile_move_payloads] == [True, True]
    assert [payload["show_result_info"]["recycle_discard"] for payload in terminal_tile_move_payloads] == [False, True]
    assert not any(
        payload.get("type") == "gamestate/jiandan/show_result"
        and payload.get("show_result_info", {}).get("defer_score_settlement") is True
        and payload.get("show_result_info", {}).get("hepai_player_index") == 0
        for payload in game.outbound_payloads
    )
    final_payloads = [
        payload
        for payload in game.outbound_payloads
        if payload.get("type") == "gamestate/jiandan/show_result"
        and payload.get("show_result_info", {}).get("liuju_step") == "settle_hu"
    ]
    assert len(final_payloads) == 4 * 3
    viewer_zero_panels = [payload for payload in final_payloads if payload.get("player_index") == 0]
    assert [payload["show_result_info"]["hepai_player_index"] for payload in viewer_zero_panels] == [0, 2, 3]
    assert viewer_zero_panels[-1]["show_result_info"]["liuju_status_final"] is True


def test_continue_after_discard_responses_skips_claims_when_anyone_wins() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
        player.combination_tiles = []
    game.tiles_list = [33, 34]
    game.player_list[0].hand_tiles = [15]
    game.player_list[1].waiting_tiles = {15}
    game.player_list[2].hand_tiles = [15, 15, 31]

    tile = game.record_discard(0, 15)
    window = game.continue_after_discard_responses(
        0,
        tile,
        {1: "hu"},
        {2: "peng"},
        settlements={1: {"points": 6}},
    )

    assert window["status"] == "waiting_hand_action"
    assert window["reason"] == "discard_win"
    assert window["player"] == 2
    assert window["drawn_tile"] == 33
    assert game.player_list[2].combination_tiles == []
    assert game.player_list[2].hand_tiles == [15, 15, 31, 33]


def test_continue_after_discard_responses_claim_returns_only_cut_window() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
        player.combination_tiles = []
    game.player_list[0].hand_tiles = [15]
    game.player_list[2].hand_tiles = [15, 15, 31]

    tile = game.record_discard(0, 15)
    window = game.continue_after_discard_responses(0, tile, {}, {2: "peng"})

    assert window["status"] == "onlycut_after_action"
    assert window["reason"] == "discard_claim"
    assert window["player"] == 2
    assert window["claim_result"]["meld_code"] == "k15"
    assert window["actions"][2] == ["cut"]


def test_apply_action_results_discard_claim_gang_emits_supplement_draw() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
        player.combination_tiles = []
        player.combination_mask = []
    game.tiles_list = [33, 34]
    game.player_list[0].hand_tiles = [15]
    game.player_list[3].hand_tiles = [15, 15, 15, 41]

    cut_tile = game.record_discard(0, 15)
    window = {
        "status": "waiting_action_after_cut",
        "player": 0,
        "tile": cut_tile,
        "actions": {3: ["gang", "pass"]},
    }

    next_window = game.apply_action_results(window, {3: {"action_type": "gang"}})

    assert next_window["status"] == "waiting_hand_action"
    assert next_window["reason"] == "discard_gang"
    action_payloads = [
        payload
        for payload in game.outbound_payloads
        if payload.get("type") == "gamestate/jiandan/do_action"
    ]
    claim_payload = next(
        payload for payload in action_payloads
        if payload["player_index"] == 0 and payload["do_action_info"]["action_list"] == ["gang"]
    )
    gang_draw_payload = next(
        payload for payload in action_payloads
        if payload["player_index"] == 3 and payload["do_action_info"]["action_list"] == ["deal_gang_tile"]
    )

    assert claim_payload["do_action_info"]["combination_target"] == "g15"
    assert gang_draw_payload["do_action_info"]["deal_tile"] == 33


def test_continue_after_discard_responses_no_claim_returns_next_draw_window() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
    game.tiles_list = [33]
    game.player_list[0].hand_tiles = [15]
    game.player_list[2].waiting_tiles = {15}

    tile = game.record_discard(0, 15)
    window = game.continue_after_discard_responses(0, tile, {2: "pass"}, {2: "pass"})

    assert window["status"] == "waiting_hand_action"
    assert window["reason"] == "discard_no_claim"
    assert window["player"] == 1
    assert window["drawn_tile"] == 33
    assert not game.can_win_by_discard(2, 15)


def test_continue_after_final_discard_no_win_ends_by_wall() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
        player.combination_tiles = []
    game.tiles_list = []
    game.current_player_index = 0
    game.player_list[0].hand_tiles = [15]

    discard_window = game.apply_turn_action(0, "cut", tile=15)
    assert discard_window["status"] == "waiting_action_after_cut"
    assert discard_window["actions"] == {0: [], 1: [], 2: [], 3: []}

    window = game.continue_after_discard_responses(0, 15, {}, {})
    assert window["status"] == "END"
    assert window["ended_by"] == "wall"
    assert window["claim_result"]["drawn_tile"] is None
    assert game.game_status == "END"
    assert game.ended_by == "wall"


def test_continue_after_rob_kong_responses_unrobbed_returns_hand_window() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
        player.combination_tiles = []
    game.tiles_list = [33, 34]
    game.player_list[0].hand_tiles = [15, 41]
    game.player_list[0].combination_tiles = ["k15"]
    game.player_list[2].waiting_tiles = {15}
    game.attempt_added_kong(0, 15)

    window = game.continue_after_rob_kong_responses(0, 15, {2: "pass"})

    assert window["status"] == "waiting_hand_action"
    assert window["reason"] == "added_kong"
    assert window["player"] == 0
    assert window["drawn_tile"] == 33
    assert window["rob_kong_result"]["meld_code"] == "g15"


def test_continue_after_rob_kong_responses_robbed_returns_next_draw_window() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
        player.combination_tiles = []
    game.tiles_list = [33, 34]
    game.player_list[0].hand_tiles = [15, 41]
    game.player_list[0].combination_tiles = ["k15"]
    game.player_list[2].waiting_tiles = {15}
    game.attempt_added_kong(0, 15)

    window = game.continue_after_rob_kong_responses(0, 15, {2: "hu"}, {2: {"points": 8}})

    assert window["status"] == "waiting_hand_action"
    assert window["reason"] == "rob_kong"
    assert window["player"] == 3
    assert window["drawn_tile"] == 33
    assert window["rob_kong_result"]["winners"] == [2]
    assert game.current_player_index == 3
    assert game.player_list[3].hand_tiles == [33]
    assert game.player_list[0].combination_tiles == ["k15"]


def test_rob_kong_continues_from_winner_next_seat_not_kong_player_next_seat() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
        player.combination_tiles = []
    game.tiles_list = [33, 34]
    game.player_list[3].hand_tiles = [15, 41]
    game.player_list[3].combination_tiles = ["k15"]
    game.player_list[2].waiting_tiles = {15}
    game.attempt_added_kong(3, 15)

    window = game.continue_after_rob_kong_responses(3, 15, {2: "hu"}, {2: {"points": 8}})

    assert window["status"] == "waiting_hand_action"
    assert window["reason"] == "rob_kong"
    assert window["player"] == 3
    assert window["drawn_tile"] == 33
    assert game.current_player_index == 3
    assert game.player_list[3].hand_tiles == [41, 33]


def test_apply_action_results_robbed_kong_emits_hu_result_and_normal_draw() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
        player.combination_tiles = []
    game.tiles_list = [33, 34]
    game.player_list[0].hand_tiles = [15, 41]
    game.player_list[0].combination_tiles = ["k15"]
    game.player_list[2].waiting_tiles = {15}
    game.attempt_added_kong(0, 15)
    window = {
        "status": "waiting_action_qianggang",
        "player": 0,
        "tile": 15,
        "actions": {2: ["hu", "pass"]},
    }

    next_window = game.apply_action_results(
        window,
        {2: {"action_type": "hu"}},
        settlements={2: {"points": 8}},
    )

    assert next_window["status"] == "waiting_hand_action"
    assert next_window["player"] == 3
    action_payloads = [
        payload
        for payload in game.outbound_payloads
        if payload.get("type") == "gamestate/jiandan/do_action"
    ]
    assert any(
        payload["do_action_info"]["action_list"] == ["hu_second"]
        and payload["do_action_info"]["action_player"] == 2
        for payload in action_payloads
    )
    assert any(
        payload["do_action_info"]["action_list"] == ["deal_tile"]
        and payload["do_action_info"]["action_player"] == 3
        and payload["do_action_info"]["deal_tile"] == 33
        for payload in action_payloads
    )
    assert not any(
        payload["do_action_info"]["action_list"] == ["deal_gang_tile"]
        for payload in action_payloads
    )
    mid_hand_payloads = [
        payload
        for payload in game.outbound_payloads
        if payload.get("type") == "gamestate/jiandan/show_result"
        and payload.get("show_result_info", {}).get("defer_score_settlement") is True
    ]
    assert mid_hand_payloads
    assert mid_hand_payloads[0]["show_result_info"]["hepai_player_index"] == 2
    assert mid_hand_payloads[0]["show_result_info"]["is_qianggang"] is True


def test_apply_action_results_robbed_kong_as_third_win_ends_hand_with_final_panels() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
        player.combination_tiles = []
    game.tiles_list = [33, 34]
    game.player_list[0].is_hu = True
    game.player_list[1].is_hu = True
    game.hu_order_counter = 2
    game.deferred_hu_settlements = [
        {"source": "self_draw", "tile": 11, "winner": 0, "points": 8, "hu_order": 1},
        {"source": "discard", "discarder": 3, "tile": 12, "winner": 1, "points": 8, "hu_order": 2},
    ]
    game.player_list[3].hand_tiles = [15, 41]
    game.player_list[3].combination_tiles = ["k15"]
    game.player_list[2].waiting_tiles = {15}
    game.attempt_added_kong(3, 15)
    window = {
        "status": "waiting_action_qianggang",
        "player": 3,
        "tile": 15,
        "actions": {2: ["hu", "pass"]},
    }

    next_window = game.apply_action_results(
        window,
        {2: {"action_type": "hu"}},
        settlements={2: {"points": 8}},
    )

    assert next_window["status"] == "END"
    assert game.game_status == "END"
    assert [settlement["winner"] for settlement in game.deferred_hu_settlements] == [0, 1, 2]
    action_payloads = [
        payload
        for payload in game.outbound_payloads
        if payload.get("type") == "gamestate/jiandan/do_action"
    ]
    assert any(
        payload["do_action_info"]["action_list"] == ["hu_third"]
        and payload["do_action_info"]["action_player"] == 2
        for payload in action_payloads
    )
    assert not any(
        payload["do_action_info"]["action_list"] in (["deal_tile"], ["deal_gang_tile"])
        for payload in action_payloads
    )
    terminal_tile_move_payloads = [
        payload
        for payload in game.outbound_payloads
        if payload.get("type") == "gamestate/jiandan/show_result"
        and payload.get("player_index") == 0
        and payload.get("show_result_info", {}).get("defer_score_settlement") is True
    ]
    assert len(terminal_tile_move_payloads) == 1
    assert terminal_tile_move_payloads[0]["show_result_info"]["hepai_player_index"] == 2
    assert terminal_tile_move_payloads[0]["show_result_info"]["is_qianggang"] is True
    final_payloads = [
        payload
        for payload in game.outbound_payloads
        if payload.get("type") == "gamestate/jiandan/show_result"
        and payload.get("show_result_info", {}).get("liuju_step") == "settle_hu"
    ]
    assert len(final_payloads) == 4 * 3
    viewer_zero_panels = [payload for payload in final_payloads if payload.get("player_index") == 0]
    assert [payload["show_result_info"]["hepai_player_index"] for payload in viewer_zero_panels] == [0, 1, 2]
    assert viewer_zero_panels[-1]["show_result_info"]["is_qianggang"] is True
    assert viewer_zero_panels[-1]["show_result_info"]["liuju_status_final"] is True


def test_apply_action_results_multi_robbed_kong_ends_hand_and_scores_chankan() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
        player.combination_tiles = []
    game.tiles_list = [33, 34]
    game.player_list[0].hand_tiles = [15, 41]
    game.player_list[0].combination_tiles = ["k15"]
    for winner_index in (1, 2, 3):
        game.player_list[winner_index].hand_tiles = [
            11, 12, 13,
            21, 22, 23,
            31, 32, 33,
            45, 45, 45,
            15,
        ]
        game.player_list[winner_index].waiting_tiles = {15}
    game.attempt_added_kong(0, 15)
    window = {
        "status": "waiting_action_qianggang",
        "player": 0,
        "tile": 15,
        "actions": {
            1: ["hu", "pass"],
            2: ["hu", "pass"],
            3: ["hu", "pass"],
        },
    }

    next_window = game.apply_action_results(
        window,
        {
            1: {"action_type": "hu"},
            2: {"action_type": "hu"},
            3: {"action_type": "hu"},
        },
    )

    assert next_window["status"] == "END"
    assert next_window["rob_kong_result"]["winners"] == [1, 2, 3]
    assert game.game_status == "END"
    assert [settlement["winner"] for settlement in game.deferred_hu_settlements] == [1, 2, 3]
    assert all(settlement["source"] == "rob_kong" for settlement in game.deferred_hu_settlements)
    assert all("chankan" in settlement["fan_ids"] for settlement in game.deferred_hu_settlements)
    assert all(settlement["score_changes"][0] < 0 for settlement in game.deferred_hu_settlements)
    action_payloads = [
        payload
        for payload in game.outbound_payloads
        if payload.get("type") == "gamestate/jiandan/do_action"
    ]
    hu_actions = [
        payload["do_action_info"]["action_list"][0]
        for payload in action_payloads
        if payload.get("player_index") == 0
        and payload["do_action_info"]["action_list"][0].startswith("hu_")
    ]
    assert hu_actions == ["hu_first", "hu_second", "hu_third"]
    assert not any(
        payload["do_action_info"]["action_list"] in (["deal_tile"], ["deal_gang_tile"])
        for payload in action_payloads
    )
    terminal_tile_move_payloads = [
        payload
        for payload in game.outbound_payloads
        if payload.get("type") == "gamestate/jiandan/show_result"
        and payload.get("player_index") == 0
        and payload.get("show_result_info", {}).get("defer_score_settlement") is True
    ]
    assert [payload["show_result_info"]["hepai_player_index"] for payload in terminal_tile_move_payloads] == [1, 2, 3]
    assert [payload["show_result_info"]["recycle_discard"] for payload in terminal_tile_move_payloads] == [False, False, True]
    assert all(payload["show_result_info"]["is_qianggang"] is True for payload in terminal_tile_move_payloads)
    final_payloads = [
        payload
        for payload in game.outbound_payloads
        if payload.get("type") == "gamestate/jiandan/show_result"
        and payload.get("show_result_info", {}).get("liuju_step") == "settle_hu"
    ]
    assert len(final_payloads) == 4 * 3
    viewer_zero_panels = [payload for payload in final_payloads if payload.get("player_index") == 0]
    assert [payload["show_result_info"]["hepai_player_index"] for payload in viewer_zero_panels] == [1, 2, 3]
    assert all(payload["show_result_info"]["is_qianggang"] is True for payload in viewer_zero_panels)
    assert all("chankan" in payload["show_result_info"]["hu_fan"] for payload in viewer_zero_panels)
    assert viewer_zero_panels[-1]["show_result_info"]["liuju_status_final"] is True


def test_context_fans_are_carried_into_final_settlement_payloads() -> None:
    for fan_id, setup in [
        ("rinshan", lambda game: _setup_context_fan_self_draw(game, is_gang_draw=True)),
        ("heavenly_win", lambda game: _setup_context_fan_self_draw(game, heavenly=True)),
        ("haitei", lambda game: _setup_context_fan_self_draw(game, wall_empty=True)),
        ("houtei", _setup_context_fan_houtei),
        ("chankan", _setup_context_fan_chankan),
    ]:
        game = JiandanGameState()
        game.initialize_round()
        setup(game)
        payload = final_settlement_payloads(game, 0)[-1]

        assert fan_id in game.deferred_hu_settlements[-1]["fan_ids"]
        assert fan_id in payload["show_result_info"]["hu_fan"]


def _setup_context_fan_self_draw(
    game: JiandanGameState,
    *,
    is_gang_draw: bool = False,
    heavenly: bool = False,
    wall_empty: bool = False,
) -> None:
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
    game.player_list[0].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 45, 45, 45, 41, 41]
    game.hand_action_is_gang_draw[0] = is_gang_draw
    game.opening_action_taken = not heavenly
    if wall_empty:
        game.tiles_list = []
    game.record_self_draw_win(0, 41)


def _setup_context_fan_houtei(game: JiandanGameState) -> None:
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
    game.tiles_list = []
    game.player_list[1].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 45, 45, 45, 41]
    game.record_discard_win(1, 0, 41)


def _setup_context_fan_chankan(game: JiandanGameState) -> None:
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
        player.combination_tiles = []
    game.player_list[0].hand_tiles = [15]
    game.player_list[0].combination_tiles = ["k15"]
    game.player_list[1].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 45, 45, 45, 15]
    game.player_list[1].waiting_tiles = {15}
    game.resolve_added_kong_responses(0, 15, {1: "hu"})


def test_scripted_flow_discard_claim_forced_cut_discard_win_next_draw() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
        player.combination_tiles = []
        player.discard_tiles = []
    game.tiles_list = [33, 34]
    game.current_player_index = 0
    game.player_list[0].hand_tiles = [15]
    game.player_list[1].hand_tiles = [11, 12, 13, 21, 22, 23, 32, 33, 34, 45, 45, 45, 31]
    game.player_list[2].hand_tiles = [15, 15, 31]
    game.player_list[3].hand_tiles = [11, 12, 13, 21, 22, 23, 32, 33, 34, 45, 45, 45, 31]

    first_window = game.begin_hand_action(0)
    assert first_window["actions"][0] == ["cut"], first_window

    discard_window = game.apply_turn_action(0, "cut", tile=15)
    assert discard_window["status"] == "waiting_action_after_cut"
    assert "peng" in discard_window["actions"][2], discard_window

    claim_window = game.continue_after_discard_responses(0, 15, {}, {2: "peng"})
    assert claim_window["status"] == "onlycut_after_action"
    assert claim_window["player"] == 2
    assert claim_window["actions"][2] == ["cut"]
    assert game.player_list[2].combination_tiles == ["k15"]

    second_discard_window = game.apply_turn_action(2, "cut", tile=31)
    assert second_discard_window["status"] == "waiting_action_after_cut"
    assert "hu" in second_discard_window["actions"][1], second_discard_window
    assert "hu" in second_discard_window["actions"][3], second_discard_window

    next_window = game.continue_after_discard_responses(
        2,
        31,
        {1: "pass", 3: "hu"},
        settlements={3: {"points": 8}},
    )
    assert next_window["status"] == "waiting_hand_action"
    assert next_window["reason"] == "discard_win"
    assert next_window["player"] == 0
    assert next_window["drawn_tile"] == 33
    assert game.player_list[1].discard_win_lockout_tiles == {31}
    assert game.player_list[3].is_hu
    assert game.deferred_hu_settlements == [
        {"source": "discard", "discarder": 2, "tile": 31, "points": 8, "winner": 3, "hu_order": 1}
    ]
    assert game.player_list[0].hand_tiles == [33]


def test_wait_action_collects_submitted_action() -> None:
    async def scenario() -> None:
        game = JiandanGameState()
        game.action_dict = {0: ["cut"], 1: [], 2: [], 3: []}
        wait_task = asyncio.create_task(game.wait_action(timeout=1.0))
        await asyncio.sleep(0)

        await game.submit_action(0, "cut", TileId=15, cutIndex=2)
        result = await wait_task

        assert result[0]["action_type"] == "cut"
        assert result[0]["TileId"] == 15
        assert result[0]["cutIndex"] == 2
        assert result[0]["cutClass"] is False
        assert game.waiting_players_list == []
        assert game.action_dict[0] == []

    asyncio.run(scenario())


def test_visible_action_payloads_are_addressed_to_each_viewer() -> None:
    game = JiandanGameState()

    payloads = game.emit_visible_action_payloads(
        {"action": "cut", "player": 0, "tile": 15, "cutIndex": 0}
    )

    assert [payload["player_index"] for payload in payloads] == [0, 1, 2, 3]
    assert [payload["player_index"] for payload in game.outbound_payloads[-4:]] == [0, 1, 2, 3]
    assert all(payload["type"] == "gamestate/jiandan/do_action" for payload in payloads)
    assert payloads[0]["do_action_info"]["action_list"] == ["cut"]


def test_wait_action_defaults_pending_pass_on_timeout() -> None:
    async def scenario() -> None:
        game = JiandanGameState()
        game.action_dict = {0: [], 1: ["hu", "pass"], 2: [], 3: []}

        result = await game.wait_action(timeout=0.001)

        assert result[1]["action_type"] == "pass"
        assert game.waiting_players_list == []
        assert game.action_dict[1] == []

    asyncio.run(scenario())


def test_wait_action_defaults_pending_ready_on_timeout() -> None:
    async def scenario() -> None:
        game = JiandanGameState()
        game.action_dict = {0: ["ready"], 1: [], 2: [], 3: []}

        result = await game.wait_action(timeout=0.001)

        assert result[0]["action_type"] == "ready"
        assert game.waiting_players_list == []
        assert game.action_dict[0] == []

    asyncio.run(scenario())


def test_wait_action_defaults_pending_cut_on_timeout_with_draw_slot() -> None:
    async def scenario() -> None:
        game = JiandanGameState()
        game.player_list[0].hand_tiles = [11, 12, 13]
        game.player_list[0].has_draw_slot = True
        game.action_dict = {0: ["cut"], 1: [], 2: [], 3: []}

        result = await game.wait_action(timeout=0.001)

        assert result[0]["action_type"] == "cut"
        assert result[0]["TileId"] == 13
        assert result[0]["cutIndex"] == 2
        assert result[0]["cutClass"] is True
        assert game.waiting_players_list == []
        assert game.action_dict[0] == []

    asyncio.run(scenario())


def test_wait_action_defaults_pending_cut_on_timeout_without_draw_slot() -> None:
    async def scenario() -> None:
        game = JiandanGameState()
        game.player_list[0].hand_tiles = [11, 12, 13]
        game.player_list[0].has_draw_slot = False
        game.action_dict = {0: ["cut"], 1: [], 2: [], 3: []}

        result = await game.wait_action(timeout=0.001)

        assert result[0]["action_type"] == "cut"
        assert result[0]["TileId"] == 13
        assert result[0]["cutIndex"] == 2
        assert result[0]["cutClass"] is False
        assert game.waiting_players_list == []
        assert game.action_dict[0] == []

    asyncio.run(scenario())


def test_auto_bot_cuts_last_tile_after_delay() -> None:
    async def scenario() -> None:
        game = JiandanGameState(room_data={
            "room_id": "bot-delay-test",
            "player_list": [0, 101, 102, 103],
            "player_settings": {0: {"username": "auto-bot"}},
        })
        game.initialize_round()
        for player in game.player_list:
            player.hand_tiles = []
            player.waiting_tiles = set()
        game.player_list[0].hand_tiles = [11, 12, 13]
        game.player_list[0].has_draw_slot = True

        game.open_action_window(game.begin_hand_action(0))
        started = time.perf_counter()
        result = await game.wait_action(timeout=1.0)
        elapsed = time.perf_counter() - started

        assert elapsed >= 0.45
        assert result[0]["action_type"] == "cut"
        assert result[0]["TileId"] == 13
        assert result[0]["cutIndex"] == 2
        assert result[0]["cutClass"] is True
        assert game.waiting_players_list == []
        assert game.action_dict[0] == []
        assert game.bot_action_ticks[0] == game.server_action_tick

    asyncio.run(scenario())


def test_cleanup_cancels_pending_bot_tasks() -> None:
    async def scenario() -> None:
        game = JiandanGameState(room_data={
            "room_id": "bot-cleanup-test",
            "player_list": [0, 101, 102, 103],
            "player_settings": {0: {"username": "auto-bot"}},
        })
        game.initialize_round()
        for player in game.player_list:
            player.hand_tiles = []
        game.player_list[0].hand_tiles = [11]

        game.open_action_window(game.begin_hand_action(0))
        wait_task = asyncio.create_task(game.wait_action(timeout=1.0))
        await asyncio.sleep(0)

        assert game.bot_tasks
        await game.cleanup_game_state()
        assert game.bot_tasks == set()
        wait_task.cancel()
        await asyncio.gather(wait_task, return_exceptions=True)

    asyncio.run(scenario())


def test_submit_action_rejects_non_waiting_or_illegal_action() -> None:
    async def scenario() -> None:
        game = JiandanGameState()
        game.action_dict = {0: ["cut"], 1: [], 2: [], 3: []}
        game.waiting_players_list = [0]

        try:
            await game.submit_action(1, "cut")
        except ValueError:
            pass
        else:
            raise AssertionError("non-waiting player action should be rejected")

        try:
            await game.submit_action(0, "hu")
        except ValueError:
            pass
        else:
            raise AssertionError("illegal action should be rejected")

    asyncio.run(scenario())


def test_disconnect_reconnect_tags_are_local_shell_behavior() -> None:
    async def scenario() -> None:
        game = JiandanGameState()

        await game.player_disconnect(101)
        assert "offline" in game.player_list[0].tag_list

        await game.player_reconnect(101)
        assert "offline" not in game.player_list[0].tag_list

    asyncio.run(scenario())


def test_cleanup_cancels_attached_game_task() -> None:
    async def scenario() -> None:
        game = JiandanGameState()
        game.game_task = asyncio.create_task(asyncio.sleep(10))

        await game.cleanup_game_state()

        assert game.game_task.cancelled()

    asyncio.run(scenario())


def test_run_game_loop_starts_and_can_be_cancelled() -> None:
    async def scenario() -> None:
        game = JiandanGameState()
        game.game_task = asyncio.create_task(game.run_game_loop())
        await asyncio.sleep(0.1)

        assert game.game_status == "waiting_hand_action"
        assert game.waiting_players_list
        assert any(payload["type"] == "gamestate/jiandan/broadcast_hand_action" for payload in game.outbound_payloads)

        await game.cleanup_game_state()
        assert game.game_task.cancelled()

    asyncio.run(scenario())


def test_run_game_loop_sends_game_start_before_first_hand_action() -> None:
    async def scenario() -> None:
        game = JiandanGameState()
        game.game_task = asyncio.create_task(game.run_game_loop())
        await asyncio.sleep(0.1)

        payload_types = [payload["type"] for payload in game.outbound_payloads]
        assert payload_types[:4] == ["gamestate/jiandan/game_start"] * 4
        assert "gamestate/jiandan/broadcast_hand_action" in payload_types[4:]

        await game.cleanup_game_state()
        assert game.game_task.cancelled()

    asyncio.run(scenario())


def test_round_ready_phase_waits_for_human_and_marks_bots_ready() -> None:
    async def scenario() -> None:
        game = JiandanGameState()
        for idx, player in enumerate(game.player_list):
            if idx > 0:
                player.user_id = idx
        ready_task = asyncio.create_task(game.run_round_ready_phase(timeout=1.0))
        await asyncio.sleep(0.1)

        assert game.game_status == "waiting_ready"
        assert game.action_dict[0] == ["ready"]
        assert game.action_dict[1] == []
        ready_payload = next(
            payload
            for payload in reversed(game.outbound_payloads)
            if payload["type"] == "gamestate/jiandan/ready_status"
        )
        assert ready_payload["ready_status_info"]["player_to_ready"][0] is False
        assert ready_payload["ready_status_info"]["player_to_ready"][1] is True

        await game.submit_action(0, "ready")
        results = await ready_task

        assert results[0]["action_type"] == "ready"
        assert game.waiting_players_list == []
        final_ready_payload = next(
            payload
            for payload in reversed(game.outbound_payloads)
            if payload["type"] == "gamestate/jiandan/ready_status"
        )
        assert all(final_ready_payload["ready_status_info"]["player_to_ready"].values())

    asyncio.run(scenario())


def test_result_ready_timeout_matches_draw_panel_duration_without_winners() -> None:
    game = JiandanGameState()
    game.deferred_hu_settlements = []

    assert game.estimated_round_result_ready_timeout() == 2.35


def test_result_ready_timeout_keeps_multi_winner_panel_window() -> None:
    game = JiandanGameState()
    game.deferred_hu_settlements = [{"winner": 0}, {"winner": 1}, {"winner": 2}]

    assert game.estimated_round_result_ready_timeout() == 26.0


def test_final_round_waits_for_ready_before_game_end() -> None:
    async def scenario() -> None:
        game = JiandanGameState()
        game.current_round = game.max_round * 4

        async def end_immediately(timeout=None) -> dict:
            game.game_status = "END"
            return {"status": "END"}

        game.resolve_action_window = end_immediately
        game.game_task = asyncio.create_task(game.run_game_loop())
        for _ in range(100):
            payload_types = [payload["type"] for payload in game.outbound_payloads]
            if "gamestate/jiandan/ready_status" in payload_types:
                break
            await asyncio.sleep(0.01)

        payload_types = [payload["type"] for payload in game.outbound_payloads]
        assert "gamestate/jiandan/ready_status" in payload_types
        assert "gamestate/jiandan/game_end" not in payload_types

        for idx in range(4):
            await game.submit_action(idx, "ready")
        await asyncio.wait_for(game.game_task, timeout=1.0)

        payload_types = [payload["type"] for payload in game.outbound_payloads]
        assert payload_types[-4:] == ["gamestate/jiandan/game_end"] * 4

    asyncio.run(scenario())


def test_advance_round_after_ready_rotates_dealer_and_preserves_scores() -> None:
    game = JiandanGameState()
    game.player_list[0].score = 48
    game.initialize_round()
    game.game_status = "END"

    game.advance_round_after_ready()

    assert game.current_round == 2
    assert game.round_index == 2
    assert game.dealer_index == 1
    assert game.current_player_index == 1
    assert game.player_list[0].score == 48
    assert game.action_dict == {0: [], 1: [], 2: [], 3: []}
    assert game.waiting_players_list == []


def test_recording_initializes_standard_game_record_round() -> None:
    game = JiandanGameState()
    game.start_game_recording()
    game.initialize_round()
    game.start_round_recording()

    title = game.game_record["game_title"]
    round_record = game.game_record["game_round"]["round_index_1"]

    assert title["rule"] == "jiandan"
    assert title["sub_rule"] == "jiandan/standard"
    assert title["hepai_limit"] == 0
    assert round_record["current_round"] == 1
    assert round_record["dealer_index"] == 0
    assert len(round_record["p0_tiles"]) == 14
    assert len(round_record["p1_tiles"]) == 13
    assert round_record["action_ticks"] == []


def test_recording_tracks_visible_cut_claim_and_draw_ticks() -> None:
    game = JiandanGameState()
    game.start_game_recording()
    game.initialize_round()
    game.start_round_recording()

    game.record_visible_action({"action": "cut", "player": 0, "tile": 41, "cutClass": False})
    game.record_visible_action(
        {
            "action": "peng",
            "player": 2,
            "tile": 41,
            "combination_mask": [1, 41, 0, 41, 0, 41],
        }
    )
    game.record_visible_action({"action": "deal_tile", "player": 1, "tile": 33})

    ticks = game.game_record["game_round"]["round_index_1"]["action_ticks"]
    assert ticks == [
        ["c", 41, "F"],
        ["p", 41, 2, 41, 41],
        ["d", 33],
    ]


def test_recording_finalizes_deferred_hu_at_round_end() -> None:
    game = JiandanGameState()
    game.start_game_recording()
    game.initialize_round()
    game.start_round_recording()
    game.deferred_hu_settlements = [
        {
            "source": "discard",
            "discarder": 0,
            "winner": 2,
            "tile": 41,
            "points": 8,
            "fan_ids": ["duiduihu"],
            "score_changes": [-48, 0, 48, 0],
        }
    ]

    game.finalize_round_recording()
    game.finalize_game_recording()

    ticks = game.game_record["game_round"]["round_index_1"]["action_ticks"]
    assert ticks[-2:] == [
        ["hu_second", 2, 8, ["duiduihu"], [-48, 0, 48, 0], 41, 0],
        ["end"],
    ]
    assert game.player_list[2].record_counter.dianhe_times == 1
    assert game.player_list[2].record_counter.win_score == 8
    assert game.player_list[0].record_counter.fangchong_times == 1
    assert "end_time" in game.game_record["game_title"]


def test_recording_finalizes_wall_draw_round() -> None:
    game = JiandanGameState()
    game.start_game_recording()
    game.initialize_round()
    game.start_round_recording()

    game.finalize_round_recording()

    ticks = game.game_record["game_round"]["round_index_1"]["action_ticks"]
    assert ticks[-2:] == [["liuju"], ["end"]]


def test_persist_game_record_uses_jiandan_database_adapter() -> None:
    calls = []

    class FakeDatabase:
        def store_jiandan_game_record(
            self,
            game_record: dict,
            player_list: list,
            room_type: str,
            match_type: str,
        ) -> str:
            calls.append((game_record, player_list, room_type, match_type))
            return "record-id"

    game = JiandanGameState(db_manager=FakeDatabase())
    game.start_game_recording()

    assert game.persist_game_record() == "record-id"
    assert len(calls) == 1
    assert calls[0][0] is game.game_record
    assert calls[0][1] is game.player_list
    assert calls[0][2:] == ("custom", "1/4")


def test_open_action_window_sets_live_action_fields() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
    game.player_list[0].hand_tiles = [41]

    window = game.open_action_window(game.begin_hand_action(0))

    assert window["action_tick"] == 1
    assert game.live_pending_window is window
    assert game.action_dict[0] == ["cut"]
    assert game.waiting_players_list == [0]
    assert game.outbound_payloads[-1]["type"] == "gamestate/jiandan/broadcast_hand_action"
    assert game.outbound_payloads[-1]["action_list"] == ["cut"]


def test_resolve_action_window_applies_queued_cut() -> None:
    async def scenario() -> None:
        game = JiandanGameState()
        game.initialize_round()
        for player in game.player_list:
            player.hand_tiles = []
            player.waiting_tiles = set()
        game.player_list[0].hand_tiles = [41]
        game.player_list[2].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 45, 45, 45, 41]

        game.open_action_window(game.begin_hand_action(0))
        resolve_task = asyncio.create_task(game.resolve_action_window(timeout=1.0))
        await asyncio.sleep(0)
        await game.submit_action(0, "cut", TileId=41)
        window = await resolve_task

        assert window["status"] == "waiting_action_after_cut"
        assert window["tile"] == 41
        assert "hu" in window["actions"][2]
        assert game.action_dict[2] == ["hu", "pass"]
        assert game.waiting_players_list == [2]

    asyncio.run(scenario())


def test_resolve_action_window_applies_discard_win_and_opens_next_draw() -> None:
    async def scenario() -> None:
        game = JiandanGameState()
        game.initialize_round()
        for player in game.player_list:
            player.hand_tiles = []
            player.waiting_tiles = set()
        game.tiles_list = [33, 34]
        game.player_list[0].hand_tiles = [41]
        game.player_list[2].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 45, 45, 45, 41]

        discard_window = game.open_action_window(game.apply_turn_action(0, "cut", tile=41))
        resolve_task = asyncio.create_task(game.resolve_action_window(timeout=1.0, settlements={2: {"points": 8}}))
        await asyncio.sleep(0)
        await game.submit_action(2, "hu")
        next_window = await resolve_task

        assert discard_window["status"] == "waiting_action_after_cut"
        assert next_window["status"] == "waiting_hand_action"
        assert next_window["reason"] == "discard_win"
        assert next_window["player"] == 3
        assert next_window["drawn_tile"] == 33
        assert game.player_list[2].is_hu
        assert game.player_list[3].hand_tiles == [33]
        assert game.deferred_hu_settlements == [
            {"source": "discard", "discarder": 0, "tile": 41, "points": 8, "winner": 2, "hu_order": 1}
        ]

    asyncio.run(scenario())


def test_apply_action_results_resolves_discard_claim_window() -> None:
    game = JiandanGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
        player.combination_tiles = []
    game.player_list[0].hand_tiles = [15]
    game.player_list[2].hand_tiles = [15, 15, 31]

    window = game.apply_turn_action(0, "cut", tile=15)
    next_window = game.apply_action_results(
        window,
        {2: {"action_type": "peng", "target_tile": None, "TileId": None, "cutIndex": -1, "cutClass": False}},
    )

    assert next_window["status"] == "onlycut_after_action"
    assert next_window["reason"] == "discard_claim"
    assert next_window["player"] == 2
    assert game.player_list[2].combination_tiles == ["k15"]
    assert game.action_dict[2] == ["cut"]
    claim_payloads = [
        payload
        for payload in game.outbound_payloads
        if payload.get("type") == "gamestate/jiandan/do_action"
        and payload["do_action_info"]["action_list"] == ["peng"]
    ]
    assert claim_payloads
    assert claim_payloads[0]["do_action_info"]["combination_mask"] == [1, 15, 0, 15, 0, 15]


def test_flush_outbound_payloads_sends_to_connected_player() -> None:
    async def scenario() -> None:
        game = JiandanGameState()
        websocket = FakeWebSocket()
        game.game_server = SimpleNamespace(
            user_id_to_connection={
                101: SimpleNamespace(websocket=websocket),
            }
        )
        game.initialize_round()
        for player in game.player_list:
            player.hand_tiles = []
        game.player_list[0].hand_tiles = [41]

        game.open_action_window(game.begin_hand_action(0))
        await game.flush_outbound_payloads()

        assert websocket.sent
        assert websocket.sent[0]["type"] == "gamestate/jiandan/broadcast_hand_action"
        assert websocket.sent[0]["player_index"] == 0
        assert game.websocket_sent_payloads == websocket.sent
        assert game.outbound_send_cursor == len(game.outbound_payloads)

    asyncio.run(scenario())


def test_send_payload_to_player_without_connection_keeps_outbox_fallback() -> None:
    async def scenario() -> None:
        game = JiandanGameState()
        before = len(game.outbound_payloads)

        sent = await game.send_payload_to_player(0, {"type": "test/jiandan"})

        assert not sent
        assert len(game.outbound_payloads) == before + 1
        assert game.outbound_payloads[-1]["type"] == "test/jiandan"
        assert game.outbound_payloads[-1]["player_index"] == 0

    asyncio.run(scenario())


def test_player_reconnect_sends_game_start_then_pending_action_payload() -> None:
    async def scenario() -> None:
        game = JiandanGameState()
        websocket = FakeWebSocket()
        game.game_server = SimpleNamespace(
            user_id_to_connection={
                102: SimpleNamespace(websocket=websocket),
            }
        )
        game.player_list[0].hand_tiles = [11, 12, 13]
        game.player_list[0].combination_tiles = ["G15"]
        game.player_list[1].hand_tiles = [21, 22, 23]
        game.player_list[1].tag_list = ["offline"]
        game.game_status = "waiting_action_after_cut"
        game.live_pending_window = {"status": "waiting_action_after_cut", "tile": 41}
        game.action_dict = {0: [], 1: ["hu", "pass"], 2: [], 3: []}

        await game.player_reconnect(102)

        assert "offline" not in game.player_list[1].tag_list
        assert [payload["type"] for payload in websocket.sent[-2:]] == [
            "gamestate/jiandan/game_start",
            "gamestate/jiandan/ask_other_action",
        ]
        game_start = websocket.sent[-2]
        pending_action = websocket.sent[-1]
        assert game_start["player_index"] == 1
        assert game_start["game_info"]["players_info"][0]["hand_tiles"] is None
        assert game_start["game_info"]["players_info"][0]["combination_tiles"] == ["G0"]
        assert game_start["game_info"]["players_info"][1]["hand_tiles"] == [21, 22, 23]
        assert pending_action["player_index"] == 1
        assert pending_action["action_list"] == ["hu", "pass"]
        assert pending_action["ask_other_action_info"]["cut_tile"] == 41

    asyncio.run(scenario())


def test_complete_game_lifecycle_sends_ready_game_end_and_finishes_room() -> None:
    async def scenario() -> None:
        cleanup_calls = []
        finish_calls = []

        class FakeManager:
            async def cleanup_game_state_complete(self, gamestate_id: str = None, room_id: str = None) -> None:
                cleanup_calls.append((gamestate_id, room_id))

        class FakeRoomManager:
            async def finish_custom_game_room(self, room_id: str) -> None:
                finish_calls.append(room_id)

        game = JiandanGameState()
        game.game_server = SimpleNamespace(
            user_id_to_connection={},
            gamestate_manager=FakeManager(),
            room_manager=FakeRoomManager(),
        )
        game.game_status = "END"
        game.player_list[0].score = 20

        await game.complete_game_lifecycle()

        payload_types = [payload["type"] for payload in game.outbound_payloads]
        assert payload_types[-8:-4] == ["gamestate/jiandan/ready_status"] * 4
        assert payload_types[-4:] == ["gamestate/jiandan/game_end"] * 4
        assert game.player_list[0].record_counter.rank_result == 1
        assert cleanup_calls == [(game.gamestate_id, None)]
        assert finish_calls == [game.room_id]

    asyncio.run(scenario())


def run() -> None:
    tests = [
        test_wall_is_136_no_flowers_and_deal_shape,
        test_fixed_dealer_rotation,
        test_third_winner_flow_end_conditions,
        test_wall_exhaustion_ends_hand,
        test_next_active_skips_winners,
        test_discard_win_lockout_helpers,
        test_discard_pass_lockout_clears_and_restarts_on_own_discard,
        test_discard_win_defers_settlement_and_next_draw_skips_winner,
        test_draw_after_discard_resolution_ends_on_empty_wall,
        test_resolve_discard_win_responses_allows_independent_multi_ron,
        test_discard_win_continues_from_winner_next_seat_not_discarder_next_seat,
        test_discard_win_with_pass_locks_only_passing_non_winner,
        test_resolve_discard_win_responses_ends_after_third_winner_without_draw,
        test_resolve_discard_win_responses_no_winner_only_records_passes,
        test_resolve_discard_win_responses_rejects_locked_out_win,
        test_resolve_discard_claim_prefers_peng_over_chi_and_forces_cut,
        test_resolve_discard_claim_chi_only_from_fixed_next_seat,
        test_resolve_discard_claim_chi_returns_unity_combination_mask,
        test_resolve_discard_claim_gang_draws_supplement_tile,
        test_resolve_discard_claim_no_claim_draws_next_active_player,
        test_record_self_draw_win_defers_settlement,
        test_zero_point_win_with_empty_fans_is_preserved_in_deferred_settlement,
        test_calculated_discard_win_settlement_scores_only_discarder,
        test_calculated_multi_ron_settlements_each_charge_discarder,
        test_calculated_self_draw_settlement_scores_remaining_non_winners,
        test_declare_concealed_kong_draws_supplement_and_hides_public_tile,
        test_added_kong_without_robbery_upgrades_triplet_and_draws_supplement,
        test_added_kong_robbed_does_not_upgrade_or_draw_supplement,
        test_added_kong_robbery_respects_same_tile_lockout,
        test_begin_hand_action_refreshes_waiting_from_pre_draw_tiles,
        test_apply_turn_cut_refreshes_waits_and_opens_discard_response_window,
        test_apply_turn_self_draw_win_continues_to_next_player_draw,
        test_apply_action_results_self_draw_win_emits_deferred_show_result,
        test_apply_action_results_third_self_draw_win_with_zero_target_ends_hand,
        test_apply_turn_concealed_kong_returns_followup_hand_action_window,
        test_apply_action_results_concealed_kong_emits_mask_and_supplement_draw,
        test_concealed_kong_supplement_self_draw_scores_rinshan,
        test_opening_self_draw_context_scores_heavenly_and_earthly_win,
        test_last_tile_context_scores_haitei_and_houtei,
        test_pre_win_context_scores_nine_gates_in_live_settlement,
        test_discard_win_pre_win_context_scores_nine_gates,
        test_apply_turn_added_kong_opens_rob_kong_window,
        test_apply_action_results_added_kong_pass_emits_meld_update_and_supplement_draw,
        test_continue_after_discard_responses_multi_ron_returns_next_hand_window,
        test_apply_action_results_mid_multi_ron_marks_recycle_only_on_last_panel,
        test_apply_action_results_terminal_discard_win_emits_tile_move_then_final_settlement,
        test_apply_action_results_terminal_multi_ron_emits_each_final_settlement,
        test_continue_after_discard_responses_skips_claims_when_anyone_wins,
        test_continue_after_discard_responses_claim_returns_only_cut_window,
        test_apply_action_results_discard_claim_gang_emits_supplement_draw,
        test_continue_after_discard_responses_no_claim_returns_next_draw_window,
        test_continue_after_final_discard_no_win_ends_by_wall,
        test_continue_after_rob_kong_responses_unrobbed_returns_hand_window,
        test_continue_after_rob_kong_responses_robbed_returns_next_draw_window,
        test_rob_kong_continues_from_winner_next_seat_not_kong_player_next_seat,
        test_apply_action_results_robbed_kong_emits_hu_result_and_normal_draw,
        test_apply_action_results_robbed_kong_as_third_win_ends_hand_with_final_panels,
        test_apply_action_results_multi_robbed_kong_ends_hand_and_scores_chankan,
        test_context_fans_are_carried_into_final_settlement_payloads,
        test_scripted_flow_discard_claim_forced_cut_discard_win_next_draw,
        test_wait_action_collects_submitted_action,
        test_visible_action_payloads_are_addressed_to_each_viewer,
        test_wait_action_defaults_pending_pass_on_timeout,
        test_wait_action_defaults_pending_ready_on_timeout,
        test_wait_action_defaults_pending_cut_on_timeout_with_draw_slot,
        test_wait_action_defaults_pending_cut_on_timeout_without_draw_slot,
        test_auto_bot_cuts_last_tile_after_delay,
        test_cleanup_cancels_pending_bot_tasks,
        test_submit_action_rejects_non_waiting_or_illegal_action,
        test_disconnect_reconnect_tags_are_local_shell_behavior,
        test_cleanup_cancels_attached_game_task,
        test_run_game_loop_starts_and_can_be_cancelled,
        test_run_game_loop_sends_game_start_before_first_hand_action,
        test_round_ready_phase_waits_for_human_and_marks_bots_ready,
        test_result_ready_timeout_matches_draw_panel_duration_without_winners,
        test_result_ready_timeout_keeps_multi_winner_panel_window,
        test_final_round_waits_for_ready_before_game_end,
        test_advance_round_after_ready_rotates_dealer_and_preserves_scores,
        test_recording_initializes_standard_game_record_round,
        test_recording_tracks_visible_cut_claim_and_draw_ticks,
        test_recording_finalizes_deferred_hu_at_round_end,
        test_recording_finalizes_wall_draw_round,
        test_persist_game_record_uses_jiandan_database_adapter,
        test_open_action_window_sets_live_action_fields,
        test_resolve_action_window_applies_queued_cut,
        test_resolve_action_window_applies_discard_win_and_opens_next_draw,
        test_apply_action_results_resolves_discard_claim_window,
        test_flush_outbound_payloads_sends_to_connected_player,
        test_send_payload_to_player_without_connection_keeps_outbox_fallback,
        test_player_reconnect_sends_game_start_then_pending_action_payload,
        test_complete_game_lifecycle_sends_ready_game_end_and_finishes_room,
    ]
    for test in tests:
        test()
    print(f"jiandan gamestate tests ok: {len(tests)} tests")


if __name__ == "__main__":
    run()
