from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class DebugScenarioError(ValueError):
    pass


DEBUG_SCENARIOS = {
    "earthly_win",
    "haitei",
    "heavenly_win",
    "houtei",
    "multi_ron_2",
    "multi_ron_3",
    "nine_gates",
    "rinshan",
    "rob_kong",
    "rob_kong_multi_ron_2",
    "same_tile_lockout",
}


async def start_debug_scenario(game_state: Any, scenario_name: str) -> dict:
    """Cancel the active live loop, inject a scenario, and run it as the live loop.

    Debug scenarios mutate the whole hand. If the normal game loop is already
    waiting on an old action window, direct mutation would leave that coroutine
    with a stale local window. Cancelling the old loop first keeps Unity-visible
    scenario testing deterministic and removable.
    """
    current_task = asyncio.current_task()
    old_task = getattr(game_state, "game_task", None)
    if old_task and not old_task.done() and old_task is not current_task:
        old_task.cancel()
        try:
            await old_task
        except asyncio.CancelledError:
            logger.info("new_rule debug_scenario cancelled old loop, room_id=%s", game_state.room_id)

    game_state.start_round_recording()
    window = apply_debug_scenario(game_state, scenario_name)
    await game_state.flush_outbound_payloads()
    game_state.game_task = asyncio.create_task(_run_debug_scenario_loop(game_state))
    return window


async def _run_debug_scenario_loop(game_state: Any) -> None:
    """Drive an injected debug hand, then resume the normal new-rule loop."""
    try:
        while game_state.game_status != "END":
            await game_state.resolve_action_window(timeout=game_state.estimated_action_window_timeout())
            await game_state.flush_outbound_payloads()
        game_state.finalize_round_recording()
        await game_state.run_round_ready_phase(timeout=game_state.estimated_round_result_ready_timeout())
        if game_state.current_round >= game_state.max_round * 4:
            game_state.finalize_game_recording()
            await game_state.complete_game_lifecycle()
            return
        game_state.advance_round_after_ready()
        await game_state.flush_outbound_payloads()
        await game_state.run_game_loop()
    except asyncio.CancelledError:
        logger.info("new_rule debug_scenario loop cancelled, room_id=%s", game_state.room_id)
        raise
    except Exception as exc:
        logger.error("new_rule debug_scenario loop failed, room_id=%s: %s", game_state.room_id, exc, exc_info=True)
        raise


def apply_debug_scenario(game_state: Any, scenario_name: str) -> dict:
    """Inject a dev-only new-rule scenario and open its next normal action window.

    This module must stay isolated from production scoring/action logic. It is
    intended for deterministic Unity smoke tests of rare events only.
    """
    scenario_name = (scenario_name or "").strip()
    if scenario_name not in DEBUG_SCENARIOS:
        raise DebugScenarioError(f"Unknown new-rule debug scenario: {scenario_name}")
    if getattr(game_state, "room_rule", None) != "new_rule":
        raise DebugScenarioError("Debug scenarios are only available for new_rule.")

    _reset_common_state(game_state)

    if scenario_name == "multi_ron_2":
        return _apply_multi_ron(game_state, winner_count=2)
    if scenario_name == "multi_ron_3":
        return _apply_multi_ron(game_state, winner_count=3)
    if scenario_name == "rob_kong":
        return _apply_rob_kong(game_state)
    if scenario_name == "rob_kong_multi_ron_2":
        return _apply_rob_kong_multi_ron_2(game_state)
    if scenario_name == "same_tile_lockout":
        return _apply_same_tile_lockout(game_state)
    if scenario_name == "haitei":
        return _apply_haitei(game_state)
    if scenario_name == "houtei":
        return _apply_houtei(game_state)
    if scenario_name == "rinshan":
        return _apply_rinshan(game_state)
    if scenario_name == "heavenly_win":
        return _apply_heavenly_win(game_state)
    if scenario_name == "earthly_win":
        return _apply_earthly_win(game_state)
    if scenario_name == "nine_gates":
        return _apply_nine_gates(game_state)

    raise DebugScenarioError(f"Unhandled new-rule debug scenario: {scenario_name}")


def _reset_common_state(game_state: Any) -> None:
    for task in list(getattr(game_state, "bot_tasks", [])):
        task.cancel()
    game_state.bot_tasks.clear()
    game_state.bot_action_ticks = {}

    game_state.live_pending_window = None
    game_state.action_dict = {idx: [] for idx in range(4)}
    game_state.waiting_players_list = []
    for idx in range(4):
        game_state.action_events[idx].clear()
        while not game_state.action_queues[idx].empty():
            game_state.action_queues[idx].get_nowait()

    game_state.deferred_hu_settlements = []
    game_state.deferred_scores_applied = False
    game_state.hu_order_counter = 0
    game_state.ended_by = None
    game_state.live_pending_window = None
    game_state.hand_action_is_gang_draw = {idx: False for idx in range(4)}
    game_state.natural_draw_count = {idx: 0 for idx in range(4)}
    game_state.opening_action_taken = True
    game_state.opening_flow_interrupted = True

    for player in game_state.player_list:
        player.hand_tiles = []
        player.discard_tiles = []
        player.discard_origin_tiles = []
        player.combination_tiles = []
        player.combination_mask = []
        player.combination_masks = []
        player.waiting_tiles = set()
        player.discard_win_lockout_tiles = set()
        player.is_hu = False
        player.hu_order = 0


