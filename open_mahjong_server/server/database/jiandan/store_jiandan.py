"""Store Jiandan replays in the existing shared replay tables."""

from __future__ import annotations

import json
import logging
import secrets
import string

from psycopg2 import Error

logger = logging.getLogger(__name__)

_GAME_ID_ALPHABET = string.ascii_letters + string.digits
_GAME_ID_LENGTH = 10


def _generate_game_id(length: int = _GAME_ID_LENGTH) -> str:
    return "".join(secrets.choice(_GAME_ID_ALPHABET) for _ in range(length))


def store_jiandan_game_record(
    db_manager,
    game_record: dict,
    player_list: list,
    room_type: str,
    match_type: str,
):
    """Persist one Jiandan game without changing shared database helpers."""
    if any(getattr(player, "user_id", 0) <= 10 for player in player_list):
        logger.info("Jiandan game contains a bot; replay persistence skipped")
        return None

    conn = None
    cursor = None
    try:
        conn = db_manager._get_connection()
        cursor = conn.cursor()
        game_record_json = json.dumps(game_record, ensure_ascii=False, default=str)

        game_id = None
        for _ in range(5):
            candidate = _generate_game_id()
            try:
                cursor.execute(
                    "INSERT INTO game_records (game_id, record) VALUES (%s, %s)",
                    (candidate, game_record_json),
                )
                game_id = candidate
                break
            except Error:
                conn.rollback()
                logger.warning("Jiandan replay id collision: %s; retrying", candidate)

        if game_id is None:
            logger.error("Jiandan replay id generation exhausted retries")
            return None

        title = game_record.get("game_title") or {}
        rule = title.get("rule", "jiandan")
        sub_rule = title.get("sub_rule", "jiandan/standard")
        match_tier = title.get("match_tier")
        event_id = title.get("event_id")

        for player in player_list:
            try:
                cursor.execute(
                    """
                    INSERT INTO game_player_records (
                        game_id, user_id, username, score, rank,
                        original_player_index, rule, sub_rule, match_type,
                        room_type, match_tier, event_id, title_used,
                        character_used, profile_used, voice_used
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        game_id,
                        player.user_id,
                        player.username,
                        player.score,
                        player.record_counter.rank_result,
                        player.original_player_index,
                        rule,
                        sub_rule,
                        match_type,
                        room_type,
                        match_tier,
                        event_id,
                        getattr(player, "title_used", None),
                        getattr(player, "character_used", None),
                        getattr(player, "profile_used", None),
                        getattr(player, "voice_used", None),
                    ),
                )
            except Error as exc:
                logger.warning(
                    "Jiandan replay player row skipped: user_id=%s error=%s",
                    player.user_id,
                    exc,
                )

        conn.commit()

        try:
            from ..scene_stats import record_game_metrics

            record_game_metrics(
                db_manager,
                game_id,
                game_record,
                player_list,
                {
                    "rule": rule,
                    "sub_rule": sub_rule,
                    "room_type": room_type,
                    "match_tier": match_tier,
                    "event_id": event_id,
                    "match_type": match_type,
                },
            )
        except Exception as exc:
            logger.warning("Jiandan game metrics persistence failed: %s", exc)

        return game_id
    except Error as exc:
        logger.error("Jiandan replay persistence failed: %s", exc, exc_info=True)
        if conn is not None:
            conn.rollback()
        return None
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            db_manager._put_connection(conn)
