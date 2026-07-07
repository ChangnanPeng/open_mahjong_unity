from __future__ import annotations

from pathlib import Path
import sys

SERVER_ROOT = Path(__file__).resolve().parents[3]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from server.gamestate.game_new_rule import NewRuleGameState
from server.gamestate.game_new_rule.debug_scenarios import apply_debug_scenario


def test_multi_ron_2_scenario_opens_discard_then_two_hu_window() -> None:
    game = NewRuleGameState()

    hand_window = apply_debug_scenario(game, "multi_ron_2")

    assert hand_window["status"] == "waiting_hand_action"
    assert game.action_dict[0] == ["cut"]
    assert 19 in game.player_list[0].hand_tiles

    response_window = game.apply_action_results(
        hand_window,
        {0: {"player_index": 0, "action_type": "cut", "TileId": 19, "cutIndex": 8, "cutClass": False}},
    )

    assert response_window["status"] == "waiting_action_after_cut"
    assert response_window["tile"] == 19
    assert "hu" in game.action_dict[1]
    assert "hu" in game.action_dict[2]
    assert "hu" not in game.action_dict[3]


def test_multi_ron_3_scenario_can_end_hand_through_normal_response_resolution() -> None:
    game = NewRuleGameState()
    hand_window = apply_debug_scenario(game, "multi_ron_3")
    response_window = game.apply_action_results(
        hand_window,
        {0: {"player_index": 0, "action_type": "cut", "TileId": 19, "cutIndex": 8, "cutClass": False}},
    )

    final_window = game.apply_action_results(
        response_window,
        {
            1: {"player_index": 1, "action_type": "hu"},
            2: {"player_index": 2, "action_type": "hu"},
            3: {"player_index": 3, "action_type": "hu"},
        },
    )

    assert final_window["status"] == "END"
    assert game.ended_by == "win"
    assert [settlement["winner"] for settlement in game.deferred_hu_settlements] == [1, 2, 3]
    assert all(settlement["source"] == "discard" for settlement in game.deferred_hu_settlements)


def test_rob_kong_scenario_opens_added_kong_then_rob_window() -> None:
    game = NewRuleGameState()

    hand_window = apply_debug_scenario(game, "rob_kong")

    assert hand_window["status"] == "waiting_hand_action"
    assert "jiagang" in game.action_dict[0]

    rob_window = game.apply_action_results(
        hand_window,
        {0: {"player_index": 0, "action_type": "jiagang", "target_tile": 19}},
    )

    assert rob_window["status"] == "waiting_action_qianggang"
    assert rob_window["tile"] == 19
    assert "hu" in game.action_dict[1]
    assert "hu" not in game.action_dict[2]
    assert "hu" not in game.action_dict[3]
    assert any(
        payload.get("type") == "gamestate/new_rule/do_action"
        and payload.get("do_action_info", {}).get("action_list") == ["jiagang"]
        for payload in game.outbound_payloads
    )

    game.apply_action_results(
        rob_window,
        {1: {"player_index": 1, "action_type": "hu"}},
    )

    assert 19 not in game.player_list[0].hand_tiles
    assert game.player_list[0].combination_tiles == ["k19"]


def test_rob_kong_multi_ron_2_scenario_allows_lower_and_upper_players_to_rob() -> None:
    game = NewRuleGameState()

    hand_window = apply_debug_scenario(game, "rob_kong_multi_ron_2")

    assert hand_window["status"] == "waiting_hand_action"
    assert "jiagang" in game.action_dict[0]

    rob_window = game.apply_action_results(
        hand_window,
        {0: {"player_index": 0, "action_type": "jiagang", "target_tile": 19}},
    )

    assert rob_window["status"] == "waiting_action_qianggang"
    assert "hu" in game.action_dict[1]
    assert "hu" not in game.action_dict[2]
    assert "hu" in game.action_dict[3]

    next_window = game.apply_action_results(
        rob_window,
        {
            1: {"player_index": 1, "action_type": "hu"},
            3: {"player_index": 3, "action_type": "hu"},
        },
    )

    assert next_window["status"] == "waiting_hand_action"
    assert next_window["reason"] == "rob_kong"
    assert next_window["rob_kong_result"]["winners"] == [1, 3]
    assert 19 not in game.player_list[0].hand_tiles
    assert game.player_list[0].combination_tiles == ["k19"]
    assert [settlement["winner"] for settlement in game.deferred_hu_settlements] == [1, 3]
    assert all(settlement["source"] == "rob_kong" for settlement in game.deferred_hu_settlements)


