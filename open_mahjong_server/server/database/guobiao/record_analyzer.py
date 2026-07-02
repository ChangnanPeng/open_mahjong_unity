"""
从国标牌谱 JSON 推理玩家本场指标（和牌/放铳/错和/副露/和巡等）。
供 backfill_history_stats 与 backfill_game_player_metrics 共用。
"""
from typing import Any, Dict, Optional

from .round_score_utils import _parse_score_changes
from .store_guobiao import FAN_NAME_TO_FIELD, STACKABLE_FANS

HU_ACTIONS = frozenset({"hu_self", "hu_first", "hu_second", "hu_third"})
RON_ACTIONS = frozenset({"hu_first", "hu_second", "hu_third"})
VISIBLE_FULU_CODES = frozenset({"cl", "cm", "cr", "p", "g", "jg"})
DRAW_CODES = frozenset({"d", "bd", "gd", "mo"})
CLAIM_CODES = frozenset({"cl", "cm", "cr", "p", "g"})


def _parse_hu_tick(tick: list) -> Optional[dict]:
    """统一解析和牌 tick（国标 hu_* 与日麻 hu_riichi）。"""
    if not isinstance(tick, list) or not tick:
        return None
    code = tick[0]
    if code == "hu_riichi" and len(tick) >= 7:
        hu_class = tick[2]
        if not isinstance(hu_class, str) or hu_class not in HU_ACTIONS:
            return None
        if not isinstance(tick[1], int):
            return None
        return {
            "hu_class": hu_class,
            "winner_seat": tick[1] % 4,
            "fan_score": int(tick[3]) if isinstance(tick[3], (int, float)) else 0,
            "yaku": tick[5] if len(tick) > 5 else [],
            "score_changes": _parse_score_changes(tick[6]),
        }
    if code in HU_ACTIONS and len(tick) >= 5:
        if not isinstance(tick[1], int):
            return None
        return {
            "hu_class": code,
            "winner_seat": tick[1] % 4,
            "fan_score": int(tick[2]) if isinstance(tick[2], (int, float)) else 0,
            "yaku": tick[3] if len(tick) > 3 else [],
            "score_changes": _parse_score_changes(tick[4]),
        }
    return None


def reconstruct_round_win_turns(rd: Dict[str, Any]) -> Dict[int, int]:
    """从一局 action_ticks 推理每位 seat 的和巡总和。"""
    ticks = rd.get("action_ticks") or []
    if not isinstance(ticks, list):
        return {}
    start = rd.get("start_player_index")
    if not isinstance(start, int):
        start = rd.get("dealer_index")
    if not isinstance(start, int):
        start = 0
    current_seat = start % 4
    xunmu = 1
    win_turn_by_seat: Dict[int, int] = {}
    for tick in ticks:
        if not isinstance(tick, list) or not tick:
            continue
        code = tick[0]
        if code in DRAW_CODES:
            continue
        if code == "c":
            if current_seat == 0:
                xunmu += 1
            current_seat = (current_seat + 1) % 4
        elif code in CLAIM_CODES:
            if len(tick) >= 3 and isinstance(tick[2], int):
                current_seat = tick[2] % 4
        elif code == "ca":
            if len(tick) >= 2 and isinstance(tick[1], int):
                current_seat = tick[1] % 4
        elif code == "end":
            break
        else:
            hu = _parse_hu_tick(tick)
            if hu:
                yaku = hu["yaku"]
                is_cuohe = isinstance(yaku, list) and any("错和" in str(f) for f in yaku)
                if not is_cuohe:
                    win_seat = hu["winner_seat"]
                    win_turn_by_seat[win_seat] = win_turn_by_seat.get(win_seat, 0) + xunmu
    return win_turn_by_seat


def seat_to_original_map(seats) -> Dict[int, int]:
    """seats[original] = seat → {seat: original}。缺省视为 seat==original。"""
    if not isinstance(seats, list) or len(seats) != 4:
        return {0: 0, 1: 1, 2: 2, 3: 3}
    m: Dict[int, int] = {}
    for orig, seat in enumerate(seats):
        try:
            m[int(seat)] = int(orig)
        except (TypeError, ValueError):
            pass
    if len(m) == 4:
        return m
    return {0: 0, 1: 1, 2: 2, 3: 3}


