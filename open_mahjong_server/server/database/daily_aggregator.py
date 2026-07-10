"""
每日 04:00 聚合任务（统计日 = 北京时间当日 04:00 ~ 次日 04:00）：
- daily_stats：每日对局数 / 日活 / 活跃用户 / 最大在线
- scene_daily_stats：各场次（room_type/match_tier/event_id/rule/game_type）聚合
"""
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from psycopg2 import Error

logger = logging.getLogger(__name__)

STAT_TZ = "Asia/Shanghai"
STAT_DAY_OFFSET_HOURS = 4  # 统计日边界：04:00 切日
SHANGHAI_TZ = timezone(timedelta(hours=8))
REGISTERED_USER_ID_MIN = 10000000
DEFAULT_RESTORE_SINCE = date(2026, 6, 6)
# 场次指标仅统计天梯四档
MATCH_TIERS = ("beginner", "intermediate", "advanced", "mcrpl")
MATCH_TIER_SQL = ", ".join(f"'{t}'" for t in MATCH_TIERS)
DAU_METRIC_BACKFILL_META_KEY = "daily_stats_dau_v1"

_SCENE_METRIC_COLUMNS = [
    "total_games", "total_rounds", "win_count", "self_draw_count", "deal_in_count",
    "total_fan_score", "total_win_turn", "total_fangchong_score",
    "first_place_count", "second_place_count", "third_place_count", "fourth_place_count",
    "fulu_round_count", "cuohe_count", "total_round_score",
]


def _stat_date_expr(column: str) -> str:
    """将 timestamptz 映射到统计日：减去 4 小时后取日期（04:00 切日）。"""
    return f"(({column} AT TIME ZONE '{STAT_TZ}') - interval '{STAT_DAY_OFFSET_HOURS} hours')::date"


def current_stat_date() -> date:
    """当前时刻所属的统计日（北京时间 04:00 切日）。"""
    now = datetime.now(SHANGHAI_TZ)
    return (now - timedelta(hours=STAT_DAY_OFFSET_HOURS)).date()


def aggregate_daily_stats(db_manager, stat_date: date, max_online: int = None) -> None:
    """聚合某统计日的 daily_stats（对局数/日活/活跃用户/最大在线），UPSERT。"""
    conn = None
    try:
        conn = db_manager._get_connection()
        cursor = conn.cursor()
        date_expr_gr = _stat_date_expr("gr.created_at")
        cursor.execute(
            f"SELECT COUNT(*) FROM game_records WHERE {_stat_date_expr('created_at')} = %s",
            (stat_date,),
        )
        game_count = int(cursor.fetchone()[0] or 0)

        cursor.execute(
            """
            SELECT COUNT(*)::int
            FROM daily_login_users
            WHERE stat_date = %s AND user_id > %s
            """,
            (stat_date, REGISTERED_USER_ID_MIN),
        )
        dau = int(cursor.fetchone()[0] or 0)

        cursor.execute(f"""
            SELECT COUNT(DISTINCT gpr.user_id)
            FROM game_player_records gpr
            INNER JOIN game_records gr ON gr.game_id = gpr.game_id
            WHERE {date_expr_gr} = %s
              AND gpr.user_id > %s
        """, (stat_date, REGISTERED_USER_ID_MIN))
        active_users = int(cursor.fetchone()[0] or 0)

        if max_online is None:
            cursor.execute(
                "SELECT COALESCE(max_online, 0) FROM daily_online_cache WHERE stat_date = %s",
                (stat_date,),
            )
            row = cursor.fetchone()
            max_online = int(row[0]) if row else 0
        else:
            max_online = int(max_online)
        cursor.execute("""
            INSERT INTO daily_stats (stat_date, game_count, dau, active_users, max_online, updated_at)
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (stat_date) DO UPDATE SET
                game_count = EXCLUDED.game_count,
                dau = EXCLUDED.dau,
                active_users = EXCLUDED.active_users,
                max_online = GREATEST(daily_stats.max_online, EXCLUDED.max_online),
                updated_at = CURRENT_TIMESTAMP
        """, (stat_date, game_count, dau, active_users, max_online))
        conn.commit()
        logger.info(
            "daily_stats 已聚合 %s: games=%s dau=%s active=%s max_online=%s",
            stat_date, game_count, dau, active_users, max_online,
        )
    except Error as e:
        logger.error("聚合 daily_stats 失败 %s: %s", stat_date, e, exc_info=True)
        if conn:
            conn.rollback()
    finally:
        if conn:
            cursor.close()
            db_manager._put_connection(conn)