def _apply_multi_ron(game_state: Any, *, winner_count: int) -> dict:
    discard_tile = 19
    game_state.dealer_index = 0
    game_state.current_player_index = 0
    game_state.game_status = "waiting_hand_action"
    game_state.tiles_list = [31, 32, 33, 34, 35, 36]

    game_state.player_list[0].hand_tiles = [
        11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 24, 31, 47
    ]
    waiting_hand = [11, 12, 13, 14, 15, 16, 17, 18, 21, 22, 23, 31, 31]
    non_waiting_hand = [11, 12, 13, 14, 15, 16, 17, 18, 21, 22, 24, 32, 47]
    for idx in range(1, 4):
        if idx <= winner_count:
            game_state.player_list[idx].hand_tiles = list(waiting_hand)
            game_state.player_list[idx].waiting_tiles = {discard_tile}
            game_state.player_list[idx].user_id = 2
        else:
            game_state.player_list[idx].hand_tiles = list(non_waiting_hand)
            game_state.player_list[idx].waiting_tiles = set()

    game_state.emit_game_start_payloads()
    return game_state.open_action_window(game_state.begin_hand_action(0))


def _apply_rob_kong(game_state: Any) -> dict:
    kong_tile = 19
    game_state.dealer_index = 0
    game_state.current_player_index = 0
    game_state.game_status = "waiting_hand_action"
    game_state.tiles_list = [31, 32, 33, 34, 35, 36]

    player = game_state.player_list[0]
    player.hand_tiles = [kong_tile, 11, 12, 13, 14, 15, 16, 17, 18, 21, 22]
    player.combination_tiles = [f"k{kong_tile}"]
    player.combination_mask = [[1, kong_tile, 0, kong_tile, 0, kong_tile]]

    waiting_hand = [11, 12, 13, 14, 15, 16, 17, 18, 21, 22, 23, 31, 31]
    game_state.player_list[1].hand_tiles = list(waiting_hand)
    game_state.player_list[1].waiting_tiles = {kong_tile}
    game_state.player_list[1].user_id = 2
    non_waiting_hand = [11, 12, 13, 14, 15, 16, 17, 18, 21, 22, 24, 32, 47]
    for idx in (2, 3):
        game_state.player_list[idx].hand_tiles = list(non_waiting_hand)
        game_state.player_list[idx].waiting_tiles = set()

    game_state.emit_game_start_payloads()
    return game_state.open_action_window(game_state.begin_hand_action(0))


def _apply_rob_kong_multi_ron_2(game_state: Any) -> dict:
    kong_tile = 19
    game_state.dealer_index = 0
    game_state.current_player_index = 0
    game_state.game_status = "waiting_hand_action"
    game_state.tiles_list = [31, 32, 33, 34, 35, 36]

    player = game_state.player_list[0]
    player.hand_tiles = [kong_tile, 11, 12, 13, 14, 15, 16, 17, 18, 21, 22]
    player.combination_tiles = [f"k{kong_tile}"]
    player.combination_mask = [[1, kong_tile, 0, kong_tile, 0, kong_tile]]

    waiting_hand = [11, 12, 13, 14, 15, 16, 17, 18, 21, 22, 23, 31, 31]
    for idx in (1, 3):
        game_state.player_list[idx].hand_tiles = list(waiting_hand)
        game_state.player_list[idx].waiting_tiles = {kong_tile}
        game_state.player_list[idx].user_id = 2
    game_state.player_list[2].hand_tiles = _non_waiting_hand()
    game_state.player_list[2].waiting_tiles = set()

    game_state.emit_game_start_payloads()
    return game_state.open_action_window(game_state.begin_hand_action(0))


def _apply_same_tile_lockout(game_state: Any) -> dict:
    lock_tile = 15
    game_state.dealer_index = 0
    game_state.current_player_index = 3
    game_state.game_status = "waiting_hand_action"
    game_state.tiles_list = [lock_tile, lock_tile, 31, 32, 33, 34]

    game_state.player_list[0].hand_tiles = _waiting_hand_for_15()
    game_state.player_list[0].waiting_tiles = {lock_tile}

    for idx in (1, 2):
        player = game_state.player_list[idx]
        player.hand_tiles = _non_claiming_hand_for_lockout()
        player.waiting_tiles = set()
        player.user_id = 0

    cutter = game_state.player_list[3]
    cutter.hand_tiles = _non_claiming_hand_for_lockout() + [lock_tile]
    cutter.waiting_tiles = set()
    cutter.user_id = 0
    cutter.has_draw_slot = True

    game_state.emit_game_start_payloads()
    return game_state.open_action_window(game_state.begin_hand_action(3))


