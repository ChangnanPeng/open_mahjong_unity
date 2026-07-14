from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace

SERVER_ROOT = Path(__file__).resolve().parents[3]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from server.gamestate.game_jiandan import JiandanGameState
from server.gamestate.gamestate_manager import GameStateManager
from server.room.room_manager import RoomManager
from server.room.room_router import handle_room_message
from server.server import GameServer


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_json(self, payload: dict) -> None:
        self.sent.append(payload)


class FakeDbManager:
    def get_user_settings(self, user_id: int) -> dict:
        return {
            "username": f"user-{user_id}",
            "title_id": 1,
            "profile_image_id": 1,
            "character_id": 1,
            "voice_id": 1,
        }


class FakeGameStateManager:
    def is_user_in_active_game(self, user_id: int) -> bool:
        return False


class FakeMatchManager:
    def is_user_committed(self, user_id: int) -> bool:
        return False

    def is_user_in_queue(self, user_id: int) -> bool:
        return False


def _server():
    websocket = FakeWebSocket()
    player = SimpleNamespace(
        user_id=101,
        username="host",
        current_room_id=None,
        websocket=websocket,
    )
    server = SimpleNamespace(
        players={"conn-101": player},
        user_id_to_connection={101: player},
        db_manager=FakeDbManager(),
        gamestate_manager=FakeGameStateManager(),
        match_manager=FakeMatchManager(),
    )
    server.room_manager = RoomManager(server)

    async def create_jiandan_room(*args, **kwargs):
        return await server.room_manager.create_Jiandan_room(*args, **kwargs)

    server.create_Jiandan_room = create_jiandan_room
    return server, websocket, player


def _add_player(server, user_id: int, connect_id: str):
    websocket = FakeWebSocket()
    player = SimpleNamespace(
        user_id=user_id,
        username=f"user-{user_id}",
        current_room_id=None,
        websocket=websocket,
    )
    server.players[connect_id] = player
    server.user_id_to_connection[user_id] = player
    return websocket, player


def _create_message() -> dict:
    return {
        "type": "room/create_Jiandan_room",
        "roomname": "jiandan smoke",
        "gameround": 1,
        "password": "",
        "roundTimerValue": 0,
        "stepTimerValue": 0,
        "tips": True,
        "random_seed": 0,
        "sub_rule": "jiandan/standard",
        "allow_spectator": True,
    }


async def _create_room(server):
    return await server.room_manager.create_Jiandan_room(
        "conn-101",
        "jiandan smoke",
        1,
        "",
        0,
        0,
        True,
        0,
    )


def test_room_manager_creates_fixed_first_win_room() -> None:
    async def scenario() -> None:
        server, websocket, player = _server()

        response = await _create_room(server)

        assert response.success is True
        assert response.type == "room/create_room_done"
        room = response.room_info
        assert room["room_rule"] == "jiandan"
        assert room["sub_rule"] == "jiandan/standard"
        assert room["hepai_limit"] == 0
        assert room["open_cuohe"] is False
        assert room["tips"] is True
        assert room["allow_spectator"] is True
        assert room["player_list"] == [101]
        assert room["is_player_set_random_seed"] is False
        assert player.current_room_id == room["room_id"]
        assert any(payload["type"] == "room/refresh_room_info" for payload in websocket.sent)
        for excluded in (
            "hand_end_mode",
            "winner_target",
            "hand_flow",
            "presentation_profile",
            "rule_composition",
        ):
            assert excluded not in room

    asyncio.run(scenario())


def test_room_router_does_not_accept_multi_stage_configuration() -> None:
    async def scenario() -> None:
        server, websocket, _player = _server()
        message = _create_message()
        message.update({
            "hand_end_mode": "third_win",
            "winner_target": 3,
            "presentation_profile": {"show_interim_result": True},
        })

        await handle_room_message(server, "conn-101", message, websocket)

        assert websocket.sent[-1]["success"] is True
        room = websocket.sent[-1]["room_info"]
        assert room["room_rule"] == "jiandan"
        assert "hand_end_mode" not in room
        assert "winner_target" not in room
        assert "presentation_profile" not in room

    asyncio.run(scenario())