def aggregate_scene_daily_stats(db_manager, stat_date: date) -> None:
    """聚合某统计日的天梯场次 scene_daily_stats（仅 beginner/intermediate/advanced/mcrpl）。

    单日 DELETE + INSERT，04:00 定时任务调用，开销可控。
    """
    conn = None
    try:
        conn = db_manager._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"""
            DELETE FROM scene_daily_stats
            WHERE stat_date = %s
              AND room_type = 'match'
              AND match_tier IN ({MATCH_TIER_SQL})
            """,
            (stat_date,),
        )

        date_expr = _stat_date_expr("created_at")
        inner = f"""
            SELECT
                %s::date AS stat_date,
                room_type, match_tier, event_id, rule, game_type,
                COUNT(DISTINCT game_id) AS total_games,
                SUM(per_game_rounds) AS total_rounds,
                SUM(win_count) AS win_count,
                SUM(self_draw_count) AS self_draw_count,
                SUM(deal_in_count) AS deal_in_count,
                SUM(total_fan_score) AS total_fan_score,
                SUM(total_win_turn) AS total_win_turn,
                SUM(total_fangchong_score) AS total_fangchong_score,
                SUM(first_place_count) AS first_place_count,
                SUM(second_place_count) AS second_place_count,
                SUM(third_place_count) AS third_place_count,
                SUM(fourth_place_count) AS fourth_place_count,
                SUM(fulu_round_count) AS fulu_round_count,
                SUM(cuohe_count) AS cuohe_count,
                SUM(total_round_score) AS total_round_score
            FROM (
                SELECT game_id, room_type, match_tier, event_id, rule, game_type,
                       MAX(total_rounds) AS per_game_rounds,
                       SUM(win_count) AS win_count,
                       SUM(self_draw_count) AS self_draw_count,
                       SUM(deal_in_count) AS deal_in_count,
                       SUM(total_fan_score) AS total_fan_score,
                       SUM(total_win_turn) AS total_win_turn,
                       SUM(total_fangchong_score) AS total_fangchong_score,
                       SUM(first_place_count) AS first_place_count,
                       SUM(second_place_count) AS second_place_count,
                       SUM(third_place_count) AS third_place_count,
                       SUM(fourth_place_count) AS fourth_place_count,
                       SUM(fulu_round_count) AS fulu_round_count,
                       SUM(cuohe_count) AS cuohe_count,
                       SUM(total_round_score) AS total_round_score
                FROM game_player_metrics
                WHERE {date_expr} = %s
                  AND room_type = 'match'
                  AND match_tier IN ({MATCH_TIER_SQL})
                GROUP BY game_id, room_type, match_tier, event_id, rule, game_type
            ) g
            GROUP BY room_type, match_tier, event_id, rule, game_type
        """
        cols = ("stat_date, room_type, match_tier, event_id, rule, game_type, "
                + ", ".join(_SCENE_METRIC_COLUMNS))
        cursor.execute(
            f"INSERT INTO scene_daily_stats ({cols}) {inner}",
            (stat_date, stat_date),
        )
        conn.commit()
        logger.info("scene_daily_stats 已聚合 %s（天梯四档）", stat_date)
        try:
            from .tier_fan_aggregator import increment_scene_tier_fan_for_date
            increment_scene_tier_fan_for_date(db_manager, stat_date)
        except Exception as e:
            logger.warning("scene_tier_fan_daily 增量失败 %s: %s", stat_date, e)
    except Error as e:
        logger.error("聚合 scene_daily_stats 失败 %s: %s", stat_date, e, exc_info=True)
        if conn:
            conn.rollback()
    finally:
        if conn:
            cursor.close()
            db_manager._put_connection(conn)


def run_daily_aggregation(db_manager, stat_date: date, max_online: int = None) -> None:
    """一次聚合某统计日的 daily_stats 与 scene_daily_stats（各单日，轻量）。"""
    aggregate_daily_stats(db_manager, stat_date, max_online)
    aggregate_scene_daily_stats(db_manager, stat_date)


