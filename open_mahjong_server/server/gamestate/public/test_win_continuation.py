from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys


SERVER_ROOT = Path(__file__).resolve().parents[3]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from server.gamestate.game_new_rule import NewRuleActionPolicy, NewRuleGameState, NewRuleSettlementPolicy
from server.gamestate.game_new_rule.boardcast import game_info_payload
from server.gamestate.public.presentation_profile import PresentationProfile
from server.gamestate.public.win_continuation import HandEndMode, WinContinuationPolicy
from server.room.room_validators import NewRuleRoomValidator


@dataclass
class FakePlayer:
    player_index: int
    is_hu: bool = False


def room_data(mode: str) -> dict:
    return {
        "room_id": "flow-test",
        "player_list": [101, 102, 103, 104],
        "player_settings": {},
        "game_round": 1,
        "round_timer": 0,
        "step_timer": 0,
        "hand_end_mode": mode,
    }


def test_modes_expose_targets_without_rule_dependencies() -> None:
    assert WinContinuationPolicy(HandEndMode.FIRST_WIN).winner_target == 1
    assert WinContinuationPolicy(HandEndMode.SECOND_WIN).winner_target == 2
    assert WinContinuationPolicy(HandEndMode.THIRD_WIN).winner_target == 3


def test_policy_can_be_composed_with_non_new_rule_players() -> None:
    # The policy only needs player_index/is_hu, so a future Guobiao state can
    # adopt it without inheriting NewRuleGameState or its scoring/actions.
    players = [FakePlayer(i, is_hu=i in {1, 2}) for i in range(4)]
    policy = WinContinuationPolicy(HandEndMode.THIRD_WIN)
    assert policy.next_active_index(players, 0) == 3
    assert not policy.should_end(2, wall_tiles=10)
    assert policy.should_end(3, wall_tiles=10)


def test_legacy_blood_battle_flag_maps_to_public_policy() -> None:
    assert WinContinuationPolicy.from_room_data({"blood_battle": False}).mode == HandEndMode.FIRST_WIN
    assert WinContinuationPolicy.from_room_data({"blood_battle": True}).mode == HandEndMode.THIRD_WIN


def test_room_validation_accepts_three_public_modes() -> None:
    common = {
        "room_name": "flow",
        "game_round": 1,
        "round_timer": 0,
        "step_timer": 0,
    }
    for mode in HandEndMode:
        validated = NewRuleRoomValidator(**common, hand_end_mode=mode.value)
        assert validated.hand_end_mode == mode.value


def test_first_second_and_third_win_modes_end_at_their_targets() -> None:
    for mode, target in (("first_win", 1), ("second_win", 2), ("third_win", 3)):
        game = NewRuleGameState(room_data=room_data(mode))
        game.initialize_round()
        for winner in range(target - 1):
            game.mark_player_hu(winner)
            assert game.game_status != "END"
        game.mark_player_hu(target - 1)
        assert game.game_status == "END"
        assert game.ended_by == "win"


def test_hand_end_target_does_not_truncate_same_event_multi_ron() -> None:
    first = NewRuleGameState(room_data=room_data("first_win"))
    first.player_list[1].waiting_tiles = {11}
    first.player_list[2].waiting_tiles = {11}
    result = first.resolve_discard_win_responses(
        0,
        11,
        {1: "hu", 2: "hu"},
        {1: {"points": 0}, 2: {"points": 0}},
    )
    assert result["winners"] == [1, 2]
    assert first.hu_count == 2
    assert result["ended"] is True

    second = NewRuleGameState(room_data=room_data("second_win"))
    second.mark_player_hu(3, {"points": 0})
    second.player_list[1].waiting_tiles = {11}
    second.player_list[2].waiting_tiles = {11}
    result = second.resolve_discard_win_responses(
        0,
        11,
        {1: "hu", 2: "hu"},
        {1: {"points": 0}, 2: {"points": 0}},
    )
    assert result["winners"] == [1, 2]
    assert second.hu_count == 3
    assert result["ended"] is True


def test_new_rule_composes_public_flow_rule_scoring_and_presentation() -> None:
    game = NewRuleGameState(room_data=room_data("second_win"))
    assert game.winner_target == 2
    assert isinstance(game.rule_composition.actions, NewRuleActionPolicy)
    assert isinstance(game.settlement_policy, NewRuleSettlementPolicy)
    assert game.rule_composition.settlement is game.settlement_policy
    assert game.rule_composition.hand_flow is game.win_continuation
    assert game.presentation_profile == PresentationProfile.for_win_continuation(
        game.win_continuation,
        score_display_multiplier=6,
        draw_slot_win_tile=True,
        complete_discard_before_ron=True,
        concealed_win_tile=True,
        preserve_win_animation_on_resume=True,
        win_tile_to_buhua=True,
        winner_result_sequence=True,
        defer_win_details=True,
    )


def test_game_info_declares_capabilities_instead_of_requiring_rule_name_checks() -> None:
    game = NewRuleGameState(room_data=room_data("first_win"))
    payload = game_info_payload(game, 0)
    assert payload["hand_end_mode"] == "first_win"
    assert payload["winner_target"] == 1
    assert payload["hand_flow"] == {
        "mode": "first_win",
        "winner_target": 1,
        "winners_exit_hand": False,
    }
    assert payload["presentation_profile"] == {
        "winner_exit_animation": False,
        "defer_win_details": True,
        "result_sequence": "winner_sequence",
        "win_tile_to_buhua": True,
        "score_display_multiplier": 6,
        "draw_slot_win_tile": True,
        "complete_discard_before_ron": True,
        "concealed_win_tile": True,
        "preserve_win_animation_on_resume": True,
    }


def run() -> None:
    tests = [
        test_modes_expose_targets_without_rule_dependencies,
        test_policy_can_be_composed_with_non_new_rule_players,
        test_legacy_blood_battle_flag_maps_to_public_policy,
        test_room_validation_accepts_three_public_modes,
        test_first_second_and_third_win_modes_end_at_their_targets,
        test_hand_end_target_does_not_truncate_same_event_multi_ron,
        test_new_rule_composes_public_flow_rule_scoring_and_presentation,
        test_game_info_declares_capabilities_instead_of_requiring_rule_name_checks,
    ]
    for test in tests:
        test()
    print(f"win continuation composition tests ok: {len(tests)} tests")


if __name__ == "__main__":
    run()
