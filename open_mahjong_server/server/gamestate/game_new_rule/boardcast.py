from __future__ import annotations

from typing import Any, Optional

from ..public.deal_tile_view import sanitize_deal_tile_for_viewer


def public_melds_for_viewer(player: Any, viewer_index: Optional[int], *, reveal_final: bool = False) -> list[str]:
    melds: list[str] = []
    for meld in player.combination_tiles:
        if isinstance(meld, str) and meld.startswith("G") and not reveal_final and viewer_index != player.player_index:
            melds.append("G0")
        else:
            melds.append(meld)
    return melds


def player_view(game_state: Any, player_index: int, viewer_index: Optional[int], *, reveal_final: bool = False) -> dict:
    player = game_state.player_list[player_index]
    include_hand = reveal_final or viewer_index == player_index
    return {
        "player_index": player_index,
        "user_id": player.user_id,
        "username": player.username,
        "score": player.score,
        "is_hu": player.is_hu,
        "hu_order": player.hu_order,
        "tag_list": list(player.tag_list),
        "discard_tiles": list(player.discard_tiles),
        "combination_tiles": public_melds_for_viewer(player, viewer_index, reveal_final=reveal_final),
        "hand_count": len(player.hand_tiles),
        "hand_tiles": list(player.hand_tiles) if include_hand else None,
    }


def _safe_room_id(room_id: Any) -> int:
    try:
        return int(room_id)
    except (TypeError, ValueError):
        return 0


def unity_player_info(
    game_state: Any,
    player_index: int,
    viewer_index: Optional[int],
    *,
    reveal_final: bool = False,
) -> dict:
    player = game_state.player_list[player_index]
    include_hand = reveal_final or viewer_index == player_index
    hand_tiles = list(player.hand_tiles) if include_hand else None
    return {
        "username": player.username,
        "user_id": player.user_id,
        "hand_tiles_count": len(player.hand_tiles),
        "hand_tiles": hand_tiles,
        "discard_tiles": list(player.discard_tiles),
        "discard_origin_tiles": list(player.discard_origin_tiles),
        "combination_tiles": public_melds_for_viewer(player, viewer_index, reveal_final=reveal_final),
        "combination_mask": list(player.combination_mask),
        "remaining_time": player.remaining_time,
        "player_index": player_index,
        "original_player_index": player.original_player_index,
        "score": player.score,
        "huapai_list": [],
        "title_used": 0,
        "character_used": 0,
        "profile_used": 0,
        "voice_used": 0,
        "score_history": [],
        "round_number_history": [],
        "tag_list": list(player.tag_list),
        "discard_riichi_flags": [],
        "dingque_suit": 0,
        "is_hu": player.is_hu,
    }


def unity_game_info(game_state: Any, viewer_index: Optional[int], *, reveal_final: bool = False) -> dict:
    return {
        "room_id": _safe_room_id(game_state.room_id),
        "gamestate_id": game_state.gamestate_id,
        "tips": game_state.tips,
        "current_player_index": game_state.current_player_index,
        "action_tick": game_state.server_action_tick,
        "max_round": game_state.max_round,
        "tile_count": len(game_state.tiles_list),
        "commitment": "",
        "salt": "",
        "current_round": game_state.current_round,
        "step_time": game_state.step_time,
        "round_time": game_state.round_time,
        "room_type": game_state.room_type,
        "room_rule": game_state.room_rule,
        "sub_rule": game_state.sub_rule,
        "hepai_limit": 0,
        "open_cuohe": False,
        "show_moqie_hint": False,
        "tactical_call": False,
        "claim_protection": True,
        "isPlayerSetRandomSeed": bool(game_state.room_random_seed),
        "player_entry_order": [player.user_id for player in game_state.player_list],
        "players_info": [
            unity_player_info(game_state, idx, viewer_index, reveal_final=reveal_final)
            for idx in range(len(game_state.player_list))
        ],
        "self_hand_tiles": list(game_state.player_list[viewer_index].hand_tiles)
        if viewer_index is not None and viewer_index in range(len(game_state.player_list))
        else None,
        "dealer_index": game_state.dealer_index,
        "view_player_index": viewer_index,
        "blood_battle": True,
    }


