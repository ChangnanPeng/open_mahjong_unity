from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace

SERVER_ROOT = Path(__file__).resolve().parents[3]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from server.room.room_manager import RoomManager
from server.room.room_router import handle_room_message
from server.server import GameServer
from server.gamestate.gamestate_manager import GameStateManager
from server.gamestate.gamestate_router import handle_gamestate_message
from server.gamestate.game_jianzhong import JianzhongGameState


class FakeWebSocket:
    def __init__(self):
        self.sent = []
        self.accepted = False

    async def accept(self) -> None:
        self.accepted = True

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
    server = SimpleNamespace()
    server.players = {"conn-101": player}
    server.user_id_to_connection = {101: player}
    server.db_manager = FakeDbManager()
    server.gamestate_manager = FakeGameStateManager()
    server.match_manager = FakeMatchManager()
    server.room_manager = RoomManager(server)

    async def create_Jianzhong_room(*args, **kwargs):
        return await server.room_manager.create_Jianzhong_room(*args, **kwargs)

    async def start_game(connect_id: str, room_id: str):
        response = await server.gamestate_manager.start_game(connect_id, room_id)
        if response:
            await server.players[connect_id].websocket.send_json(response.dict(exclude_none=True))

    server.create_Jianzhong_room = create_Jianzhong_room
    server.start_game = start_game
    return server, websocket, player


def _add_connected_player(server, user_id: int, connect_id: str):
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


async def _connect_real_session(server: GameServer, user_id: int, connect_id: str):
    websocket = FakeWebSocket()
    await server.connect(websocket, connect_id)
    server.store_player_session(connect_id, user_id, f"player-{user_id}")
    return websocket


def _real_game_server():
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
    return server, websocket, player


def _create_message() -> dict:
    return {
        "type": "room/create_Jianzhong_room",
        "roomname": "jianzhong smoke",
        "gameround": 1,
        "password": "",
        "roundTimerValue": 0,
        "stepTimerValue": 0,
        "tips": False,
        "random_seed": 0,
    }


async def _dispatch_server_message(server, connect_id: str, message: dict, websocket: FakeWebSocket) -> None:
    message_type = message.get("type", "")
    if message_type.startswith("room/"):
        await handle_room_message(server, connect_id, message, websocket)
    elif message_type.startswith("gamestate/"):
        await handle_gamestate_message(server, connect_id, message, websocket)
    else:
        raise AssertionError(f"unsupported smoke message type: {message_type}")


async def _started_room_with_responder():
    server, websocket, _player = _server()
    response_websocket, response_player = _add_connected_player(server, 102, "conn-102")
    response = await server.room_manager.create_Jianzhong_room(
        "conn-101",
        "jianzhong smoke",
        1,
        "",
        0,
        0,
        False,
        0,
    )
    room_info = server.room_manager.rooms[response.room_info["room_id"]]
    room_info["player_list"] = [101, 102, 1, 2]
    room_info["player_settings"].update({
        102: {"user_id": 102, "username": "responder"},
        1: {"user_id": 1, "username": "bot-1"},
        2: {"user_id": 2, "username": "bot-2"},
    })
    room_info["ready_list"] = [102]
    response_player.current_room_id = room_info["room_id"]
    server.calculation_service = None
    server.gamestate_manager = GameStateManager(server)

    start_response = await server.gamestate_manager.start_game("conn-101", room_info["room_id"])
    assert start_response is None, start_response
    await asyncio.sleep(0.05)

    game_state = server.gamestate_manager.get_game_state_by_room_id(room_info["room_id"])
    assert isinstance(game_state, JianzhongGameState)
    return server, websocket, response_websocket, game_state


async def _started_room_with_connected_players():
    server, host_websocket, _player = _server()
    websockets = {101: host_websocket}
    for user_id in (102, 103, 104):
        websocket, player = _add_connected_player(server, user_id, f"conn-{user_id}")
        websockets[user_id] = websocket
    response = await server.room_manager.create_Jianzhong_room(
        "conn-101",
        "jianzhong smoke",
        1,
        "",
        0,
        0,
        False,
        0,
    )
    room_info = server.room_manager.rooms[response.room_info["room_id"]]
    room_info["player_list"] = [101, 102, 103, 104]
    room_info["player_settings"].update({
        102: {"user_id": 102, "username": "player-102"},
        103: {"user_id": 103, "username": "player-103"},
        104: {"user_id": 104, "username": "player-104"},
    })
    room_info["ready_list"] = [102, 103, 104]
    for user_id in (102, 103, 104):
        server.user_id_to_connection[user_id].current_room_id = room_info["room_id"]
    server.calculation_service = None
    server.gamestate_manager = GameStateManager(server)

    start_response = await server.gamestate_manager.start_game("conn-101", room_info["room_id"])
    assert start_response is None, start_response
    await asyncio.sleep(0.05)

    game_state = server.gamestate_manager.get_game_state_by_room_id(room_info["room_id"])
    assert isinstance(game_state, JianzhongGameState)
    return server, websockets, game_state


async def _send_host_cut(server, websocket, game_state: JianzhongGameState, tile: int) -> None:
    await handle_gamestate_message(
        server,
        "conn-101",
        {
            "type": "gamestate/jianzhong/cut_tile",
            "gamestate_id": game_state.gamestate_id,
            "TileId": tile,
            "cutIndex": 0,
            "cutClass": False,
        },
        websocket,
    )


async def _wait_for_status(game_state: JianzhongGameState, status: str, player_index: int | None = None) -> None:
    for _ in range(20):
        if game_state.game_status == status and (player_index is None or game_state.current_player_index == player_index):
            return
        await asyncio.sleep(0.05)
    raise AssertionError((game_state.game_status, game_state.current_player_index, game_state.waiting_players_list))


async def _wait_for_condition(condition, detail) -> None:
    for _ in range(20):
        if condition():
            return
        await asyncio.sleep(0.05)
    raise AssertionError(detail())


def _force_final_configured_round(game_state: JianzhongGameState) -> None:
    game_state.current_round = game_state.max_round * 4
    game_state.round_index = game_state.current_round


def test_room_manager_creates_public_jianzhong_room() -> None:
    async def scenario() -> None:
        server, websocket, player = _server()

        response = await server.room_manager.create_Jianzhong_room(
            "conn-101",
            "jianzhong smoke",
            1,
            "",
            0,
            0,
            False,
            0,
        )

        assert response.success is True
        assert response.type == "room/create_room_done"
        room_info = server.room_manager.rooms[response.room_info["room_id"]]
        assert room_info["room_rule"] == "jianzhong"
        assert room_info["sub_rule"] == "jianzhong/standard"
        assert room_info["hepai_limit"] == 0
        assert room_info["open_cuohe"] is False
        assert room_info["hidden_room"] is False
        assert room_info["allow_spectator"] is True
        assert room_info["max_player"] == 4
        assert room_info["player_list"] == [101]
        assert room_info["random_seed"] == 0
        assert room_info["hand_end_mode"] == "third_win"
        assert room_info["is_player_set_random_seed"] is False
        assert player.current_room_id == room_info["room_id"]
        assert room_info["room_id"] in server.room_manager.rooms
        assert any(payload["type"] == "room/refresh_room_info" for payload in websocket.sent)

    asyncio.run(scenario())


def test_room_router_persists_second_winner_flow_option() -> None:
    async def scenario() -> None:
        server, websocket, _player = _server()
        message = _create_message()
        message["hand_end_mode"] = "second_win"

        await handle_room_message(server, "conn-101", message, websocket)

        assert websocket.sent[-1]["success"] is True
        room_id = websocket.sent[-1]["room_info"]["room_id"]
        room_info = server.room_manager.rooms[room_id]
        assert room_info["hand_end_mode"] == "second_win"

        game = JianzhongGameState(room_data={
            **room_info,
            "player_list": [101, 102, 103, 104],
        })
        assert game.winner_target == 2

    asyncio.run(scenario())


def test_jianzhong_room_is_listed_and_syncable() -> None:
    async def scenario() -> None:
        server, _websocket, _player = _server()

        response = await server.room_manager.create_Jianzhong_room(
            "conn-101",
            "jianzhong smoke",
            1,
            "",
            0,
            0,
            False,
            0,
        )

        assert response.success is True
        room_id = response.room_info["room_id"]
        room_list_response = server.room_manager.get_room_list()
        assert room_list_response.success is True
        assert any(room["room_id"] == room_id for room in room_list_response.room_list)

        sync_response = await server.room_manager.sync_my_room("conn-101")
        assert sync_response.success is True
        assert sync_response.type == "room/refresh_room_info"
        assert sync_response.room_info["room_id"] == room_id
        assert sync_response.room_info["hidden_room"] is False

    asyncio.run(scenario())


def test_jianzhong_room_allows_join_by_room_id() -> None:
    async def scenario() -> None:
        server, _websocket, _player = _server()
        _add_connected_player(server, 102, "conn-102")

        response = await server.room_manager.create_Jianzhong_room(
            "conn-101",
            "jianzhong smoke",
            1,
            "",
            0,
            0,
            False,
            0,
        )

        assert response.success is True
        room_id = response.room_info["room_id"]
        join_response = await server.room_manager.join_room("conn-102", room_id, "")

        assert join_response.success is True
        assert join_response.type == "room/join_room_done"
        room_info = server.room_manager.rooms[room_id]
        assert room_info["hidden_room"] is False
        assert room_info["player_list"] == [101, 102]
        assert server.players["conn-102"].current_room_id == room_id

    asyncio.run(scenario())


def test_jianzhong_room_start_requires_host() -> None:
    async def scenario() -> None:
        server, _websocket, _player = _server()
        _add_connected_player(server, 102, "conn-102")

        response = await server.room_manager.create_Jianzhong_room(
            "conn-101",
            "jianzhong smoke",
            1,
            "",
            0,
            0,
            False,
            0,
        )

        assert response.success is True
        room_id = response.room_info["room_id"]
        room_info = server.room_manager.rooms[room_id]
        room_info["player_list"] = [101, 102, 1, 2]
        room_info["player_settings"].update({
            102: {"user_id": 102, "username": "player-102"},
            1: {"user_id": 1, "username": "bot-1"},
            2: {"user_id": 2, "username": "bot-2"},
        })
        room_info["ready_list"] = [102]
        server.players["conn-102"].current_room_id = room_id
        server.calculation_service = None
        server.gamestate_manager = GameStateManager(server)

        blocked_response = await server.gamestate_manager.start_game("conn-102", room_id)
        assert blocked_response is not None
        assert blocked_response.success is False
        assert room_info.get("is_game_running", False) is False
        assert server.gamestate_manager.get_game_state_by_room_id(room_id) is None

        start_response = await server.gamestate_manager.start_game("conn-101", room_id)
        assert start_response is None, start_response
        await asyncio.sleep(0.05)
        game_state = server.gamestate_manager.get_game_state_by_room_id(room_id)
        assert isinstance(game_state, JianzhongGameState)

        await server.gamestate_manager.cleanup_game_state_complete(gamestate_id=game_state.gamestate_id)

    asyncio.run(scenario())


