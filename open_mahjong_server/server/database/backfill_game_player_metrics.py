"""
从历史牌谱回填 game_player_metrics，供 scene_daily_stats 日聚合使用。

- 国标：复用 record_analyzer 完整推理
- 其他规则：写入 rank/score/场次维度，和牌细项尝试复用 tick 分析（结构兼容时）
- created_at 使用 game_records.created_at

用法：
  python -m server.database.backfill_game_player_metrics [--truncate] [--from YYYY-MM-DD] [--to YYYY-MM-DD] [--aggregate]
"""
import argparse
import json
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional, Set

from psycopg2 import Error

from .guobiao.record_analyzer import analyze_record_for_player
from .guobiao.round_score_utils import sum_player_round_score
from .scene_stats import derive_game_type
from .daily_aggregator import MATCH_TIERS

MATCH_TIER_SET = set(MATCH_TIERS)

logger = logging.getLogger(__name__)

REGISTERED_USER_ID_MIN = 10000000
STAT_TZ = "Asia/Shanghai"
STAT_DAY_OFFSET_HOURS = 4


def _stat_date_expr(column: str) -> str:
    return f"(({column} AT TIME ZONE '{STAT_TZ}') - interval '{STAT_DAY_OFFSET_HOURS} hours')::date"


def _resolve_scene_fields(
    record: Optional[Dict[str, Any]],
    room_type: Optional[str],
    match_tier: Optional[str],
    event_id: Optional[str],
) -> tuple:
    """从牌谱 JSON 补全场次维度（含天梯初级/中级 tips 推断）。"""
    title = (record or {}).get("game_title") or {}
    if not room_type:
        room_type = title.get("room_type")
    if not match_tier:
        match_tier = title.get("match_tier")
    if not event_id:
        event_id = title.get("event_id")
    if room_type == "match" and not match_tier:
        tips = title.get("tips")
        if tips is not None:
            if isinstance(tips, str):
                match_tier = "beginner" if tips.lower() in ("true", "1", "yes") else "intermediate"
            else:
                match_tier = "beginner" if tips else "intermediate"
    return room_type, match_tier, event_id
_METRIC_INSERT_SQL = """
    INSERT INTO game_player_metrics (
        game_id, user_id, username, rule, sub_rule, room_type, match_tier, event_id,
        game_type, match_type, score, rank, total_rounds,
        win_count, self_draw_count, deal_in_count, total_fan_score, total_win_turn,
        total_fangchong_score, first_place_count, second_place_count, third_place_count,
        fourth_place_count, fulu_round_count, cuohe_count, total_round_score, created_at
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
    )
"""


def _count_rounds(record: Dict[str, Any]) -> int:
    game_round = record.get("game_round") or {}
    if not isinstance(game_round, dict):
        return 0
    return sum(1 for k in game_round.keys() if isinstance(k, str) and k.startswith("round_index_"))


def _parse_record(raw) -> Optional[Dict[str, Any]]:
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    if isinstance(raw, dict):
        return raw
    return None


def _rank_place_counts(rank: int) -> tuple:
    return (
        1 if rank == 1 else 0,
        1 if rank == 2 else 0,
        1 if rank == 3 else 0,
        1 if rank == 4 else 0,
    )


def _build_metrics_row(
    game_id: str,
    user_id: int,
    username: str,
    rule: str,
    sub_rule: Optional[str],
    room_type: Optional[str],
    match_tier: Optional[str],
    event_id: Optional[str],
    match_type: Optional[str],
    score: int,
    rank: int,
    record: Dict[str, Any],
    original_player_index: Optional[int],
    created_at,
) -> tuple:
    game_type = derive_game_type(match_type)
    total_rounds = _count_rounds(record)
    first, second, third, fourth = _rank_place_counts(rank)

    win_count = self_draw = deal_in = 0
    total_fan_score = total_win_turn = total_fangchong_score = 0
    fulu_round_count = cuohe_count = total_round_score = 0

    if rule == "guobiao" and original_player_index is not None:
        cnt = analyze_record_for_player(record, original_player_index)
        if cnt:
            self_draw = cnt["zimo"]
            win_count = cnt["zimo"] + cnt["dianhe"]
            deal_in = cnt["fangchong"]
            total_fan_score = cnt["win_score"]
            total_fangchong_score = cnt["fangchong_score"]
            fulu_round_count = cnt["fulu_rounds"]
            cuohe_count = cnt["cuohe"]
            total_win_turn = cnt["win_turn"]
        total_round_score = sum_player_round_score(record, original_player_index)
    elif original_player_index is not None:
        cnt = analyze_record_for_player(record, original_player_index)
        if cnt:
            self_draw = cnt["zimo"]
            win_count = cnt["zimo"] + cnt["dianhe"]
            deal_in = cnt["fangchong"]
            total_fan_score = cnt["win_score"]
            total_fangchong_score = cnt["fangchong_score"]
            fulu_round_count = cnt["fulu_rounds"]
            cuohe_count = cnt["cuohe"]
            total_win_turn = cnt["win_turn"]

    return (
        game_id, user_id, username, rule, sub_rule, room_type, match_tier, event_id,
        game_type, match_type, score, rank, total_rounds,
        win_count, self_draw, deal_in, total_fan_score, total_win_turn,
        total_fangchong_score, first, second, third, fourth,
        fulu_round_count, cuohe_count, total_round_score, created_at,
    )


