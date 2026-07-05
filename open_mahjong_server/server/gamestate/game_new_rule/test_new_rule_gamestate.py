from __future__ import annotations

import asyncio
from collections import Counter
from pathlib import Path
import sys
from types import SimpleNamespace

SERVER_ROOT = Path(__file__).resolve().parents[3]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from server.gamestate.game_new_rule import NewRuleGameState


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_json(self, payload: dict) -> None:
        self.sent.append(payload)


def test_wall_is_136_no_flowers_and_deal_shape() -> None:
    game = NewRuleGameState()
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
    game = NewRuleGameState()
    assert game.dealer_index == 0
    assert game.advance_dealer_after_round() == 1
    assert game.advance_dealer_after_round() == 2
    assert game.advance_dealer_after_round() == 3
    assert game.advance_dealer_after_round() == 0


def test_blood_battle_end_conditions() -> None:
    game = NewRuleGameState()
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
    game = NewRuleGameState()
    game.initialize_round()
    game.tiles_list.clear()
    assert game.should_end_hand()


def test_next_active_skips_winners() -> None:
    game = NewRuleGameState()
    game.initialize_round()
    game.mark_player_hu(1)
    assert game.next_active_index(0) == 2
    game.mark_player_hu(2)
    assert game.next_active_index(0) == 3


def test_discard_win_lockout_helpers() -> None:
    game = NewRuleGameState()
    game.add_discard_win_lockout(0, 15)
    assert not game.can_win_by_discard(0, 15)
    assert game.can_win_by_discard(0, 16)
    game.clear_lockout_on_discard(0, 19)
    assert game.can_win_by_discard(0, 15)
    assert not game.can_win_by_discard(0, 19)


def test_discard_pass_lockout_clears_and_restarts_on_own_discard() -> None:
    game = NewRuleGameState()
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
    game = NewRuleGameState()
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
    game = NewRuleGameState()
    game.initialize_round()
    game.tiles_list = []
    drawn = game.draw_after_discard_resolution(0)
    assert drawn is None
    assert game.game_status == "END"
    assert game.ended_by == "wall"


def test_resolve_discard_win_responses_allows_independent_multi_ron() -> None:
    game = NewRuleGameState()
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


def test_discard_win_with_pass_locks_only_passing_non_winner() -> None:
    game = NewRuleGameState()
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
    game = NewRuleGameState()
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
    game = NewRuleGameState()
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
    game = NewRuleGameState()
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
    game = NewRuleGameState()
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
    assert game.game_status == "waiting_only_cut"


def test_resolve_discard_claim_chi_only_from_fixed_next_seat() -> None:
    game = NewRuleGameState()
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
    game = NewRuleGameState()
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
    game = NewRuleGameState()
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
    game = NewRuleGameState()
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
    game = NewRuleGameState()
    game.initialize_round()
    game.player_list[0].hand_tiles = [11, 12, 13, 41, 41]

    game.record_self_draw_win(0, 41, {"points": 6})

    assert game.player_list[0].is_hu
    assert game.deferred_hu_settlements == [
        {"source": "self_draw", "tile": 41, "points": 6, "winner": 0, "hu_order": 1}
    ]


def test_zero_point_win_with_empty_fans_is_preserved_in_deferred_settlement() -> None:
    game = NewRuleGameState()
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
    game = NewRuleGameState()
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
    game = NewRuleGameState()
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
    game = NewRuleGameState()
    game.initialize_round()
    game.player_list[1].is_hu = True
    game.player_list[1].hu_order = 1
    game.hu_order_counter = 1
    game.player_list[0].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 45, 45, 45, 15, 15]

    game.record_self_draw_win(0, 15)
    settlement = game.deferred_hu_settlements[0]

    assert settlement["points"] == 5
    assert settlement["score_changes"] == [30, 0, -15, -15]


def test_declare_concealed_kong_draws_supplement_and_hides_public_tile() -> None:
    game = NewRuleGameState()
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
    assert game.game_status == "waiting_hand_action"


def test_added_kong_without_robbery_upgrades_triplet_and_draws_supplement() -> None:
    game = NewRuleGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
        player.combination_tiles = []
    game.tiles_list = [33, 34]
    game.player_list[0].hand_tiles = [15, 41]
    game.player_list[0].combination_tiles = ["k15"]
    game.player_list[2].waiting_tiles = {15}

    attempt = game.attempt_added_kong(0, 15)
    result = game.resolve_added_kong_responses(0, 15, {2: "pass"})

    assert attempt["next_status"] == "waiting_rob_kong"
    assert not result["robbed"]
    assert result["passed"] == [2]
    assert result["meld_code"] == "g15"
    assert result["drawn_tile"] == 33
    assert game.player_list[0].hand_tiles == [41, 33]
    assert game.player_list[0].combination_tiles == ["g15"]
    assert not game.can_win_by_discard(2, 15)
    assert game.game_status == "waiting_hand_action"


