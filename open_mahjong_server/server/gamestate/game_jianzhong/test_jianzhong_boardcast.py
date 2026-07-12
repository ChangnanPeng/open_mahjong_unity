from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace

SERVER_ROOT = Path(__file__).resolve().parents[3]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from server.gamestate.game_jianzhong import JianzhongGameState
from server.gamestate.game_jianzhong.boardcast import (
    ask_action_payload,
    final_settlement_payload,
    final_settlement_payloads,
    game_end_payload,
    game_start_payload,
    game_info_payload,
    mid_hand_hu_result_payload,
    pending_action_payload,
    ready_status_payload,
    visible_action_payload,
)


def test_game_info_masks_concealed_kong_for_other_players() -> None:
    game = JianzhongGameState()
    game.player_list[0].hand_tiles = [11, 12, 13]
    game.player_list[0].combination_tiles = ["G15"]
    game.player_list[0].combination_mask = [[2, 15, 2, 15, 2, 15, 2, 15]]

    owner_view = game_info_payload(game, 0)
    other_view = game_info_payload(game, 1)

    assert owner_view["players_info"][0]["combination_tiles"] == ["G15"]
    assert owner_view["players_info"][0]["combination_mask"] == [[2, 15, 2, 15, 2, 15, 2, 15]]
    assert other_view["players_info"][0]["combination_tiles"] == ["G0"]
    assert other_view["players_info"][0]["combination_mask"] == [[2, 0, 2, 0, 2, 0, 2, 0]]
    assert other_view["players_info"][0]["hand_tiles"] is None
    assert other_view["players_info"][0]["hand_tiles_count"] == 3


def test_game_info_preserves_player_cosmetics_and_room_state() -> None:
    room_data = JianzhongGameState._default_room_data()
    room_data.update({
        "allow_spectator": True,
        "claim_protection": False,
        "player_settings": {
            101: {
                "username": "p1",
                "title_id": 7,
                "profile_image_id": 8,
                "character_id": 9,
                "voice_id": 10,
            },
        },
    })
    game = JianzhongGameState(room_data=room_data)

    payload = game_info_payload(game, 0)
    player = payload["players_info"][0]

    assert player["title_used"] == 7
    assert player["profile_used"] == 8
    assert player["character_used"] == 9
    assert player["voice_used"] == 10
    assert payload["commitment"] == game.commitment
    assert payload["salt"] == game.salt
    assert payload["claim_protection"] is False
    assert payload["isPlayerSetRandomSeed"] is game.isPlayerSetRandomSeed


def test_visible_concealed_kong_payload_masks_other_viewers_but_keeps_mask_shape() -> None:
    game = JianzhongGameState()
    action_info = {
        "action": "angang",
        "player": 0,
        "tile": 15,
        "meld_code": "G15",
        "combination_mask": [2, 15, 2, 15, 2, 15, 2, 15],
    }

    owner_payload = visible_action_payload(game, 0, action_info)
    other_payload = visible_action_payload(game, 1, action_info)

    assert owner_payload["do_action_info"]["combination_target"] == "G15"
    assert owner_payload["do_action_info"]["combination_mask"] == [2, 15, 2, 15, 2, 15, 2, 15]
    assert other_payload["do_action_info"]["combination_target"] == "G0"
    assert other_payload["do_action_info"]["combination_mask"] == [2, 0, 2, 0, 2, 0, 2, 0]


def test_mid_hand_win_payload_hides_fans_points_and_self_draw_tile() -> None:
    game = JianzhongGameState()

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

    result_payload = mid_hand_hu_result_payload(
        game,
        1,
        {
            "source": "self_draw",
            "winner": 0,
            "tile": 41,
        },
    )
    assert result_payload["show_result_info"]["hepai_tile"] == 0


def test_mid_hand_discard_win_keeps_public_discard_tile_but_hides_scoring() -> None:
    game = JianzhongGameState()

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


def test_mid_hand_result_carries_multi_ron_recycle_contract() -> None:
    game = JianzhongGameState()
    settlement = {
        "source": "discard",
        "winner": 1,
        "discarder": 0,
        "tile": 41,
    }

    payload = mid_hand_hu_result_payload(
        game,
        2,
        settlement,
        multi_ron=True,
        recycle_discard=False,
    )

    info = payload["show_result_info"]
    assert info["multi_ron"] is True
    assert info["recycle_discard"] is False
    assert info["ron_discarder_index"] == 0