def test_jianzhong_room_rejects_non_member_ready_and_non_host_kick() -> None:
    async def scenario() -> None:
        server, _websocket, _player = _server()
        _add_connected_player(server, 102, "conn-102")

        response = await server.room_manager.create_Jianzhong_room(
            "conn-101",
            "jianzhong smoke",
            1,
            "",
            0,
            0,
            False,
            0,
        )

        assert response.success is True
        room_id = response.room_info["room_id"]
        room_info = server.room_manager.rooms[room_id]

        ready_response = await server.room_manager.set_player_ready("conn-102", room_id, True)
        assert ready_response is not None
        assert ready_response.success is False
        assert room_info.get("ready_list", []) == []

        kick_response = await server.room_manager.kick_player_from_room("conn-102", room_id, 101)
        assert kick_response.success is False
        assert room_info["player_list"] == [101]
        assert server.players["conn-101"].current_room_id == room_id

    asyncio.run(scenario())


def test_room_manager_preserves_jianzhong_spectator_setting() -> None:
    async def scenario() -> None:
        server, _websocket, _player = _server()

        response = await server.room_manager.create_Jianzhong_room(
            "conn-101",
            "jianzhong smoke",
            1,
            "",
            0,
            0,
            False,
            0,
            allow_spectator=True,
        )

        assert response.success is True
        room_info = server.room_manager.rooms[response.room_info["room_id"]]
        assert room_info["allow_spectator"] is True
        assert response.room_info["allow_spectator"] is True

    asyncio.run(scenario())


def test_game_server_jianzhong_create_wrapper_preserves_spectator_setting() -> None:
    async def scenario() -> None:
        server, _websocket, _player = _real_game_server()

        response = await server.create_Jianzhong_room(
            "conn-101",
            "jianzhong smoke",
            1,
            "",
            0,
            0,
            False,
            0,
            allow_spectator=True,
        )

        assert response.success is True
        room_info = server.room_manager.rooms[response.room_info["room_id"]]
        assert room_info["room_rule"] == "jianzhong"
        assert room_info["hepai_limit"] == 0
        assert room_info["open_cuohe"] is False
        assert room_info["allow_spectator"] is True
        assert response.room_info["allow_spectator"] is True

    asyncio.run(scenario())


def test_jianzhong_smoke_uses_game_server_connection_session() -> None:
    async def scenario() -> None:
        server = GameServer()
        server.db_manager = FakeDbManager()
        server.match_manager = FakeMatchManager()
        server.calculation_service = None
        websocket = FakeWebSocket()

        await server.connect(websocket, "conn-101")
        server.store_player_session("conn-101", 101, "host")
        assert websocket.accepted is True
        assert server.players["conn-101"].user_id == 101
        assert server.user_id_to_connection[101] is server.players["conn-101"]

        await _dispatch_server_message(server, "conn-101", _create_message(), websocket)
        assert websocket.sent[-1]["type"] == "room/create_room_done"
        room_id = websocket.sent[-1]["room_info"]["room_id"]
        room_info = server.room_manager.rooms[room_id]
        room_info["player_list"] = [101, 1, 2, 3]
        room_info["player_settings"].update({
            1: {"user_id": 1, "username": "bot-1"},
            2: {"user_id": 2, "username": "bot-2"},
            3: {"user_id": 3, "username": "bot-3"},
        })

        await _dispatch_server_message(
            server,
            "conn-101",
            {"type": "room/start_game", "room_id": room_id},
            websocket,
        )
        await asyncio.sleep(0.05)

        game_state = server.gamestate_manager.get_game_state_by_room_id(room_id)
        assert isinstance(game_state, JianzhongGameState)
        assert room_info["is_game_running"] is True
        assert server.players["conn-101"].current_room_id == room_id

        cut_tile = game_state.player_list[0].hand_tiles[0]
        await _dispatch_server_message(
            server,
            "conn-101",
            {
                "type": "gamestate/jianzhong/cut_tile",
                "gamestate_id": game_state.gamestate_id,
                "TileId": cut_tile,
                "cutIndex": 0,
                "cutClass": False,
            },
            websocket,
        )
        await _wait_for_condition(
            lambda: cut_tile in game_state.player_list[0].discard_tiles,
            lambda: (game_state.game_status, game_state.player_list[0].discard_tiles),
        )

        await server.gamestate_manager.cleanup_game_state_complete(gamestate_id=game_state.gamestate_id)
        assert game_state.game_task.cancelled()

    asyncio.run(scenario())


def test_jianzhong_smoke_uses_four_game_server_connection_sessions() -> None:
    async def scenario() -> None:
        server = GameServer()
        server.db_manager = FakeDbManager()
        server.match_manager = FakeMatchManager()
        server.calculation_service = None
        websockets = {}
        for user_id in (101, 102, 103, 104):
            connect_id = f"conn-{user_id}"
            websockets[user_id] = await _connect_real_session(server, user_id, connect_id)

        await _dispatch_server_message(server, "conn-101", _create_message(), websockets[101])
        room_id = websockets[101].sent[-1]["room_info"]["room_id"]
        room_info = server.room_manager.rooms[room_id]
        room_info["player_list"] = [101, 102, 103, 104]
        room_info["player_settings"].update({
            102: {"user_id": 102, "username": "player-102"},
            103: {"user_id": 103, "username": "player-103"},
            104: {"user_id": 104, "username": "player-104"},
        })
        room_info["ready_list"] = [102, 103, 104]
        for user_id in (102, 103, 104):
            server.user_id_to_connection[user_id].current_room_id = room_id

        await _dispatch_server_message(
            server,
            "conn-101",
            {"type": "room/start_game", "room_id": room_id},
            websockets[101],
        )
        await asyncio.sleep(0.05)

        game_state = server.gamestate_manager.get_game_state_by_room_id(room_id)
        assert isinstance(game_state, JianzhongGameState)
        current_user_id = game_state.player_list[game_state.current_player_index].user_id
        await _wait_for_condition(
            lambda: any(
                payload["type"] == "gamestate/jianzhong/broadcast_hand_action"
                and payload.get("player_index") == game_state.current_player_index
                for payload in websockets[current_user_id].sent
            ),
            lambda: websockets[current_user_id].sent,
        )

        cutter_index = game_state.current_player_index
        cut_tile = game_state.player_list[cutter_index].hand_tiles[0]
        await _dispatch_server_message(
            server,
            f"conn-{current_user_id}",
            {
                "type": "gamestate/jianzhong/cut_tile",
                "gamestate_id": game_state.gamestate_id,
                "TileId": cut_tile,
                "cutIndex": 0,
                "cutClass": False,
            },
            websockets[current_user_id],
        )
        await _wait_for_condition(
            lambda: cut_tile in game_state.player_list[cutter_index].discard_tiles,
            lambda: (game_state.game_status, game_state.player_list[cutter_index].discard_tiles),
        )

        assert all(websocket.accepted for websocket in websockets.values())
        assert all(server.user_id_to_connection[user_id].current_room_id == room_id for user_id in (101, 102, 103, 104))

        await server.gamestate_manager.cleanup_game_state_complete(gamestate_id=game_state.gamestate_id)
        assert game_state.game_task.cancelled()

    asyncio.run(scenario())


def test_room_router_handles_jianzhong_create_message() -> None:
    async def scenario() -> None:
        server, websocket, player = _server()

        message = _create_message()
        message["allow_spectator"] = True
        await handle_room_message(server, "conn-101", message, websocket)

        assert websocket.sent[-1]["type"] == "room/create_room_done"
        assert websocket.sent[-1]["success"] is True
        room_info = websocket.sent[-1]["room_info"]
        assert room_info["room_rule"] == "jianzhong"
        assert room_info["open_cuohe"] is False
        assert room_info["allow_spectator"] is True
        assert player.current_room_id == room_info["room_id"]

    asyncio.run(scenario())


def test_jianzhong_protocol_dispatch_create_start_cut_smoke() -> None:
    async def scenario() -> None:
        server, websocket, player = _server()

        await _dispatch_server_message(server, "conn-101", _create_message(), websocket)
        assert websocket.sent[-1]["type"] == "room/create_room_done"
        assert websocket.sent[-1]["success"] is True

        room_id = websocket.sent[-1]["room_info"]["room_id"]
        room_info = server.room_manager.rooms[room_id]
        room_info["player_list"] = [101, 1, 2, 3]
        room_info["player_settings"].update({
            1: {"user_id": 1, "username": "bot-1"},
            2: {"user_id": 2, "username": "bot-2"},
            3: {"user_id": 3, "username": "bot-3"},
        })
        server.calculation_service = None
        server.gamestate_manager = GameStateManager(server)

        await _dispatch_server_message(
            server,
            "conn-101",
            {"type": "room/start_game", "room_id": room_id},
            websocket,
        )
        await asyncio.sleep(0.05)

        game_state = server.gamestate_manager.get_game_state_by_room_id(room_id)
        assert isinstance(game_state, JianzhongGameState)
        assert room_info["is_game_running"] is True
        assert player.current_room_id == room_id
        assert game_state.waiting_players_list == [0]

        cut_tile = game_state.player_list[0].hand_tiles[0]
        await _dispatch_server_message(
            server,
            "conn-101",
            {
                "type": "gamestate/jianzhong/cut_tile",
                "gamestate_id": game_state.gamestate_id,
                "TileId": cut_tile,
                "cutIndex": 0,
                "cutClass": False,
            },
            websocket,
        )
        await _wait_for_condition(
            lambda: cut_tile in game_state.player_list[0].discard_tiles,
            lambda: (game_state.game_status, game_state.player_list[0].discard_tiles),
        )
        assert cut_tile in game_state.player_list[0].discard_tiles

        await server.gamestate_manager.cleanup_game_state_complete(gamestate_id=game_state.gamestate_id)
        assert game_state.game_task.cancelled()

    asyncio.run(scenario())


