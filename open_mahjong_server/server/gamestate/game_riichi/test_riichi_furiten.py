"""日麻放过荣和 → 同巡/立直振听 回归测试。"""
from __future__ import annotations

import unittest
from types import SimpleNamespace

from server.gamestate.game_riichi.wait_action import (
    _apply_passed_ron_furiten,
    _ron_eligible_indexes_from_action_dict,
)


class RiichiPassedRonFuritenTest(unittest.TestCase):
    def test_snapshot_survives_action_dict_clear_after_pass(self):
        """复现：立直家 pass 后自身 action_dict 被清空，事后再扫会漏掉 eligible。"""
        action_dict = {
            0: [],
            1: ["hu_first", "pass"],
            2: [],
            3: [],
        }
        snapshot = _ron_eligible_indexes_from_action_dict(action_dict)
        self.assertEqual(snapshot, [1])

        # 等待循环在玩家响应后清空该座位操作列表（与 wait_action 一致）
        action_dict[1] = []
        buggy_late_scan = _ron_eligible_indexes_from_action_dict(action_dict)
        self.assertEqual(buggy_late_scan, [])
        self.assertEqual(snapshot, [1])

    def test_apply_passed_ron_sets_riichi_furiten(self):
        players = [
            SimpleNamespace(tag_list=[], temp_furiten=False, riichi_furiten=False),
            SimpleNamespace(tag_list=["riichi"], temp_furiten=False, riichi_furiten=False),
            SimpleNamespace(tag_list=[], temp_furiten=False, riichi_furiten=False),
            SimpleNamespace(tag_list=[], temp_furiten=False, riichi_furiten=False),
        ]
        gs = SimpleNamespace(player_list=players)

        _apply_passed_ron_furiten(gs, [1])

        self.assertTrue(players[1].temp_furiten)
        self.assertTrue(players[1].riichi_furiten)
        self.assertFalse(players[0].temp_furiten)
        self.assertFalse(players[0].riichi_furiten)

    def test_apply_passed_ron_empty_eligible_is_noop(self):
        """旧 bug：eligible 为空时直接 return，立直振听永不挂上。"""
        players = [
            SimpleNamespace(tag_list=["riichi"], temp_furiten=False, riichi_furiten=False),
        ]
        gs = SimpleNamespace(player_list=players)
        _apply_passed_ron_furiten(gs, [])
        self.assertFalse(players[0].temp_furiten)
        self.assertFalse(players[0].riichi_furiten)

    def test_multi_eligible_snapshot_keeps_early_passer(self):
        """多人可荣和时，先 pass 的座位也会被快照保留。"""
        action_dict = {
            0: [],
            1: ["hu_first", "pass"],
            2: ["hu_second", "peng", "pass"],
            3: [],
        }
        snapshot = _ron_eligible_indexes_from_action_dict(action_dict)
        self.assertEqual(snapshot, [1, 2])
        action_dict[1] = []  # 先 pass 的立直家
        self.assertEqual(_ron_eligible_indexes_from_action_dict(action_dict), [2])
        self.assertEqual(snapshot, [1, 2])


if __name__ == "__main__":
    unittest.main()
