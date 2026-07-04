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
    refresh_waiting_tiles,
)
from server.gamestate.game_changsha.boardcast import _build_do_action_payload
from server.gamestate.game_changsha.init_tiles import init_changsha_tiles
from server.gamestate.public.next_game_round import next_game_round_random_switchseat
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


class ConditionalTingpai:
    def __init__(self, expected_hand, expected_melds, waiting_tiles):
        self.expected_hand = list(expected_hand)
        self.expected_melds = list(expected_melds)
        self.waiting_tiles = set(waiting_tiles)
        self.calls = []

    def Changsha_tingpai_check(self, hand_list, tiles_combination):
        hand = list(hand_list)
        melds = list(tiles_combination)
        self.calls.append((hand, melds))
        if hand == self.expected_hand and melds == self.expected_melds:
            return set(self.waiting_tiles)
        return set()


class HandMappedTingpai:
    def __init__(self, waits_by_hand):
        self.waits_by_hand = {
            tuple(hand): set(waits) for hand, waits in waits_by_hand.items()
        }

    def Changsha_tingpai_check(self, hand_list, tiles_combination):
        return set(self.waits_by_hand.get(tuple(hand_list), set()))


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

    def test_discard_check_allows_next_player_to_chi(self):
        state = SimpleNamespace(
            player_list=[
                DummyPlayer(0, [31, 32, 33]),
                DummyPlayer(1, [12, 14, 25]),
                DummyPlayer(2, [12, 14, 26]),
                DummyPlayer(3, [11, 12, 13]),
            ],
            current_player_index=0,
            tiles_list=[21],
            dihe_possible=True,
            calculation_service=FixedTingpai([]),
        )

        actions = check_action_after_cut(state, 13)

        self.assertIn("chi_mid", actions[1])
        self.assertIn("pass", actions[1])
        self.assertNotIn("chi_mid", actions[2])
        self.assertNotIn("chi_mid", actions[3])

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

    def test_discard_open_kong_checks_ready_after_declared_kong(self):
        checker = ConditionalTingpai(
            expected_hand=[12, 13, 14],
            expected_melds=["g11"],
            waiting_tiles=[15],
        )
        state = SimpleNamespace(
            player_list=[
                DummyPlayer(0, [21, 22, 23]),
                DummyPlayer(1, [11, 11, 11, 12, 13, 14]),
                DummyPlayer(2, [21, 22, 23]),
                DummyPlayer(3, [31, 32, 33]),
            ],
            current_player_index=0,
            tiles_list=[31],
            dihe_possible=True,
            calculation_service=checker,
        )

        actions = check_action_after_cut(state, 11)

        self.assertIn("gang", actions[1])
        self.assertIn(([12, 13, 14], ["g11"]), checker.calls)

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
        state._format_changsha_bird_tile = ChangshaGameState._format_changsha_bird_tile
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

    def test_bird_scoring_displays_tile_name_rank_and_multiplier(self):
        players = [SimpleNamespace(player_index=i, score=0) for i in range(4)]
        state = SimpleNamespace(
            player_list=players,
            bird_count=2,
            dealer_bird=False,
            calculation_service=FixedBaseCalculation(),
        )
        state._draw_changsha_birds = lambda count: [24, 31]
        state._is_sea_bottom_win = ChangshaGameState._is_sea_bottom_win
        state._changsha_bird_seat = lambda tile, origin: {24: 2, 31: 0}[tile]
        state._format_changsha_bird_tile = ChangshaGameState._format_changsha_bird_tile
        state._player_by_index = lambda index: players[index]

        result = ChangshaGameState._score_changsha_win(
            state,
            winner=1,
            fan_list=["小胡"],
            is_zimo=False,
            discarder=2,
        )

        self.assertEqual(ChangshaGameState._format_changsha_bird_tile(24), "4饼=4")
        self.assertIn("鸟牌:4饼=4,1条=1", result["fan_display"])
        self.assertIn("中鸟:4饼=4", result["fan_display"])
        self.assertIn("扎鸟倍数:x2", result["fan_display"])
        self.assertEqual(players[1].score, 2)
        self.assertEqual(players[2].score, -2)

    def test_bird_draw_uses_remaining_wall_front(self):
        state = SimpleNamespace(tiles_list=[11, 22, 33])

        birds = ChangshaGameState._draw_changsha_birds(state, 2)

        self.assertEqual(birds, [11, 22])
        self.assertEqual(state.tiles_list, [33])

    def test_sea_bottom_win_uses_winning_tile_as_bird_when_wall_empty(self):
        players = [
            SimpleNamespace(player_index=0, score=0, hand_tiles=[]),
            SimpleNamespace(player_index=1, score=0, hand_tiles=[11]),
            SimpleNamespace(player_index=2, score=0, hand_tiles=[]),
            SimpleNamespace(player_index=3, score=0, hand_tiles=[]),
        ]
        state = SimpleNamespace(
            player_list=players,
            bird_count=2,
            dealer_bird=False,
            calculation_service=FixedBaseCalculation(),
            tiles_list=[],
        )
        state._draw_changsha_birds = lambda count: ChangshaGameState._draw_changsha_birds(state, count)
        state._is_sea_bottom_win = ChangshaGameState._is_sea_bottom_win
        state._sea_bottom_bird_tile = lambda winner: ChangshaGameState._sea_bottom_bird_tile(state, winner)
        state._changsha_bird_seat = ChangshaGameState._changsha_bird_seat
        state._format_changsha_bird_tile = ChangshaGameState._format_changsha_bird_tile
        state._player_by_index = lambda index: players[index]

        result = ChangshaGameState._score_changsha_win(
            state,
            winner=1,
            fan_list=["海底"],
            is_zimo=False,
            discarder=2,
        )

        self.assertEqual(result["birds"], [11])
        self.assertEqual(players[1].score, 2)
        self.assertEqual(players[2].score, -2)

    def test_sea_bottom_skips_noten_players(self):
        p1_hand = [11, 12, 13]
        p2_hand = [21, 22, 23]
        state = SimpleNamespace(
            player_list=[
                DummyPlayer(0, [31, 32, 33]),
                DummyPlayer(1, p1_hand),
                DummyPlayer(2, p2_hand),
                DummyPlayer(3, [17, 18, 19]),
            ],
            current_player_index=0,
            calculation_service=HandMappedTingpai({
                tuple(p1_hand): [],
                tuple(p2_hand): [24],
            }),
        )
        state.refresh_waiting_tiles = lambda player_index: refresh_waiting_tiles(state, player_index)

        self.assertEqual(ChangshaGameState._next_sea_bottom_player(state), 2)

    def test_sea_bottom_ends_when_no_player_is_tenpai(self):
        state = SimpleNamespace(
            player_list=[
                DummyPlayer(0, [31, 32, 33]),
                DummyPlayer(1, [11, 12, 13]),
                DummyPlayer(2, [21, 22, 23]),
                DummyPlayer(3, [17, 18, 19]),
            ],
            current_player_index=0,
            calculation_service=FixedTingpai([]),
        )
        state.refresh_waiting_tiles = lambda player_index: refresh_waiting_tiles(state, player_index)

        self.assertIsNone(ChangshaGameState._next_sea_bottom_player(state))

    def test_changsha_angang_broadcast_reveals_mask_and_target(self):
        state = SimpleNamespace(server_action_tick=3)
        mask = [0, 11, 0, 11, 0, 11, 0, 11]

        payload = _build_do_action_payload(
            state,
            ["angang"],
            0,
            1,
            combination_mask=mask,
            combination_target="G11",
        )

        self.assertEqual(payload["combination_mask"], mask)
        self.assertEqual(payload["combination_target"], "G11")

    def test_winner_becomes_next_round_dealer(self):
        players = [
            SimpleNamespace(
                player_index=i,
                original_player_index=i,
                hand_tiles=[11 + i],
                huapai_list=[i],
                discard_tiles=[21 + i],
                waiting_tiles={31 + i},
                combination_tiles=[f"p{i}"],
                combination_mask=[i],
                remaining_time=99,
                tag_list=["peida"],
            )
            for i in range(4)
        ]
        state = SimpleNamespace(
            player_list=players,
            current_round=1,
            round_index=1,
            current_player_index=2,
            xunmu=8,
            round_time=20,
            hu_class="hu_self",
            action_dict={0: ["ready"]},
            backward_tiles_list_type="double",
        )

        ChangshaGameState._make_player_next_dealer(state, 2)
        next_game_round_random_switchseat(state, keep_dealer_seat=True)

        self.assertEqual(
            [player.original_player_index for player in state.player_list],
            [2, 3, 0, 1],
        )
        self.assertEqual(state.player_list[0].player_index, 0)
        self.assertEqual(state.player_list[0].original_player_index, 2)
        self.assertEqual(state.current_player_index, 0)
        self.assertEqual(state.current_round, 2)
        self.assertEqual(state.player_list[0].hand_tiles, [])


if __name__ == "__main__":
    unittest.main()
