"""
一次性迁移：清理早期错误牌谱，修复 6/11–6/21「仅旧补花 / 短 bd」批次。

删除：含三段吃碰杠、三段暗杠（无真实手牌 ID）、或缺 seats 的牌谱。
修复：其余仍含「bh 缺 T/F」或「bd 缺 action_player」的牌谱，按手牌推演补全。

由 DatabaseManager.init_database 在首次启动时调用；用 app_meta 标记，成功后不再重复。
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from psycopg2.extras import RealDictCursor

from ..gamestate.public.hand_slot_utils import normalize_tile, tiles_equal

logger = logging.getLogger(__name__)

META_KEY = "legacy_game_record_tick_fix_v1"

MELD_CODES = frozenset({"cl", "cm", "cr", "p", "g"})


def _expected_meld_hand_count(code: str) -> int:
    return 3 if code == "g" else 2


def _tick_code(tick: Any) -> str:
    if not isinstance(tick, (list, tuple)) or not tick:
        return ""
    return str(tick[0]).strip()


def _is_legacy_meld(tick: Any) -> bool:
    code = _tick_code(tick)
    if code not in MELD_CODES or not isinstance(tick, (list, tuple)):
        return False
    return len(tick) < 3 + _expected_meld_hand_count(code)


def _is_legacy_angang(tick: Any) -> bool:
    return _tick_code(tick) == "ag" and isinstance(tick, (list, tuple)) and len(tick) < 7


def _is_legacy_buhua(tick: Any) -> bool:
    return _tick_code(tick) == "bh" and isinstance(tick, (list, tuple)) and len(tick) < 4


def _is_short_bd(tick: Any) -> bool:
    return _tick_code(tick) == "bd" and isinstance(tick, (list, tuple)) and len(tick) < 3


def _iter_rounds(record: dict):
    game_round = record.get("game_round") or {}
    if not isinstance(game_round, dict):
        return
    for key, rd in game_round.items():
        if isinstance(rd, dict):
            yield key, rd


def _round_missing_seats(rd: dict) -> bool:
    seats = rd.get("seats")
    return not isinstance(seats, list) or len(seats) != 4


def classify_record(record: dict) -> str:
    """
    返回:
      delete — 早期错误（旧鸣牌/旧暗杠/缺 seats）
      fix    — 仅旧补花/短 bd，可推理修复
      ok     — 无需处理
    """
    if not isinstance(record, dict):
        return "delete"

    has_legacy_meld = False
    has_legacy_angang = False
    has_legacy_buhua = False
    has_short_bd = False
    missing_seats = False

    for _, rd in _iter_rounds(record):
        if _round_missing_seats(rd):
            missing_seats = True
        for tick in rd.get("action_ticks") or []:
            if _is_legacy_meld(tick):
                has_legacy_meld = True
            elif _is_legacy_angang(tick):
                has_legacy_angang = True
            elif _is_legacy_buhua(tick):
                has_legacy_buhua = True
            elif _is_short_bd(tick):
                has_short_bd = True

    if missing_seats or has_legacy_meld or has_legacy_angang:
        return "delete"
    if has_legacy_buhua or has_short_bd:
        return "fix"
    return "ok"


def _remove_one(hand: List[int], tile: int, prefer_last: bool = False) -> bool:
    if prefer_last and hand and tiles_equal(hand[-1], tile):
        hand.pop()
        return True
    for i, t in enumerate(hand):
        if t == tile:
            hand.pop(i)
            return True
    for i, t in enumerate(hand):
        if tiles_equal(t, tile):
            hand.pop(i)
            return True
    return False


def _remove_n_normalized(hand: List[int], tile: int, count: int, prefer_last: bool = False) -> bool:
    for _ in range(count):
        if not _remove_one(hand, tile, prefer_last=prefer_last and _ == 0):
            return False
        prefer_last = False
    return True


def fix_record_ticks(record: dict) -> Tuple[dict, Dict[str, int]]:
    """就地修复 bh / bd tick，返回 (record, stats)。"""
    stats = {
        "bh_fixed": 0,
        "bd_fixed": 0,
        "bh_remove_fail": 0,
        "rounds": 0,
    }

    for _, rd in _iter_rounds(record):
        ticks = rd.get("action_ticks")
        if not isinstance(ticks, list) or not ticks:
            continue
        stats["rounds"] += 1

        hands = {
            0: list(rd.get("p0_tiles") or []),
            1: list(rd.get("p1_tiles") or []),
            2: list(rd.get("p2_tiles") or []),
            3: list(rd.get("p3_tiles") or []),
        }
        start = rd.get("start_player_index")
        if start is None:
            start = rd.get("dealer_index", 0)
        current = int(start) if start is not None else 0
        just_drew: Dict[int, Optional[int]] = {0: None, 1: None, 2: None, 3: None}
        last_bh_seat: Optional[int] = None

        new_ticks: List[Any] = []
        for tick in ticks:
            if not isinstance(tick, list) or not tick:
                new_ticks.append(tick)
                continue

            code = _tick_code(tick)

            if code == "bh":
                seat = int(tick[2]) if len(tick) >= 3 else current
                flower = int(tick[1])
                if len(tick) < 4:
                    inferred_mo = just_drew.get(seat) is not None and tiles_equal(
                        just_drew[seat], flower
                    )
                    flag = "T" if inferred_mo else "F"
                    tick = ["bh", flower, seat, flag]
                    stats["bh_fixed"] += 1
                is_mo = str(tick[3]).upper() == "T"
                if not _remove_one(hands[seat], flower, prefer_last=is_mo):
                    stats["bh_remove_fail"] += 1
                just_drew[seat] = None
                last_bh_seat = seat
                current = seat
                new_ticks.append(tick)
                continue

            if code in ("d", "gd", "bd"):
                tile = int(tick[1])
                if code == "bd":
                    if len(tick) < 3:
                        seat = last_bh_seat if last_bh_seat is not None else current
                        tick = ["bd", tile, seat]
                        stats["bd_fixed"] += 1
                    else:
                        seat = int(tick[2])
                    current = seat
                # d / gd 使用 current
                hands[current].append(tile)
                just_drew[current] = tile
                last_bh_seat = None
                new_ticks.append(tick)
                continue

            if code == "c":
                tile = int(tick[1])
                _remove_one(hands[current], tile, prefer_last=True)
                just_drew[current] = None
                last_bh_seat = None
                current = (current + 1) % 4
                new_ticks.append(tick)
                continue

            if code in MELD_CODES:
                seat = int(tick[2]) if len(tick) >= 3 else current
                need = _expected_meld_hand_count(code)
                if len(tick) >= 3 + need:
                    for i in range(need):
                        _remove_one(hands[seat], int(tick[3 + i]), prefer_last=False)
                else:
                    # 不应出现在 fix 路径；兜底按牌种删
                    ming = int(tick[1])
                    n = normalize_tile(ming)
                    if code == "p":
                        _remove_n_normalized(hands[seat], n, 2)
                    elif code == "g":
                        _remove_n_normalized(hands[seat], n, 3)
                    elif code == "cl":
                        _remove_one(hands[seat], n - 1)
                        _remove_one(hands[seat], n - 2)
                    elif code == "cm":
                        _remove_one(hands[seat], n - 1)
                        _remove_one(hands[seat], n + 1)
                    elif code == "cr":
                        _remove_one(hands[seat], n + 1)
                        _remove_one(hands[seat], n + 2)
                just_drew[seat] = None
                last_bh_seat = None
                current = seat
                new_ticks.append(tick)
                continue

            if code == "ag":
                seat = current
                tile = int(tick[1])
                is_mo = len(tick) >= 3 and str(tick[2]).upper() == "T"
                if len(tick) >= 7:
                    for i in range(4):
                        _remove_one(hands[seat], int(tick[3 + i]), prefer_last=False)
                else:
                    _remove_n_normalized(hands[seat], tile, 4, prefer_last=is_mo)
                just_drew[seat] = None
                last_bh_seat = None
                new_ticks.append(tick)
                continue

            if code == "jg":
                tile = int(tick[1])
                is_mo = len(tick) >= 3 and str(tick[2]).upper() == "T"
                _remove_one(hands[current], tile, prefer_last=is_mo)
                just_drew[current] = None
                last_bh_seat = None
                new_ticks.append(tick)
                continue

            if code == "ca":
                new_ticks.append(tick)
                continue

            # hu / liuju / end / 其它：不改手牌推演关键状态
            last_bh_seat = None
            new_ticks.append(tick)

        rd["action_ticks"] = new_ticks

    return record, stats


def _is_meta_done(db_manager, meta_key: str) -> bool:
    conn = None
    try:
        conn = db_manager._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS app_meta (
                   meta_key VARCHAR(100) PRIMARY KEY,
                   meta_value TEXT,
                   updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
               )"""
        )
        conn.commit()
        cursor.execute(
            "SELECT meta_value FROM app_meta WHERE meta_key = %s",
            (meta_key,),
        )
        row = cursor.fetchone()
        return row is not None and row[0] == "1"
    except Exception:
        return False
    finally:
        if conn:
            cursor.close()
            db_manager._put_connection(conn)


