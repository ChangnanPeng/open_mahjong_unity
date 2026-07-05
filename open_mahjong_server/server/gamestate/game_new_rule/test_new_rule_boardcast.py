from __future__ import annotations

from pathlib import Path
import sys

SERVER_ROOT = Path(__file__).resolve().parents[3]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from server.gamestate.game_new_rule import NewRuleGameState
from server.gamestate.game_new_rule.boardcast import (
    ask_action_payload,
    final_settlement_payload,
    game_start_payload,
    game_info_payload,
    pending_action_payload,
    visible_action_payload,
)


def test_game_info_masks_concealed_kong_for_other_players() -> None:
    game = NewRuleGameState()
    game.player_list[0].hand_tiles = [11, 12, 13]
    game.player_list[0].combination_tiles = ["G15"]

    owner_view = game_info_payload(game, 0)
    other_view = game_info_payload(game, 1)

    assert owner_view["players_info"][0]["combination_tiles"] == ["G15"]
    assert other_view["players_info"][0]["combination_tiles"] == ["G0"]
    assert other_view["players_info"][0]["hand_tiles"] is None
    assert other_view["players_info"][0]["hand_tiles_count"] == 3


def test_mid_hand_win_payload_hides_fans_points_and_self_draw_tile() -> None:
    game = NewRuleGameState()

    payload = visible_action_payload(
        game,
        1,
        {
            "action": "hu_self",
            "player": 0,
            "tile": 41,
            "fan_ids": ["pinfu"],
            "fan_names": ["平和"],
            "points": 2,
        },
    )

    assert payload["tile"] is None
    assert payload["fan_ids"] is None
    assert payload["fan_names"] is None
    assert payload["points"] is None


def test_mid_hand_discard_win_keeps_public_discard_tile_but_hides_scoring() -> None:
    game = NewRuleGameState()

    payload = visible_action_payload(
        game,
        0,
        {
            "action": "hu",
            "player": 2,
            "tile": 41,
            "fan_ids": ["pinfu"],
            "fan_names": ["平和"],
            "points": 2,
        },
    )

    assert payload["tile"] == 41
    assert payload["fan_ids"] is None
    assert payload["fan_names"] is None
    assert payload["points"] is None


def test_deal_tile_payload_hides_drawn_tile_from_other_viewers() -> None:
    game = NewRuleGameState()

    owner_payload = visible_action_payload(game, 0, {"action": "deal_tile", "player": 0, "tile": 31})
    other_payload = visible_action_payload(game, 1, {"action": "deal_tile", "player": 0, "tile": 31})

    assert owner_payload["do_action_info"]["action_list"] == ["deal_tile"]
    assert owner_payload["do_action_info"]["deal_tile"] == 31
    assert other_payload["do_action_info"]["deal_tile"] is None


def test_final_settlement_reveals_hands_concealed_kongs_and_deferred_results() -> None:
    game = NewRuleGameState()
    game.player_list[0].hand_tiles = [11, 12, 13]
    game.player_list[0].combination_tiles = ["G15"]
    game.deferred_hu_settlements = [{"winner": 0, "points": 8, "fan_ids": ["pinfu"]}]
    game.ended_by = "win"

    payload = final_settlement_payload(game, 1)

    player_zero = payload["game_info"]["players_info"][0]
    assert player_zero["hand_tiles"] == [11, 12, 13]
    assert player_zero["combination_tiles"] == ["G15"]
    assert payload["show_result_info"]["hepai_player_index"] == 0
    assert payload["show_result_info"]["hu_score"] == 8
    assert payload["show_result_info"]["hu_fan"] == ["pinfu"]
    assert payload["show_result_info"]["hu_class"] == "hu"
    assert payload["show_result_info"]["player_to_score"] == {
        0: game.player_list[0].score,
        1: game.player_list[1].score,
        2: game.player_list[2].score,
        3: game.player_list[3].score,
    }


