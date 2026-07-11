from __future__ import annotations

from pathlib import Path
import sys

SERVER_ROOT = Path(__file__).resolve().parents[3]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from server.gamestate.game_jianzhong import JianzhongGameState
from server.gamestate.game_jianzhong.action_check import (
    check_action_after_cut,
    check_action_hand_action,
    check_action_jiagang,
    check_only_cut,
    refresh_waiting_tiles,
)


def prepared_game() -> JianzhongGameState:
    game = JianzhongGameState()
    game.initialize_round()
    for player in game.player_list:
        player.hand_tiles = []
        player.waiting_tiles = set()
        player.combination_tiles = []
    game.current_player_index = 0
    game.tiles_list = [11, 12, 13]
    return game


def test_hand_action_cut_hu_angang_jiagang() -> None:
    game = prepared_game()
    player = game.player_list[0]
    player.hand_tiles = [11, 11, 11, 11, 22, 22, 22, 33, 33, 33, 45, 45, 47, 47]
    player.waiting_tiles = {22}
    player.combination_tiles = ["k22"]
    player.hand_tiles.append(22)

    actions = check_action_hand_action(game, 0)
    assert "hu_self" in actions[0], actions
    assert "angang" in actions[0], actions
    assert "jiagang" in actions[0], actions
    assert "cut" in actions[0], actions


def test_hand_action_no_kong_when_wall_empty() -> None:
    game = prepared_game()
    game.tiles_list = []
    game.player_list[0].hand_tiles = [11, 11, 11, 11, 22, 22, 22, 33, 33, 33, 45, 45, 47, 47]
    actions = check_action_hand_action(game, 0)
    assert "angang" not in actions[0], actions
    assert "jiagang" not in actions[0], actions
    assert actions[0] == ["cut"], actions


def test_after_cut_allows_chi_peng_gang_hu_when_wall_has_tiles() -> None:
    game = prepared_game()
    game.player_list[1].hand_tiles = [13, 14, 18]
    game.player_list[2].hand_tiles = [15, 15, 15]
    game.player_list[2].waiting_tiles = {15}
    game.player_list[3].waiting_tiles = {15}

    actions = check_action_after_cut(game, 15)
    assert "chi_left" in actions[1], actions
    assert "peng" in actions[2], actions
    assert "gang" in actions[2], actions
    assert "hu" in actions[2], actions
    assert "hu" in actions[3], actions
    assert actions[0] == [], actions
    assert actions[1][-1] == "pass", actions
    assert actions[2][-1] == "pass", actions
    assert actions[3][-1] == "pass", actions


def test_after_cut_chi_only_fixed_next_seat_not_next_active_player() -> None:
    game = prepared_game()
    game.mark_player_hu(1)
    game.player_list[2].hand_tiles = [13, 14, 18]

    actions = check_action_after_cut(game, 15)
    assert actions[1] == [], actions
    assert "chi_left" not in actions[2], actions


def test_final_discard_only_allows_hu() -> None:
    game = prepared_game()
    game.tiles_list = []
    game.player_list[1].hand_tiles = [13, 14]
    game.player_list[2].hand_tiles = [15, 15, 15]
    game.player_list[2].waiting_tiles = {15}

    actions = check_action_after_cut(game, 15)
    assert actions[1] == [], actions
    assert actions[2] == ["hu", "pass"], actions
    assert actions[3] == [], actions


def test_discard_win_lockout_blocks_hu_but_not_melds() -> None:
    game = prepared_game()
    game.player_list[2].hand_tiles = [15, 15, 15]
    game.player_list[2].waiting_tiles = {15}
    game.add_discard_win_lockout(2, 15)

    actions = check_action_after_cut(game, 15)
    assert "hu" not in actions[2], actions
    assert "peng" in actions[2], actions
    assert "gang" in actions[2], actions


def test_rob_kong_respects_lockout_and_skips_winners() -> None:
    game = prepared_game()
    game.player_list[1].waiting_tiles = {15}
    game.player_list[2].waiting_tiles = {15}
    game.player_list[3].waiting_tiles = {15}
    game.add_discard_win_lockout(2, 15)
    game.mark_player_hu(3)

    actions = check_action_jiagang(game, 15)
    assert actions[1] == ["hu", "pass"], actions
    assert actions[2] == [], actions
    assert actions[3] == [], actions


def test_after_chi_peng_only_cut() -> None:
    game = prepared_game()
    game.player_list[1].hand_tiles = [11, 11, 11, 11]
    game.player_list[1].combination_tiles = ["k11"]
    actions = check_only_cut(game, 1)
    assert actions[1] == ["cut"], actions


def test_refresh_waiting_tiles_from_jianzhong_calculator() -> None:
    game = prepared_game()
    game.player_list[1].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 45, 45, 45, 41]

    waits = refresh_waiting_tiles(game, 1)
    assert 41 in waits, waits
    assert game.player_list[1].waiting_tiles == waits


def run() -> None:
    tests = [
        test_hand_action_cut_hu_angang_jiagang,
        test_hand_action_no_kong_when_wall_empty,
        test_after_cut_allows_chi_peng_gang_hu_when_wall_has_tiles,
        test_after_cut_chi_only_fixed_next_seat_not_next_active_player,
        test_final_discard_only_allows_hu,
        test_discard_win_lockout_blocks_hu_but_not_melds,
        test_rob_kong_respects_lockout_and_skips_winners,
        test_after_chi_peng_only_cut,
        test_refresh_waiting_tiles_from_jianzhong_calculator,
    ]
    for test in tests:
        test()
    print(f"jianzhong action_check tests ok: {len(tests)} tests")


if __name__ == "__main__":
    run()