def test_jianzhong_room_can_start_game_state() -> None:
    async def scenario() -> None:
        server, websocket, player = _server()
        response = await server.room_manager.create_Jianzhong_room(
            "conn-101",
            "jianzhong smoke",
            1,
            "",
            0,
            0,
            False,
            0,
        )
        room_info = server.room_manager.rooms[response.room_info["room_id"]]
        room_info["player_list"] = [101, 1, 2, 3]
        room_info["player_settings"].update({
            1: {"user_id": 1, "username": "bot-1"},
            2: {"user_id": 2, "username": "bot-2"},
            3: {"user_id": 3, "username": "bot-3"},
        })
        server.calculation_service = None
        server.gamestate_manager = GameStateManager(server)

        start_response = await server.gamestate_manager.start_game("conn-101", room_info["room_id"])
        await asyncio.sleep(0.05)

        assert start_response is None, start_response
        assert room_info["is_game_running"] is True
        game_state = server.gamestate_manager.get_game_state_by_room_id(room_info["room_id"])
        assert isinstance(game_state, JianzhongGameState)
        assert game_state.room_rule == "jianzhong"
        assert game_state.game_task is not None
        assert game_state.outbound_payloads
        await _wait_for_condition(
            lambda: any(
                payload["type"] == "gamestate/jianzhong/broadcast_hand_action"
                and payload.get("player_index") == game_state.current_player_index
                for payload in websocket.sent
            ),
            lambda: websocket.sent,
        )

        await server.gamestate_manager.cleanup_game_state_complete(gamestate_id=game_state.gamestate_id)
        assert server.gamestate_manager.get_game_state_by_room_id(room_info["room_id"]) is None
        assert game_state.game_task.cancelled()
        assert any(payload["type"] == "room/refresh_room_info" for payload in websocket.sent)
        assert player.current_room_id == room_info["room_id"]

    asyncio.run(scenario())


def test_jianzhong_room_accepts_first_cut_message() -> None:
    async def scenario() -> None:
        server, websocket, _player = _server()
        response = await server.room_manager.create_Jianzhong_room(
            "conn-101",
            "jianzhong smoke",
            1,
            "",
            0,
            0,
            False,
            0,
        )
        room_info = server.room_manager.rooms[response.room_info["room_id"]]
        room_info["player_list"] = [101, 1, 2, 3]
        room_info["player_settings"].update({
            1: {"user_id": 1, "username": "bot-1"},
            2: {"user_id": 2, "username": "bot-2"},
            3: {"user_id": 3, "username": "bot-3"},
        })
        server.calculation_service = None
        server.gamestate_manager = GameStateManager(server)

        start_response = await server.gamestate_manager.start_game("conn-101", room_info["room_id"])
        assert start_response is None, start_response
        await asyncio.sleep(0.05)

        game_state = server.gamestate_manager.get_game_state_by_room_id(room_info["room_id"])
        assert isinstance(game_state, JianzhongGameState)
        assert game_state.waiting_players_list == [0]
        cut_tile = game_state.player_list[0].hand_tiles[0]

        await handle_gamestate_message(
            server,
            "conn-101",
            {
                "type": "gamestate/jianzhong/cut_tile",
                "gamestate_id": game_state.gamestate_id,
                "TileId": cut_tile,
                "cutIndex": 0,
                "cutClass": False,
            },
            websocket,
        )

        for _ in range(20):
            if cut_tile in game_state.player_list[0].discard_tiles:
                break
            await asyncio.sleep(0.05)

        assert cut_tile in game_state.player_list[0].discard_tiles

        await server.gamestate_manager.cleanup_game_state_complete(gamestate_id=game_state.gamestate_id)
        assert game_state.game_task.cancelled()

    asyncio.run(scenario())


def test_jianzhong_room_accepts_discard_win_response_message() -> None:
    async def scenario() -> None:
        server, websocket, _player = _server()
        response_websocket, response_player = _add_connected_player(server, 102, "conn-102")
        response = await server.room_manager.create_Jianzhong_room(
            "conn-101",
            "jianzhong smoke",
            1,
            "",
            0,
            0,
            False,
            0,
        )
        room_info = server.room_manager.rooms[response.room_info["room_id"]]
        room_info["player_list"] = [101, 102, 1, 2]
        room_info["player_settings"].update({
            102: {"user_id": 102, "username": "responder"},
            1: {"user_id": 1, "username": "bot-1"},
            2: {"user_id": 2, "username": "bot-2"},
        })
        room_info["ready_list"] = [102]
        response_player.current_room_id = room_info["room_id"]
        server.calculation_service = None
        server.gamestate_manager = GameStateManager(server)

        start_response = await server.gamestate_manager.start_game("conn-101", room_info["room_id"])
        assert start_response is None, start_response
        await asyncio.sleep(0.05)

        game_state = server.gamestate_manager.get_game_state_by_room_id(room_info["room_id"])
        assert isinstance(game_state, JianzhongGameState)

        # 0-point legal wait: exposed 222m plus 345m/456p/678s and a single east,
        # waiting on east for the pair. This exercises a legal hu with no fan.
        game_state.player_list[0].hand_tiles = [41]
        game_state.player_list[1].hand_tiles = [13, 14, 15, 24, 25, 26, 36, 37, 38, 41]
        game_state.player_list[1].combination_tiles = ["k12"]

        await handle_gamestate_message(
            server,
            "conn-101",
            {
                "type": "gamestate/jianzhong/cut_tile",
                "gamestate_id": game_state.gamestate_id,
                "TileId": 41,
                "cutIndex": 0,
                "cutClass": False,
            },
            websocket,
        )

        for _ in range(20):
            if game_state.game_status == "waiting_action_after_cut" and 1 in game_state.waiting_players_list:
                break
            await asyncio.sleep(0.05)

        assert game_state.game_status == "waiting_action_after_cut"
        assert 1 in game_state.waiting_players_list
        assert "hu" in game_state.action_dict[1]
        action_tick = game_state.server_action_tick

        await handle_gamestate_message(
            server,
            "conn-102",
            {
                "type": "gamestate/jianzhong/send_action",
                "gamestate_id": game_state.gamestate_id,
                "action": "hu",
                "action_tick": action_tick,
            },
            response_websocket,
        )

        for _ in range(20):
            if game_state.player_list[1].is_hu:
                break
            await asyncio.sleep(0.05)

        assert game_state.player_list[1].is_hu
        settlement = game_state.deferred_hu_settlements[0]
        assert settlement["source"] == "discard"
        assert settlement["discarder"] == 0
        assert settlement["tile"] == 41
        assert settlement["winner"] == 1
        assert settlement["hu_order"] == 1
        assert settlement["is_win"] is True
        assert settlement["points"] == 0
        assert settlement["raw_points"] == 0
        assert settlement["fan_ids"] == []
        assert settlement["fan_names"] == []

        await server.gamestate_manager.cleanup_game_state_complete(gamestate_id=game_state.gamestate_id)
        assert game_state.game_task.cancelled()

    asyncio.run(scenario())


def test_jianzhong_room_accepts_discard_pass_response_message() -> None:
    async def scenario() -> None:
        server, websocket, _player = _server()
        response_websocket, response_player = _add_connected_player(server, 102, "conn-102")
        response = await server.room_manager.create_Jianzhong_room(
            "conn-101",
            "jianzhong smoke",
            1,
            "",
            0,
            0,
            False,
            0,
        )
        room_info = server.room_manager.rooms[response.room_info["room_id"]]
        room_info["player_list"] = [101, 102, 1, 2]
        room_info["player_settings"].update({
            102: {"user_id": 102, "username": "responder"},
            1: {"user_id": 1, "username": "bot-1"},
            2: {"user_id": 2, "username": "bot-2"},
        })
        room_info["ready_list"] = [102]
        response_player.current_room_id = room_info["room_id"]
        server.calculation_service = None
        server.gamestate_manager = GameStateManager(server)

        start_response = await server.gamestate_manager.start_game("conn-101", room_info["room_id"])
        assert start_response is None, start_response
        await asyncio.sleep(0.05)

        game_state = server.gamestate_manager.get_game_state_by_room_id(room_info["room_id"])
        assert isinstance(game_state, JianzhongGameState)
        game_state.tiles_list = [33, 34]
        game_state.player_list[0].hand_tiles = [41]
        game_state.player_list[1].hand_tiles = [13, 14, 15, 24, 25, 26, 36, 37, 38, 41]
        game_state.player_list[1].combination_tiles = ["k12"]

        await handle_gamestate_message(
            server,
            "conn-101",
            {
                "type": "gamestate/jianzhong/cut_tile",
                "gamestate_id": game_state.gamestate_id,
                "TileId": 41,
                "cutIndex": 0,
                "cutClass": False,
            },
            websocket,
        )

        for _ in range(20):
            if game_state.game_status == "waiting_action_after_cut" and 1 in game_state.waiting_players_list:
                break
            await asyncio.sleep(0.05)

        assert "hu" in game_state.action_dict[1]
        action_tick = game_state.server_action_tick

        await handle_gamestate_message(
            server,
            "conn-102",
            {
                "type": "gamestate/jianzhong/send_action",
                "gamestate_id": game_state.gamestate_id,
                "action": "pass",
                "action_tick": action_tick,
            },
            response_websocket,
        )

        for _ in range(20):
            if game_state.game_status == "waiting_hand_action" and game_state.current_player_index == 1:
                break
            await asyncio.sleep(0.05)

        assert not game_state.player_list[1].is_hu
        assert game_state.player_list[1].discard_win_lockout_tiles == {41}
        assert game_state.current_player_index == 1
        assert game_state.player_list[1].hand_tiles[-1] == 33

        await server.gamestate_manager.cleanup_game_state_complete(gamestate_id=game_state.gamestate_id)
        assert game_state.game_task.cancelled()

    asyncio.run(scenario())