def test_final_settlement_keeps_zero_point_empty_fan_result() -> None:
    game = NewRuleGameState()
    game.deferred_hu_settlements = [
        {
            "winner": 0,
            "points": 0,
            "raw_points": 0,
            "fan_ids": [],
            "fan_names": [],
            "score_changes": [0, 0, 0, 0],
        }
    ]
    game.ended_by = "win"

    payload = final_settlement_payload(game, 1)

    assert payload["show_result_info"]["hu_score"] == 0
    assert payload["show_result_info"]["hu_fan"] == []


def test_final_settlement_applies_score_changes_once() -> None:
    game = NewRuleGameState()
    game.deferred_hu_settlements = [
        {
            "winner": 1,
            "points": 8,
            "score_changes": [-48, 48, 0, 0],
        }
    ]
    game.ended_by = "win"

    first_payload = final_settlement_payload(game, 0)
    second_payload = final_settlement_payload(game, 1)

    assert first_payload["game_info"]["players_info"][0]["score"] == -48
    assert first_payload["game_info"]["players_info"][1]["score"] == 48
    assert second_payload["game_info"]["players_info"][0]["score"] == -48
    assert second_payload["game_info"]["players_info"][1]["score"] == 48


def test_final_settlement_sums_multiple_score_changes_once() -> None:
    game = NewRuleGameState()
    game.deferred_hu_settlements = [
        {
            "winner": 1,
            "points": 8,
            "score_changes": [-48, 48, 0, 0],
        },
        {
            "winner": 2,
            "points": 5,
            "score_changes": [-10, 0, 30, -20],
        },
    ]
    game.ended_by = "win"

    first_payload = final_settlement_payload(game, 0)
    second_payload = final_settlement_payload(game, 1)

    first_scores = [
        player_info["score"]
        for player_info in first_payload["game_info"]["players_info"]
    ]
    second_scores = [
        player_info["score"]
        for player_info in second_payload["game_info"]["players_info"]
    ]
    assert first_scores == [-58, 48, 30, -20]
    assert second_scores == [-58, 48, 30, -20]
    assert first_payload["show_result_info"]["score_changes"] == {0: -58, 1: 48, 2: 30, 3: -20}


def test_final_settlement_without_winners_emits_unity_draw_result() -> None:
    game = NewRuleGameState()
    game.game_status = "END"
    game.ended_by = "wall"
    game.deferred_hu_settlements = []

    payload = final_settlement_payload(game, 0)

    assert payload["type"] == "gamestate/new_rule/show_result"
    assert payload["show_result_info"]["hepai_player_index"] == -1
    assert payload["show_result_info"]["hu_class"] == "liuju"
    assert payload["show_result_info"]["hu_score"] == 0
    assert payload["show_result_info"]["hu_fan"] == []
    assert payload["show_result_info"]["liuju_step"] == "final"
    assert payload["show_result_info"]["liuju_status_final"] is True


def test_ask_action_payload_includes_action_tick_and_actions() -> None:
    game = NewRuleGameState()
    game.server_action_tick = 7

    payload = ask_action_payload(game, 2, ["hu", "pass"], cut_tile=41)

    assert payload["type"] == "gamestate/new_rule/ask_other_action"
    assert payload["player_index"] == 2
    assert payload["action_list"] == ["hu", "pass"]
    assert payload["action_tick"] == 7
    assert payload["cut_tile"] == 41


def test_ask_action_payload_includes_unity_bridge_fields() -> None:
    game = NewRuleGameState()
    game.initialize_round()
    game.server_action_tick = 3

    hand_payload = ask_action_payload(game, 0, ["cut"])
    other_payload = ask_action_payload(game, 1, ["hu", "pass"], cut_tile=41)

    assert hand_payload["game_info"]["room_rule"] == "new_rule"
    assert hand_payload["game_info"]["sub_rule"] == "new_rule/standard"
    assert hand_payload["game_info"]["self_hand_tiles"] == game.player_list[0].hand_tiles
    assert hand_payload["type"] == "gamestate/new_rule/broadcast_hand_action"
    assert hand_payload["ask_hand_action_info"]["action_list"] == ["cut"]
    assert hand_payload["ask_hand_action_info"]["remain_tiles"] == len(game.tiles_list)
    assert hand_payload["ask_other_action_info"] is None

    assert other_payload["type"] == "gamestate/new_rule/ask_other_action"
    assert other_payload["ask_hand_action_info"] is None
    assert other_payload["ask_other_action_info"]["action_list"] == ["hu", "pass"]
    assert other_payload["ask_other_action_info"]["cut_tile"] == 41
    assert other_payload["ask_other_action_info"]["action_tick"] == 3


