import asyncio
import importlib
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from server.game_calculation.changsha.changsha_hepai_check import (
    Changsha_Hepai_Check,
    INITIAL_HU_NAMES,
    changsha_base_from_fans,
    evaluate_changsha_initial_hu,
)
from server.gamestate.game_changsha.ChangshaGameState import ChangshaGameState
from server.gamestate.game_changsha.action_check import (
    check_action_after_cut,
    check_action_after_gang_forced_cut,
    check_action_hand_action,
    check_hepai,
    refresh_waiting_tiles,
)
from server.gamestate.game_changsha.boardcast import _build_do_action_payload
from server.gamestate.game_changsha.init_tiles import init_changsha_tiles
from server.gamestate.public.next_game_round import next_game_round_random_switchseat
from server.room.room_validators import ChangshaRoomValidator

wait_action_module = importlib.import_module("server.gamestate.game_changsha.wait_action")


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


class FixedCalculationAndTingpai:
    def __init__(self, result, waiting_tiles):
        self.result = result
        self.waiting_tiles = set(waiting_tiles)

    def Changsha_hepai_check(self, hand_list, tiles_combination, way_to_hepai, get_tile):
        return self.result

    def Changsha_tingpai_check(self, hand_list, tiles_combination):
        return set(self.waiting_tiles)


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

    def test_discard_check_allows_upper_player_to_chi(self):
        state = SimpleNamespace(
            player_list=[
                DummyPlayer(0, [11, 12, 25]),
                DummyPlayer(1, [31, 32, 33]),
                DummyPlayer(2, [12, 14, 26]),
                DummyPlayer(3, [11, 12, 13]),
            ],
            current_player_index=3,
            tiles_list=[21],
            dihe_possible=True,
            calculation_service=FixedTingpai([]),
        )

        actions = check_action_after_cut(state, 13)

        self.assertIn("chi_left", actions[0])
        self.assertIn("pass", actions[0])
        self.assertEqual(actions[3], [])
        self.assertNotIn("chi_mid", actions[2])
        self.assertNotIn("chi_mid", actions[1])

    def test_discard_check_rejects_lower_player_chi(self):
        state = SimpleNamespace(
            player_list=[
                DummyPlayer(0, [11, 12, 25]),
                DummyPlayer(1, [31, 32, 33]),
                DummyPlayer(2, [12, 14, 26]),
                DummyPlayer(3, [11, 12, 13]),
            ],
            current_player_index=1,
            tiles_list=[21],
            dihe_possible=True,
            calculation_service=FixedTingpai([]),
        )

        actions = check_action_after_cut(state, 13)

        self.assertNotIn("chi_left", actions[0])
        self.assertNotIn("chi_mid", actions[0])
        self.assertNotIn("chi_right", actions[0])

    def test_forced_gang_discard_only_allows_win_claims(self):
        state = SimpleNamespace(
            player_list=[
                DummyPlayer(0, [12, 13, 14]),
                DummyPlayer(1, [11, 12, 13, 13]),
                DummyPlayer(2, [13, 13, 13]),
                DummyPlayer(3, [21, 22, 23]),
            ],
            current_player_index=0,
            tiles_list=[21],
            dihe_possible=False,
            last_draw_was_gang=True,
            calculation_service=FixedCalculationAndTingpai((1, ["小胡"]), [13]),
            result_dict={},
            player_passed_hu_base={},
        )
        actions = check_action_after_gang_forced_cut(state, 13)

        for player_index in (1, 2, 3):
            self.assertTrue(any(action.startswith("hu_") for action in actions[player_index]))
            self.assertIn("pass", actions[player_index])
            self.assertNotIn("chi_left", actions[player_index])
            self.assertNotIn("chi_mid", actions[player_index])
            self.assertNotIn("chi_right", actions[player_index])
            self.assertNotIn("peng", actions[player_index])
            self.assertNotIn("gang", actions[player_index])
        self.assertEqual(actions[0], [])

    def test_forced_gang_discard_does_not_offer_melds_without_hu(self):
        state = SimpleNamespace(
            player_list=[
                DummyPlayer(0, [12, 13, 14]),
                DummyPlayer(1, [11, 12, 13, 13]),
                DummyPlayer(2, [13, 13, 13]),
                DummyPlayer(3, [21, 22, 23]),
            ],
            current_player_index=0,
            tiles_list=[21],
            dihe_possible=False,
            last_draw_was_gang=True,
            calculation_service=FixedTingpai([]),
            result_dict={},
            player_passed_hu_base={},
        )

        actions = check_action_after_gang_forced_cut(state, 13)

        self.assertEqual(actions, {0: [], 1: [], 2: [], 3: []})

    def test_open_kong_locked_player_can_win_but_not_meld(self):
        locked_player = DummyPlayer(1, [11, 12, 13, 13, 13], waiting_tiles=[13])
        locked_player.open_kong_locked = True
        state = SimpleNamespace(
            player_list=[
                DummyPlayer(0, [21, 22, 23]),
                locked_player,
                DummyPlayer(2, [13, 13, 13]),
                DummyPlayer(3, [21, 22, 23]),
            ],
            current_player_index=0,
            tiles_list=[21],
            dihe_possible=False,
            last_draw_was_gang=False,
            calculation_service=FixedCalculationAndTingpai((1, ["小胡"]), [13]),
            result_dict={},
            player_passed_hu_base={},
        )

        actions = check_action_after_cut(state, 13)

        self.assertTrue(any(action.startswith("hu_") for action in actions[1]))
        self.assertIn("pass", actions[1])
        self.assertNotIn("chi_left", actions[1])
        self.assertNotIn("chi_mid", actions[1])
        self.assertNotIn("chi_right", actions[1])
        self.assertNotIn("peng", actions[1])
        self.assertNotIn("gang", actions[1])

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

    def test_self_replacement_without_ready_only_offers_buzhang(self):
        state = SimpleNamespace(
            player_list=[
                DummyPlayer(0, [17, 12, 13]),
                DummyPlayer(1),
                DummyPlayer(2),
                DummyPlayer(3),
            ],
            tiles_list=[31],
            calculation_service=FixedTingpai([]),
        )
        state.player_list[0].combination_tiles = ["k17"]
        state._is_open_kong_ready_after_declared = lambda player, tile: ChangshaGameState._is_open_kong_ready_after_declared(state, player, tile)

        actions = check_action_hand_action(state, 0)

        self.assertIn("buzhang", actions[0])
        self.assertNotIn("jiagang", actions[0])

    def test_self_replacement_ready_offers_buzhang_and_open_kong(self):
        checker = ConditionalTingpai(
            expected_hand=[12, 13],
            expected_melds=["g17"],
            waiting_tiles=[14],
        )
        state = SimpleNamespace(
            player_list=[
                DummyPlayer(0, [17, 12, 13]),
                DummyPlayer(1),
                DummyPlayer(2),
                DummyPlayer(3),
            ],
            tiles_list=[31],
            calculation_service=checker,
        )
        state.player_list[0].combination_tiles = ["k17"]
        state._is_open_kong_ready_after_declared = lambda player, tile: ChangshaGameState._is_open_kong_ready_after_declared(state, player, tile)

        actions = check_action_hand_action(state, 0)

        self.assertIn("buzhang", actions[0])
        self.assertIn("jiagang", actions[0])

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

    def test_jiangjianghu_is_detected_and_displayed(self):
        score, fan_list = Changsha_Hepai_Check().hepai_check(
            [12, 12, 12, 15, 15, 15, 18, 18, 18, 22, 22, 22, 25, 25],
            [],
            ["自摸"],
            25,
        )

        self.assertEqual(score, 12)
        self.assertIn("将将胡", fan_list)

    def test_jiangjianghu_only_requires_all_jiang_tiles(self):
        score, fan_list = Changsha_Hepai_Check().hepai_check(
            [12, 12, 15, 15, 18, 18, 22, 22, 25, 25, 28, 28, 32, 35],
            [],
            ["自摸"],
            35,
        )

        self.assertEqual(score, 6)
        self.assertEqual(fan_list, ["将将胡"])


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

        self.assertEqual(ChangshaGameState._format_changsha_bird_tile(24), "四筒")
        self.assertIn("鸟牌:四筒,一条", result["fan_display"])
        self.assertIn("中鸟:四筒", result["fan_display"])
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

    def test_sea_bottom_rechecks_and_clears_stale_waiting_tiles(self):
        stale_player = DummyPlayer(1, [11, 12, 13], waiting_tiles=[14])
        tenpai_player = DummyPlayer(2, [21, 22, 23])
        state = SimpleNamespace(
            player_list=[
                DummyPlayer(0, [31, 32, 33]),
                stale_player,
                tenpai_player,
                DummyPlayer(3, [17, 18, 19]),
            ],
            current_player_index=0,
            calculation_service=HandMappedTingpai({
                tuple(stale_player.hand_tiles): [],
                tuple(tenpai_player.hand_tiles): [24],
            }),
        )
        state._player_by_index = lambda index: ChangshaGameState._player_by_index(state, index)

        self.assertEqual(ChangshaGameState._next_sea_bottom_player(state), 2)
        self.assertEqual(stale_player.waiting_tiles, set())

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

    def test_buzhang_from_peng_uses_single_replacement_and_broadcasts_buzhang(self):
        player = DummyPlayer(0, [17, 12, 13])
        player.combination_tiles = ["k17"]
        player.combination_mask = [[1, 17, 0, 17, 0, 17]]
        state = SimpleNamespace(
            player_list=[player, DummyPlayer(1), DummyPlayer(2), DummyPlayer(3)],
            action_dict={},
            jiagang_tile=None,
        )
        payloads = []
        state.prepare_gang_replacement = lambda count, forced: setattr(
            state, "replacement_args", (count, forced)
        )

        async def capture_broadcast(*args, **kwargs):
            payloads.append(kwargs)

        with patch.object(wait_action_module, "broadcast_do_action", capture_broadcast), \
            patch.object(wait_action_module, "player_action_record_jiagang", lambda *args, **kwargs: None), \
            patch.object(wait_action_module, "check_action_jiagang", lambda *args, **kwargs: {0: [], 1: [], 2: [], 3: []}):
            asyncio.run(wait_action_module._execute_jiagang_replacement(state, 0, 17, "buzhang", 1, False))

        self.assertEqual(player.combination_tiles, ["g17"])
        self.assertEqual(state.replacement_args, (1, False))
        self.assertEqual(state.game_status, "deal_card_after_gang")
        self.assertEqual(payloads[0]["action_list"], ["buzhang"])
        self.assertEqual(payloads[0]["combination_target"], "k17")

    def test_open_jiagang_uses_configured_replacement_and_forced_discard(self):
        player = DummyPlayer(0, [17, 12, 13])
        player.combination_tiles = ["k17"]
        player.combination_mask = [[1, 17, 0, 17, 0, 17]]
        state = SimpleNamespace(
            player_list=[player, DummyPlayer(1), DummyPlayer(2), DummyPlayer(3)],
            action_dict={},
            jiagang_tile=None,
        )
        payloads = []
        state.prepare_gang_replacement = lambda count, forced: setattr(
            state, "replacement_args", (count, forced)
        )

        async def capture_broadcast(*args, **kwargs):
            payloads.append(kwargs)

        with patch.object(wait_action_module, "broadcast_do_action", capture_broadcast), \
            patch.object(wait_action_module, "player_action_record_jiagang", lambda *args, **kwargs: None), \
            patch.object(wait_action_module, "check_action_jiagang", lambda *args, **kwargs: {0: [], 1: [], 2: [], 3: []}):
            asyncio.run(wait_action_module._execute_jiagang_replacement(state, 0, 17, "jiagang", 2, True))

        self.assertEqual(player.combination_tiles, ["g17"])
        self.assertEqual(state.replacement_args, (2, True))
        self.assertEqual(state.game_status, "deal_card_after_gang")
        self.assertEqual(payloads[0]["action_list"], ["jiagang"])
        self.assertEqual(payloads[0]["combination_target"], "k17")

    def test_angang_execution_broadcasts_revealed_mask(self):
        player = DummyPlayer(0, [11, 11, 11, 11, 12, 13])
        state = SimpleNamespace(
            player_list=[player, DummyPlayer(1), DummyPlayer(2), DummyPlayer(3)],
        )
        payloads = []
        state.prepare_gang_replacement = lambda count, forced: setattr(
            state, "replacement_args", (count, forced)
        )

        async def capture_broadcast(*args, **kwargs):
            payloads.append(kwargs)

        with patch.object(wait_action_module, "broadcast_do_action", capture_broadcast), \
            patch.object(wait_action_module, "player_action_record_angang", lambda *args, **kwargs: None):
            asyncio.run(wait_action_module._execute_angang_replacement(state, 0, 11, "angang", 2, True))

        self.assertEqual(player.combination_tiles, ["G11"])
        self.assertEqual(player.combination_mask, [[0, 11, 0, 11, 0, 11, 0, 11]])
        self.assertEqual(state.replacement_args, (2, True))
        self.assertEqual(payloads[0]["action_list"], ["angang"])
        self.assertEqual(payloads[0]["combination_mask"], [0, 11, 0, 11, 0, 11, 0, 11])

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

    def test_sea_bottom_taker_becomes_next_round_dealer_on_draw(self):
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
                tag_list=[],
            )
            for i in range(4)
        ]
        state = SimpleNamespace(
            player_list=players,
            current_round=1,
            round_index=1,
            current_player_index=0,
            xunmu=8,
            round_time=20,
            hu_class="liuju",
            action_dict={0: ["ready"]},
            backward_tiles_list_type="double",
            sea_bottom_player_index=3,
        )

        ChangshaGameState._make_player_next_dealer(state, state.sea_bottom_player_index)
        next_game_round_random_switchseat(state, keep_dealer_seat=True)

        self.assertEqual(state.player_list[0].original_player_index, 3)
        self.assertEqual(state.player_list[0].player_index, 0)
        self.assertEqual(state.current_player_index, 0)
        self.assertEqual(state.current_round, 2)


if __name__ == "__main__":
    unittest.main()