def _mark_meta_done(db_manager, meta_key: str, value: str = "1") -> None:
    conn = None
    try:
        conn = db_manager._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS app_meta (
                   meta_key VARCHAR(100) PRIMARY KEY,
                   meta_value TEXT,
                   updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
               )"""
        )
        cursor.execute(
            """
            INSERT INTO app_meta (meta_key, meta_value)
            VALUES (%s, %s)
            ON CONFLICT (meta_key) DO UPDATE SET
                meta_value = EXCLUDED.meta_value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (meta_key, value),
        )
        conn.commit()
    except Exception as e:
        logger.error("标记 meta %s 失败: %s", meta_key, e, exc_info=True)
        if conn:
            conn.rollback()
    finally:
        if conn:
            cursor.close()
            db_manager._put_connection(conn)


def _delete_games(db_manager, game_ids: List[str]) -> int:
    if not game_ids:
        return 0
    conn = None
    try:
        conn = db_manager._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM game_player_metrics WHERE game_id = ANY(%s::varchar[])",
            (game_ids,),
        )
        cursor.execute(
            "DELETE FROM game_records WHERE game_id = ANY(%s::varchar[])",
            (game_ids,),
        )
        deleted = cursor.rowcount
        conn.commit()
        return deleted
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            cursor.close()
            db_manager._put_connection(conn)