def game_view(game_state: Any, viewer_index: Optional[int], *, reveal_final: bool = False) -> dict:
    payload = {
        "room_id": game_state.room_id,
        "gamestate_id": game_state.gamestate_id,
        "room_rule": game_state.room_rule,
        "sub_rule": game_state.sub_rule,
        "current_player_index": game_state.current_player_index,
        "dealer_index": game_state.dealer_index,
        "current_round": game_state.current_round,
        "round_index": game_state.round_index,
        "tiles_left": len(game_state.tiles_list),
        "game_status": game_state.game_status,
        "action_tick": game_state.server_action_tick,
        "players_info": [
            player_view(game_state, idx, viewer_index, reveal_final=reveal_final)
            for idx in range(len(game_state.player_list))
        ],
    }
    if reveal_final:
        payload["deferred_hu_settlements"] = list(game_state.deferred_hu_settlements)
        payload["ended_by"] = game_state.ended_by
    return payload


def ask_action_payload(
    game_state: Any,
    viewer_index: int,
    action_list: list[str],
    *,
    cut_tile: Optional[int] = None,
    rob_kong_tile: Optional[int] = None,
) -> dict:
    return {
        "type": "gamestate/new_rule/ask_action",
        "success": True,
        "game_info": game_view(game_state, viewer_index),
        "unity_game_info": unity_game_info(game_state, viewer_index),
        "player_index": viewer_index,
        "action_list": list(action_list),
        "action_tick": game_state.server_action_tick,
        "cut_tile": cut_tile,
        "rob_kong_tile": rob_kong_tile,
        "ask_hand_action_info": {
            "action_list": list(action_list),
            "remaining_time": game_state.player_list[viewer_index].remaining_time,
            "player_index": viewer_index,
            "remain_tiles": len(game_state.tiles_list),
            "action_tick": game_state.server_action_tick,
        } if cut_tile is None and rob_kong_tile is None else None,
        "ask_other_action_info": {
            "action_list": list(action_list),
            "remaining_time": game_state.player_list[viewer_index].remaining_time,
            "cut_tile": cut_tile if cut_tile is not None else rob_kong_tile,
            "action_tick": game_state.server_action_tick,
        } if cut_tile is not None or rob_kong_tile is not None else None,
    }


def visible_action_payload(
    game_state: Any,
    viewer_index: Optional[int],
    action_info: dict,
    *,
    reveal_final: bool = False,
) -> dict:
    action = action_info.get("action")
    actor = action_info.get("player")
    deal_tile = action_info.get("tile") if action in {"deal_tile", "deal_gang_tile", "deal_buhua_tile"} else None
    viewer_deal_tile = sanitize_deal_tile_for_viewer(deal_tile, actor, viewer_index) if actor is not None and viewer_index is not None else deal_tile
    payload = {
        "type": "gamestate/new_rule/do_action",
        "success": True,
        "action": action,
        "player": actor,
        "tile": action_info.get("tile"),
        "game_info": game_view(game_state, viewer_index, reveal_final=reveal_final),
        "unity_game_info": unity_game_info(game_state, viewer_index, reveal_final=reveal_final),
        "do_action_info": {
            "action_list": [action] if action else [],
            "action_player": actor if actor is not None else -1,
            "action_tick": game_state.server_action_tick,
            "cut_tile": action_info.get("tile") if action == "cut" else None,
            "cut_tile_index": action_info.get("cut_index"),
            "cut_class": False,
            "deal_tile": viewer_deal_tile,
            "combination_target": action_info.get("meld_code"),
            "combination_mask": action_info.get("combination_mask"),
            "is_mo_gang": action == "angang",
        },
    }

    if action == "angang" and not reveal_final and viewer_index != actor:
        payload["meld_code"] = "G0"
    elif "meld_code" in action_info:
        payload["meld_code"] = action_info["meld_code"]

    if action in {"hu", "hu_self", "rob_kong"} and not reveal_final:
        if action == "hu_self" and viewer_index != actor:
            payload["tile"] = None
        payload["fan_ids"] = None
        payload["fan_names"] = None
        payload["points"] = None
    else:
        for key in ("fan_ids", "fan_names", "points", "score_changes"):
            if key in action_info:
                payload[key] = action_info[key]
    return payload