def test_added_kong_robbed_does_not_upgrade_or_draw_supplement() -> None:
    game = NewRuleGameState()
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
    assert game.player_list[0].hand_tiles == [15, 41]
    assert game.player_list[0].combination_tiles == ["k15"]
    assert result["draw_player"] == 1
    assert result["drawn_tile"] == 33


def test_added_kong_robbery_respects_same_tile_lockout() -> None:
    game = NewRuleGameState()
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
    game = NewRuleGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
    game.player_list[0].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 45, 45, 45, 41, 41]

    window = game.begin_hand_action(0)

    assert 41 in game.player_list[0].waiting_tiles
    assert "hu_self" in window["actions"][0], window


def test_apply_turn_cut_refreshes_waits_and_opens_discard_response_window() -> None:
    game = NewRuleGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
    game.player_list[0].hand_tiles = [41]
    game.player_list[2].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 45, 45, 45, 41]

    window = game.apply_turn_action(0, "cut", tile=41)

    assert window["status"] == "waiting_discard_response"
    assert "hu" in window["actions"][2], window
    assert game.player_list[0].discard_tiles == [41]


def test_apply_turn_self_draw_win_continues_to_next_player_draw() -> None:
    game = NewRuleGameState()
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


def test_apply_turn_concealed_kong_returns_followup_hand_action_window() -> None:
    game = NewRuleGameState()
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
    assert game.player_list[0].hand_tiles == [41, 33]
    assert window["status"] == "waiting_hand_action"
    assert "cut" in window["actions"][0], window


def test_apply_turn_added_kong_opens_rob_kong_window() -> None:
    game = NewRuleGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
        player.combination_tiles = []
    game.player_list[0].hand_tiles = [15, 41]
    game.player_list[0].combination_tiles = ["k15"]
    game.player_list[2].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 45, 45, 45, 15]

    window = game.apply_turn_action(0, "jiagang", tile=15)

    assert window["status"] == "waiting_rob_kong"
    assert "hu" in window["actions"][2], window
    assert game.player_list[0].combination_tiles == ["k15"]
    assert game.player_list[0].hand_tiles == [15, 41]


def test_continue_after_discard_responses_multi_ron_returns_next_hand_window() -> None:
    game = NewRuleGameState()
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


def test_continue_after_discard_responses_skips_claims_when_anyone_wins() -> None:
    game = NewRuleGameState()
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
    game = NewRuleGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
        player.combination_tiles = []
    game.player_list[0].hand_tiles = [15]
    game.player_list[2].hand_tiles = [15, 15, 31]

    tile = game.record_discard(0, 15)
    window = game.continue_after_discard_responses(0, tile, {}, {2: "peng"})

    assert window["status"] == "waiting_only_cut"
    assert window["reason"] == "discard_claim"
    assert window["player"] == 2
    assert window["claim_result"]["meld_code"] == "k15"
    assert window["actions"][2] == ["cut"]


def test_continue_after_discard_responses_no_claim_returns_next_draw_window() -> None:
    game = NewRuleGameState()
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
    game = NewRuleGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
        player.combination_tiles = []
    game.tiles_list = []
    game.current_player_index = 0
    game.player_list[0].hand_tiles = [15]

    discard_window = game.apply_turn_action(0, "cut", tile=15)
    assert discard_window["status"] == "waiting_discard_response"
    assert discard_window["actions"] == {0: [], 1: [], 2: [], 3: []}

    window = game.continue_after_discard_responses(0, 15, {}, {})
    assert window["status"] == "END"
    assert window["ended_by"] == "wall"
    assert window["claim_result"]["drawn_tile"] is None
    assert game.game_status == "END"
    assert game.ended_by == "wall"


def test_continue_after_rob_kong_responses_unrobbed_returns_hand_window() -> None:
    game = NewRuleGameState()
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
    game = NewRuleGameState()
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
    assert window["player"] == 1
    assert window["drawn_tile"] == 33
    assert window["rob_kong_result"]["winners"] == [2]
    assert game.player_list[0].combination_tiles == ["k15"]