def test_room_is_listed_syncable_and_joinable() -> None:
    async def scenario() -> None:
        server, _websocket, _player = _server()
        _add_player(server, 102, "conn-102")
        response = await _create_room(server)
        room_id = response.room_info["room_id"]

        room_list = server.room_manager.get_room_list()
        sync = await server.room_manager.sync_my_room("conn-101")
        joined = await server.room_manager.join_room("conn-102", room_id, "")

        assert any(room["room_id"] == room_id for room in room_list.room_list)
        assert sync.type == "room/refresh_room_info"
        assert sync.room_info["room_id"] == room_id
        assert joined.success is True
        assert server.room_manager.rooms[room_id]["player_list"] == [101, 102]
        assert server.players["conn-102"].current_room_id == room_id

    asyncio.run(scenario())


def test_game_server_wrapper_preserves_scoped_room_options() -> None:
    async def scenario() -> None:
        server = GameServer()
        server.db_manager = FakeDbManager()
        server.gamestate_manager = FakeGameStateManager()
        server.match_manager = FakeMatchManager()
        websocket = FakeWebSocket()
        player = SimpleNamespace(
            user_id=101,
            username="host",
            current_room_id=None,
            websocket=websocket,
        )
        server.players["conn-101"] = player
        server.user_id_to_connection[101] = player

        response = await server.create_Jiandan_room(
            "conn-101",
            "jiandan smoke",
            1,
            "",
            0,
            0,
            True,
            0,
            allow_spectator=False,
        )

        assert response.success is True
        assert response.room_info["room_rule"] == "jiandan"
        assert response.room_info["allow_spectator"] is False
        assert "hand_end_mode" not in response.room_info

    asyncio.run(scenario())


def test_room_can_start_dedicated_jiandan_state() -> None:
    async def scenario() -> None:
        server, _websocket, _player = _server()
        response = await _create_room(server)
        room = server.room_manager.rooms[response.room_info["room_id"]]
        room["player_list"] = [101, 1, 2, 3]
        room["player_settings"].update({
            1: {"user_id": 1, "username": "bot-1"},
            2: {"user_id": 2, "username": "bot-2"},
            3: {"user_id": 3, "username": "bot-3"},
        })
        server.calculation_service = None
        server.gamestate_manager = GameStateManager(server)

        start_response = await server.gamestate_manager.start_game("conn-101", room["room_id"])
        await asyncio.sleep(0.05)
        state = server.gamestate_manager.get_game_state_by_room_id(room["room_id"])

        assert start_response is None
        assert isinstance(state, JiandanGameState)
        assert state.room_rule == "jiandan"
        assert not hasattr(state, "winner_target")
        assert room["is_game_running"] is True

        await server.gamestate_manager.cleanup_game_state_complete(gamestate_id=state.gamestate_id)

    asyncio.run(scenario())


def test_host_requirement_is_shared_with_existing_room_flow() -> None:
    async def scenario() -> None:
        server, _websocket, _player = _server()
        _add_player(server, 102, "conn-102")
        response = await _create_room(server)
        room = server.room_manager.rooms[response.room_info["room_id"]]
        room["player_list"] = [101, 102, 1, 2]
        room["player_settings"].update({
            102: {"user_id": 102, "username": "player-102"},
            1: {"user_id": 1, "username": "bot-1"},
            2: {"user_id": 2, "username": "bot-2"},
        })
        room["ready_list"] = [102]
        server.players["conn-102"].current_room_id = room["room_id"]
        server.calculation_service = None
        server.gamestate_manager = GameStateManager(server)

        blocked = await server.gamestate_manager.start_game("conn-102", room["room_id"])

        assert blocked is not None
        assert blocked.success is False
        assert server.gamestate_manager.get_game_state_by_room_id(room["room_id"]) is None

    asyncio.run(scenario())


def run() -> None:
    tests = [
        test_room_manager_creates_fixed_first_win_room,
        test_room_router_does_not_accept_multi_stage_configuration,
        test_room_is_listed_syncable_and_joinable,
        test_game_server_wrapper_preserves_scoped_room_options,
        test_room_can_start_dedicated_jiandan_state,
        test_host_requirement_is_shared_with_existing_room_flow,
    ]
    for test in tests:
        test()
    print(f"jiandan room creation tests ok: {len(tests)} tests")


if __name__ == "__main__":
    run()