def test_same_tile_lockout_scenario_covers_pass_self_draw_and_next_same_discard() -> None:
    game = NewRuleGameState()

    hand_window = apply_debug_scenario(game, "same_tile_lockout")

    assert hand_window["status"] == "waiting_hand_action"
    assert hand_window["player"] == 3

    first_response = game.apply_action_results(
        hand_window,
        {3: {"player_index": 3, "action_type": "cut", "TileId": 15, "cutIndex": 13, "cutClass": True}},
    )
    assert first_response["status"] == "waiting_action_after_cut"
    assert first_response["tile"] == 15
    assert "hu" in game.action_dict[0]
    assert "pass" in game.action_dict[0]

    self_draw_window = game.apply_action_results(
        first_response,
        {0: {"player_index": 0, "action_type": "pass"}},
    )
    assert 15 in game.player_list[0].discard_win_lockout_tiles
    assert self_draw_window["status"] == "waiting_hand_action"
    assert self_draw_window["player"] == 0
    assert self_draw_window["drawn_tile"] == 15
    assert "hu_self" in game.action_dict[0]

    second_response = game.apply_action_results(
        self_draw_window,
        {0: {"player_index": 0, "action_type": "cut", "TileId": 15, "cutIndex": 13, "cutClass": True}},
    )
    assert second_response["status"] == "waiting_action_after_cut"
    assert game.player_list[0].discard_win_lockout_tiles == {15}

    bot_draw_window = game.apply_action_results(second_response, {})
    assert bot_draw_window["status"] == "waiting_hand_action"
    assert bot_draw_window["player"] == 1
    assert bot_draw_window["drawn_tile"] == 15

    locked_response = game.apply_action_results(
        bot_draw_window,
        {1: {"player_index": 1, "action_type": "cut", "TileId": 15, "cutIndex": 13, "cutClass": True}},
    )
    assert locked_response["status"] == "waiting_action_after_cut"
    assert locked_response["tile"] == 15
    assert "hu" not in game.action_dict[0]


def test_same_tile_lockout_scenario_unlocks_after_cutting_different_tile() -> None:
    game = NewRuleGameState()

    hand_window = apply_debug_scenario(game, "same_tile_lockout")
    first_response = game.apply_action_results(
        hand_window,
        {3: {"player_index": 3, "action_type": "cut", "TileId": 15, "cutIndex": 13, "cutClass": True}},
    )
    self_draw_window = game.apply_action_results(
        first_response,
        {0: {"player_index": 0, "action_type": "pass"}},
    )

    assert 15 in game.player_list[0].discard_win_lockout_tiles
    assert "hu_self" in game.action_dict[0]

    different_cut_response = game.apply_action_results(
        self_draw_window,
        {0: {"player_index": 0, "action_type": "cut", "TileId": 11, "cutIndex": 0, "cutClass": False}},
    )
    assert different_cut_response["status"] == "waiting_action_after_cut"
    assert game.player_list[0].discard_win_lockout_tiles == {11}

    bot_draw_window = game.apply_action_results(different_cut_response, {})
    assert bot_draw_window["status"] == "waiting_hand_action"
    assert bot_draw_window["player"] == 1
    assert bot_draw_window["drawn_tile"] == 15

    unlocked_response = game.apply_action_results(
        bot_draw_window,
        {1: {"player_index": 1, "action_type": "cut", "TileId": 15, "cutIndex": 13, "cutClass": True}},
    )
    assert unlocked_response["status"] == "waiting_action_after_cut"
    assert unlocked_response["tile"] == 15
    assert "hu" in game.action_dict[0]


def test_same_tile_lockout_blocks_immediate_next_same_discard_by_next_bot() -> None:
    game = NewRuleGameState()

    _setup_lockout_chain_game(game, current_player=1, wall=[15])
    game.player_list[1].hand_tiles = _non_claiming_lockout_hand() + [15]
    game.player_list[1].has_draw_slot = True

    first_window = game.open_action_window(game.begin_hand_action(1))
    first_response = game.apply_action_results(
        first_window,
        {1: {"player_index": 1, "action_type": "cut", "TileId": 15, "cutIndex": 13, "cutClass": True}},
    )
    assert "hu" in game.action_dict[0]

    next_draw = game.apply_action_results(
        first_response,
        {0: {"player_index": 0, "action_type": "pass"}},
    )
    assert game.player_list[0].discard_win_lockout_tiles == {15}
    assert next_draw["player"] == 2
    assert next_draw["drawn_tile"] == 15

    locked_response = game.apply_action_results(
        next_draw,
        {2: {"player_index": 2, "action_type": "cut", "TileId": 15, "cutIndex": 13, "cutClass": True}},
    )

    assert locked_response["status"] == "waiting_action_after_cut"
    assert locked_response["tile"] == 15
    assert "hu" not in game.action_dict[0]