def test_scripted_flow_discard_claim_forced_cut_discard_win_next_draw() -> None:
    game = NewRuleGameState()
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
    assert discard_window["status"] == "waiting_discard_response"
    assert "peng" in discard_window["actions"][2], discard_window

    claim_window = game.continue_after_discard_responses(0, 15, {}, {2: "peng"})
    assert claim_window["status"] == "waiting_only_cut"
    assert claim_window["player"] == 2
    assert claim_window["actions"][2] == ["cut"]
    assert game.player_list[2].combination_tiles == ["k15"]

    second_discard_window = game.apply_turn_action(2, "cut", tile=31)
    assert second_discard_window["status"] == "waiting_discard_response"
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
        game = NewRuleGameState()
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
    game = NewRuleGameState()

    payloads = game.emit_visible_action_payloads(
        {"action": "cut", "player": 0, "tile": 15, "cutIndex": 0}
    )

    assert [payload["player_index"] for payload in payloads] == [0, 1, 2, 3]
    assert [payload["player_index"] for payload in game.outbound_payloads[-4:]] == [0, 1, 2, 3]
    assert all(payload["type"] == "gamestate/new_rule/do_action" for payload in payloads)
    assert payloads[0]["do_action_info"]["action_list"] == ["cut"]


def test_wait_action_defaults_pending_pass_on_timeout() -> None:
    async def scenario() -> None:
        game = NewRuleGameState()
        game.action_dict = {0: [], 1: ["hu", "pass"], 2: [], 3: []}

        result = await game.wait_action(timeout=0.001)

        assert result[1]["action_type"] == "pass"
        assert game.waiting_players_list == []
        assert game.action_dict[1] == []

    asyncio.run(scenario())


def test_submit_action_rejects_non_waiting_or_illegal_action() -> None:
    async def scenario() -> None:
        game = NewRuleGameState()
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
        game = NewRuleGameState()

        await game.player_disconnect(101)
        assert "offline" in game.player_list[0].tag_list

        await game.player_reconnect(101)
        assert "offline" not in game.player_list[0].tag_list

    asyncio.run(scenario())


def test_cleanup_cancels_attached_game_task() -> None:
    async def scenario() -> None:
        game = NewRuleGameState()
        game.game_task = asyncio.create_task(asyncio.sleep(10))

        await game.cleanup_game_state()

        assert game.game_task.cancelled()

    asyncio.run(scenario())


def test_run_game_loop_starts_draft_loop_and_can_be_cancelled() -> None:
    async def scenario() -> None:
        game = NewRuleGameState()
        game.game_task = asyncio.create_task(game.run_game_loop())
        await asyncio.sleep(0.1)

        assert game.game_status == "waiting_hand_action"
        assert game.waiting_players_list
        assert any(payload["type"] == "gamestate/new_rule/ask_action" for payload in game.outbound_payloads)

        await game.cleanup_game_state()
        assert game.game_task.cancelled()

    asyncio.run(scenario())


def test_open_action_window_sets_live_action_fields() -> None:
    game = NewRuleGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
    game.player_list[0].hand_tiles = [41]

    window = game.open_action_window(game.begin_hand_action(0))

    assert window["action_tick"] == 1
    assert game.live_pending_window is window
    assert game.action_dict[0] == ["cut"]
    assert game.waiting_players_list == [0]
    assert game.outbound_payloads[-1]["type"] == "gamestate/new_rule/ask_action"
    assert game.outbound_payloads[-1]["action_list"] == ["cut"]


def test_resolve_action_window_applies_queued_cut() -> None:
    async def scenario() -> None:
        game = NewRuleGameState()
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

        assert window["status"] == "waiting_discard_response"
        assert window["tile"] == 41
        assert "hu" in window["actions"][2]
        assert game.action_dict[2] == ["hu", "pass"]
        assert game.waiting_players_list == [2]

    asyncio.run(scenario())


def test_resolve_action_window_applies_discard_win_and_opens_next_draw() -> None:
    async def scenario() -> None:
        game = NewRuleGameState()
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

        assert discard_window["status"] == "waiting_discard_response"
        assert next_window["status"] == "waiting_hand_action"
        assert next_window["reason"] == "discard_win"
        assert next_window["player"] == 1
        assert next_window["drawn_tile"] == 33
        assert game.player_list[2].is_hu
        assert game.deferred_hu_settlements == [
            {"source": "discard", "discarder": 0, "tile": 41, "points": 8, "winner": 2, "hu_order": 1}
        ]

    asyncio.run(scenario())


