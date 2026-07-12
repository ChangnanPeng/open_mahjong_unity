"""Shared persistence for rules stored in game_records/game_player_records."""

from __future__ import annotations

import json
import logging
import secrets
import string
from typing import Any

from psycopg2 import Error

logger = logging.getLogger(__name__)

_GAME_ID_ALPHABET = string.ascii_letters + string.digits
_GAME_ID_LENGTH = 10
_UNIQUE_VIOLATION = "23505"


def generate_game_id(length: int = _GAME_ID_LENGTH) -> str:
    return "".join(secrets.choice(_GAME_ID_ALPHABET) for _ in range(length))


def store_game_record(
    db_manager: Any,
    game_record: dict,
    player_list: list,
    room_type: str,
    match_type: str,
    *,
    default_rule: str,
    default_sub_rule: str,
    log_label: str,
) -> str | None:
    """Store a replay and its per-player index rows in the shared tables."""
    if any(getattr(player, "user_id", 0) <= 10 for player in player_list):
        logger.info("%s game contains a bot; replay persistence skipped", log_label)
        return None

    conn = None
    cursor = None
    try:
        conn = db_manager._get_connection()
        cursor = conn.cursor()
        record_json = json.dumps(game_record, ensure_ascii=False, default=str)

        game_id = None
        for _ in range(5):
            candidate = generate_game_id()
            try:
                cursor.execute(
                    "INSERT INTO game_records (game_id, record) VALUES (%s, %s)",
                    (candidate, record_json),
                )
                game_id = candidate
                break
            except Error as exc:
                conn.rollback()
                if getattr(exc, "pgcode", None) != _UNIQUE_VIOLATION:
                    raise
                logger.warning("game_id collision for %s; retrying", candidate)

        if game_id is None:
            logger.error("%s replay id generation exhausted retries", log_label)
            return None

        title = game_record.get("game_title") or {}
        rule = title.get("rule", default_rule)
        sub_rule = title.get("sub_rule", default_sub_rule)
        match_tier = title.get("match_tier")
        event_id = title.get("event_id")
        saved_count = 0

        for player in player_list:
            cursor.execute("SAVEPOINT player_record")
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
                cursor.execute("RELEASE SAVEPOINT player_record")
                saved_count += 1
            except Error as exc:
                cursor.execute("ROLLBACK TO SAVEPOINT player_record")
                cursor.execute("RELEASE SAVEPOINT player_record")
                logger.warning(
                    "%s player replay index skipped: user_id=%s error=%s",
                    log_label,
                    player.user_id,
                    exc,
                )

        conn.commit()
        logger.info(
            "%s replay stored: game_id=%s player_rows=%s",
            log_label,
            game_id,
            saved_count,
        )

        try:
            from .scene_stats import record_game_metrics

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
            logger.warning("%s game metrics persistence failed: %s", log_label, exc)

        return game_id
    except Error as exc:
        logger.error("%s replay persistence failed: %s", log_label, exc, exc_info=True)
        if conn is not None:
            conn.rollback()
        return None
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            db_manager._put_connection(conn)