def test_same_tile_lockout_survives_peng_claim_before_same_tile_is_cut_again() -> None:
    game = NewRuleGameState()

    _setup_lockout_chain_game(game, current_player=3, wall=[15])
    game.player_list[3].hand_tiles = _non_claiming_lockout_hand() + [15]
    game.player_list[3].has_draw_slot = True
    game.player_list[1].hand_tiles = [15, 15, 11, 12, 13, 21, 22, 23, 31, 32, 33, 41, 42]

    first_window = game.open_action_window(game.begin_hand_action(3))
    first_response = game.apply_action_results(
        first_window,
        {3: {"player_index": 3, "action_type": "cut", "TileId": 15, "cutIndex": 13, "cutClass": True}},
    )
    assert "hu" in game.action_dict[0]
    assert "peng" in game.action_dict[1]

    claim_window = game.apply_action_results(
        first_response,
        {
            0: {"player_index": 0, "action_type": "pass"},
            1: {"player_index": 1, "action_type": "peng"},
        },
    )
    assert game.player_list[0].discard_win_lockout_tiles == {15}
    assert claim_window["status"] == "onlycut_after_action"
    assert claim_window["player"] == 1

    no_claim_window = game.apply_action_results(
        claim_window,
        {1: {"player_index": 1, "action_type": "cut", "TileId": 11, "cutIndex": 0, "cutClass": False}},
    )
    assert no_claim_window["status"] == "waiting_action_after_cut"

    next_draw = game.apply_action_results(no_claim_window, {})
    assert next_draw["status"] == "waiting_hand_action"
    assert next_draw["player"] == 2
    assert next_draw["drawn_tile"] == 15

    locked_response = game.apply_action_results(
        next_draw,
        {2: {"player_index": 2, "action_type": "cut", "TileId": 15, "cutIndex": 13, "cutClass": True}},
    )
    assert locked_response["status"] == "waiting_action_after_cut"
    assert "hu" not in game.action_dict[0]


def test_same_tile_lockout_survives_peng_chain_and_blocks_robbing_added_kong() -> None:
    game = NewRuleGameState()

    _setup_lockout_chain_game(game, current_player=3, wall=[17, 15, 31])
    game.player_list[3].hand_tiles = _non_claiming_lockout_hand() + [15]
    game.player_list[3].has_draw_slot = True
    game.player_list[2].hand_tiles = [15, 15, 11, 12, 13, 21, 22, 23, 31, 32, 33, 41, 42]
    game.player_list[1].hand_tiles = [17, 17, 18, 12, 13, 21, 22, 23, 31, 32, 33, 41, 42]

    first_window = game.open_action_window(game.begin_hand_action(3))
    first_response = game.apply_action_results(
        first_window,
        {3: {"player_index": 3, "action_type": "cut", "TileId": 15, "cutIndex": 13, "cutClass": True}},
    )
    assert "hu" in game.action_dict[0]
    assert "peng" in game.action_dict[2]

    c_claim_window = game.apply_action_results(
        first_response,
        {
            0: {"player_index": 0, "action_type": "pass"},
            2: {"player_index": 2, "action_type": "peng"},
        },
    )
    assert game.player_list[0].discard_win_lockout_tiles == {15}
    assert game.player_list[2].combination_tiles == ["k15"]

    c_cut_response = game.apply_action_results(
        c_claim_window,
        {2: {"player_index": 2, "action_type": "cut", "TileId": 11, "cutIndex": 0, "cutClass": False}},
    )
    d_draw_window = game.apply_action_results(c_cut_response, {})
    assert d_draw_window["player"] == 3
    assert d_draw_window["drawn_tile"] == 17

    d_cut_response = game.apply_action_results(
        d_draw_window,
        {3: {"player_index": 3, "action_type": "cut", "TileId": 17, "cutIndex": 13, "cutClass": True}},
    )
    assert "peng" in game.action_dict[1]

    b_claim_window = game.apply_action_results(
        d_cut_response,
        {1: {"player_index": 1, "action_type": "peng"}},
    )
    assert game.player_list[1].combination_tiles == ["k17"]

    b_cut_response = game.apply_action_results(
        b_claim_window,
        {1: {"player_index": 1, "action_type": "cut", "TileId": 18, "cutIndex": 0, "cutClass": False}},
    )
    c_draw_window = game.apply_action_results(b_cut_response, {})
    assert c_draw_window["status"] == "waiting_hand_action"
    assert c_draw_window["player"] == 2
    assert c_draw_window["drawn_tile"] == 15
    assert "jiagang" in game.action_dict[2]

    rob_window = game.apply_action_results(
        c_draw_window,
        {2: {"player_index": 2, "action_type": "jiagang", "target_tile": 15}},
    )
    assert rob_window["status"] == "waiting_action_qianggang"
    assert rob_window["tile"] == 15
    assert "hu" not in game.action_dict[0]
    assert game.player_list[0].discard_win_lockout_tiles == {15}