def test_deal_tile_payload_hides_drawn_tile_from_other_viewers() -> None:
    game = JianzhongGameState()

    owner_payload = visible_action_payload(game, 0, {"action": "deal_tile", "player": 0, "tile": 31})
    other_payload = visible_action_payload(game, 1, {"action": "deal_tile", "player": 0, "tile": 31})

    assert owner_payload["do_action_info"]["action_list"] == ["deal_tile"]
    assert owner_payload["tile"] == 31
    assert owner_payload["do_action_info"]["deal_tile"] == 31
    assert other_payload["tile"] is None
    assert other_payload["do_action_info"]["deal_tile"] is None


def test_claim_protection_delays_cut_for_non_claiming_viewers() -> None:
    class FakeWebSocket:
        def __init__(self) -> None:
            self.sent = []

        async def send_json(self, payload: dict) -> None:
            self.sent.append(payload)

    async def scenario() -> None:
        game = JianzhongGameState()
        game.claim_protect_delay = 60
        connections = {}
        for player in game.player_list:
            websocket = FakeWebSocket()
            connections[player.user_id] = SimpleNamespace(websocket=websocket)
        game.game_server = SimpleNamespace(
            user_id_to_connection=connections,
            friend_manager=None,
        )

        game.begin_claim_protection({0: [], 1: ["hu", "pass"], 2: [], 3: []}, 0)
        game.emit_visible_action_payloads({"action": "cut", "player": 0, "tile": 31})
        await game.flush_outbound_payloads()

        assert len(connections[101].websocket.sent) == 1
        assert len(connections[102].websocket.sent) == 1
        assert connections[103].websocket.sent == []
        assert connections[104].websocket.sent == []

        await game.finish_claim_protection()

        assert len(connections[103].websocket.sent) == 1
        assert len(connections[104].websocket.sent) == 1
        await game.cleanup_game_state()

    asyncio.run(scenario())


def test_claim_payload_identifies_the_discarder() -> None:
    game = JianzhongGameState()

    payload = visible_action_payload(
        game,
        2,
        {
            "action": "peng",
            "player": 1,
            "tile": 31,
            "meld_code": "k31",
            "combination_mask": [1, 31, 0, 31, 0, 31],
            "cut_from_player": 0,
        },
    )

    assert payload["do_action_info"]["cut_from_player"] == 0


def test_final_settlement_reveals_hands_concealed_kongs_and_deferred_results() -> None:
    game = JianzhongGameState()
    game.player_list[0].hand_tiles = [11, 12, 13]
    game.player_list[0].combination_tiles = ["G15"]
    game.deferred_hu_settlements = [
        {
            "winner": 0,
            "points": 8,
            "fan_ids": ["pinfu"],
            "fan_names": ["平和"],
        }
    ]
    game.ended_by = "win"

    payload = final_settlement_payload(game, 1)

    player_zero = payload["game_info"]["players_info"][0]
    assert player_zero["hand_tiles"] == [11, 12, 13]
    assert player_zero["combination_tiles"] == ["G15"]
    assert payload["show_result_info"]["hepai_player_index"] == 0
    assert payload["show_result_info"]["hu_score"] == 8
    assert payload["show_result_info"]["hu_fan"] == ["pinfu"]
    assert payload["show_result_info"]["hu_class"] == "hu_first"
    assert payload["show_result_info"]["player_to_score"] == {
        0: game.player_list[0].score,
        1: game.player_list[1].score,
        2: game.player_list[2].score,
        3: game.player_list[3].score,
    }


def test_final_settlement_keeps_zero_point_empty_fan_result() -> None:
    game = JianzhongGameState()
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


def test_final_settlement_preserves_zero_discarder_index() -> None:
    game = JianzhongGameState()
    game.deferred_hu_settlements = [
        {
            "source": "discard",
            "discarder": 0,
            "winner": 1,
            "tile": 41,
            "points": 8,
            "fan_ids": ["pinfu"],
            "score_changes": [-48, 48, 0, 0],
        }
    ]
    game.ended_by = "win"

    payload = final_settlement_payload(game, 2)

    assert payload["show_result_info"]["ron_discarder_index"] == 0