def run_dau_metric_backfill_once(db_manager) -> None:
    """一次性：为已有统计日重算日活与修正后的活跃用户（含游客对局）。"""
    if _is_meta_done(db_manager, DAU_METRIC_BACKFILL_META_KEY):
        return
    conn = None
    dates: list = []
    try:
        conn = db_manager._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT stat_date FROM daily_stats
            UNION
            SELECT DISTINCT stat_date FROM daily_login_users
            ORDER BY stat_date
            """
        )
        dates = [r[0] for r in cursor.fetchall()]
        if not dates:
            end = current_stat_date()
            start = end - timedelta(days=30)
            current = start
            while current <= end:
                dates.append(current)
                current += timedelta(days=1)
    except Error as e:
        logger.error("查询日活回填日期失败: %s", e, exc_info=True)
        return
    finally:
        if conn:
            cursor.close()
            db_manager._put_connection(conn)

    for stat_date in dates:
        aggregate_daily_stats(db_manager, stat_date)
    _mark_meta_done(db_manager, DAU_METRIC_BACKFILL_META_KEY)
    logger.info("日活指标一次性回填完成，共 %d 个统计日", len(dates))


def _is_meta_done(db_manager, meta_key: str) -> bool:
    conn = None
    try:
        conn = db_manager._get_connection()
        cursor = conn.cursor()
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


def _mark_meta_done(db_manager, meta_key: str) -> None:
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
            (meta_key, "1"),
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


def run_daily_aggregation_range(db_manager, date_from: date, date_to: date) -> None:
    current = date_from
    while current <= date_to:
        run_daily_aggregation(db_manager, current)
        current += timedelta(days=1)


def run_startup_stats_restore(
    db_manager,
    since_date: date = DEFAULT_RESTORE_SINCE,
    date_to: Optional[date] = None,
) -> None:
    """启动维护：增量回填未写入的 metrics，再补齐未聚合的统计日。"""
    if date_to is None:
        date_to = current_stat_date()

    if date_to < since_date:
        logger.info("统计维护跳过：结束日 %s 早于起始日 %s", date_to, since_date)
        return

    from .backfill_game_player_metrics import backfill_missing_game_player_metrics

    logger.info("统计维护：增量回填未合并 metrics（%s ~ %s）", since_date, date_to)
    rows = backfill_missing_game_player_metrics(
        db_manager, date_from=since_date, date_to=date_to,
    )

    logger.info("统计维护：补齐未聚合统计日（%s ~ %s）", since_date, date_to)
    run_catchup_aggregation(db_manager, since_date=since_date, date_to=date_to)

    try:
        conn = db_manager._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM scene_tier_fan_daily")
        fan_rows = int(cursor.fetchone()[0] or 0)
        cursor.close()
        db_manager._put_connection(conn)
        if fan_rows == 0:
            from .tier_fan_aggregator import rebuild_scene_tier_fan_daily_range
            logger.info("scene_tier_fan_daily 为空，执行一次性全量重建")
            rebuild_scene_tier_fan_daily_range(db_manager, since_date, date_to)
    except Exception as e:
        logger.warning("检查/重建 scene_tier_fan_daily 失败: %s", e)

    run_dau_metric_backfill_once(db_manager)
    logger.info("统计维护完成（metrics 增量 %d 行）", rows)


def run_catchup_aggregation(
    db_manager,
    days: int = 7,
    since_date: Optional[date] = None,
    date_to: Optional[date] = None,
) -> None:
    """补齐缺失日的 daily_stats / scene_daily_stats 聚合。"""
    conn = None
    end = date_to or current_stat_date()
    start = since_date or (end - timedelta(days=days))
    try:
        conn = db_manager._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT d::date AS stat_date
            FROM generate_series(%s::date, %s::date, interval '1 day') d
            WHERE d::date NOT IN (SELECT stat_date FROM daily_stats)
               OR d::date NOT IN (
                   SELECT DISTINCT stat_date FROM scene_daily_stats
                   WHERE room_type = 'match'
                     AND match_tier IN ("""
            + MATCH_TIER_SQL +
            """)
               )
            ORDER BY d
            """,
            (start, end),
        )
        missing = [r[0] for r in cursor.fetchall()]
    except Error as e:
        logger.error("查询缺失日期失败: %s", e, exc_info=True)
        missing = []
    finally:
        if conn:
            cursor.close()
            db_manager._put_connection(conn)

    if not missing:
        logger.info("每日统计无需补齐")
        return
    for stat_date in missing:
        logger.info("补齐每日统计: %s", stat_date)
        run_daily_aggregation(db_manager, stat_date)
