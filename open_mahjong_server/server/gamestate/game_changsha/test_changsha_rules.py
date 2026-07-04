import unittest
from types import SimpleNamespace

from server.game_calculation.changsha.changsha_hepai_check import (
    INITIAL_HU_NAMES,
    changsha_base_from_fans,
    evaluate_changsha_initial_hu,
)
from server.gamestate.game_changsha.ChangshaGameState import ChangshaGameState
from server.gamestate.game_changsha.action_check import (
    check_action_after_cut,
    check_hepai,
)
from server.gamestate.game_changsha.init_tiles import init_changsha_tiles
from server.room.room_validators import ChangshaRoomValidator


class DummyPlayer:
    def __init__(self, player_index, hand_tiles=None, waiting_tiles=None):
        self.player_index = player_index
        self.hand_tiles = list(hand_tiles or [])
        self.waiting_tiles = set(waiting_tiles or [])
        self.combination_tiles = []
        self.combination_mask = []
        self.tag_list = []
        self.has_draw_slot = False

    def get_tile(self, tiles_list, *, mark_draw_slot=True):
        tile = tiles_list.pop(0)
        self.hand_tiles.append(tile)
        if mark_draw_slot:
            self.has_draw_slot = True
        return tile


class FixedCalculation:
    def __init__(self, result):
        self.result = result

    def Changsha_hepai_check(self, hand_list, tiles_combination, way_to_hepai, get_tile):
        return self.result


class FixedTingpai:
    def __init__(self, waiting_tiles):
        self.waiting_tiles = set(waiting_tiles)

    def Changsha_tingpai_check(self, hand_list, tiles_combination):
        return set(self.waiting_tiles)


class FixedBaseCalculation:
    def Changsha_base_from_fans(self, fan_list, dealer_related=False):
        return 1