def test_final_settlement_applies_score_changes_once() -> None:
    game = JianzhongGameState()
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
    game = JianzhongGameState()
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
    assert first_payload["show_result_info"]["score_changes"] == {0: -10, 1: 0, 2: 30, 3: -20}


def test_final_settlement_payloads_emit_each_winner_in_order() -> None:
    game = JianzhongGameState()
    game.deferred_hu_settlements = [
        {
            "winner": 1,
            "source": "discard",
            "discarder": 0,
            "points": 8,
            "fan_ids": ["pinfu"],
            "score_changes": [-48, 48, 0, 0],
        },
        {
            "winner": 2,
            "source": "self_draw",
            "points": 5,
            "fan_ids": ["haitei"],
            "score_changes": [-10, 0, 30, -20],
        },
    ]
    game.ended_by = "win"

    payloads = final_settlement_payloads(game, 0)

    assert [payload["show_result_info"]["hepai_player_index"] for payload in payloads] == [1, 2]
    assert [payload["show_result_info"]["hu_fan"] for payload in payloads] == [["pinfu"], ["haitei"]]
    assert [payload["show_result_info"]["liuju_status_final"] for payload in payloads] == [False, True]
    assert all(payload["show_result_info"]["liuju_step"] == "settle_hu" for payload in payloads)
    assert [payload["show_result_info"]["score_changes"] for payload in payloads] == [
        {0: -48, 1: 48, 2: 0, 3: 0},
        {0: -10, 1: 0, 2: 30, 3: -20},
    ]
    assert [payload["show_result_info"]["player_to_score"] for payload in payloads] == [
        {0: -48, 1: 48, 2: 0, 3: 0},
        {0: -58, 1: 48, 2: 30, 3: -20},
    ]
    total_from_panels = {idx: 0 for idx in range(4)}
    for payload in payloads:
        for player_index, change in payload["show_result_info"]["score_changes"].items():
            total_from_panels[player_index] += change
    assert total_from_panels == {0: -58, 1: 48, 2: 30, 3: -20}
    assert [player.score for player in game.player_list] == [-58, 48, 30, -20]


def test_final_settlement_panel_scores_inherit_from_existing_scores() -> None:
    game = JianzhongGameState()
    game.player_list[0].score = 100
    game.player_list[1].score = 200
    game.player_list[2].score = 300
    game.player_list[3].score = 400
    game.deferred_hu_settlements = [
        {
            "winner": 1,
            "source": "discard",
            "discarder": 0,
            "points": 8,
            "score_changes": [-48, 48, 0, 0],
        },
        {
            "winner": 2,
            "source": "self_draw",
            "points": 5,
            "score_changes": [-10, 0, 30, -20],
        },
    ]
    game.ended_by = "win"

    payloads = final_settlement_payloads(game, 0)

    assert [payload["show_result_info"]["player_to_score"] for payload in payloads] == [
        {0: 52, 1: 248, 2: 300, 3: 400},
        {0: 42, 1: 248, 2: 330, 3: 380},
    ]
    assert [player.score for player in game.player_list] == [42, 248, 330, 380]


def test_final_settlement_maps_discard_win_to_unity_hu_classes() -> None:
    game = JianzhongGameState()
    game.deferred_hu_settlements = [
        {"winner": 1, "source": "discard", "discarder": 0, "points": 1},
        {"winner": 2, "source": "discard", "discarder": 0, "points": 1},
        {"winner": 3, "source": "discard", "discarder": 0, "points": 1},
    ]
    game.ended_by = "win"

    payloads = final_settlement_payloads(game, 0)

    assert [payload["show_result_info"]["hu_class"] for payload in payloads] == [
        "hu_first",
        "hu_second",
        "hu_third",
    ]


def test_final_settlement_without_winners_emits_unity_draw_result() -> None:
    game = JianzhongGameState()
    game.game_status = "END"
    game.ended_by = "wall"
    game.deferred_hu_settlements = []

    payload = final_settlement_payload(game, 0)

    assert payload["type"] == "gamestate/jianzhong/show_result"
    assert payload["show_result_info"]["hepai_player_index"] == -1
    assert payload["show_result_info"]["hu_class"] == "liuju"
    assert payload["show_result_info"]["hu_score"] == 0
    assert payload["show_result_info"]["hu_fan"] == []
    assert payload["show_result_info"]["liuju_step"] == "final"
    assert payload["show_result_info"]["liuju_status_final"] is True