def test_jianzhong_room_accepts_peng_claim_response_message() -> None:
    async def scenario() -> None:
        server, websocket, response_websocket, game_state = await _started_room_with_responder()
        game_state.tiles_list = [33, 34]
        game_state.player_list[0].hand_tiles = [15]
        game_state.player_list[1].hand_tiles = [15, 15, 31]
        game_state.player_list[1].combination_tiles = []

        await _send_host_cut(server, websocket, game_state, 15)
        await _wait_for_status(game_state, "waiting_action_after_cut")

        assert 1 in game_state.waiting_players_list
        assert "peng" in game_state.action_dict[1]
        action_tick = game_state.server_action_tick

        await handle_gamestate_message(
            server,
            "conn-102",
            {
                "type": "gamestate/jianzhong/send_action",
                "gamestate_id": game_state.gamestate_id,
                "action": "peng",
                "action_tick": action_tick,
            },
            response_websocket,
        )

        await _wait_for_status(game_state, "onlycut_after_action", 1)

        assert game_state.player_list[1].combination_tiles == ["k15"]
        assert game_state.player_list[1].hand_tiles == [31]
        assert game_state.action_dict[1] == ["cut"]

        await server.gamestate_manager.cleanup_game_state_complete(gamestate_id=game_state.gamestate_id)
        assert game_state.game_task.cancelled()

    asyncio.run(scenario())


def test_jianzhong_room_accepts_chi_claim_response_message() -> None:
    async def scenario() -> None:
        server, websocket, response_websocket, game_state = await _started_room_with_responder()
        game_state.tiles_list = [33, 34]
        game_state.player_list[0].hand_tiles = [12]
        game_state.player_list[1].hand_tiles = [13, 14, 31]
        game_state.player_list[1].combination_tiles = []

        await _send_host_cut(server, websocket, game_state, 12)
        await _wait_for_status(game_state, "waiting_action_after_cut")

        assert 1 in game_state.waiting_players_list
        assert "chi_right" in game_state.action_dict[1]
        action_tick = game_state.server_action_tick

        await handle_gamestate_message(
            server,
            "conn-102",
            {
                "type": "gamestate/jianzhong/send_action",
                "gamestate_id": game_state.gamestate_id,
                "action": "chi_right",
                "action_tick": action_tick,
            },
            response_websocket,
        )

        await _wait_for_status(game_state, "onlycut_after_action", 1)

        assert game_state.player_list[1].combination_tiles == ["s12"]
        assert game_state.player_list[1].hand_tiles == [31]
        assert game_state.action_dict[1] == ["cut"]

        await server.gamestate_manager.cleanup_game_state_complete(gamestate_id=game_state.gamestate_id)
        assert game_state.game_task.cancelled()

    asyncio.run(scenario())


def test_jianzhong_room_accepts_gang_claim_response_message() -> None:
    async def scenario() -> None:
        server, websocket, response_websocket, game_state = await _started_room_with_responder()
        game_state.tiles_list = [33, 34]
        game_state.player_list[0].hand_tiles = [15]
        game_state.player_list[1].hand_tiles = [15, 15, 15, 31]
        game_state.player_list[1].combination_tiles = []

        await _send_host_cut(server, websocket, game_state, 15)
        await _wait_for_status(game_state, "waiting_action_after_cut")

        assert 1 in game_state.waiting_players_list
        assert "gang" in game_state.action_dict[1]
        action_tick = game_state.server_action_tick

        await handle_gamestate_message(
            server,
            "conn-102",
            {
                "type": "gamestate/jianzhong/send_action",
                "gamestate_id": game_state.gamestate_id,
                "action": "gang",
                "action_tick": action_tick,
            },
            response_websocket,
        )

        await _wait_for_status(game_state, "waiting_hand_action", 1)

        assert game_state.player_list[1].combination_tiles == ["g15"]
        assert game_state.player_list[1].hand_tiles == [31, 33]
        assert "cut" in game_state.action_dict[1]

        await server.gamestate_manager.cleanup_game_state_complete(gamestate_id=game_state.gamestate_id)
        assert game_state.game_task.cancelled()

    asyncio.run(scenario())


def test_jianzhong_room_accepts_concealed_kong_hand_action_message() -> None:
    async def scenario() -> None:
        server, websocket, _response_websocket, game_state = await _started_room_with_responder()
        game_state.game_task.cancel()
        await asyncio.sleep(0)
        game_state.tiles_list = [33, 34]
        game_state.player_list[0].hand_tiles = [15, 15, 15, 15, 41]
        game_state.player_list[0].combination_tiles = []
        game_state.open_action_window(game_state.begin_hand_action(0))

        assert "angang" in game_state.action_dict[0]
        action_tick = game_state.server_action_tick
        resolve_task = asyncio.create_task(game_state.resolve_action_window(timeout=1.0))
        await asyncio.sleep(0)

        await handle_gamestate_message(
            server,
            "conn-101",
            {
                "type": "gamestate/jianzhong/send_action",
                "gamestate_id": game_state.gamestate_id,
                "action": "angang",
                "targetTile": 15,
                "action_tick": action_tick,
            },
            websocket,
        )

        await resolve_task

        assert game_state.player_list[0].combination_tiles == ["G15"]
        assert game_state.player_list[0].hand_tiles == [41, 33]
        assert "cut" in game_state.action_dict[0]

        await server.gamestate_manager.cleanup_game_state_complete(gamestate_id=game_state.gamestate_id)
        assert game_state.game_task.cancelled()

    asyncio.run(scenario())


def test_jianzhong_room_accepts_added_kong_pass_response_messages() -> None:
    async def scenario() -> None:
        server, websocket, response_websocket, game_state = await _started_room_with_responder()
        game_state.game_task.cancel()
        await asyncio.sleep(0)
        game_state.tiles_list = [33, 34]
        game_state.player_list[0].hand_tiles = [15, 41]
        game_state.player_list[0].combination_tiles = ["k15"]
        game_state.player_list[1].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 45, 45, 45, 15]
        game_state.open_action_window(game_state.begin_hand_action(0))

        assert "jiagang" in game_state.action_dict[0]
        action_tick = game_state.server_action_tick
        resolve_task = asyncio.create_task(game_state.resolve_action_window(timeout=1.0))
        await asyncio.sleep(0)

        await handle_gamestate_message(
            server,
            "conn-101",
            {
                "type": "gamestate/jianzhong/send_action",
                "gamestate_id": game_state.gamestate_id,
                "action": "jiagang",
                "targetTile": 15,
                "action_tick": action_tick,
            },
            websocket,
        )

        await resolve_task

        assert 1 in game_state.waiting_players_list
        assert "hu" in game_state.action_dict[1]
        action_tick = game_state.server_action_tick
        resolve_task = asyncio.create_task(game_state.resolve_action_window(timeout=1.0))
        await asyncio.sleep(0)

        await handle_gamestate_message(
            server,
            "conn-102",
            {
                "type": "gamestate/jianzhong/send_action",
                "gamestate_id": game_state.gamestate_id,
                "action": "pass",
                "action_tick": action_tick,
            },
            response_websocket,
        )

        await resolve_task

        assert game_state.player_list[0].combination_tiles == ["g15"]
        assert game_state.player_list[0].hand_tiles == [41, 33]
        assert "cut" in game_state.action_dict[0]

        await server.gamestate_manager.cleanup_game_state_complete(gamestate_id=game_state.gamestate_id)
        assert game_state.game_task.cancelled()

    asyncio.run(scenario())


def test_jianzhong_room_accepts_robbing_kong_win_response_message() -> None:
    async def scenario() -> None:
        server, websocket, response_websocket, game_state = await _started_room_with_responder()
        game_state.game_task.cancel()
        await asyncio.sleep(0)
        game_state.tiles_list = [33, 34]
        game_state.player_list[0].hand_tiles = [15, 41]
        game_state.player_list[0].combination_tiles = ["k15"]
        game_state.player_list[1].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 45, 45, 45, 15]
        game_state.open_action_window(game_state.begin_hand_action(0))

        assert "jiagang" in game_state.action_dict[0]
        action_tick = game_state.server_action_tick
        resolve_task = asyncio.create_task(game_state.resolve_action_window(timeout=1.0))
        await asyncio.sleep(0)

        await handle_gamestate_message(
            server,
            "conn-101",
            {
                "type": "gamestate/jianzhong/send_action",
                "gamestate_id": game_state.gamestate_id,
                "action": "jiagang",
                "targetTile": 15,
                "action_tick": action_tick,
            },
            websocket,
        )

        await resolve_task

        assert 1 in game_state.waiting_players_list
        assert "hu" in game_state.action_dict[1]
        action_tick = game_state.server_action_tick
        resolve_task = asyncio.create_task(game_state.resolve_action_window(timeout=1.0))
        await asyncio.sleep(0)

        await handle_gamestate_message(
            server,
            "conn-102",
            {
                "type": "gamestate/jianzhong/send_action",
                "gamestate_id": game_state.gamestate_id,
                "action": "hu",
                "action_tick": action_tick,
            },
            response_websocket,
        )

        await resolve_task

        assert game_state.player_list[1].is_hu
        assert game_state.player_list[0].combination_tiles == ["k15"]
        assert game_state.player_list[0].hand_tiles == [41]
        settlement = game_state.deferred_hu_settlements[0]
        assert settlement["source"] == "rob_kong"
        assert settlement["kong_player"] == 0
        assert settlement["tile"] == 15
        assert settlement["winner"] == 1
        assert settlement["hu_order"] == 1
        assert settlement["is_win"] is True
        assert "chankan" in settlement["fan_ids"]

        await server.gamestate_manager.cleanup_game_state_complete(gamestate_id=game_state.gamestate_id)
        assert game_state.game_task.cancelled()

    asyncio.run(scenario())


def test_jianzhong_room_emits_final_settlement_reveal_payloads() -> None:
    async def scenario() -> None:
        server, _websocket, _response_websocket, game_state = await _started_room_with_responder()
        game_state.game_task.cancel()
        await asyncio.sleep(0)
        game_state.player_list[0].hand_tiles = [11, 12, 13]
        game_state.player_list[0].combination_tiles = ["G15"]
        game_state.deferred_hu_settlements = [
            {
                "source": "rob_kong",
                "kong_player": 0,
                "tile": 15,
                "winner": 1,
                "hu_order": 1,
                "points": 8,
                "fan_ids": ["qiang_gang"],
                "fan_names": ["鎶㈡潬"],
            }
        ]
        game_state.ended_by = "win"

        game_state.open_action_window(game_state._end_window())

        final_payloads = [
            payload
            for payload in game_state.outbound_payloads
            if payload.get("type") == "gamestate/jianzhong/show_result"
            and payload.get("show_result_info", {}).get("defer_score_settlement") is not True
        ]
        assert len(final_payloads) == 4
        viewer_one_payload = next(payload for payload in final_payloads if payload["player_index"] == 1)
        player_zero = viewer_one_payload["game_info"]["players_info"][0]
        assert player_zero["hand_tiles"] == [11, 12, 13]
        assert player_zero["combination_tiles"] == ["G15"]
        assert viewer_one_payload["show_result_info"]["hepai_player_index"] == 1
        assert viewer_one_payload["show_result_info"]["hu_score"] == 8

        await server.gamestate_manager.cleanup_game_state_complete(gamestate_id=game_state.gamestate_id)
        assert game_state.game_task.cancelled()

    asyncio.run(scenario())


