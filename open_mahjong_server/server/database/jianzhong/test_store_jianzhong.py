from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys

SERVER_ROOT = Path(__file__).resolve().parents[3]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from server.database.jianzhong.store_jianzhong import store_jianzhong_game_record


class FakeCursor:
    def __init__(self) -> None:
        self.calls = []
        self.closed = False

    def execute(self, sql, params=None) -> None:
        self.calls.append((" ".join(sql.split()), params))

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self) -> None:
        self.cursor_instance = FakeCursor()
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return self.cursor_instance

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class FakeDatabase:
    def __init__(self) -> None:
        self.connection = FakeConnection()
        self.returned = []

    def _get_connection(self):
        return self.connection

    def _put_connection(self, connection) -> None:
        self.returned.append(connection)


def _player(user_id: int, index: int):
    return SimpleNamespace(
        user_id=user_id,
        username=f"player-{index}",
        score=100 + index,
        original_player_index=index,
        record_counter=SimpleNamespace(rank_result=index + 1),
        title_used=None,
        character_used=None,
        profile_used=None,
        voice_used=None,
    )


def test_jianzhong_record_uses_shared_tables_and_rule_identity() -> None:
    database = FakeDatabase()
    record = {
        "game_title": {
            "rule": "jianzhong",
            "sub_rule": "jianzhong/standard",
        },
        "game_round": {},
    }
    players = [_player(101 + index, index) for index in range(4)]

    game_id = store_jianzhong_game_record(
        database,
        record,
        players,
        "custom",
        "1/4",
    )

    assert isinstance(game_id, str) and len(game_id) == 10
    calls = database.connection.cursor_instance.calls
    assert sum("INSERT INTO game_records" in sql for sql, _ in calls) == 1
    player_inserts = [params for sql, params in calls if "INSERT INTO game_player_records" in sql]
    assert len(player_inserts) == 4
    assert all(params[6:10] == ("jianzhong", "jianzhong/standard", "1/4", "custom") for params in player_inserts)
    assert database.connection.commits == 1
    assert database.returned == [database.connection]
    assert database.connection.cursor_instance.closed


def test_jianzhong_record_skips_games_with_bots() -> None:
    database = FakeDatabase()
    players = [_player(1, 0)] + [_player(102 + index, index + 1) for index in range(3)]

    assert store_jianzhong_game_record(
        database,
        {"game_title": {}},
        players,
        "custom",
        "1/4",
    ) is None
    assert database.connection.cursor_instance.calls == []


def run() -> None:
    tests = [
        test_jianzhong_record_uses_shared_tables_and_rule_identity,
        test_jianzhong_record_skips_games_with_bots,
    ]
    for test in tests:
        test()
    print(f"jianzhong database tests ok: {len(tests)} tests")


if __name__ == "__main__":
    run()
