from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace

SERVER_ROOT = Path(__file__).resolve().parents[3]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from server.gamestate.gamestate_manager import GameStateManager
from server.gamestate.game_jianzhong import JianzhongGameState


class FakeRoomManager:
    def __init__(self, room_data: dict):
        self.rooms = {room_data["room_id"]: room_data}

    def all_players_ready(self, room_data: dict) -> bool:
        return True


def _room_data() -> dict:
    return {
        "room_id": "jianzhong-manager-room",
        "player_list": [101, 102, 103, 104],
        "player_settings": {
            101: {"username": "p1"},
            102: {"username": "p2"},
            103: {"username": "p3"},
            104: {"username": "p4"},
        },
        "round_timer": 0,
        "step_timer": 0,
        "game_round": 1,
        "room_rule": "jianzhong",
        "room_type": "custom",
        "sub_rule": "jianzhong/standard",
        "tips": False,
        "random_seed": 1,
        "allow_spectator": True,
    }


def _server(room_data: dict):
    server = SimpleNamespace()
    server.room_manager = FakeRoomManager(room_data)
    server.players = {"conn-101": SimpleNamespace(user_id=101)}
    server.user_id_to_connection = {}
    server.calculation_service = None
    server.db_manager = None
    return server


def test_manager_starts_and_cleans_up_jianzhong_game_state() -> None:
    async def scenario() -> None:
        room_data = _room_data()
        server = _server(room_data)
        manager = GameStateManager(server)
        server.gamestate_manager = manager

        response = await manager.start_game("conn-101", room_data["room_id"])
        await asyncio.sleep(0.05)

        assert response is None
        assert room_data["is_game_running"]
        game_state = manager.get_game_state_by_room_id(room_data["room_id"])
        assert isinstance(game_state, JianzhongGameState)
        assert manager.get_game_state_by_gamestate_id(game_state.gamestate_id) is game_state
        assert manager.get_game_state_by_user_id(101) is game_state
        assert game_state.game_task is not None
        assert game_state.spectator_enabled is True
        spectator_list = manager.get_spectator_list()
        assert len(spectator_list) == 1
        assert spectator_list[0].gamestate_id == game_state.gamestate_id

        await manager.cleanup_game_state_complete(gamestate_id=game_state.gamestate_id)

        assert manager.get_game_state_by_room_id(room_data["room_id"]) is None
        assert manager.get_game_state_by_gamestate_id(game_state.gamestate_id) is None
        assert manager.get_game_state_by_user_id(101) is None
        assert game_state.game_task.cancelled()

    asyncio.run(scenario())


def run() -> None:
    tests = [
        test_manager_starts_and_cleans_up_jianzhong_game_state,
    ]
    for test in tests:
        test()
    print(f"jianzhong gamestate_manager tests ok: {len(tests)} tests")


if __name__ == "__main__":
    run()
