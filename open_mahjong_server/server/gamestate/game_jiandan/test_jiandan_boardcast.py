from __future__ import annotations

from pathlib import Path
import sys

SERVER_ROOT = Path(__file__).resolve().parents[3]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from server.gamestate.game_jiandan import JiandanGameState
from server.gamestate.game_jiandan.boardcast import (
    ask_action_payload,
    final_settlement_payload,
    final_settlement_payloads,
    game_end_payload,
    game_info_payload,
    game_start_payload,
    pending_action_payload,
    ready_status_payload,
    visible_action_payload,
)


def test_game_info_masks_concealed_kong_for_other_players() -> None:
    game = JiandanGameState()
    game.player_list[0].hand_tiles = [11, 12, 13]
    game.player_list[0].combination_tiles = ["G15"]
    game.player_list[0].combination_mask = [[2, 15, 2, 15, 2, 15, 2, 15]]

    owner_view = game_info_payload(game, 0)
    other_view = game_info_payload(game, 1)

    assert owner_view["players_info"][0]["combination_tiles"] == ["G15"]
    assert other_view["players_info"][0]["combination_tiles"] == ["G0"]
    assert other_view["players_info"][0]["combination_mask"] == [[2, 0, 2, 0, 2, 0, 2, 0]]
    assert other_view["players_info"][0]["hand_tiles"] is None
    assert other_view["players_info"][0]["hand_tiles_count"] == 3


def test_game_info_uses_only_standard_room_contract() -> None:
    payload = game_info_payload(JiandanGameState(), 0)

    assert payload["room_rule"] == "jiandan"
    assert payload["sub_rule"] == "jiandan/standard"
    assert payload["hepai_limit"] == 0
    for excluded in (
        "hand_end_mode",
        "winner_target",
        "hand_flow",
        "presentation_profile",
        "rule_composition",
    ):
        assert excluded not in payload


def test_visible_self_draw_hides_private_tile_and_scoring() -> None:
    game = JiandanGameState()
    action = {
        "action": "hu_self",
        "player": 0,
        "tile": 41,
        "fan_ids": ["pinfu"],
        "points": 2,
    }

    owner_payload = visible_action_payload(game, 0, action)
    other_payload = visible_action_payload(game, 1, action)

    assert owner_payload["tile"] == 41
    assert other_payload["tile"] is None
    assert other_payload["fan_ids"] is None
    assert other_payload["fan_names"] is None
    assert other_payload["points"] is None


def test_visible_discard_win_keeps_public_tile_but_hides_scoring() -> None:
    payload = visible_action_payload(
        JiandanGameState(),
        0,
        {
            "action": "hu",
            "player": 2,
            "tile": 41,
            "fan_ids": ["pinfu"],
            "points": 2,
        },
    )

    assert payload["tile"] == 41
    assert payload["fan_ids"] is None
    assert payload["points"] is None


def test_visible_concealed_kong_masks_other_viewers() -> None:
    action = {
        "action": "angang",
        "player": 0,
        "tile": 15,
        "meld_code": "G15",
        "combination_mask": [2, 15, 2, 15, 2, 15, 2, 15],
    }

    owner_payload = visible_action_payload(JiandanGameState(), 0, action)
    other_payload = visible_action_payload(JiandanGameState(), 1, action)

    assert owner_payload["do_action_info"]["combination_target"] == "G15"
    assert other_payload["do_action_info"]["combination_target"] == "G0"
    assert other_payload["do_action_info"]["combination_mask"] == [2, 0, 2, 0, 2, 0, 2, 0]


def test_first_win_emits_one_final_result_and_applies_scores_once() -> None:
    game = JiandanGameState()
    game.player_list[1].hand_tiles = [11, 12, 13]
    game.deferred_hu_settlements = [
        {
            "source": "discard",
            "winner": 1,
            "discarder": 0,
            "tile": 41,
            "points": 8,
            "fan_ids": ["pinfu"],
            "score_changes": [-48, 48, 0, 0],
        }
    ]
    game.ended_by = "win"

    payloads = final_settlement_payloads(game, 0)
    repeated = final_settlement_payload(game, 1)

    assert len(payloads) == 1
    info = payloads[0]["show_result_info"]
    assert info["hepai_player_index"] == 1
    assert info["hu_score"] == 48
    assert info["hu_fan"] == ["pinfu"]
    assert info["ron_discarder_index"] == 0
    assert payloads[0]["game_info"]["players_info"][0]["score"] == -48
    assert repeated["game_info"]["players_info"][0]["score"] == -48
    for excluded in (
        "liuju_step",
        "liuju_status_final",
        "suppress_hand_reveal",
        "defer_score_settlement",
        "multi_ron",
        "recycle_discard",
    ):
        assert excluded not in info


def test_draw_emits_one_standard_result() -> None:
    game = JiandanGameState()
    game.ended_by = "wall_exhausted"

    payloads = final_settlement_payloads(game, 0)

    assert len(payloads) == 1
    info = payloads[0]["show_result_info"]
    assert info["hu_class"] == "liuju"
    assert info["hu_score"] == 0
    assert info["hepai_player_index"] == -1


def test_ask_action_payload_includes_standard_bridge_fields() -> None:
    game = JiandanGameState()
    game.server_action_tick = 7

    payload = ask_action_payload(game, 0, ["cut", "hu"])

    assert payload["type"] == "gamestate/jiandan/broadcast_hand_action"
    assert payload["action_tick"] == 7
    assert payload["ask_hand_action_info"]["action_list"] == ["cut", "hu"]
    assert payload["ask_hand_action_info"]["action_tick"] == 7


def test_pending_action_replays_standard_action_ask() -> None:
    game = JiandanGameState()
    game.game_status = "waiting_action_after_cut"
    game.live_pending_window = {"tile": 31}
    game.action_dict[1] = ["hu", "pass"]

    payload = pending_action_payload(game, 1)

    assert payload is not None
    assert payload["type"] == "gamestate/jiandan/ask_other_action"
    assert payload["cut_tile"] == 31
    assert payload["ask_other_action_info"]["action_list"] == ["hu", "pass"]


def test_game_start_ready_and_game_end_use_rule_routes() -> None:
    game = JiandanGameState()
    game.action_dict[0] = ["ready"]

    start = game_start_payload(game, 0)
    ready = ready_status_payload(game, 0)
    end = game_end_payload(game, 0)

    assert start["type"] == "gamestate/jiandan/game_start"
    assert ready["type"] == "gamestate/jiandan/ready_status"
    assert ready["ready_status_info"]["player_to_ready"][0] is False
    assert end["type"] == "gamestate/jiandan/game_end"
    assert len(end["game_end_info"]["player_final_data"]) == 4


def run() -> None:
    tests = [
        test_game_info_masks_concealed_kong_for_other_players,
        test_game_info_uses_only_standard_room_contract,
        test_visible_self_draw_hides_private_tile_and_scoring,
        test_visible_discard_win_keeps_public_tile_but_hides_scoring,
        test_visible_concealed_kong_masks_other_viewers,
        test_first_win_emits_one_final_result_and_applies_scores_once,
        test_draw_emits_one_standard_result,
        test_ask_action_payload_includes_standard_bridge_fields,
        test_pending_action_replays_standard_action_ask,
        test_game_start_ready_and_game_end_use_rule_routes,
    ]
    for test in tests:
        test()
    print(f"jiandan boardcast tests ok: {len(tests)} tests")


if __name__ == "__main__":
    run()
