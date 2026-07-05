from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace

SERVER_ROOT = Path(__file__).resolve().parents[3]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from server.gamestate.gamestate_router import handle_gamestate_message
from server.gamestate.game_new_rule import NewRuleGameState


class FakeGameStateManager:
    def __init__(self, game_state):
        self.game_state = game_state

    def get_game_state_by_gamestate_id(self, gamestate_id: str):
        if gamestate_id == self.game_state.gamestate_id:
            return self.game_state
        return None


class FakeWebSocket:
    async def send_json(self, payload: dict) -> None:
        pass


def _server_with_game(game: NewRuleGameState):
    server = SimpleNamespace()
    server.players = {"conn-101": SimpleNamespace(user_id=101), "conn-102": SimpleNamespace(user_id=102)}
    server.gamestate_manager = FakeGameStateManager(game)
    game.game_server = server
    return server


def test_new_rule_cut_tile_route_queues_cut_action() -> None:
    async def scenario() -> None:
        game = NewRuleGameState()
        server = _server_with_game(game)
        game.player_list[0].hand_tiles = [11, 12, 13]
        game.waiting_players_list = [0]
        game.action_dict = {0: ["cut"], 1: [], 2: [], 3: []}

        await handle_gamestate_message(
            server,
            "conn-101",
            {
                "type": "gamestate/new_rule/cut_tile",
                "gamestate_id": game.gamestate_id,
                "TileId": 12,
                "cutIndex": 1,
                "cutClass": False,
            },
            FakeWebSocket(),
        )

        queued = await game.action_queues[0].get()
        assert queued["action_type"] == "cut"
        assert queued["TileId"] == 12
        assert queued["cutIndex"] == 1
        assert queued["cutClass"] is False

    asyncio.run(scenario())


def test_new_rule_send_action_route_queues_response_action() -> None:
    async def scenario() -> None:
        game = NewRuleGameState()
        server = _server_with_game(game)
        game.game_status = "waiting_discard_response"
        game.server_action_tick = 3
        game.waiting_players_list = [1]
        game.action_dict = {0: [], 1: ["hu", "pass"], 2: [], 3: []}

        await handle_gamestate_message(
            server,
            "conn-102",
            {
                "type": "gamestate/new_rule/send_action",
                "gamestate_id": game.gamestate_id,
                "action": "hu",
                "action_tick": 3,
            },
            FakeWebSocket(),
        )

        queued = await game.action_queues[1].get()
        assert queued["action_type"] == "hu"

    asyncio.run(scenario())


def test_new_rule_route_rejects_non_new_rule_state() -> None:
    async def scenario() -> None:
        game = NewRuleGameState()
        server = _server_with_game(game)
        game.room_rule = "guobiao"
        game.player_list[0].hand_tiles = [11, 12, 13]
        game.waiting_players_list = [0]
        game.action_dict = {0: ["cut"], 1: [], 2: [], 3: []}

        await handle_gamestate_message(
            server,
            "conn-101",
            {
                "type": "gamestate/new_rule/cut_tile",
                "gamestate_id": game.gamestate_id,
                "TileId": 12,
                "cutIndex": 1,
            },
            FakeWebSocket(),
        )

        assert game.action_queues[0].empty()

    asyncio.run(scenario())


def run() -> None:
    tests = [
        test_new_rule_cut_tile_route_queues_cut_action,
        test_new_rule_send_action_route_queues_response_action,
        test_new_rule_route_rejects_non_new_rule_state,
    ]
    for test in tests:
        test()
    print(f"new_rule router tests ok: {len(tests)} tests")


if __name__ == "__main__":
    run()