def test_ask_action_payload_includes_action_tick_and_actions() -> None:
    game = JianzhongGameState()
    game.server_action_tick = 7

    payload = ask_action_payload(game, 2, ["hu", "pass"], cut_tile=41)

    assert payload["type"] == "gamestate/jianzhong/ask_other_action"
    assert payload["player_index"] == 2
    assert payload["action_list"] == ["hu", "pass"]
    assert payload["action_tick"] == 7
    assert payload["cut_tile"] == 41


def test_ask_action_payload_includes_unity_bridge_fields() -> None:
    game = JianzhongGameState()
    game.initialize_round()
    game.server_action_tick = 3

    hand_payload = ask_action_payload(game, 0, ["cut"])
    other_payload = ask_action_payload(game, 1, ["hu", "pass"], cut_tile=41)

    assert hand_payload["game_info"]["room_rule"] == "jianzhong"
    assert hand_payload["game_info"]["sub_rule"] == "jianzhong/standard"
    assert hand_payload["game_info"]["self_hand_tiles"] == game.player_list[0].hand_tiles
    assert hand_payload["type"] == "gamestate/jianzhong/broadcast_hand_action"
    assert hand_payload["ask_hand_action_info"]["action_list"] == ["cut"]
    assert hand_payload["ask_hand_action_info"]["remain_tiles"] == len(game.tiles_list)
    assert hand_payload["ask_other_action_info"] is None

    assert other_payload["type"] == "gamestate/jianzhong/ask_other_action"
    assert other_payload["ask_hand_action_info"] is None
    assert other_payload["ask_other_action_info"]["action_list"] == ["hu", "pass"]
    assert other_payload["ask_other_action_info"]["cut_tile"] == 41
    assert other_payload["ask_other_action_info"]["action_tick"] == 3


def test_game_start_payload_uses_viewer_safe_state() -> None:
    game = JianzhongGameState()
    game.player_list[0].hand_tiles = [11, 12, 13]
    game.player_list[0].combination_tiles = ["G15"]
    game.player_list[1].hand_tiles = [21, 22, 23]

    payload = game_start_payload(game, 1)

    assert payload["type"] == "gamestate/jianzhong/game_start"
    assert payload["player_index"] == 1
    assert payload["game_info"]["players_info"][0]["hand_tiles"] is None
    assert payload["game_info"]["players_info"][0]["combination_tiles"] == ["G0"]
    assert payload["game_info"]["players_info"][1]["hand_tiles"] == [21, 22, 23]


def test_pending_action_payload_replays_standard_action_ask() -> None:
    game = JianzhongGameState()
    game.initialize_round()
    game.game_status = "waiting_action_after_cut"
    game.live_pending_window = {"status": "waiting_action_after_cut", "tile": 41}
    game.action_dict = {0: [], 1: ["hu", "pass"], 2: [], 3: []}
    game.server_action_tick = 9

    payload = pending_action_payload(game, 1)

    assert payload is not None
    assert payload["type"] == "gamestate/jianzhong/ask_other_action"
    assert payload["player_index"] == 1
    assert payload["action_list"] == ["hu", "pass"]
    assert payload["action_tick"] == 9
    assert payload["ask_other_action_info"]["cut_tile"] == 41


def test_game_start_payload_after_end_reveals_final_state_and_applies_scores_once() -> None:
    game = JianzhongGameState()
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


def test_score_history_records_one_aggregate_row_and_broadcasts_it() -> None:
    game = JianzhongGameState()
    game.current_round = 7
    game.deferred_hu_settlements = [
        {
            "winner": 1,
            "score_changes": [-48, 48, 0, 0],
        },
        {
            "winner": 2,
            "score_changes": [-10, 0, 30, -20],
        },
    ]

    first_payloads = final_settlement_payloads(game, 0)
    second_payloads = final_settlement_payloads(game, 0)

    histories = [
        info["score_history"]
        for info in first_payloads[-1]["game_info"]["players_info"]
    ]
    round_histories = [
        info["round_number_history"]
        for info in first_payloads[-1]["game_info"]["players_info"]
    ]
    assert histories == [["-58"], ["+48"], ["+30"], ["-20"]]
    assert round_histories == [[7], [7], [7], [7]]
    assert [player.score_history for player in game.player_list] == histories
    assert [player.round_number_history for player in game.player_list] == round_histories
    assert second_payloads[-1]["game_info"]["players_info"][0]["score_history"] == ["-58"]