def _final_scores(game_state: Any) -> dict[int, int]:
    return {
        player.player_index: player.score
        for player in game_state.player_list
    }


def _total_score_changes(game_state: Any) -> dict[int, int]:
    totals = {player.player_index: 0 for player in game_state.player_list}
    for settlement in getattr(game_state, "deferred_hu_settlements", []):
        changes = settlement.get("score_changes") or []
        for player_index, change in enumerate(changes):
            if player_index in totals:
                totals[player_index] += change
    return totals


def _final_show_result_info(game_state: Any) -> dict:
    settlements = list(getattr(game_state, "deferred_hu_settlements", []))
    player_to_score = _final_scores(game_state)
    score_changes = _total_score_changes(game_state)
    action_tick = getattr(game_state, "server_action_tick", 0)

    if not settlements:
        return {
            "hepai_player_index": -1,
            "player_to_score": player_to_score,
            "hu_score": 0,
            "hu_fan": [],
            "hu_class": "liuju",
            "hepai_player_hand": [],
            "hepai_player_huapai": [],
            "hepai_player_combination_mask": [],
            "action_tick": action_tick,
            "score_changes": score_changes,
            "liuju_step": "final",
            "liuju_status_final": True,
        }

    settlement = settlements[-1]
    winner_index = settlement.get("winner", -1)
    winner = game_state.player_list[winner_index] if winner_index in range(len(game_state.player_list)) else None
    hand = list(winner.hand_tiles) if winner is not None else []
    win_tile = settlement.get("tile")
    if settlement.get("source") != "self_draw" and win_tile is not None:
        hand = hand + [win_tile]
    source = settlement.get("source")
    hu_class = "hu_self" if source == "self_draw" else "hu"

    return {
        "hepai_player_index": winner_index,
        "player_to_score": player_to_score,
        "hu_score": settlement.get("points", 0),
        "hu_fan": list(settlement.get("fan_names") or settlement.get("fan_ids") or []),
        "hu_class": hu_class,
        "hepai_player_hand": hand,
        "hepai_player_huapai": [],
        "hepai_player_combination_mask": list(winner.combination_mask) if winner is not None else [],
        "action_tick": action_tick,
        "score_changes": score_changes,
        "hepai_tile": win_tile,
        "suppress_hand_reveal": False,
        "defer_score_settlement": False,
        "is_qianggang": source == "rob_kong",
        "ron_discarder_index": settlement.get("discarder") or settlement.get("kong_player"),
    }


def final_settlement_payload(game_state: Any, viewer_index: Optional[int]) -> dict:
    if hasattr(game_state, "apply_deferred_score_changes"):
        game_state.apply_deferred_score_changes()
    return {
        "type": "gamestate/new_rule/final_settlement",
        "success": True,
        "player_index": viewer_index,
        "game_info": game_view(game_state, viewer_index, reveal_final=True),
        "unity_game_info": unity_game_info(game_state, viewer_index, reveal_final=True),
        "show_result_info": _final_show_result_info(game_state),
    }


def reconnect_payload(game_state: Any, viewer_index: int) -> dict:
    reveal_final = getattr(game_state, "game_status", None) == "END"
    if reveal_final and hasattr(game_state, "apply_deferred_score_changes"):
        game_state.apply_deferred_score_changes()
    action_list = list(game_state.action_dict.get(viewer_index, []))
    return {
        "type": "gamestate/new_rule/reconnect",
        "success": True,
        "player_index": viewer_index,
        "game_info": game_view(game_state, viewer_index, reveal_final=reveal_final),
        "unity_game_info": unity_game_info(game_state, viewer_index, reveal_final=reveal_final),
        "action_list": action_list,
        "action_tick": game_state.server_action_tick,
    }