def test_haitei_scenario_self_draw_scores_last_tile_draw() -> None:
    game = NewRuleGameState()
    hand_window = apply_debug_scenario(game, "haitei")

    assert "hu_self" in game.action_dict[0]
    assert game.tiles_list == []

    final_window = game.apply_action_results(
        hand_window,
        {0: {"player_index": 0, "action_type": "hu_self", "target_tile": 15}},
    )

    assert final_window["status"] == "END"
    assert "haitei" in game.deferred_hu_settlements[-1]["fan_ids"]


def test_houtei_scenario_discard_win_scores_last_discard() -> None:
    game = NewRuleGameState()
    hand_window = apply_debug_scenario(game, "houtei")

    response_window = game.apply_action_results(
        hand_window,
        {0: {"player_index": 0, "action_type": "cut", "TileId": 15, "cutIndex": 12, "cutClass": False}},
    )

    assert response_window["status"] == "waiting_action_after_cut"
    assert game.tiles_list == []
    assert "hu" in game.action_dict[1]

    final_window = game.apply_action_results(
        response_window,
        {1: {"player_index": 1, "action_type": "hu"}},
    )

    assert final_window["status"] == "END"
    assert "houtei" in game.deferred_hu_settlements[-1]["fan_ids"]


def test_rinshan_scenario_kong_supplement_self_draw_scores_kong_win() -> None:
    game = NewRuleGameState()
    hand_window = apply_debug_scenario(game, "rinshan")

    assert "angang" in game.action_dict[0]

    supplement_window = game.apply_action_results(
        hand_window,
        {0: {"player_index": 0, "action_type": "angang", "target_tile": 19}},
    )

    assert supplement_window["status"] == "waiting_hand_action"
    assert supplement_window["drawn_tile"] == 15
    assert "hu_self" in game.action_dict[0]

    game.apply_action_results(
        supplement_window,
        {0: {"player_index": 0, "action_type": "hu_self", "target_tile": 15}},
    )

    assert "rinshan" in game.deferred_hu_settlements[-1]["fan_ids"]


def test_heavenly_win_scenario_scores_opening_dealer_self_draw() -> None:
    game = NewRuleGameState()
    hand_window = apply_debug_scenario(game, "heavenly_win")

    assert "hu_self" in game.action_dict[0]
    game.apply_action_results(
        hand_window,
        {0: {"player_index": 0, "action_type": "hu_self", "target_tile": 15}},
    )

    assert "heavenly_win" in game.deferred_hu_settlements[-1]["fan_ids"]


def test_earthly_win_scenario_scores_first_non_dealer_self_draw() -> None:
    game = NewRuleGameState()
    hand_window = apply_debug_scenario(game, "earthly_win")

    assert game.dealer_index == 1
    assert hand_window["player"] == 0
    assert "hu_self" in game.action_dict[0]
    game.apply_action_results(
        hand_window,
        {0: {"player_index": 0, "action_type": "hu_self", "target_tile": 15}},
    )

    assert "earthly_win" in game.deferred_hu_settlements[-1]["fan_ids"]


def test_nine_gates_scenario_scores_true_nine_gates() -> None:
    game = NewRuleGameState()
    hand_window = apply_debug_scenario(game, "nine_gates")

    assert "hu_self" in game.action_dict[0]
    game.apply_action_results(
        hand_window,
        {0: {"player_index": 0, "action_type": "hu_self", "target_tile": 15}},
    )

    assert "nine_gates" in game.deferred_hu_settlements[-1]["fan_ids"]