def test_score_history_records_zero_row_for_no_winner_draw() -> None:
    game = JianzhongGameState()
    game.current_round = 3

    payload = final_settlement_payload(game, 0)

    assert [
        info["score_history"]
        for info in payload["game_info"]["players_info"]
    ] == [["0"], ["0"], ["0"], ["0"]]
    assert [
        info["round_number_history"]
        for info in payload["game_info"]["players_info"]
    ] == [[3], [3], [3], [3]]


def test_ready_status_payload_uses_existing_ready_shape() -> None:
    game = JianzhongGameState()
    game.action_dict = {0: ["ready"], 1: [], 2: [], 3: []}

    payload = ready_status_payload(game, 0)

    assert payload["type"] == "gamestate/jianzhong/ready_status"
    assert payload["player_index"] == 0
    assert payload["ready_status_info"]["player_to_ready"] == {
        0: False,
        1: True,
        2: True,
        3: True,
    }


def test_game_end_payload_uses_existing_game_end_shape() -> None:
    game = JianzhongGameState()
    game.player_list[0].score = 30
    game.player_list[1].score = -10
    game.player_list[0].record_counter.rank_result = 1
    game.player_list[1].record_counter.rank_result = 2

    payload = game_end_payload(game, 0)

    assert payload["type"] == "gamestate/jianzhong/game_end"
    assert payload["player_index"] == 0
    assert payload["game_end_info"]["master_seed"] == str(game.master_seed)
    assert payload["game_end_info"]["player_final_data"]["0"]["rank"] == 1
    assert payload["game_end_info"]["player_final_data"]["0"]["score"] == 30
    assert payload["game_end_info"]["player_final_data"]["1"]["rank"] == 2


def run() -> None:
    tests = [
        test_game_info_masks_concealed_kong_for_other_players,
        test_game_info_preserves_player_cosmetics_and_room_state,
        test_visible_concealed_kong_payload_masks_other_viewers_but_keeps_mask_shape,
        test_mid_hand_win_payload_hides_fans_points_and_self_draw_tile,
        test_mid_hand_discard_win_keeps_public_discard_tile_but_hides_scoring,
        test_mid_hand_result_carries_multi_ron_recycle_contract,
        test_deal_tile_payload_hides_drawn_tile_from_other_viewers,
        test_claim_protection_delays_cut_for_non_claiming_viewers,
        test_claim_payload_identifies_the_discarder,
        test_final_settlement_reveals_hands_concealed_kongs_and_deferred_results,
        test_final_settlement_keeps_zero_point_empty_fan_result,
        test_final_settlement_preserves_zero_discarder_index,
        test_final_settlement_applies_score_changes_once,
        test_final_settlement_sums_multiple_score_changes_once,
        test_final_settlement_payloads_emit_each_winner_in_order,
        test_final_settlement_panel_scores_inherit_from_existing_scores,
        test_final_settlement_maps_discard_win_to_unity_hu_classes,
        test_final_settlement_without_winners_emits_unity_draw_result,
        test_ask_action_payload_includes_action_tick_and_actions,
        test_ask_action_payload_includes_unity_bridge_fields,
        test_game_start_payload_uses_viewer_safe_state,
        test_pending_action_payload_replays_standard_action_ask,
        test_game_start_payload_after_end_reveals_final_state_and_applies_scores_once,
        test_score_history_records_one_aggregate_row_and_broadcasts_it,
        test_score_history_records_zero_row_for_no_winner_draw,
        test_ready_status_payload_uses_existing_ready_shape,
        test_game_end_payload_uses_existing_game_end_shape,
    ]
    for test in tests:
        test()
    print(f"jianzhong boardcast tests ok: {len(tests)} tests")


if __name__ == "__main__":
    run()