def test_jianzhong_room_reconnect_restores_game_start_and_pending_action_by_manager() -> None:
    async def scenario() -> None:
        server, websockets, game_state = await _started_room_with_connected_players()
        for player in game_state.player_list:
            player.hand_tiles = []
            player.combination_tiles = []
            player.tag_list = []
        game_state.player_list[0].hand_tiles = [11, 12, 13]
        game_state.player_list[0].combination_tiles = ["G15"]
        game_state.player_list[1].hand_tiles = [21, 22, 23]
        game_state.game_status = "waiting_action_after_cut"
        game_state.live_pending_window = {"status": "waiting_action_after_cut", "tile": 41}
        game_state.action_dict = {0: [], 1: ["hu", "pass"], 2: [], 3: []}
        game_state.server_action_tick = 9

        await server.gamestate_manager.player_disconnect(102)
        assert "offline" in game_state.player_list[1].tag_list

        await server.gamestate_manager.player_reconnect(102)

        assert "offline" not in game_state.player_list[1].tag_list
        game_start_payloads = [
            payload
            for payload in websockets[102].sent
            if payload.get("type") == "gamestate/jianzhong/game_start"
        ]
        assert game_start_payloads, websockets[102].sent
        payload = game_start_payloads[-1]
        assert payload["player_index"] == 1
        player_zero = payload["game_info"]["players_info"][0]
        player_one = payload["game_info"]["players_info"][1]
        assert player_zero["hand_tiles"] is None
        assert player_zero["hand_tiles_count"] == 3
        assert player_zero["combination_tiles"] == ["G0"]
        assert player_one["hand_tiles"] == [21, 22, 23]
        pending_action_payloads = [
            item
            for item in websockets[102].sent
            if item.get("type") == "gamestate/jianzhong/ask_other_action"
        ]
        assert pending_action_payloads, websockets[102].sent
        pending_payload = pending_action_payloads[-1]
        assert pending_payload["action_list"] == ["hu", "pass"]
        assert pending_payload["action_tick"] == 9
        assert pending_payload["ask_other_action_info"]["cut_tile"] == 41

        await server.gamestate_manager.cleanup_game_state_complete(gamestate_id=game_state.gamestate_id)
        assert game_state.game_task.cancelled()

    asyncio.run(scenario())


def test_jianzhong_room_reconnect_after_end_reveals_final_state_by_manager() -> None:
    async def scenario() -> None:
        server, websockets, game_state = await _started_room_with_connected_players()
        for player in game_state.player_list:
            player.hand_tiles = []
            player.combination_tiles = []
            player.score = 0
            player.tag_list = []
        game_state.game_status = "END"
        game_state.ended_by = "win"
        game_state.player_list[0].hand_tiles = [11, 12, 13]
        game_state.player_list[0].combination_tiles = ["G15"]
        game_state.player_list[1].hand_tiles = [21, 22, 23]
        game_state.deferred_hu_settlements = [
            {
                "source": "discard",
                "discarder": 0,
                "winner": 1,
                "tile": 41,
                "hu_order": 1,
                "points": 8,
                "fan_ids": ["duiduihu"],
                "score_changes": [-48, 48, 0, 0],
            }
        ]

        await server.gamestate_manager.player_disconnect(102)
        await server.gamestate_manager.player_reconnect(102)

        game_start_payloads = [
            payload
            for payload in websockets[102].sent
            if payload.get("type") == "gamestate/jianzhong/game_start"
        ]
        assert game_start_payloads, websockets[102].sent
        payload = game_start_payloads[-1]
        player_zero = payload["game_info"]["players_info"][0]
        player_one = payload["game_info"]["players_info"][1]
        assert payload["game_info"]["room_rule"] == "jianzhong"
        assert player_zero["hand_tiles"] == [11, 12, 13]
        assert player_zero["combination_tiles"] == ["G15"]
        assert player_one["hand_tiles"] == [21, 22, 23]
        assert player_zero["score"] == -48
        assert player_one["score"] == 48

        await server.gamestate_manager.player_reconnect(102)
        second_payload = [
            payload
            for payload in websockets[102].sent
            if payload.get("type") == "gamestate/jianzhong/game_start"
        ][-1]
        assert second_payload["game_info"]["players_info"][0]["score"] == -48
        assert second_payload["game_info"]["players_info"][1]["score"] == 48
        show_result_payloads = [
            payload
            for payload in websockets[102].sent
            if payload.get("type") == "gamestate/jianzhong/show_result"
        ]
        assert show_result_payloads, websockets[102].sent

        await server.gamestate_manager.cleanup_game_state_complete(gamestate_id=game_state.gamestate_id)
        assert game_state.game_task.done()

    asyncio.run(scenario())


def test_jianzhong_room_scripted_peng_cut_discard_win_continues_by_messages() -> None:
    async def scenario() -> None:
        server, websockets, game_state = await _started_room_with_connected_players()
        game_state.tiles_list = [33, 34]
        game_state.current_player_index = 0
        for player in game_state.player_list:
            player.hand_tiles = []
            player.waiting_tiles = set()
            player.combination_tiles = []
            player.discard_tiles = []
            player.discard_win_lockout_tiles = set()
            player.is_hu = False
            player.hu_order = 0
        game_state.hu_order_counter = 0
        game_state.deferred_hu_settlements = []

        game_state.player_list[0].hand_tiles = [15]
        game_state.player_list[1].hand_tiles = [21, 22, 23, 24, 25, 26, 36, 37, 38, 41, 41, 45, 45]
        game_state.player_list[2].hand_tiles = [15, 15, 31]
        game_state.player_list[3].hand_tiles = [11, 12, 13, 21, 22, 23, 32, 33, 34, 45, 45, 45, 31]
        game_state.open_action_window(game_state.begin_hand_action(0))

        await _send_host_cut(server, websockets[101], game_state, 15)
        await _wait_for_status(game_state, "waiting_action_after_cut")

        assert "peng" in game_state.action_dict[2], game_state.action_dict
        peng_tick = game_state.server_action_tick
        await handle_gamestate_message(
            server,
            "conn-103",
            {
                "type": "gamestate/jianzhong/send_action",
                "gamestate_id": game_state.gamestate_id,
                "action": "peng",
                "action_tick": peng_tick,
            },
            websockets[103],
        )

        await _wait_for_status(game_state, "onlycut_after_action", 2)
        assert game_state.player_list[2].combination_tiles == ["k15"]
        assert game_state.player_list[2].hand_tiles == [31]

        await handle_gamestate_message(
            server,
            "conn-103",
            {
                "type": "gamestate/jianzhong/cut_tile",
                "gamestate_id": game_state.gamestate_id,
                "TileId": 31,
                "cutIndex": 0,
                "cutClass": False,
            },
            websockets[103],
        )

        await _wait_for_status(game_state, "waiting_action_after_cut")
        assert 31 in game_state.player_list[2].discard_tiles
        assert "hu" in game_state.action_dict[3], game_state.action_dict

        hu_tick = game_state.server_action_tick
        await handle_gamestate_message(
            server,
            "conn-104",
            {
                "type": "gamestate/jianzhong/send_action",
                "gamestate_id": game_state.gamestate_id,
                "action": "hu",
                "action_tick": hu_tick,
            },
            websockets[104],
        )

        await _wait_for_status(game_state, "waiting_hand_action", 0)
        assert game_state.player_list[3].is_hu
        settlement = game_state.deferred_hu_settlements[0]
        assert settlement["source"] == "discard"
        assert settlement["discarder"] == 2
        assert settlement["tile"] == 31
        assert settlement["winner"] == 3
        assert settlement["hu_order"] == 1
        assert settlement["is_win"] is True
        assert game_state.player_list[0].hand_tiles == [33]
        assert game_state.current_player_index == 0

        await server.gamestate_manager.cleanup_game_state_complete(gamestate_id=game_state.gamestate_id)
        assert game_state.game_task.cancelled()

    asyncio.run(scenario())


def test_jianzhong_room_scripted_multi_ron_continues_by_messages() -> None:
    async def scenario() -> None:
        server, websockets, game_state = await _started_room_with_connected_players()
        game_state.tiles_list = [33, 34]
        game_state.current_player_index = 0
        for player in game_state.player_list:
            player.hand_tiles = []
            player.waiting_tiles = set()
            player.combination_tiles = []
            player.discard_tiles = []
            player.discard_win_lockout_tiles = set()
            player.is_hu = False
            player.hu_order = 0
        game_state.hu_order_counter = 0
        game_state.deferred_hu_settlements = []

        game_state.player_list[0].hand_tiles = [45]
        game_state.player_list[1].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 41, 41, 45, 45]
        game_state.player_list[2].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 42, 42, 45, 45]
        game_state.open_action_window(game_state.begin_hand_action(0))

        await _send_host_cut(server, websockets[101], game_state, 45)
        await _wait_for_status(game_state, "waiting_action_after_cut")

        assert "hu" in game_state.action_dict[1], game_state.action_dict
        assert "hu" in game_state.action_dict[2], game_state.action_dict
        hu_tick = game_state.server_action_tick
        await handle_gamestate_message(
            server,
            "conn-102",
            {
                "type": "gamestate/jianzhong/send_action",
                "gamestate_id": game_state.gamestate_id,
                "action": "hu",
                "action_tick": hu_tick,
            },
            websockets[102],
        )
        await handle_gamestate_message(
            server,
            "conn-103",
            {
                "type": "gamestate/jianzhong/send_action",
                "gamestate_id": game_state.gamestate_id,
                "action": "hu",
                "action_tick": hu_tick,
            },
            websockets[103],
        )

        await _wait_for_status(game_state, "waiting_hand_action", 3)
        assert game_state.player_list[1].is_hu
        assert game_state.player_list[2].is_hu
        assert game_state.player_list[3].hand_tiles == [33]
        assert [settlement["winner"] for settlement in game_state.deferred_hu_settlements] == [1, 2]
        assert [settlement["score_changes"] for settlement in game_state.deferred_hu_settlements] == [
            [-48, 48, 0, 0],
            [-48, 0, 48, 0],
        ]

        await server.gamestate_manager.cleanup_game_state_complete(gamestate_id=game_state.gamestate_id)
        assert game_state.game_task.cancelled()

    asyncio.run(scenario())


