from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
import sys

SERVER_ROOT = Path(__file__).resolve().parents[3]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from server.database.data_router import handle_data_message
from server.database.jiandan.get_jiandan_stats import (
    get_jiandan_fan_stats_total,
    get_jiandan_history_stats,
)
from server.database.jiandan.store_jiandan import (
    FAN_FIELDS,
    create_jiandan_stats_tables,
    store_jiandan_fan_stats,
    store_jiandan_game_stats,
)


class FakeCursor:
    def __init__(self) -> None:
        self.calls = []
        self.current_sql = ""
        self.closed = False

    def execute(self, sql, params=None) -> None:
        self.current_sql = " ".join(sql.split())
        self.calls.append((self.current_sql, params))

    def fetchone(self):
        if "SELECT 1 FROM users" in self.current_sql:
            return (1,)
        if "FROM jiandan_fan_stats" in self.current_sql:
            return {fan_id: int(fan_id == "pinfu") * 3 for fan_id in FAN_FIELDS}
        return None

    def fetchall(self):
        if "FROM jiandan_history_stats" not in self.current_sql:
            return []
        return [
            {
                "rule": "jiandan",
                "mode": "1/4",
                "total_games": 2,
                "total_rounds": 4,
                "win_count": 1,
                "self_draw_count": 1,
                "deal_in_count": 0,
                "total_fan_score": 3,
                "total_win_turn": 2,
                "total_fangchong_score": 0,
                "first_place_count": 1,
                "second_place_count": 1,
                "third_place_count": 0,
                "fourth_place_count": 0,
                "fulu_round_count": 1,
            }
        ]

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self) -> None:
        self.cursor_instance = FakeCursor()
        self.commits = 0
        self.rollbacks = 0

    def cursor(self, cursor_factory=None):
        return self.cursor_instance

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class FakeDatabase:
    def __init__(self) -> None:
        self.connections = []
        self.returned = []

    def _get_connection(self):
        connection = FakeConnection()
        self.connections.append(connection)
        return connection

    def _put_connection(self, connection) -> None:
        self.returned.append(connection)


def _counter(**overrides):
    values = {
        "zimo_times": 0,
        "dianhe_times": 0,
        "fangchong_times": 0,
        "win_score": 0,
        "win_turn": 0,
        "fangchong_score": 0,
        "rank_result": 4,
        "fulu_times": 0,
        "recorded_fans": [],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_schema_uses_all_stable_fan_ids() -> None:
    cursor = FakeCursor()
    create_jiandan_stats_tables(cursor)
    sql = " ".join(call[0] for call in cursor.calls)
    assert "CREATE TABLE IF NOT EXISTS jiandan_history_stats" in sql
    assert "CREATE TABLE IF NOT EXISTS jiandan_fan_stats" in sql
    assert all(fan_id in sql for fan_id in FAN_FIELDS)


def test_game_stats_upsert_uses_record_counter() -> None:
    database = FakeDatabase()
    player = SimpleNamespace(
        user_id=10000001,
        record_counter=_counter(
            zimo_times=1,
            dianhe_times=2,
            fangchong_times=1,
            win_score=12,
            win_turn=7,
            fangchong_score=3,
            rank_result=2,
            fulu_times=2,
        ),
    )
    store_jiandan_game_stats(database, "game-id", [player], "custom", 2, 5)

    calls = database.connections[0].cursor_instance.calls
    insert_params = next(params for sql, params in calls if "INSERT INTO jiandan_history_stats" in sql)
    assert insert_params[:3] == [10000001, "jiandan", "2/4"]
    assert insert_params[3:] == [1, 5, 3, 1, 1, 12, 7, 3, 0, 1, 0, 0, 2]
    assert database.connections[0].commits == 1


def test_fan_stats_count_repeated_ids_and_chinese_fallback() -> None:
    database = FakeDatabase()
    player = SimpleNamespace(
        user_id=10000001,
        record_counter=_counter(
            recorded_fans=[["pinfu", "two_suit_triplets", "two_suit_triplets"], ["门前清"]]
        ),
    )
    store_jiandan_fan_stats(database, "game-id", [player], "custom", 1)

    calls = database.connections[0].cursor_instance.calls
    insert_params = next(params for sql, params in calls if "INSERT INTO jiandan_fan_stats" in sql)
    fan_values = dict(zip(FAN_FIELDS, insert_params[3:]))
    assert fan_values["pinfu"] == 1
    assert fan_values["two_suit_triplets"] == 2
    assert fan_values["closed_hand"] == 1


def test_stats_queries_return_client_shape() -> None:
    database = FakeDatabase()
    history = get_jiandan_history_stats(database, 10000001)
    fan_stats = get_jiandan_fan_stats_total(database, 10000001)

    assert history[0]["mode"] == "1/4"
    assert history[0]["win_count"] == 1
    assert fan_stats["pinfu"] == 3
    assert set(fan_stats) == set(FAN_FIELDS)


def test_data_router_dispatches_jiandan_stats() -> None:
    database = FakeDatabase()
    game_server = SimpleNamespace(db_manager=database)

    class FakeWebSocket:
        def __init__(self) -> None:
            self.payloads = []

        async def send_json(self, payload) -> None:
            self.payloads.append(payload)

    websocket = FakeWebSocket()
    asyncio.run(
        handle_data_message(
            game_server,
            "connection-id",
            {"type": "data/get_jiandan_stats", "userid": "10000001"},
            websocket,
        )
    )
    payload = websocket.payloads[0]
    assert payload["success"] is True
    assert payload["type"] == "data/get_jiandan_stats"
    assert payload["rule_stats"]["rule"] == "jiandan"
    assert payload["rule_stats"]["history_stats"][0]["mode"] == "1/4"
    assert payload["rule_stats"]["total_fan_stats"]["pinfu"] == 3


def run() -> None:
    tests = [
        test_schema_uses_all_stable_fan_ids,
        test_game_stats_upsert_uses_record_counter,
        test_fan_stats_count_repeated_ids_and_chinese_fallback,
        test_stats_queries_return_client_shape,
        test_data_router_dispatches_jiandan_stats,
    ]
    for test in tests:
        test()
    print(f"jiandan statistics smoke tests ok: {len(tests)} tests")


if __name__ == "__main__":
    run()