def scan_legacy_counts(db_manager) -> Dict[str, int]:
    """扫描库中仍存在的旧格式数量（验证用）。"""
    conn = None
    counts = {
        "total": 0,
        "legacy_meld_games": 0,
        "legacy_angang_games": 0,
        "legacy_buhua_games": 0,
        "short_bd_games": 0,
        "missing_seats_games": 0,
        "legacy_meld_ticks": 0,
        "legacy_angang_ticks": 0,
        "legacy_buhua_ticks": 0,
        "short_bd_ticks": 0,
    }
    try:
        conn = db_manager._get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT game_id, record FROM game_records")
        for row in cursor:
            counts["total"] += 1
            record = row["record"]
            if isinstance(record, str):
                record = json.loads(record)
            flags = {
                "meld": False,
                "ag": False,
                "bh": False,
                "bd": False,
                "seats": False,
            }
            for _, rd in _iter_rounds(record or {}):
                if _round_missing_seats(rd):
                    flags["seats"] = True
                for tick in rd.get("action_ticks") or []:
                    if _is_legacy_meld(tick):
                        counts["legacy_meld_ticks"] += 1
                        flags["meld"] = True
                    elif _is_legacy_angang(tick):
                        counts["legacy_angang_ticks"] += 1
                        flags["ag"] = True
                    elif _is_legacy_buhua(tick):
                        counts["legacy_buhua_ticks"] += 1
                        flags["bh"] = True
                    elif _is_short_bd(tick):
                        counts["short_bd_ticks"] += 1
                        flags["bd"] = True
            if flags["meld"]:
                counts["legacy_meld_games"] += 1
            if flags["ag"]:
                counts["legacy_angang_games"] += 1
            if flags["bh"]:
                counts["legacy_buhua_games"] += 1
            if flags["bd"]:
                counts["short_bd_games"] += 1
            if flags["seats"]:
                counts["missing_seats_games"] += 1
        return counts
    finally:
        if conn:
            cursor.close()
            db_manager._put_connection(conn)