def test_apply_action_results_resolves_discard_claim_window() -> None:
    game = NewRuleGameState()
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

    assert next_window["status"] == "waiting_only_cut"
    assert next_window["reason"] == "discard_claim"
    assert next_window["player"] == 2
    assert game.player_list[2].combination_tiles == ["k15"]
    assert game.action_dict[2] == ["cut"]
    claim_payloads = [
        payload
        for payload in game.outbound_payloads
        if payload.get("type") == "gamestate/new_rule/do_action"
        and payload["do_action_info"]["action_list"] == ["peng"]
    ]
    assert claim_payloads
    assert claim_payloads[0]["do_action_info"]["combination_mask"] == [1, 15, 0, 15, 0, 15]


def test_flush_outbound_payloads_sends_to_connected_player() -> None:
    async def scenario() -> None:
        game = NewRuleGameState()
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
        assert websocket.sent[0]["type"] == "gamestate/new_rule/ask_action"
        assert websocket.sent[0]["player_index"] == 0
        assert game.websocket_sent_payloads == websocket.sent
        assert game.outbound_send_cursor == len(game.outbound_payloads)

    asyncio.run(scenario())


def test_send_payload_to_player_without_connection_keeps_outbox_fallback() -> None:
    async def scenario() -> None:
        game = NewRuleGameState()
        before = len(game.outbound_payloads)

        sent = await game.send_payload_to_player(0, {"type": "test/new_rule"})

        assert not sent
        assert len(game.outbound_payloads) == before + 1
        assert game.outbound_payloads[-1]["type"] == "test/new_rule"
        assert game.outbound_payloads[-1]["player_index"] == 0

    asyncio.run(scenario())


def test_player_reconnect_sends_safe_reconnect_payload() -> None:
    async def scenario() -> None:
        game = NewRuleGameState()
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
        game.action_dict = {0: [], 1: ["hu", "pass"], 2: [], 3: []}

        await game.player_reconnect(102)

        assert "offline" not in game.player_list[1].tag_list
        assert websocket.sent
        payload = websocket.sent[-1]
        assert payload["type"] == "gamestate/new_rule/reconnect"
        assert payload["player_index"] == 1
        assert payload["action_list"] == ["hu", "pass"]
        assert payload["game_info"]["players_info"][0]["hand_tiles"] is None
        assert payload["game_info"]["players_info"][0]["combination_tiles"] == ["G0"]
        assert payload["game_info"]["players_info"][1]["hand_tiles"] == [21, 22, 23]

    asyncio.run(scenario())


def run() -> None:
    tests = [
        test_wall_is_136_no_flowers_and_deal_shape,
        test_fixed_dealer_rotation,
        test_blood_battle_end_conditions,
        test_wall_exhaustion_ends_hand,
        test_next_active_skips_winners,
        test_discard_win_lockout_helpers,
        test_discard_pass_lockout_clears_and_restarts_on_own_discard,
        test_discard_win_defers_settlement_and_next_draw_skips_winner,
        test_draw_after_discard_resolution_ends_on_empty_wall,
        test_resolve_discard_win_responses_allows_independent_multi_ron,
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
        test_apply_turn_concealed_kong_returns_followup_hand_action_window,
        test_apply_turn_added_kong_opens_rob_kong_window,
        test_continue_after_discard_responses_multi_ron_returns_next_hand_window,
        test_continue_after_discard_responses_skips_claims_when_anyone_wins,
        test_continue_after_discard_responses_claim_returns_only_cut_window,
        test_continue_after_discard_responses_no_claim_returns_next_draw_window,
        test_continue_after_final_discard_no_win_ends_by_wall,
        test_continue_after_rob_kong_responses_unrobbed_returns_hand_window,
        test_continue_after_rob_kong_responses_robbed_returns_next_draw_window,
        test_scripted_flow_discard_claim_forced_cut_discard_win_next_draw,
        test_wait_action_collects_submitted_action,
        test_visible_action_payloads_are_addressed_to_each_viewer,
        test_wait_action_defaults_pending_pass_on_timeout,
        test_submit_action_rejects_non_waiting_or_illegal_action,
        test_disconnect_reconnect_tags_are_local_shell_behavior,
        test_cleanup_cancels_attached_game_task,
        test_run_game_loop_starts_draft_loop_and_can_be_cancelled,
        test_open_action_window_sets_live_action_fields,
        test_resolve_action_window_applies_queued_cut,
        test_resolve_action_window_applies_discard_win_and_opens_next_draw,
        test_apply_action_results_resolves_discard_claim_window,
        test_flush_outbound_payloads_sends_to_connected_player,
        test_send_payload_to_player_without_connection_keeps_outbox_fallback,
        test_player_reconnect_sends_safe_reconnect_payload,
    ]
    for test in tests:
        test()
    print(f"new_rule gamestate skeleton tests ok: {len(tests)} tests")


if __name__ == "__main__":
    run()