def analyze_record_for_player(record: Dict[str, Any], original_player_index: int) -> Optional[dict]:
    """从牌谱重建该玩家本场计数（zimo/dianhe/fangchong/fangchong_score/cuohe/fulu_rounds/win_score）。"""
    game_round = record.get("game_round") or {}
    if not isinstance(game_round, dict):
        return None
    zimo = dianhe = fangchong = cuohe = fulu_rounds = 0
    win_score = fangchong_score = win_turn = 0
    for rd in game_round.values():
        if not isinstance(rd, dict):
            continue
        seat2orig = seat_to_original_map(rd.get("seats"))
        my_seat = None
        for s, o in seat2orig.items():
            if o == original_player_index:
                my_seat = s
                break
        if my_seat is None:
            continue
        ticks = rd.get("action_ticks") or []
        had_fulu = False
        for tick in ticks:
            if not isinstance(tick, list) or not tick:
                continue
            code = tick[0]
            if code in VISIBLE_FULU_CODES and len(tick) >= 3 and tick[2] == my_seat:
                had_fulu = True
            hu = _parse_hu_tick(tick)
            if hu is None:
                continue
            sc = hu["score_changes"]
            if sc is None or my_seat < 0 or my_seat >= len(sc):
                continue
            yaku = hu["yaku"]
            is_cuohe = isinstance(yaku, list) and any("错和" in str(f) for f in yaku)
            hu_score = hu["fan_score"]
            my_delta = sc[my_seat]
            hu_class = hu["hu_class"]
            if is_cuohe:
                if my_delta < 0:
                    cuohe += 1
                continue
            if my_delta > 0:
                if hu_class == "hu_self":
                    zimo += 1
                else:
                    dianhe += 1
                win_score += int(hu_score)
            elif hu_class in RON_ACTIONS and my_delta < 0:
                neg = [x for x in sc if isinstance(x, (int, float)) and x < 0]
                if neg and my_delta == min(neg):
                    fangchong += 1
                    fangchong_score += int(hu_score)
        if had_fulu:
            fulu_rounds += 1
        win_turn += reconstruct_round_win_turns(rd).get(my_seat, 0)
    return {
        "zimo": zimo, "dianhe": dianhe, "fangchong": fangchong,
        "fangchong_score": fangchong_score, "cuohe": cuohe,
        "fulu_rounds": fulu_rounds, "win_score": win_score, "win_turn": win_turn,
    }


def parse_fan_increment(hu_fan: Any) -> Dict[str, int]:
    """从一次和牌的 hu_fan 列表解析番种字段增量。"""
    inc: Dict[str, int] = {}
    if not isinstance(hu_fan, list):
        return inc
    for fan_name in hu_fan:
        if not isinstance(fan_name, str):
            continue
        if "*" in fan_name:
            base_name, _, count_str = fan_name.partition("*")
            base_name = base_name.strip()
            if base_name in STACKABLE_FANS and base_name in FAN_NAME_TO_FIELD:
                try:
                    cnt = int(count_str.strip())
                except ValueError:
                    continue
                field = FAN_NAME_TO_FIELD[base_name]
                inc[field] = inc.get(field, 0) + cnt
        else:
            field = FAN_NAME_TO_FIELD.get(fan_name)
            if field:
                inc[field] = inc.get(field, 0) + 1
    return inc


def collect_fans_for_player(record: Dict[str, Any], original_player_index: int) -> Dict[str, int]:
    """从牌谱 hu tick 重建该玩家本场番种增量（跳过错和）。"""
    game_round = record.get("game_round") or {}
    if not isinstance(game_round, dict):
        return {}
    total: Dict[str, int] = {}
    for rd in game_round.values():
        if not isinstance(rd, dict):
            continue
        seat2orig = seat_to_original_map(rd.get("seats"))
        my_seat = None
        for s, o in seat2orig.items():
            if o == original_player_index:
                my_seat = s
                break
        if my_seat is None:
            continue
        for tick in rd.get("action_ticks") or []:
            if not isinstance(tick, list) or len(tick) < 4:
                continue
            code = tick[0]
            if code not in HU_ACTIONS:
                continue
            if tick[1] != my_seat:
                continue
            hu_fan = tick[3] if len(tick) > 3 else []
            if isinstance(hu_fan, list) and any("错和" in str(f) for f in hu_fan):
                continue
            for field, cnt in parse_fan_increment(hu_fan).items():
                total[field] = total.get(field, 0) + cnt
    return total
