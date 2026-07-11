from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace

SERVER_ROOT = Path(__file__).resolve().parents[3]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from server.gamestate.game_jianzhong import JianzhongGameState
from server.gamestate.game_jianzhong.get_action import get_action, get_ai_action


def _with_fake_server(game: JianzhongGameState) -> None:
    game.game_server = SimpleNamespace(
        players={
            "conn-101": SimpleNamespace(user_id=101),
            "conn-102": SimpleNamespace(user_id=102),
        }
    )


def test_get_ai_action_queues_cut_action() -> None:
    async def scenario() -> None:
        game = JianzhongGameState()
        game.player_list[0].hand_tiles = [11, 12, 13]
        game.waiting_players_list = [0]
        game.action_dict = {0: ["cut"], 1: [], 2: [], 3: []}

        await get_ai_action(game, 0, "cut", TileId=12, cutIndex=1)

        queued = await game.action_queues[0].get()
        assert queued["action_type"] == "cut"
        assert queued["TileId"] == 12
        assert queued["cutIndex"] == 1
        assert queued["cutClass"] is False
        assert game.action_events[0].is_set()

    asyncio.run(scenario())


def test_get_action_maps_connection_to_player_index() -> None:
    async def scenario() -> None:
        game = JianzhongGameState()
        _with_fake_server(game)
        game.player_list[1].hand_tiles = [15, 15, 15, 15]
        game.waiting_players_list = [1]
        game.action_dict = {0: [], 1: ["angang"], 2: [], 3: []}

        await get_action(game, "conn-102", "angang", target_tile=15)

        queued = await game.action_queues[1].get()
        assert queued["action_type"] == "angang"
        assert queued["target_tile"] == 15

    asyncio.run(scenario())


def test_get_action_rejects_illegal_cut_payload() -> None:
    async def scenario() -> None:
        game = JianzhongGameState()
        _with_fake_server(game)
        game.player_list[0].hand_tiles = [11, 12, 13]
        game.waiting_players_list = [0]
        game.action_dict = {0: ["cut"], 1: [], 2: [], 3: []}

        await get_action(game, "conn-101", "cut", TileId=19, cutIndex=0)

        assert game.action_queues[0].empty()
        assert not game.action_events[0].is_set()

    asyncio.run(scenario())


def test_get_action_ignores_stale_response_tick() -> None:
    async def scenario() -> None:
        game = JianzhongGameState()
        _with_fake_server(game)
        game.game_status = "waiting_action_after_cut"
        game.server_action_tick = 5
        game.waiting_players_list = [1]
        game.action_dict = {0: [], 1: ["hu", "pass"], 2: [], 3: []}

        await get_action(game, "conn-102", "hu", action_tick=4)

        assert game.action_queues[1].empty()
        assert not game.action_events[1].is_set()

    asyncio.run(scenario())


def test_get_action_accepts_ready_with_stale_previous_ask_tick() -> None:
    async def scenario() -> None:
        game = JianzhongGameState()
        _with_fake_server(game)
        game.game_status = "waiting_ready"
        game.server_action_tick = 6
        game.waiting_players_list = [0]
        game.action_dict = {0: ["ready"], 1: [], 2: [], 3: []}

        await get_action(game, "conn-101", "ready", action_tick=5)

        queued = await game.action_queues[0].get()
        assert queued["action_type"] == "ready"
        assert game.action_events[0].is_set()

    asyncio.run(scenario())


def test_get_action_ignores_late_ready_after_ready_window_closed() -> None:
    async def scenario() -> None:
        game = JianzhongGameState()
        _with_fake_server(game)
        game.game_status = "waiting"
        game.server_action_tick = 7
        game.waiting_players_list = []
        game.action_dict = {0: [], 1: [], 2: [], 3: []}

        await get_action(game, "conn-101", "ready", action_tick=6)

        assert game.action_queues[0].empty()
        assert not game.action_events[0].is_set()

    asyncio.run(scenario())


def test_get_action_ignores_ready_during_non_ready_window() -> None:
    async def scenario() -> None:
        game = JianzhongGameState()
        _with_fake_server(game)
        game.game_status = "waiting_hand_action"
        game.server_action_tick = 8
        game.waiting_players_list = [0]
        game.action_dict = {0: ["cut"], 1: [], 2: [], 3: []}

        await get_action(game, "conn-101", "ready", action_tick=7)

        assert game.action_queues[0].empty()
        assert not game.action_events[0].is_set()

    asyncio.run(scenario())


def test_get_action_normalizes_zero_self_draw_target_tile() -> None:
    async def scenario() -> None:
        game = JianzhongGameState()
        _with_fake_server(game)
        game.player_list[0].hand_tiles = [11, 12, 13, 14]
        game.waiting_players_list = [0]
        game.action_dict = {0: ["hu_self"], 1: [], 2: [], 3: []}

        await get_action(game, "conn-101", "hu_self", target_tile=0)

        queued = await game.action_queues[0].get()
        assert queued["action_type"] == "hu_self"
        assert queued["target_tile"] is None
        assert game.action_events[0].is_set()

    asyncio.run(scenario())


def run() -> None:
    tests = [
        test_get_ai_action_queues_cut_action,
        test_get_action_maps_connection_to_player_index,
        test_get_action_rejects_illegal_cut_payload,
        test_get_action_ignores_stale_response_tick,
        test_get_action_accepts_ready_with_stale_previous_ask_tick,
        test_get_action_ignores_late_ready_after_ready_window_closed,
        test_get_action_ignores_ready_during_non_ready_window,
        test_get_action_normalizes_zero_self_draw_target_tile,
    ]
    for test in tests:
        test()
    print(f"jianzhong get_action tests ok: {len(tests)} tests")


if __name__ == "__main__":
    run()