def test_jianzhong_room_multi_ron_as_second_and_third_winners_ends_by_messages() -> None:
    async def scenario() -> None:
        server, websockets, game_state = await _started_room_with_connected_players()
        game_state.tiles_list = [33, 34]
        game_state.current_player_index = 0
        for player in game_state.player_list:
            player.hand_tiles = []
            player.waiting_tiles = set()
            player.combination_tiles = []
            player.discard_tiles = []
            player.discard_win_lockout_tiles = set()
            player.is_hu = False
            player.hu_order = 0
        game_state.player_list[3].is_hu = True
        game_state.player_list[3].hu_order = 1
        game_state.hu_order_counter = 1
        game_state.deferred_hu_settlements = [
            {
                "source": "self_draw",
                "tile": 41,
                "winner": 3,
                "hu_order": 1,
                "score_changes": [0, 0, 0, 0],
            }
        ]
        _force_final_configured_round(game_state)

        game_state.player_list[0].hand_tiles = [45]
        game_state.player_list[1].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 41, 41, 45, 45]
        game_state.player_list[2].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 42, 42, 45, 45]
        game_state.open_action_window(game_state.begin_hand_action(0))

        await _send_host_cut(server, websockets[101], game_state, 45)
        await _wait_for_status(game_state, "waiting_action_after_cut")

        assert "hu" in game_state.action_dict[1], game_state.action_dict
        assert "hu" in game_state.action_dict[2], game_state.action_dict
        assert game_state.action_dict[3] == [], game_state.action_dict
        action_tick = game_state.server_action_tick
        await handle_gamestate_message(
            server,
            "conn-102",
            {
                "type": "gamestate/jianzhong/send_action",
                "gamestate_id": game_state.gamestate_id,
                "action": "hu",
                "action_tick": action_tick,
            },
            websockets[102],
        )
        await handle_gamestate_message(
            server,
            "conn-103",
            {
                "type": "gamestate/jianzhong/send_action",
                "gamestate_id": game_state.gamestate_id,
                "action": "hu",
                "action_tick": action_tick,
            },
            websockets[103],
        )

        await _wait_for_status(game_state, "waiting_ready")
        final_payloads = [
            payload
            for payload in game_state.outbound_payloads
            if payload.get("type") == "gamestate/jianzhong/show_result"
            and payload.get("show_result_info", {}).get("defer_score_settlement") is not True
        ]
        assert game_state.ended_by == "win"
        assert game_state.current_player_index == 0
        assert [settlement["winner"] for settlement in game_state.deferred_hu_settlements] == [3, 1, 2]
        assert [settlement["hu_order"] for settlement in game_state.deferred_hu_settlements] == [1, 2, 3]
        assert [settlement["score_changes"] for settlement in game_state.deferred_hu_settlements[-2:]] == [
            [-48, 48, 0, 0],
            [-48, 0, 48, 0],
        ]
        assert len(final_payloads) == 12
        assert [
            payload["show_result_info"]["hepai_player_index"]
            for payload in final_payloads
        ] == [3, 1, 2] * 4
        assert [
            payload["show_result_info"]["liuju_status_final"]
            for payload in final_payloads[:3]
        ] == [False, False, True]
        for payload in final_payloads:
            scores = [
                player_info["score"]
                for player_info in payload["game_info"]["players_info"]
            ]
            assert scores == [-96, 48, 48, 0]

        await server.gamestate_manager.cleanup_game_state_complete(gamestate_id=game_state.gamestate_id)
        assert game_state.game_task.done()

    asyncio.run(scenario())


def test_jianzhong_room_late_action_after_end_does_not_mutate_by_messages() -> None:
    async def scenario() -> None:
        server, websockets, game_state = await _started_room_with_connected_players()
        game_state.tiles_list = [33, 34]
        game_state.current_player_index = 0
        for player in game_state.player_list:
            player.hand_tiles = []
            player.waiting_tiles = set()
            player.combination_tiles = []
            player.discard_tiles = []
            player.discard_win_lockout_tiles = set()
            player.is_hu = False
            player.hu_order = 0
        game_state.player_list[3].is_hu = True
        game_state.player_list[3].hu_order = 1
        game_state.hu_order_counter = 1
        game_state.deferred_hu_settlements = [
            {
                "source": "self_draw",
                "tile": 41,
                "winner": 3,
                "hu_order": 1,
                "score_changes": [0, 0, 0, 0],
            }
        ]
        _force_final_configured_round(game_state)

        game_state.player_list[0].hand_tiles = [45]
        game_state.player_list[1].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 41, 41, 45, 45]
        game_state.player_list[2].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 42, 42, 45, 45]
        game_state.open_action_window(game_state.begin_hand_action(0))

        await _send_host_cut(server, websockets[101], game_state, 45)
        await _wait_for_status(game_state, "waiting_action_after_cut")

        action_tick = game_state.server_action_tick
        await handle_gamestate_message(
            server,
            "conn-102",
            {
                "type": "gamestate/jianzhong/send_action",
                "gamestate_id": game_state.gamestate_id,
                "action": "hu",
                "action_tick": action_tick,
            },
            websockets[102],
        )
        await handle_gamestate_message(
            server,
            "conn-103",
            {
                "type": "gamestate/jianzhong/send_action",
                "gamestate_id": game_state.gamestate_id,
                "action": "hu",
                "action_tick": action_tick,
            },
            websockets[103],
        )

        await _wait_for_status(game_state, "waiting_ready")
        settlements_before = list(game_state.deferred_hu_settlements)
        scores_before = [player.score for player in game_state.player_list]
        payload_count_before = len(game_state.outbound_payloads)
        tick_before = game_state.server_action_tick

        await handle_gamestate_message(
            server,
            "conn-104",
            {
                "type": "gamestate/jianzhong/send_action",
                "gamestate_id": game_state.gamestate_id,
                "action": "pass",
                "action_tick": action_tick,
            },
            websockets[104],
        )

        assert game_state.game_status == "waiting_ready"
        assert game_state.ended_by == "win"
        assert game_state.server_action_tick == tick_before
        assert game_state.deferred_hu_settlements == settlements_before
        assert [player.score for player in game_state.player_list] == scores_before
        assert len(game_state.outbound_payloads) == payload_count_before

        await server.gamestate_manager.cleanup_game_state_complete(gamestate_id=game_state.gamestate_id)
        assert game_state.game_task.done()

    asyncio.run(scenario())


def test_jianzhong_room_stale_response_after_window_change_is_ignored_by_messages() -> None:
    async def scenario() -> None:
        server, websockets, game_state = await _started_room_with_connected_players()
        game_state.tiles_list = [33, 34]
        game_state.current_player_index = 0
        for player in game_state.player_list:
            player.hand_tiles = []
            player.waiting_tiles = set()
            player.combination_tiles = []
            player.discard_tiles = []
            player.discard_win_lockout_tiles = set()
            player.is_hu = False
            player.hu_order = 0
        game_state.hu_order_counter = 0
        game_state.deferred_hu_settlements = []

        game_state.player_list[0].hand_tiles = [45]
        game_state.player_list[1].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 41, 41, 45, 45]
        game_state.player_list[2].hand_tiles = [11, 12, 13]
        game_state.open_action_window(game_state.begin_hand_action(0))

        await _send_host_cut(server, websockets[101], game_state, 45)
        await _wait_for_status(game_state, "waiting_action_after_cut")

        assert "hu" in game_state.action_dict[1], game_state.action_dict
        assert "hu" not in game_state.action_dict[2], game_state.action_dict
        old_tick = game_state.server_action_tick
        await handle_gamestate_message(
            server,
            "conn-102",
            {
                "type": "gamestate/jianzhong/send_action",
                "gamestate_id": game_state.gamestate_id,
                "action": "hu",
                "action_tick": old_tick,
            },
            websockets[102],
        )

        await _wait_for_status(game_state, "waiting_hand_action", 2)
        tick_after_window_change = game_state.server_action_tick
        payload_count_before = len(game_state.outbound_payloads)
        hand_before = list(game_state.player_list[2].hand_tiles)
        settlements_before = list(game_state.deferred_hu_settlements)

        await handle_gamestate_message(
            server,
            "conn-103",
            {
                "type": "gamestate/jianzhong/send_action",
                "gamestate_id": game_state.gamestate_id,
                "action": "pass",
                "action_tick": old_tick,
            },
            websockets[103],
        )

        assert game_state.game_status == "waiting_hand_action"
        assert game_state.current_player_index == 2
        assert game_state.server_action_tick == tick_after_window_change
        assert game_state.player_list[2].hand_tiles == hand_before
        assert game_state.player_list[2].discard_win_lockout_tiles == set()
        assert game_state.deferred_hu_settlements == settlements_before
        assert len(game_state.outbound_payloads) == payload_count_before

        await server.gamestate_manager.cleanup_game_state_complete(gamestate_id=game_state.gamestate_id)
        assert game_state.game_task.cancelled()

    asyncio.run(scenario())


def test_jianzhong_room_hu_and_pass_locks_only_passing_player_by_messages() -> None:
    async def scenario() -> None:
        server, websockets, game_state = await _started_room_with_connected_players()
        game_state.tiles_list = [33, 34]
        game_state.current_player_index = 0
        for player in game_state.player_list:
            player.hand_tiles = []
            player.waiting_tiles = set()
            player.combination_tiles = []
            player.discard_tiles = []
            player.discard_win_lockout_tiles = set()
            player.is_hu = False
            player.hu_order = 0
        game_state.hu_order_counter = 0
        game_state.deferred_hu_settlements = []

        game_state.player_list[0].hand_tiles = [45]
        game_state.player_list[1].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 41, 41, 45, 45]
        game_state.player_list[2].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 42, 42, 45, 45]
        game_state.open_action_window(game_state.begin_hand_action(0))

        await _send_host_cut(server, websockets[101], game_state, 45)
        await _wait_for_status(game_state, "waiting_action_after_cut")

        assert "hu" in game_state.action_dict[1], game_state.action_dict
        assert "hu" in game_state.action_dict[2], game_state.action_dict
        action_tick = game_state.server_action_tick
        await handle_gamestate_message(
            server,
            "conn-103",
            {
                "type": "gamestate/jianzhong/send_action",
                "gamestate_id": game_state.gamestate_id,
                "action": "pass",
                "action_tick": action_tick,
            },
            websockets[103],
        )
        await handle_gamestate_message(
            server,
            "conn-102",
            {
                "type": "gamestate/jianzhong/send_action",
                "gamestate_id": game_state.gamestate_id,
                "action": "hu",
                "action_tick": action_tick,
            },
            websockets[102],
        )

        await _wait_for_status(game_state, "waiting_hand_action", 2)
        assert game_state.player_list[1].is_hu
        assert game_state.player_list[1].discard_win_lockout_tiles == set()
        assert game_state.player_list[2].discard_win_lockout_tiles == {45}
        assert game_state.player_list[2].hand_tiles[-1] == 33
        assert [settlement["winner"] for settlement in game_state.deferred_hu_settlements] == [1]

        await server.gamestate_manager.cleanup_game_state_complete(gamestate_id=game_state.gamestate_id)
        assert game_state.game_task.cancelled()

    asyncio.run(scenario())