class ChangshaRulesTest(unittest.TestCase):
    def test_initial_deal_gives_dealer_fourteen_tiles(self):
        state = SimpleNamespace(
            player_list=[DummyPlayer(i) for i in range(4)],
            master_seed=1234,
            current_round=1,
            Debug=False,
        )

        init_changsha_tiles(state)

        self.assertEqual([len(p.hand_tiles) for p in state.player_list], [14, 13, 13, 13])
        self.assertEqual(len(state.tiles_list), 55)
        self.assertTrue(state.player_list[0].has_draw_slot)
        self.assertFalse(any(p.has_draw_slot for p in state.player_list[1:]))

    def test_discard_check_asks_all_eligible_peng_and_gang_players(self):
        state = SimpleNamespace(
            player_list=[
                DummyPlayer(0, [12, 13, 14]),
                DummyPlayer(1, [11, 11, 15]),
                DummyPlayer(2, [11, 11, 11]),
                DummyPlayer(3, [11, 11, 19]),
            ],
            current_player_index=0,
            tiles_list=[21],
            dihe_possible=True,
            calculation_service=FixedTingpai([12]),
        )

        actions = check_action_after_cut(state, 11)

        self.assertEqual(actions[0], [])
        self.assertIn("peng", actions[1])
        self.assertIn("peng", actions[2])
        self.assertIn("peng", actions[3])
        self.assertIn("gang", actions[2])

    def test_discard_open_kong_requires_ready_hand(self):
        state = SimpleNamespace(
            player_list=[
                DummyPlayer(0, [12, 13, 14]),
                DummyPlayer(1, [11, 11, 11]),
                DummyPlayer(2, [11, 11, 11]),
                DummyPlayer(3, [21, 22, 23]),
            ],
            current_player_index=0,
            tiles_list=[31],
            dihe_possible=True,
            calculation_service=FixedTingpai([]),
        )

        actions = check_action_after_cut(state, 11)

        self.assertIn("peng", actions[1])
        self.assertIn("peng", actions[2])
        self.assertNotIn("gang", actions[1])
        self.assertNotIn("gang", actions[2])

    def test_initial_hu_types_match_classic_changsha_patterns(self):
        hand = [11, 11, 11, 11, 13, 13, 23, 23, 33, 33, 24, 24, 24]

        self.assertCountEqual(
            evaluate_changsha_initial_hu(hand),
            ["四喜", "板板胡", "六六顺", "三同"],
        )

    def test_follow_hu_blocks_same_or_lower_after_pass(self):
        state = SimpleNamespace(
            player_list=[DummyPlayer(i) for i in range(4)],
            current_player_index=0,
            tiles_list=[21],
            dihe_possible=False,
            last_draw_was_gang=False,
            calculation_service=FixedCalculation((1, ["小胡"])),
            result_dict={},
            player_passed_hu_base={1: 1},
        )
        actions = {0: [], 1: [], 2: [], 3: []}

        check_hepai(state, actions, 11, 1, "dianhe")

        self.assertEqual(actions[1], [])

    def test_follow_hu_allows_higher_win_after_pass(self):
        state = SimpleNamespace(
            player_list=[DummyPlayer(i) for i in range(4)],
            current_player_index=0,
            tiles_list=[21],
            dihe_possible=False,
            last_draw_was_gang=False,
            calculation_service=FixedCalculation((6, ["碰碰胡"])),
            result_dict={},
            player_passed_hu_base={1: 1},
        )
        actions = {0: [], 1: [], 2: [], 3: []}

        check_hepai(state, actions, 11, 1, "dianhe")

        self.assertTrue(any(action.startswith("hu_") for action in actions[1]))

    def test_changsha_base_scores_are_classic_double_bird_units(self):
        self.assertEqual(changsha_base_from_fans(["小胡"], dealer_related=False), 1)
        self.assertEqual(changsha_base_from_fans(["小胡"], dealer_related=True), 2)
        self.assertEqual(changsha_base_from_fans(["碰碰胡", "清一色"], dealer_related=False), 12)
        self.assertEqual(changsha_base_from_fans(["碰碰胡", "清一色"], dealer_related=True), 14)


    def test_changsha_room_validator_uses_four_eight_sixteen_hands(self):
        base = dict(
            room_name="test",
            game_round=1,
            round_timer=20,
            step_timer=5,
            random_seed=0,
            open_kong_replacement_count=2,
            bird_count=2,
        )

        for game_round in (1, 2, 4):
            cfg = ChangshaRoomValidator(**{**base, "game_round": game_round})
            self.assertEqual(cfg.game_round, game_round)

        with self.assertRaises(ValueError):
            ChangshaRoomValidator(**{**base, "game_round": 3})

    def test_initial_hu_room_toggles_filter_detected_types(self):
        state = SimpleNamespace(
            player_list=[
                DummyPlayer(0, [11, 11, 11, 11, 13, 13, 23, 23, 33, 33, 24, 24, 24]),
                DummyPlayer(1, [11, 12, 13]),
            ],
            initial_hu_enabled={
                INITIAL_HU_NAMES["siXi"]: False,
                INITIAL_HU_NAMES["banBanHu"]: True,
                INITIAL_HU_NAMES["queYiSe"]: True,
                INITIAL_HU_NAMES["liuLiuShun"]: True,
                INITIAL_HU_NAMES["sanTong"]: True,
            },
        )

        ChangshaGameState._detect_initial_hu_types(state)

        self.assertNotIn(INITIAL_HU_NAMES["siXi"], state.initial_hu_types[0])
        self.assertIn(INITIAL_HU_NAMES["banBanHu"], state.initial_hu_types[0])

    def test_bird_scoring_uses_configured_count_and_origin(self):
        players = [SimpleNamespace(player_index=i, score=0) for i in range(4)]
        origins = []
        state = SimpleNamespace(
            player_list=players,
            bird_count=1,
            dealer_bird=False,
            calculation_service=FixedBaseCalculation(),
        )

        def draw_birds(count):
            state.requested_bird_count = count
            return [11] * count

        def bird_seat(tile, origin):
            origins.append(origin)
            return 1

        def player_by_index(index):
            return players[index]

        state._draw_changsha_birds = draw_birds
        state._changsha_bird_seat = bird_seat
        state._player_by_index = player_by_index

        result = ChangshaGameState._score_changsha_win(
            state,
            winner=1,
            fan_list=["test"],
            is_zimo=False,
            discarder=2,
        )

        self.assertEqual(state.requested_bird_count, 1)
        self.assertEqual(origins, [1])
        self.assertEqual(players[1].score, 2)
        self.assertEqual(players[2].score, -2)
        self.assertEqual(result["bird_seats"], [1])


if __name__ == "__main__":
    unittest.main()