def _get_ai_game_ids(cursor) -> Set[str]:
    cursor.execute("""
        SELECT DISTINCT game_id FROM game_player_records
        WHERE user_id <= %s
    """, (REGISTERED_USER_ID_MIN,))
    return {r[0] for r in cursor.fetchall()}


def backfill_game_player_metrics(
    db_manager,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    truncate: bool = False,
) -> int:
    """回填 game_player_metrics，返回写入行数。"""
    conn = None
    saved = 0
    try:
        conn = db_manager._get_connection()
        cursor = conn.cursor()

        if truncate:
            cursor.execute("TRUNCATE game_player_metrics")
            logger.info("已清空 game_player_metrics")

        exclude_games = _get_ai_game_ids(cursor)

        where = ["gpr.user_id > %s", "gr.created_at IS NOT NULL"]
        params: list = [REGISTERED_USER_ID_MIN]
        if date_from:
            where.append(f"{_stat_date_expr('gr.created_at')} >= %s")
            params.append(date_from)
        if date_to:
            where.append(f"{_stat_date_expr('gr.created_at')} <= %s")
            params.append(date_to)

        cursor.execute(f"""
            SELECT gpr.game_id, gpr.user_id, gpr.username, gpr.rule, gpr.sub_rule,
                   gpr.room_type, gpr.match_tier, gpr.event_id, gpr.match_type,
                   gpr.score, gpr.rank, gpr.original_player_index,
                   gr.record, gr.created_at
            FROM game_player_records gpr
            INNER JOIN game_records gr ON gr.game_id = gpr.game_id
            WHERE {' AND '.join(where)}
            ORDER BY gr.created_at, gpr.game_id, gpr.user_id
        """, params)

        for row in cursor.fetchall():
            (game_id, user_id, username, rule, sub_rule, room_type, match_tier, event_id,
             match_type, score, rank, opi, record_raw, created_at) = row
            if game_id in exclude_games:
                continue
            record = _parse_record(record_raw)
            if record is None:
                continue
            room_type, match_tier, event_id = _resolve_scene_fields(
                record, room_type, match_tier, event_id,
            )
            # 场次指标仅统计天梯四档
            if room_type != "match" or match_tier not in MATCH_TIER_SET:
                continue
            try:
                orig_idx = int(opi) if opi is not None else None
            except (TypeError, ValueError):
                orig_idx = None
            r = int(rank) if rank is not None else 0
            metrics = _build_metrics_row(
                game_id, int(user_id), username or f"用户{user_id}",
                rule, sub_rule, room_type, match_tier, event_id, match_type,
                int(score or 0), r, record, orig_idx, created_at,
            )
            cursor.execute(_METRIC_INSERT_SQL, metrics)
            saved += 1
            if saved % 5000 == 0:
                conn.commit()
                logger.info("已写入 %d 行 game_player_metrics", saved)

        conn.commit()
        logger.info("game_player_metrics 回填完成：共 %d 行", saved)
        return saved
    except Error as e:
        logger.error("回填 game_player_metrics 失败: %s", e, exc_info=True)
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            cursor.close()
            db_manager._put_connection(conn)


def backfill_daily_aggregation_range(db_manager, date_from: date, date_to: date) -> None:
    """对日期区间逐日运行 run_daily_aggregation。"""
    from .daily_aggregator import run_daily_aggregation_range
    run_daily_aggregation_range(db_manager, date_from, date_to)


def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%d").date()


def _default_date_range(db_manager) -> tuple:
    conn = None
    try:
        conn = db_manager._get_connection()
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT MIN({_stat_date_expr('created_at')}),
                   MAX({_stat_date_expr('created_at')})
            FROM game_records
        """)
        row = cursor.fetchone()
        if row and row[0] and row[1]:
            return row[0], row[1]
    finally:
        if conn:
            cursor.close()
            db_manager._put_connection(conn)
    today = datetime.now().date()
    return today - timedelta(days=30), today


if __name__ == "__main__":
    import sys
    from pathlib import Path

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="回填 game_player_metrics 并可选重跑日聚合")
    parser.add_argument("--truncate", action="store_true", help="回填前清空 game_player_metrics")
    parser.add_argument("--from", dest="date_from", metavar="YYYY-MM-DD", help="起始日期（北京时间）")
    parser.add_argument("--to", dest="date_to", metavar="YYYY-MM-DD", help="结束日期（北京时间）")
    parser.add_argument("--aggregate", action="store_true", help="回填后重跑 daily_stats / scene_daily_stats")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from server.local_config import Config
    from server.database.db_manager import DatabaseManager

    db = DatabaseManager(Config.host, Config.user, Config.password, Config.database, Config.port)
    db.init_database()

    d_from = _parse_date(args.date_from)
    d_to = _parse_date(args.date_to)
    if args.aggregate and (d_from is None or d_to is None):
        d_from, d_to = _default_date_range(db)

    backfill_game_player_metrics(db, date_from=d_from, date_to=d_to, truncate=args.truncate)

    if args.aggregate:
        if d_from is None or d_to is None:
            d_from, d_to = _default_date_range(db)
        backfill_daily_aggregation_range(db, d_from, d_to)
        print(f"日聚合完成：{d_from} ~ {d_to}")

    print("game_player_metrics 回填完成")