def run_legacy_game_record_migration(db_manager, *, force: bool = False) -> Dict[str, Any]:
    """
    执行删除 + 修复。成功后写入 app_meta。
    force=True 时忽略 meta（用于手工重跑；已修复记录会被跳过）。
    """
    result: Dict[str, Any] = {
        "skipped": False,
        "deleted": 0,
        "fixed": 0,
        "fix_bh": 0,
        "fix_bd": 0,
        "bh_remove_fail": 0,
        "ok": 0,
        "errors": [],
    }

    if not force and _is_meta_done(db_manager, META_KEY):
        logger.info("旧牌谱 tick 迁移已完成（app_meta=%s），跳过", META_KEY)
        result["skipped"] = True
        return result

    conn = None
    to_delete: List[str] = []
    to_fix: List[Tuple[str, dict]] = []

    try:
        conn = db_manager._get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT game_id, record FROM game_records ORDER BY created_at ASC")
        for row in cursor:
            game_id = row["game_id"]
            record = row["record"]
            if isinstance(record, str):
                record = json.loads(record)
            action = classify_record(record or {})
            if action == "delete":
                to_delete.append(game_id)
            elif action == "fix":
                to_fix.append((game_id, record))
            else:
                result["ok"] += 1
        cursor.close()
        db_manager._put_connection(conn)
        conn = None
    except Exception as e:
        logger.error("扫描旧牌谱失败: %s", e, exc_info=True)
        if conn:
            conn.rollback()
            cursor.close()
            db_manager._put_connection(conn)
        result["errors"].append(str(e))
        return result

    logger.info(
        "旧牌谱迁移：待删除 %d，待修复 %d，无需处理 %d",
        len(to_delete),
        len(to_fix),
        result["ok"],
    )

    # 分批删除
    batch_size = 100
    try:
        for i in range(0, len(to_delete), batch_size):
            batch = to_delete[i : i + batch_size]
            deleted = _delete_games(db_manager, batch)
            result["deleted"] += deleted
            logger.info("已删除旧错误牌谱 %d/%d", min(i + batch_size, len(to_delete)), len(to_delete))
    except Exception as e:
        logger.error("删除旧错误牌谱失败，将在下次启动重试: %s", e, exc_info=True)
        result["errors"].append(f"delete: {e}")
        return result

    # 逐条修复并写回
    try:
        conn = db_manager._get_connection()
        cursor = conn.cursor()
        for idx, (game_id, record) in enumerate(to_fix, 1):
            fixed, stats = fix_record_ticks(record)
            # 修复后仍不应含旧格式
            if classify_record(fixed) != "ok":
                msg = f"修复后仍非 ok: game_id={game_id} class={classify_record(fixed)}"
                logger.error(msg)
                result["errors"].append(msg)
                continue
            cursor.execute(
                "UPDATE game_records SET record = %s::jsonb WHERE game_id = %s",
                (json.dumps(fixed, ensure_ascii=False, default=str), game_id),
            )
            result["fixed"] += 1
            result["fix_bh"] += stats["bh_fixed"]
            result["fix_bd"] += stats["bd_fixed"]
            result["bh_remove_fail"] += stats["bh_remove_fail"]
            if idx % 50 == 0:
                conn.commit()
                logger.info("已修复牌谱 %d/%d", idx, len(to_fix))
        conn.commit()
        cursor.close()
        db_manager._put_connection(conn)
        conn = None
    except Exception as e:
        logger.error("修复旧补花牌谱失败，将在下次启动重试: %s", e, exc_info=True)
        if conn:
            conn.rollback()
            cursor.close()
            db_manager._put_connection(conn)
        result["errors"].append(f"fix: {e}")
        return result

    if result["errors"]:
        logger.error("旧牌谱迁移未完全成功，不标记 meta，下次启动重试: %s", result["errors"])
        return result

    summary = (
        f"deleted={result['deleted']}, fixed={result['fixed']}, "
        f"bh={result['fix_bh']}, bd={result['fix_bd']}, "
        f"bh_remove_fail={result['bh_remove_fail']}"
    )
    _mark_meta_done(db_manager, META_KEY, "1")
    logger.info("旧牌谱 tick 迁移完成: %s", summary)
    print(f"旧牌谱 tick 迁移完成: {summary}")
    result["summary"] = summary
    return result