def test_jianzhong_room_hu_response_skips_peng_claim_by_messages() -> None:
    async def scenario() -> None:
        server, websockets, game_state = await _started_room_with_connected_players()
        game_state.tiles_list = [33, 34]
        game_state.current_player_index = 0
        for player in game_state.player_list:
            player.hand_tiles = []
            player.waiting_tiles = set()
            player.combination_tiles = []
            player.discard_tiles = []
            player.discard_win_lockout_tiles = set()
            player.is_hu = False
            player.hu_order = 0
        game_state.hu_order_counter = 0
        game_state.deferred_hu_settlements = []

        game_state.player_list[0].hand_tiles = [45]
        game_state.player_list[1].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 41, 41, 45, 45]
        game_state.player_list[2].hand_tiles = [45, 45, 31]
        game_state.open_action_window(game_state.begin_hand_action(0))

        await _send_host_cut(server, websockets[101], game_state, 45)
        await _wait_for_status(game_state, "waiting_action_after_cut")

        assert "hu" in game_state.action_dict[1], game_state.action_dict
        assert "peng" in game_state.action_dict[2], game_state.action_dict
        action_tick = game_state.server_action_tick
        await handle_gamestate_message(
            server,
            "conn-103",
            {
                "type": "gamestate/jianzhong/send_action",
                "gamestate_id": game_state.gamestate_id,
                "action": "peng",
                "action_tick": action_tick,
            },
            websockets[103],
        )
        await handle_gamestate_message(
            server,
            "conn-102",
            {
                "type": "gamestate/jianzhong/send_action",
                "gamestate_id": game_state.gamestate_id,
                "action": "hu",
                "action_tick": action_tick,
            },
            websockets[102],
        )

        await _wait_for_status(game_state, "waiting_hand_action", 2)
        assert game_state.player_list[1].is_hu
        assert game_state.player_list[2].combination_tiles == []
        assert game_state.player_list[2].hand_tiles == [45, 45, 31, 33]
        settlement = game_state.deferred_hu_settlements[0]
        assert settlement["winner"] == 1
        assert settlement["discarder"] == 0
        assert settlement["tile"] == 45
        assert settlement["score_changes"] == [-48, 48, 0, 0]

        await server.gamestate_manager.cleanup_game_state_complete(gamestate_id=game_state.gamestate_id)
        assert game_state.game_task.cancelled()

    asyncio.run(scenario())


def test_jianzhong_room_scripted_self_draw_win_continues_by_messages() -> None:
    async def scenario() -> None:
        server, websockets, game_state = await _started_room_with_connected_players()
        game_state.tiles_list = [34, 35]
        game_state.current_player_index = 0
        for player in game_state.player_list:
            player.hand_tiles = []
            player.waiting_tiles = set()
            player.combination_tiles = []
            player.discard_tiles = []
            player.discard_win_lockout_tiles = set()
            player.is_hu = False
            player.hu_order = 0
        game_state.hu_order_counter = 0
        game_state.deferred_hu_settlements = []

        game_state.player_list[0].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 45, 45, 45, 15, 15]
        game_state.player_list[1].hand_tiles = [21, 22, 23]
        game_state.open_action_window(game_state.begin_hand_action(0))

        assert "hu_self" in game_state.action_dict[0], game_state.action_dict
        action_tick = game_state.server_action_tick
        await handle_gamestate_message(
            server,
            "conn-101",
            {
                "type": "gamestate/jianzhong/send_action",
                "gamestate_id": game_state.gamestate_id,
                "action": "hu_self",
                "action_tick": action_tick,
            },
            websockets[101],
        )

        await _wait_for_status(game_state, "waiting_hand_action", 1)
        assert game_state.player_list[0].is_hu
        settlement = game_state.deferred_hu_settlements[0]
        assert settlement["source"] == "self_draw"
        assert settlement["tile"] == 15
        assert settlement["winner"] == 0
        assert settlement["hu_order"] == 1
        assert settlement["is_win"] is True
        assert game_state.player_list[1].hand_tiles == [21, 22, 23, 34]
        assert game_state.current_player_index == 1

        await server.gamestate_manager.cleanup_game_state_complete(gamestate_id=game_state.gamestate_id)
        assert game_state.game_task.cancelled()

    asyncio.run(scenario())


def test_jianzhong_room_third_self_draw_win_ends_hand_by_messages() -> None:
    async def scenario() -> None:
        server, websockets, game_state = await _started_room_with_connected_players()
        game_state.tiles_list = [34, 35]
        game_state.current_player_index = 0
        for player in game_state.player_list:
            player.hand_tiles = []
            player.waiting_tiles = set()
            player.combination_tiles = []
            player.discard_tiles = []
            player.discard_win_lockout_tiles = set()
            player.is_hu = False
            player.hu_order = 0
        game_state.player_list[1].is_hu = True
        game_state.player_list[1].hu_order = 1
        game_state.player_list[2].is_hu = True
        game_state.player_list[2].hu_order = 2
        game_state.hu_order_counter = 2
        game_state.deferred_hu_settlements = [
            {"source": "discard", "discarder": 0, "tile": 41, "winner": 1, "hu_order": 1},
            {"source": "discard", "discarder": 0, "tile": 42, "winner": 2, "hu_order": 2},
        ]
        game_state.opening_action_taken = True
        game_state.opening_flow_interrupted = True
        _force_final_configured_round(game_state)

        game_state.player_list[0].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 45, 45, 45, 15, 15]
        game_state.open_action_window(game_state.begin_hand_action(0))

        assert "hu_self" in game_state.action_dict[0], game_state.action_dict
        action_tick = game_state.server_action_tick
        await handle_gamestate_message(
            server,
            "conn-101",
            {
                "type": "gamestate/jianzhong/send_action",
                "gamestate_id": game_state.gamestate_id,
                "action": "hu_self",
                "action_tick": action_tick,
            },
            websockets[101],
        )

        await _wait_for_status(game_state, "waiting_ready")
        final_payloads = [
            payload
            for payload in game_state.outbound_payloads
            if payload.get("type") == "gamestate/jianzhong/show_result"
            and payload.get("show_result_info", {}).get("defer_score_settlement") is not True
        ]
        assert game_state.ended_by == "win"
        assert game_state.player_list[0].is_hu
        settlement = game_state.deferred_hu_settlements[-1]
        assert settlement["source"] == "self_draw"
        assert settlement["tile"] == 15
        assert settlement["winner"] == 0
        assert settlement["hu_order"] == 3
        assert settlement["is_win"] is True
        assert settlement["points"] == 5
        assert settlement["score_changes"] == [30, 0, 0, -30]
        winner_order = [item["winner"] for item in game_state.deferred_hu_settlements]
        assert len(final_payloads) == 4 * len(winner_order)
        assert [
            payload["show_result_info"]["hepai_player_index"]
            for payload in final_payloads[:len(winner_order)]
        ] == winner_order
        assert final_payloads[-1]["show_result_info"]["score_changes"] == {0: 30, 1: 0, 2: 0, 3: -30}
        for payload in final_payloads:
            scores = [
                player_info["score"]
                for player_info in payload["game_info"]["players_info"]
            ]
            assert scores == [30, 0, 0, -30]

        await server.gamestate_manager.cleanup_game_state_complete(gamestate_id=game_state.gamestate_id)
        assert game_state.game_task.done()

    asyncio.run(scenario())


def test_jianzhong_room_final_discard_no_win_ends_by_wall_by_messages() -> None:
    async def scenario() -> None:
        server, websockets, game_state = await _started_room_with_connected_players()
        game_state.tiles_list = []
        game_state.current_player_index = 0
        for player in game_state.player_list:
            player.hand_tiles = []
            player.waiting_tiles = set()
            player.combination_tiles = []
            player.discard_tiles = []
            player.discard_win_lockout_tiles = set()
            player.is_hu = False
            player.hu_order = 0
        game_state.hu_order_counter = 0
        game_state.deferred_hu_settlements = []
        game_state.ended_by = None
        _force_final_configured_round(game_state)

        game_state.player_list[0].hand_tiles = [15]
        game_state.open_action_window(game_state.begin_hand_action(0))

        await _send_host_cut(server, websockets[101], game_state, 15)
        await _wait_for_status(game_state, "waiting_ready")

        assert game_state.ended_by == "wall"
        assert game_state.deferred_hu_settlements == []
        assert game_state.player_list[0].discard_tiles == [15]

        final_payloads = [
            payload
            for payload in websockets[101].sent
            if payload.get("type") == "gamestate/jianzhong/show_result"
        ]
        assert final_payloads, websockets[101].sent
        assert final_payloads[-1]["show_result_info"]["hu_class"] == "liuju"
        assert final_payloads[-1]["show_result_info"]["hu_fan"] == []

        await server.gamestate_manager.cleanup_game_state_complete(gamestate_id=game_state.gamestate_id)
        assert game_state.game_task.done()

    asyncio.run(scenario())


