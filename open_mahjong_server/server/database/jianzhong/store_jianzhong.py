"""Jianzhong replay persistence."""

from ..store_game_record import store_game_record


def store_jianzhong_game_record(
    db_manager,
    game_record: dict,
    player_list: list,
    room_type: str,
    match_type: str,
):
    return store_game_record(
        db_manager,
        game_record,
        player_list,
        room_type,
        match_type,
        default_rule="jianzhong",
        default_sub_rule="jianzhong/standard",
        log_label="Jianzhong",
    )