def test_game_start_payload_uses_viewer_safe_state() -> None:
    game = NewRuleGameState()
    game.player_list[0].hand_tiles = [11, 12, 13]
    game.player_list[0].combination_tiles = ["G15"]
    game.player_list[1].hand_tiles = [21, 22, 23]

    payload = game_start_payload(game, 1)

    assert payload["type"] == "gamestate/new_rule/game_start"
    assert payload["player_index"] == 1
    assert payload["game_info"]["players_info"][0]["hand_tiles"] is None
    assert payload["game_info"]["players_info"][0]["combination_tiles"] == ["G0"]
    assert payload["game_info"]["players_info"][1]["hand_tiles"] == [21, 22, 23]


def test_pending_action_payload_replays_standard_action_ask() -> None:
    game = NewRuleGameState()
    game.initialize_round()
    game.game_status = "waiting_action_after_cut"
    game.live_pending_window = {"status": "waiting_action_after_cut", "tile": 41}
    game.action_dict = {0: [], 1: ["hu", "pass"], 2: [], 3: []}
    game.server_action_tick = 9

    payload = pending_action_payload(game, 1)

    assert payload is not None
    assert payload["type"] == "gamestate/new_rule/ask_other_action"
    assert payload["player_index"] == 1
    assert payload["action_list"] == ["hu", "pass"]
    assert payload["action_tick"] == 9
    assert payload["ask_other_action_info"]["cut_tile"] == 41


def test_game_start_payload_after_end_reveals_final_state_and_applies_scores_once() -> None:
    game = NewRuleGameState()
    game.game_status = "END"
    game.ended_by = "win"
    game.player_list[0].hand_tiles = [11, 12, 13]
    game.player_list[0].combination_tiles = ["G15"]
    game.player_list[1].hand_tiles = [21, 22, 23]
    game.deferred_hu_settlements = [
        {
            "winner": 1,
            "points": 8,
            "fan_ids": ["duiduihu"],
            "score_changes": [-48, 48, 0, 0],
        }
    ]

    first_payload = game_start_payload(game, 1, reveal_final=True)
    second_payload = game_start_payload(game, 1, reveal_final=True)

    player_zero = first_payload["game_info"]["players_info"][0]
    assert player_zero["hand_tiles"] == [11, 12, 13]
    assert player_zero["combination_tiles"] == ["G15"]
    assert first_payload["game_info"]["players_info"][0]["score"] == -48
    assert first_payload["game_info"]["players_info"][1]["score"] == 48
    assert second_payload["game_info"]["players_info"][0]["score"] == -48
    assert second_payload["game_info"]["players_info"][1]["score"] == 48


def run() -> None:
    tests = [
        test_game_info_masks_concealed_kong_for_other_players,
        test_mid_hand_win_payload_hides_fans_points_and_self_draw_tile,
        test_mid_hand_discard_win_keeps_public_discard_tile_but_hides_scoring,
        test_deal_tile_payload_hides_drawn_tile_from_other_viewers,
        test_final_settlement_reveals_hands_concealed_kongs_and_deferred_results,
        test_final_settlement_keeps_zero_point_empty_fan_result,
        test_final_settlement_applies_score_changes_once,
        test_final_settlement_sums_multiple_score_changes_once,
        test_final_settlement_without_winners_emits_unity_draw_result,
        test_ask_action_payload_includes_action_tick_and_actions,
        test_ask_action_payload_includes_unity_bridge_fields,
        test_game_start_payload_uses_viewer_safe_state,
        test_pending_action_payload_replays_standard_action_ask,
        test_game_start_payload_after_end_reveals_final_state_and_applies_scores_once,
    ]
    for test in tests:
        test()
    print(f"new_rule boardcast tests ok: {len(tests)} tests")


if __name__ == "__main__":
    run()
