"""四川麻将顺和：跳过和牌后仅拦截 ≤ 放弃番数的点炮/抢杠；更高番可和；自摸不受限。"""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from server.gamestate.game_sichuan.action_check import check_action_hand_action, check_hepai
from server.gamestate.game_sichuan.shunhe import (
    activate_shunhe_if_tenpai_discard,
    is_blocked_by_shunhe,
    record_passed_self_draw_shunhe,
    record_skipped_win_fan,
)


class DummyPlayer:
    def __init__(self, player_index=0, waiting_tiles=None):
        self.player_index = player_index
        self.waiting_tiles = set(waiting_tiles or [])
        self.shunhe_skipped_fan = None
        self.shunhe_passed_max_fan = None
        self.tag_list = []
        self.hand_tiles = []
        self.combination_tiles = []
        self.is_hu = False
        self.dingque_suit = 0


class ShunheCoreTests(unittest.TestCase):
    def test_higher_fan_not_blocked(self):
        p = DummyPlayer(waiting_tiles={11})
        record_skipped_win_fan(p, 1)
        self.assertEqual(p.shunhe_passed_max_fan, 1)
        self.assertTrue(is_blocked_by_shunhe(p, 0))
        self.assertTrue(is_blocked_by_shunhe(p, 1))
        self.assertFalse(is_blocked_by_shunhe(p, 2))
        self.assertFalse(is_blocked_by_shunhe(p, 5))

    def test_active_cap_uses_max(self):
        p = DummyPlayer(waiting_tiles={11})
        record_skipped_win_fan(p, 3)
        record_skipped_win_fan(p, 1)
        self.assertEqual(p.shunhe_passed_max_fan, 3)
        self.assertTrue(is_blocked_by_shunhe(p, 3))
        self.assertFalse(is_blocked_by_shunhe(p, 4))

    def test_pending_cap_uses_max(self):
        p = DummyPlayer(waiting_tiles=set())
        record_skipped_win_fan(p, 2)
        record_skipped_win_fan(p, 4)
        self.assertIsNone(p.shunhe_passed_max_fan)
        self.assertEqual(p.shunhe_skipped_fan, 4)
        activate_shunhe_if_tenpai_discard(p, was_tenpai=True)
        self.assertEqual(p.shunhe_passed_max_fan, 4)

    def test_check_hepai_allows_higher_fan_ron(self):
        player = DummyPlayer(player_index=1, waiting_tiles={22})
        player.shunhe_passed_max_fan = 1
        player.hand_tiles = [11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 23, 22, 22]
        gs = SimpleNamespace(
            player_list=[DummyPlayer(0), player, DummyPlayer(2), DummyPlayer(3)],
            sichuan_hu_results={},
            tiles_list=[99] * 20,
            dead_wall_count=0,
            last_action_was_gang=False,
            calculation_service=MagicMock(),
        )
        gs.calculation_service.Sichuan_hepai_check.return_value = (2, ["清一色"])
        temp = {0: [], 1: [], 2: [], 3: []}
        check_hepai(gs, temp, 22, 1, "dianhe")
        self.assertIn("hu", temp[1])
        self.assertEqual(gs.sichuan_hu_results[1]["fan"], 2)

    def test_check_hepai_blocks_equal_or_lower_fan_ron(self):
        player = DummyPlayer(player_index=1, waiting_tiles={22})
        player.shunhe_passed_max_fan = 2
        player.hand_tiles = [11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 23, 22, 22]
        gs = SimpleNamespace(
            player_list=[DummyPlayer(0), player, DummyPlayer(2), DummyPlayer(3)],
            sichuan_hu_results={},
            tiles_list=[99] * 20,
            dead_wall_count=0,
            last_action_was_gang=False,
            calculation_service=MagicMock(),
        )
        gs.calculation_service.Sichuan_hepai_check.return_value = (2, ["大对子", "杠"])
        temp = {0: [], 1: [], 2: [], 3: []}
        check_hepai(gs, temp, 22, 1, "dianhe")
        self.assertNotIn("hu", temp[1])
        self.assertNotIn(1, gs.sichuan_hu_results)

    def test_stale_zimo_result_cleared_on_hand_action(self):
        """杠后补牌若不能自摸，必须清掉旧 is_zimo，避免切牌误记顺和。"""
        player = DummyPlayer(player_index=0, waiting_tiles=set())
        player.hand_tiles = [11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 23, 24, 25]
        gs = SimpleNamespace(
            player_list=[player, DummyPlayer(1), DummyPlayer(2), DummyPlayer(3)],
            sichuan_hu_results={
                0: {"fan": 5, "fan_list": ["清一色", "七对"], "is_zimo": True, "hepai_tile": 25, "way": []},
            },
            tiles_list=[99] * 20,
            dead_wall_count=0,
            last_action_was_gang=False,
            calculation_service=MagicMock(),
        )
        gs.calculation_service.Sichuan_tingpai_check.return_value = set()
        check_action_hand_action(gs, 0)
        self.assertNotIn(0, gs.sichuan_hu_results)
        self.assertFalse(record_passed_self_draw_shunhe(gs, 0))
        self.assertIsNone(player.shunhe_passed_max_fan)


if __name__ == "__main__":
    unittest.main()