def _apply_haitei(game_state: Any) -> dict:
    game_state.dealer_index = 0
    game_state.current_player_index = 0
    game_state.game_status = "waiting_hand_action"
    game_state.tiles_list = []
    game_state.player_list[0].hand_tiles = _self_draw_win_hand()
    game_state.player_list[0].has_draw_slot = True
    _fill_other_players(game_state, skip={0})
    game_state.emit_game_start_payloads()
    return game_state.open_action_window(game_state.begin_hand_action(0))


def _apply_houtei(game_state: Any) -> dict:
    discard_tile = 15
    game_state.dealer_index = 0
    game_state.current_player_index = 0
    game_state.game_status = "waiting_hand_action"
    game_state.tiles_list = []
    game_state.player_list[0].hand_tiles = [
        11, 11, 11, 22, 22, 22, 33, 33, 33, 44, 44, 44, 15, 47
    ]
    game_state.player_list[1].hand_tiles = _waiting_hand_for_15()
    game_state.player_list[1].waiting_tiles = {discard_tile}
    game_state.player_list[1].user_id = 2
    _fill_other_players(game_state, skip={0, 1})
    game_state.emit_game_start_payloads()
    return game_state.open_action_window(game_state.begin_hand_action(0))


def _apply_rinshan(game_state: Any) -> dict:
    kong_tile = 19
    game_state.dealer_index = 0
    game_state.current_player_index = 0
    game_state.game_status = "waiting_hand_action"
    game_state.tiles_list = [15, 31, 32, 33]
    game_state.player_list[0].hand_tiles = [
        kong_tile, kong_tile, kong_tile, kong_tile,
        11, 11, 11,
        22, 22, 22,
        33, 33, 33,
        15,
    ]
    game_state.player_list[0].has_draw_slot = True
    _fill_other_players(game_state, skip={0})
    game_state.emit_game_start_payloads()
    return game_state.open_action_window(game_state.begin_hand_action(0))


def _apply_heavenly_win(game_state: Any) -> dict:
    game_state.dealer_index = 0
    game_state.current_player_index = 0
    game_state.game_status = "waiting_hand_action"
    game_state.tiles_list = [31, 32, 33]
    game_state.opening_action_taken = False
    game_state.opening_flow_interrupted = False
    game_state.player_list[0].hand_tiles = _self_draw_win_hand()
    game_state.player_list[0].has_draw_slot = True
    _fill_other_players(game_state, skip={0})
    game_state.emit_game_start_payloads()
    return game_state.open_action_window(game_state.begin_hand_action(0))


def _apply_earthly_win(game_state: Any) -> dict:
    game_state.dealer_index = 1
    game_state.current_player_index = 0
    game_state.game_status = "waiting_hand_action"
    game_state.tiles_list = [31, 32, 33]
    game_state.opening_action_taken = True
    game_state.opening_flow_interrupted = False
    game_state.natural_draw_count[0] = 1
    game_state.player_list[0].hand_tiles = _self_draw_win_hand()
    game_state.player_list[0].has_draw_slot = True
    _fill_other_players(game_state, skip={0})
    game_state.emit_game_start_payloads()
    return game_state.open_action_window(game_state.begin_hand_action(0))


def _apply_nine_gates(game_state: Any) -> dict:
    game_state.dealer_index = 0
    game_state.current_player_index = 0
    game_state.game_status = "waiting_hand_action"
    game_state.tiles_list = [19, 31, 32, 33]
    game_state.player_list[0].hand_tiles = [
        11, 11, 11, 12, 13, 14, 15, 16, 17, 18, 19, 19, 19, 15
    ]
    game_state.player_list[0].has_draw_slot = True
    _fill_other_players(game_state, skip={0}, hand_factory=_non_claiming_hand_for_nine_gates)
    # Keep the manual nine-gates scenario deterministic: after player 0 skips
    # the self-draw and discards, player 1 draws 9m and immediately cuts it.
    game_state.player_list[1].user_id = 0
    game_state.emit_game_start_payloads()
    return game_state.open_action_window(game_state.begin_hand_action(0))


def _self_draw_win_hand() -> list[int]:
    return [11, 11, 11, 22, 22, 22, 33, 33, 33, 44, 44, 44, 15, 15]


def _waiting_hand_for_15() -> list[int]:
    return [11, 11, 11, 22, 22, 22, 33, 33, 33, 44, 44, 44, 15]


def _non_waiting_hand() -> list[int]:
    return [11, 12, 13, 14, 15, 16, 17, 18, 21, 22, 24, 32, 47]


def _non_claiming_hand_for_nine_gates() -> list[int]:
    return [21, 21, 22, 22, 23, 23, 31, 31, 32, 32, 41, 42, 43]


def _non_claiming_hand_for_lockout() -> list[int]:
    return [21, 21, 22, 22, 23, 23, 31, 31, 32, 32, 41, 42, 43]


def _fill_other_players(game_state: Any, *, skip: set[int], hand_factory=_non_waiting_hand) -> None:
    for idx in range(4):
        if idx in skip:
            continue
        player = game_state.player_list[idx]
        player.hand_tiles = hand_factory()
        player.waiting_tiles = set()