def test_jianzhong_room_scripted_concealed_kong_cut_by_messages() -> None:
    async def scenario() -> None:
        server, websockets, game_state = await _started_room_with_connected_players()
        game_state.tiles_list = [33, 34]
        game_state.current_player_index = 0
        for player in game_state.player_list:
            player.hand_tiles = []
            player.waiting_tiles = set()
            player.combination_tiles = []
            player.discard_tiles = []
            player.discard_win_lockout_tiles = set()
            player.is_hu = False
            player.hu_order = 0
        game_state.hu_order_counter = 0
        game_state.deferred_hu_settlements = []

        game_state.player_list[0].hand_tiles = [15, 15, 15, 15, 41]
        game_state.open_action_window(game_state.begin_hand_action(0))

        assert "angang" in game_state.action_dict[0], game_state.action_dict
        action_tick = game_state.server_action_tick
        await handle_gamestate_message(
            server,
            "conn-101",
            {
                "type": "gamestate/jianzhong/send_action",
                "gamestate_id": game_state.gamestate_id,
                "action": "angang",
                "targetTile": 15,
                "action_tick": action_tick,
            },
            websockets[101],
        )

        await _wait_for_condition(
            lambda: game_state.player_list[0].combination_tiles == ["G15"],
            lambda: (
                game_state.game_status,
                game_state.current_player_index,
                game_state.player_list[0].hand_tiles,
                game_state.player_list[0].combination_tiles,
                game_state.action_dict[0],
            ),
        )
        assert game_state.game_status == "waiting_hand_action"
        assert game_state.current_player_index == 0
        assert game_state.player_list[0].hand_tiles == [41, 33]
        assert "cut" in game_state.action_dict[0]

        await handle_gamestate_message(
            server,
            "conn-101",
            {
                "type": "gamestate/jianzhong/cut_tile",
                "gamestate_id": game_state.gamestate_id,
                "TileId": 33,
                "cutIndex": 1,
                "cutClass": False,
            },
            websockets[101],
        )

        await _wait_for_status(game_state, "waiting_hand_action", 1)
        assert game_state.player_list[0].discard_tiles == [33]
        assert game_state.player_list[1].hand_tiles == [34]

        await server.gamestate_manager.cleanup_game_state_complete(gamestate_id=game_state.gamestate_id)
        assert game_state.game_task.cancelled()

    asyncio.run(scenario())


def test_jianzhong_room_scripted_added_kong_pass_cut_by_messages() -> None:
    async def scenario() -> None:
        server, websockets, game_state = await _started_room_with_connected_players()
        game_state.tiles_list = [33, 34]
        game_state.current_player_index = 0
        for player in game_state.player_list:
            player.hand_tiles = []
            player.waiting_tiles = set()
            player.combination_tiles = []
            player.discard_tiles = []
            player.discard_win_lockout_tiles = set()
            player.is_hu = False
            player.hu_order = 0
        game_state.hu_order_counter = 0
        game_state.deferred_hu_settlements = []

        game_state.player_list[0].hand_tiles = [15, 41]
        game_state.player_list[0].combination_tiles = ["k15"]
        game_state.player_list[1].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 45, 45, 45, 15]
        game_state.open_action_window(game_state.begin_hand_action(0))

        assert "jiagang" in game_state.action_dict[0], game_state.action_dict
        action_tick = game_state.server_action_tick
        await handle_gamestate_message(
            server,
            "conn-101",
            {
                "type": "gamestate/jianzhong/send_action",
                "gamestate_id": game_state.gamestate_id,
                "action": "jiagang",
                "targetTile": 15,
                "action_tick": action_tick,
            },
            websockets[101],
        )

        await _wait_for_status(game_state, "waiting_action_qianggang")
        assert "hu" in game_state.action_dict[1], game_state.action_dict
        action_tick = game_state.server_action_tick
        await handle_gamestate_message(
            server,
            "conn-102",
            {
                "type": "gamestate/jianzhong/send_action",
                "gamestate_id": game_state.gamestate_id,
                "action": "pass",
                "action_tick": action_tick,
            },
            websockets[102],
        )

        await _wait_for_condition(
            lambda: game_state.player_list[0].combination_tiles == ["g15"],
            lambda: (
                game_state.game_status,
                game_state.current_player_index,
                game_state.player_list[0].hand_tiles,
                game_state.player_list[0].combination_tiles,
                game_state.action_dict[0],
            ),
        )
        assert game_state.game_status == "waiting_hand_action"
        assert game_state.current_player_index == 0
        assert game_state.player_list[0].hand_tiles == [41, 33]
        assert "cut" in game_state.action_dict[0]

        await handle_gamestate_message(
            server,
            "conn-101",
            {
                "type": "gamestate/jianzhong/cut_tile",
                "gamestate_id": game_state.gamestate_id,
                "TileId": 33,
                "cutIndex": 1,
                "cutClass": False,
            },
            websockets[101],
        )

        await _wait_for_status(game_state, "waiting_action_after_cut")
        assert game_state.player_list[0].discard_tiles == [33]
        assert "pass" in game_state.action_dict[1], game_state.action_dict

        action_tick = game_state.server_action_tick
        await handle_gamestate_message(
            server,
            "conn-102",
            {
                "type": "gamestate/jianzhong/send_action",
                "gamestate_id": game_state.gamestate_id,
                "action": "pass",
                "action_tick": action_tick,
            },
            websockets[102],
        )

        await _wait_for_status(game_state, "waiting_hand_action", 1)
        assert game_state.player_list[1].hand_tiles[-1] == 34

        await server.gamestate_manager.cleanup_game_state_complete(gamestate_id=game_state.gamestate_id)
        assert game_state.game_task.cancelled()

    asyncio.run(scenario())


def test_jianzhong_room_scripted_added_kong_robbed_by_messages() -> None:
    async def scenario() -> None:
        server, websockets, game_state = await _started_room_with_connected_players()
        game_state.tiles_list = [33, 34]
        game_state.current_player_index = 0
        for player in game_state.player_list:
            player.hand_tiles = []
            player.waiting_tiles = set()
            player.combination_tiles = []
            player.discard_tiles = []
            player.discard_win_lockout_tiles = set()
            player.is_hu = False
            player.hu_order = 0
        game_state.hu_order_counter = 0
        game_state.deferred_hu_settlements = []

        game_state.player_list[0].hand_tiles = [15, 41]
        game_state.player_list[0].combination_tiles = ["k15"]
        game_state.player_list[1].hand_tiles = [11, 12, 13, 21, 22, 23, 31, 32, 33, 45, 45, 45, 15]
        game_state.open_action_window(game_state.begin_hand_action(0))

        assert "jiagang" in game_state.action_dict[0], game_state.action_dict
        action_tick = game_state.server_action_tick
        await handle_gamestate_message(
            server,
            "conn-101",
            {
                "type": "gamestate/jianzhong/send_action",
                "gamestate_id": game_state.gamestate_id,
                "action": "jiagang",
                "targetTile": 15,
                "action_tick": action_tick,
            },
            websockets[101],
        )

        await _wait_for_status(game_state, "waiting_action_qianggang")
        assert "hu" in game_state.action_dict[1], game_state.action_dict
        action_tick = game_state.server_action_tick
        await handle_gamestate_message(
            server,
            "conn-102",
            {
                "type": "gamestate/jianzhong/send_action",
                "gamestate_id": game_state.gamestate_id,
                "action": "hu",
                "action_tick": action_tick,
            },
            websockets[102],
        )

        await _wait_for_status(game_state, "waiting_hand_action", 2)
        assert game_state.player_list[1].is_hu
        assert game_state.player_list[0].combination_tiles == ["k15"]
        assert game_state.player_list[0].hand_tiles == [41]
        settlement = game_state.deferred_hu_settlements[0]
        assert settlement["source"] == "rob_kong"
        assert settlement["kong_player"] == 0
        assert settlement["tile"] == 15
        assert settlement["winner"] == 1
        assert settlement["hu_order"] == 1
        assert settlement["is_win"] is True
        assert "chankan" in settlement["fan_ids"]
        assert game_state.player_list[2].hand_tiles == [33]

        await server.gamestate_manager.cleanup_game_state_complete(gamestate_id=game_state.gamestate_id)
        assert game_state.game_task.cancelled()

    asyncio.run(scenario())


def run() -> None:
    tests = [
        test_room_manager_creates_public_jianzhong_room,
        test_room_router_persists_second_winner_flow_option,
        test_jianzhong_room_is_listed_and_syncable,
        test_jianzhong_room_allows_join_by_room_id,
        test_jianzhong_room_start_requires_host,
        test_jianzhong_room_rejects_non_member_ready_and_non_host_kick,
        test_room_manager_preserves_jianzhong_spectator_setting,
        test_game_server_jianzhong_create_wrapper_preserves_spectator_setting,
        test_jianzhong_smoke_uses_game_server_connection_session,
        test_jianzhong_smoke_uses_four_game_server_connection_sessions,
        test_room_router_handles_jianzhong_create_message,
        test_jianzhong_protocol_dispatch_create_start_cut_smoke,
        test_jianzhong_room_can_start_game_state,
        test_jianzhong_room_accepts_first_cut_message,
        test_jianzhong_room_accepts_discard_win_response_message,
        test_jianzhong_room_accepts_discard_pass_response_message,
        test_jianzhong_room_accepts_peng_claim_response_message,
        test_jianzhong_room_accepts_chi_claim_response_message,
        test_jianzhong_room_accepts_gang_claim_response_message,
        test_jianzhong_room_accepts_concealed_kong_hand_action_message,
        test_jianzhong_room_accepts_added_kong_pass_response_messages,
        test_jianzhong_room_accepts_robbing_kong_win_response_message,
        test_jianzhong_room_emits_final_settlement_reveal_payloads,
        test_jianzhong_room_reconnect_restores_game_start_and_pending_action_by_manager,
        test_jianzhong_room_reconnect_after_end_reveals_final_state_by_manager,
        test_jianzhong_room_scripted_peng_cut_discard_win_continues_by_messages,
        test_jianzhong_room_scripted_multi_ron_continues_by_messages,
        test_jianzhong_room_multi_ron_as_second_and_third_winners_ends_by_messages,
        test_jianzhong_room_late_action_after_end_does_not_mutate_by_messages,
        test_jianzhong_room_stale_response_after_window_change_is_ignored_by_messages,
        test_jianzhong_room_hu_and_pass_locks_only_passing_player_by_messages,
        test_jianzhong_room_hu_response_skips_peng_claim_by_messages,
        test_jianzhong_room_scripted_self_draw_win_continues_by_messages,
        test_jianzhong_room_third_self_draw_win_ends_hand_by_messages,
        test_jianzhong_room_final_discard_no_win_ends_by_wall_by_messages,
        test_jianzhong_room_scripted_concealed_kong_cut_by_messages,
        test_jianzhong_room_scripted_added_kong_pass_cut_by_messages,
        test_jianzhong_room_scripted_added_kong_robbed_by_messages,
    ]
    for test in tests:
        test()
    print(f"jianzhong room creation tests ok: {len(tests)} tests")


if __name__ == "__main__":
    run()