def test_nine_gates_scenario_can_test_discard_win_after_skipping_self_draw() -> None:
    game = NewRuleGameState()
    hand_window = apply_debug_scenario(game, "nine_gates")

    response_window = game.apply_action_results(
        hand_window,
        {0: {"player_index": 0, "action_type": "cut", "TileId": 15, "cutIndex": 13, "cutClass": True}},
    )
    assert response_window["status"] == "waiting_action_after_cut"
    assert all(not actions for actions in game.action_dict.values())

    bot_draw_window = game.apply_action_results(response_window, {})
    assert bot_draw_window["status"] == "waiting_hand_action"
    assert bot_draw_window["player"] == 1
    assert bot_draw_window["drawn_tile"] == 19

    ron_window = game.apply_action_results(
        bot_draw_window,
        {1: {"player_index": 1, "action_type": "cut", "TileId": 19, "cutIndex": 13, "cutClass": True}},
    )
    assert ron_window["status"] == "waiting_action_after_cut"
    assert ron_window["tile"] == 19
    assert "hu" in game.action_dict[0]
    assert "pass" in game.action_dict[0]

    result_window = game.apply_action_results(
        ron_window,
        {0: {"player_index": 0, "action_type": "hu"}},
    )
    assert result_window["status"] != "waiting_action_after_cut"
    assert "nine_gates" in game.deferred_hu_settlements[-1]["fan_ids"]


def test_nine_gates_scenario_can_test_same_tile_lockout_after_cutting_9m() -> None:
    game = NewRuleGameState()
    hand_window = apply_debug_scenario(game, "nine_gates")

    response_window = game.apply_action_results(
        hand_window,
        {0: {"player_index": 0, "action_type": "cut", "TileId": 19, "cutIndex": 10, "cutClass": False}},
    )
    assert 19 in game.player_list[0].discard_win_lockout_tiles

    bot_draw_window = game.apply_action_results(response_window, {})
    assert bot_draw_window["player"] == 1
    assert bot_draw_window["drawn_tile"] == 19

    locked_window = game.apply_action_results(
        bot_draw_window,
        {1: {"player_index": 1, "action_type": "cut", "TileId": 19, "cutIndex": 13, "cutClass": True}},
    )
    assert locked_window["status"] == "waiting_action_after_cut"
    assert locked_window["tile"] == 19
    assert "hu" not in game.action_dict[0]


def _setup_lockout_chain_game(game: NewRuleGameState, *, current_player: int, wall: list[int]) -> None:
    game.initialize_round()
    game.room_rule = "new_rule"
    game.dealer_index = 0
    game.current_player_index = current_player
    game.game_status = "waiting_hand_action"
    game.tiles_list = list(wall)
    for player in game.player_list:
        player.hand_tiles = _non_claiming_lockout_hand()
        player.waiting_tiles = set()
        player.combination_tiles = []
        player.combination_mask = []
        player.discard_win_lockout_tiles = set()
        player.has_draw_slot = False
        player.is_hu = False
    game.player_list[0].hand_tiles = [11, 11, 11, 22, 22, 22, 33, 33, 33, 44, 44, 44, 15]
    game.player_list[0].waiting_tiles = {15}


def _non_claiming_lockout_hand() -> list[int]:
    return [21, 21, 22, 22, 23, 23, 31, 31, 32, 32, 41, 42, 43]


def run() -> None:
    tests = [
        test_multi_ron_2_scenario_opens_discard_then_two_hu_window,
        test_multi_ron_3_scenario_can_end_hand_through_normal_response_resolution,
        test_rob_kong_scenario_opens_added_kong_then_rob_window,
        test_rob_kong_multi_ron_2_scenario_allows_lower_and_upper_players_to_rob,
        test_same_tile_lockout_scenario_covers_pass_self_draw_and_next_same_discard,
        test_same_tile_lockout_scenario_unlocks_after_cutting_different_tile,
        test_same_tile_lockout_blocks_immediate_next_same_discard_by_next_bot,
        test_same_tile_lockout_survives_peng_claim_before_same_tile_is_cut_again,
        test_same_tile_lockout_survives_peng_chain_and_blocks_robbing_added_kong,
        test_haitei_scenario_self_draw_scores_last_tile_draw,
        test_houtei_scenario_discard_win_scores_last_discard,
        test_rinshan_scenario_kong_supplement_self_draw_scores_kong_win,
        test_heavenly_win_scenario_scores_opening_dealer_self_draw,
        test_earthly_win_scenario_scores_first_non_dealer_self_draw,
        test_nine_gates_scenario_scores_true_nine_gates,
        test_nine_gates_scenario_can_test_discard_win_after_skipping_self_draw,
        test_nine_gates_scenario_can_test_same_tile_lockout_after_cutting_9m,
    ]
    for test in tests:
        test()
    print(f"new_rule debug scenario tests ok: {len(tests)} tests")


if __name__ == "__main__":
    run()
