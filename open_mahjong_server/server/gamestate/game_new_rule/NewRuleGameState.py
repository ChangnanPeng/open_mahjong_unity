from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .init_tiles import init_new_rule_tiles

logger = logging.getLogger(__name__)


@dataclass
class NewRulePlayer:
    user_id: int
    username: str
    remaining_time: int = 0
    hand_tiles: list[int] = field(default_factory=list)
    discard_tiles: list[int] = field(default_factory=list)
    discard_origin_tiles: list[int] = field(default_factory=list)
    combination_tiles: list[str] = field(default_factory=list)
    combination_mask: list = field(default_factory=list)
    score: int = 0
    player_index: int = 0
    original_player_index: int = 0
    tag_list: list[str] = field(default_factory=list)
    waiting_tiles: set[int] = field(default_factory=set)
    is_hu: bool = False
    hu_order: int = 0
    has_draw_slot: bool = False
    discard_win_lockout_tiles: set[int] = field(default_factory=set)

    @property
    def is_bot(self) -> bool:
        return self.user_id <= 10

    def get_tile(self, tiles_list: list[int], *, mark_draw_slot: bool = True) -> int:
        tile = tiles_list.pop(0)
        self.hand_tiles.append(tile)
        if mark_draw_slot:
            self.has_draw_slot = True
        return tile

    def reset_for_round(self) -> None:
        self.hand_tiles = []
        self.discard_tiles = []
        self.discard_origin_tiles = []
        self.combination_tiles = []
        self.combination_mask = []
        self.tag_list = []
        self.waiting_tiles = set()
        self.is_hu = False
        self.hu_order = 0
        self.has_draw_slot = False
        self.discard_win_lockout_tiles = set()


class NewRuleGameState:
    """Small testable skeleton for the new rule's hand flow.

    This class is not yet a live network game state. It captures the invariants
    we want before wiring into the existing async game loop.
    """

    def __init__(
        self,
        game_server: Any = None,
        room_data: Optional[Dict[str, Any]] = None,
        calculation_service: Any = None,
        db_manager: Any = None,
        gamestate_id: str = "new-rule-test",
    ):
        room_data = room_data or self._default_room_data()
        self.game_server = game_server
        self.calculation_service = calculation_service
        self.db_manager = db_manager
        self.gamestate_id = gamestate_id
        self.room_id = room_data["room_id"]
        self.tips = room_data.get("tips", False)
        self.max_round = room_data.get("game_round", 1)
        self.step_time = room_data.get("step_timer", 0)
        self.round_time = room_data.get("round_timer", 0)
        self.room_rule = room_data.get("room_rule", "new_rule")
        self.room_type = room_data.get("room_type", "custom")
        self.sub_rule = room_data.get("sub_rule", "new_rule/standard")
        self.room_random_seed = room_data.get("random_seed", 0)
        self.allow_spectator_config = False
        self.spectator_enabled = False
        self.realtime_spectators = []

        self.player_list: List[NewRulePlayer] = []
        player_settings = room_data.get("player_settings", {})
        for index, user_id in enumerate(room_data["player_list"]):
            settings = player_settings.get(user_id, {})
            username = settings.get("username", f"用户{user_id}")
            player = NewRulePlayer(user_id, username, room_data.get("round_timer", 0))
            player.player_index = index
            player.original_player_index = index
            self.player_list.append(player)

        self.tiles_list: list[int] = []
        self.current_player_index = 0
        self.dealer_index = 0
        self.current_round = 1
        self.round_index = 1
        self.round_random_seed = self._derive_round_seed()
        self.hu_order_counter = 0
        self.deferred_hu_settlements: list[dict] = []
        self.deferred_scores_applied = False
        self.ended_by: str | None = None
        self.game_status = "waiting"
        self.dead_wall_count = 0
        self.server_action_tick = 0
        self.game_task: Optional[asyncio.Task] = None
        self.action_events: Dict[int, asyncio.Event] = {i: asyncio.Event() for i in range(4)}
        self.action_queues: Dict[int, asyncio.Queue] = {i: asyncio.Queue() for i in range(4)}
        self.waiting_players_list: list[int] = []
        self.action_dict: Dict[int, list[str]] = {i: [] for i in range(4)}
        self.live_pending_window: Optional[dict] = None
        self.outbound_payloads: list[dict] = []
        self.outbound_send_cursor = 0
        self.websocket_sent_payloads: list[dict] = []
        self.action_priority: Dict[str, int] = {
            "hu_self": 6,
            "hu": 5,
            "angang": 3,
            "jiagang": 3,
            "peng": 2,
            "gang": 2,
            "chi_left": 1,
            "chi_mid": 1,
            "chi_right": 1,
            "pass": 0,
            "cut": 0,
        }

    async def run_game_loop(self) -> None:
        """Draft local live loop.

        This loop wires action windows to hidden-information-safe payload
        builders and sends them to connected players when a lightweight
        game_server connection map is available.
        """
        try:
            self.initialize_round()
            self.open_action_window(self.begin_hand_action(self.current_player_index))
            await self.flush_outbound_payloads()
            while self.game_status != "END":
                await self.resolve_action_window()
                await self.flush_outbound_payloads()
        except asyncio.CancelledError:
            logger.info("New rule draft game loop cancelled, room_id=%s", self.room_id)
            raise
        except Exception as exc:
            logger.error("New rule draft game loop failed, room_id=%s: %s", self.room_id, exc, exc_info=True)
            raise

    async def cleanup_game_state(self) -> None:
        """Cancel the live loop task if one was attached by a future manager."""
        if self.game_task and not self.game_task.done():
            self.game_task.cancel()
            try:
                await self.game_task
            except asyncio.CancelledError:
                logger.info("New rule game loop cancelled, room_id=%s", self.room_id)
            except Exception as exc:
                logger.error("Error while cancelling new rule game loop, room_id=%s: %s", self.room_id, exc)

    async def player_disconnect(self, user_id: int) -> None:
        """Mark a player offline; broadcast/reconnect payloads are future live work."""
        for player in self.player_list:
            if player.user_id == user_id:
                if "offline" not in player.tag_list:
                    player.tag_list.append("offline")
                break

    async def player_reconnect(self, user_id: int) -> None:
        """Clear offline marker and send a sanitized reconnect snapshot if possible."""
        for player in self.player_list:
            if player.user_id == user_id:
                if "offline" in player.tag_list:
                    player.tag_list.remove("offline")
                await self.send_payload_to_player(
                    player.player_index,
                    self.build_reconnect_payload(player.player_index),
                )
                break

    async def submit_action(
        self,
        player_index: int,
        action_type: str,
        *,
        target_tile: Optional[int] = None,
        tile_id: Optional[int] = None,
        cut_index: int = -1,
    ) -> None:
        """Queue a client-style action for the currently waiting player."""
        if player_index not in self.waiting_players_list:
            raise ValueError(f"Player {player_index} is not waiting for action.")
        if action_type not in self.action_dict.get(player_index, []):
            raise ValueError(
                f"Action {action_type} is not legal for player {player_index}: "
                f"{self.action_dict.get(player_index, [])}"
            )
        await self.action_queues[player_index].put(
            {
                "player_index": player_index,
                "action_type": action_type,
                "target_tile": target_tile,
                "tile_id": tile_id,
                "cut_index": cut_index,
            }
        )
        self.action_events[player_index].set()

    async def wait_action(self, timeout: Optional[float] = None) -> Dict[int, dict]:
        """Collect queued actions for the current action_dict.

        This is a small adapter for tests and future live-loop wiring. It does
        not resolve priority or mutate hand state; the public driver helpers do
        that after the selected responses are known.
        """
        self.waiting_players_list = [idx for idx, actions in self.action_dict.items() if actions]
        for idx in range(4):
            self.action_events[idx].clear()
            while not self.action_queues[idx].empty():
                self.action_queues[idx].get_nowait()

        results: Dict[int, dict] = {}
        for idx in list(self.waiting_players_list):
            if self.player_list[idx].is_bot:
                action = self._default_bot_action(idx)
                if action is not None:
                    results[idx] = action
                    self.action_dict[idx] = []
                    self.waiting_players_list.remove(idx)

        deadline = None if timeout is None else asyncio.get_running_loop().time() + timeout
        while self.waiting_players_list:
            wait_tasks = {
                asyncio.create_task(self.action_events[idx].wait()): idx
                for idx in self.waiting_players_list
            }
            wait_timeout = None if deadline is None else max(0.0, deadline - asyncio.get_running_loop().time())
            done, pending = await asyncio.wait(wait_tasks.keys(), timeout=wait_timeout, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            if not done:
                break
            for task in done:
                idx = wait_tasks[task]
                if not self.action_queues[idx].empty():
                    results[idx] = await self.action_queues[idx].get()
                    self.action_dict[idx] = []
                    self.action_events[idx].clear()
                    self.waiting_players_list.remove(idx)

        for idx in list(self.waiting_players_list):
            if "pass" in self.action_dict.get(idx, []):
                results[idx] = {"player_index": idx, "action_type": "pass", "target_tile": None, "tile_id": None, "cut_index": -1}
                self.action_dict[idx] = []
                self.waiting_players_list.remove(idx)
        return results

    def _default_bot_action(self, player_index: int) -> Optional[dict]:
        actions = self.action_dict.get(player_index, [])
        if not actions:
            return None
        if "pass" in actions:
            return {
                "player_index": player_index,
                "action_type": "pass",
                "target_tile": None,
                "tile_id": None,
                "cut_index": -1,
            }
        if "cut" in actions and self.player_list[player_index].hand_tiles:
            return {
                "player_index": player_index,
                "action_type": "cut",
                "target_tile": None,
                "tile_id": self.player_list[player_index].hand_tiles[0],
                "cut_index": 0,
            }
        return None

    def open_action_window(self, window: dict) -> dict:
        """Expose a driver window through live-loop action fields."""
        self.live_pending_window = window
        self.game_status = window.get("status", self.game_status)
        actions = window.get("actions") or {}
        self.action_dict = {idx: list(actions.get(idx, [])) for idx in range(4)}
        self.waiting_players_list = [idx for idx, items in self.action_dict.items() if items]
        self.server_action_tick += 1
        window["action_tick"] = self.server_action_tick
        self.emit_window_payloads(window)
        return window

    def emit_window_payloads(self, window: dict) -> list[dict]:
        """Record payloads that a future WebSocket layer would send."""
        from .boardcast import ask_action_payload, final_settlement_payload

        payloads: list[dict] = []
        if window.get("status") == "END":
            payloads = [final_settlement_payload(self, idx) for idx in range(4)]
        else:
            cut_tile = window.get("tile") if window.get("status") == "waiting_discard_response" else None
            rob_kong_tile = window.get("tile") if window.get("status") == "waiting_rob_kong" else None
            for idx, actions in self.action_dict.items():
                if actions:
                    payloads.append(
                        ask_action_payload(
                            self,
                            idx,
                            actions,
                            cut_tile=cut_tile,
                            rob_kong_tile=rob_kong_tile,
                        )
                    )
        self.outbound_payloads.extend(payloads)
        return payloads

    def emit_visible_action_payloads(self, action_info: dict, *, reveal_final: bool = False) -> list[dict]:
        from .boardcast import visible_action_payload

        payloads = [
            {
                **visible_action_payload(self, idx, action_info, reveal_final=reveal_final),
                "player_index": idx,
            }
            for idx in range(4)
        ]
        self.outbound_payloads.extend(payloads)
        return payloads

    def build_reconnect_payload(self, player_index: int) -> dict:
        from .boardcast import reconnect_payload

        return reconnect_payload(self, player_index)

    async def flush_outbound_payloads(self) -> None:
        """Send newly recorded payloads to connected players where possible."""
        while self.outbound_send_cursor < len(self.outbound_payloads):
            payload = self.outbound_payloads[self.outbound_send_cursor]
            self.outbound_send_cursor += 1
            player_index = payload.get("player_index")
            if player_index is None:
                continue
            await self.send_payload_to_player(player_index, payload, record_fallback=False)

    async def send_payload_to_player(
        self,
        player_index: int,
        payload: dict,
        *,
        record_fallback: bool = True,
    ) -> bool:
        """Send a payload to one player, or keep it in the local outbox when offline."""
        if player_index not in range(len(self.player_list)):
            raise ValueError(f"Invalid player index for payload send: {player_index}")
        payload.setdefault("player_index", player_index)
        player = self.player_list[player_index]
        connection = None
        if self.game_server is not None:
            connection = getattr(self.game_server, "user_id_to_connection", {}).get(player.user_id)
        if connection is not None and getattr(connection, "websocket", None) is not None:
            await connection.websocket.send_json(payload)
            self.websocket_sent_payloads.append(payload)
            return True
        if record_fallback:
            self.outbound_payloads.append(payload)
        return False

    async def resolve_action_window(
        self,
        timeout: Optional[float] = None,
        *,
        settlements: Optional[Dict[int, dict]] = None,
    ) -> dict:
        """Wait for the current live window and apply the queued actions."""
        if self.live_pending_window is None:
            raise ValueError("No live action window is open.")
        window = self.live_pending_window
        results = await self.wait_action(timeout)
        return self.apply_action_results(window, results, settlements=settlements)

    def apply_action_results(
        self,
        window: dict,
        action_results: Dict[int, dict],
        *,
        settlements: Optional[Dict[int, dict]] = None,
    ) -> dict:
        """Apply collected live-loop actions using the tested driver helpers."""
        status = window.get("status")
        settlements = settlements or {}

        if status in {"waiting_hand_action", "waiting_only_cut"}:
            player_index = window["player"]
            action_data = action_results.get(player_index)
            if action_data is None:
                raise ValueError(f"Missing action for player {player_index}.")
            action = action_data["action_type"]
            tile = action_data.get("tile_id") if action == "cut" else action_data.get("target_tile")
            if action == "hu_self":
                tile = tile if tile is not None else self.player_list[player_index].hand_tiles[-1]
            next_window = self.apply_turn_action(
                player_index,
                action,
                tile=tile,
                settlement=settlements.get(player_index),
            )
            self.emit_visible_action_payloads(
                {
                    "action": action,
                    "player": player_index,
                    "tile": tile,
                    "cut_index": action_data.get("cut_index"),
                },
                reveal_final=next_window.get("status") == "END",
            )
            return self.open_action_window(next_window)

        if status == "waiting_discard_response":
            discarder_index = window["player"]
            tile = window["tile"]
            win_responses: Dict[int, str] = {}
            claim_responses: Dict[int, str] = {}
            for player_index, action_data in action_results.items():
                action = action_data["action_type"]
                if action in {"hu", "pass", "", "none"}:
                    win_responses[player_index] = action
                if action in {"chi_left", "chi_mid", "chi_right", "peng", "gang", "pass", "", "none"}:
                    claim_responses[player_index] = action
            next_window = self.continue_after_discard_responses(
                discarder_index,
                tile,
                win_responses,
                claim_responses,
                settlements=settlements,
            )
            claim_result = next_window.get("claim_result") or next_window.get("result") or {}
            if claim_result.get("claimed"):
                self.emit_visible_action_payloads(
                    {
                        "action": claim_result.get("action"),
                        "player": claim_result.get("claimant"),
                        "tile": tile,
                        "meld_code": claim_result.get("meld_code"),
                        "combination_mask": claim_result.get("combination_mask"),
                    },
                )
            if next_window.get("drawn_tile") is not None and next_window.get("player") is not None:
                self.emit_visible_action_payloads(
                    {
                        "action": "deal_tile",
                        "player": next_window.get("player"),
                        "tile": next_window.get("drawn_tile"),
                    },
                )
            return self.open_action_window(next_window)

        if status == "waiting_rob_kong":
            kong_player_index = window["player"]
            tile = window["tile"]
            responses = {player_index: data["action_type"] for player_index, data in action_results.items()}
            next_window = self.continue_after_rob_kong_responses(
                kong_player_index,
                tile,
                responses,
                settlements=settlements,
            )
            if next_window.get("drawn_tile") is not None and next_window.get("player") is not None:
                self.emit_visible_action_payloads(
                    {
                        "action": "deal_tile",
                        "player": next_window.get("player"),
                        "tile": next_window.get("drawn_tile"),
                    },
                )
            return self.open_action_window(next_window)

        if status == "END":
            return window
        raise ValueError(f"Unsupported live action window status: {status}")

    @staticmethod
    def _default_room_data() -> Dict[str, Any]:
        return {
            "room_id": "new-rule-test-room",
            "player_list": [101, 102, 103, 104],
            "player_settings": {},
            "round_timer": 0,
            "step_timer": 0,
            "game_round": 1,
            "room_rule": "new_rule",
            "room_type": "custom",
            "tips": False,
            "random_seed": 1,
        }

    def _derive_round_seed(self) -> int:
        seed = self.room_random_seed or 1
        return seed * 1009 + self.current_round

    def reset_round_state(self) -> None:
        for player in self.player_list:
            player.reset_for_round()
        self.tiles_list = []
        self.current_player_index = self.dealer_index
        self.hu_order_counter = 0
        self.deferred_hu_settlements = []
        self.deferred_scores_applied = False
        self.ended_by = None
        self.game_status = "waiting"
        self.round_random_seed = self._derive_round_seed()

    def initialize_round(self) -> None:
        self.reset_round_state()
        init_new_rule_tiles(self)
        self.current_player_index = self.dealer_index
        self.game_status = "waiting_hand_action"

    def begin_hand_action(self, player_index: Optional[int] = None, *, is_get_gang_tile: bool = False) -> dict:
        """Refresh waiting cache and return actions after a draw or supplement draw."""
        from .action_check import check_action_hand_action, refresh_waiting_tiles

        player_index = self.current_player_index if player_index is None else player_index
        self.current_player_index = player_index
        refresh_waiting_tiles(self, player_index, exclude_last_tile=True)
        self.game_status = "waiting_hand_action"
        return {
            "status": self.game_status,
            "player": player_index,
            "actions": check_action_hand_action(self, player_index, is_get_gang_tile=is_get_gang_tile),
        }

    def begin_only_cut(self, player_index: int) -> dict:
        """Return the forced-discard action window after chi or peng."""
        from .action_check import check_only_cut

        self.current_player_index = player_index
        self.game_status = "waiting_only_cut"
        return {
            "status": self.game_status,
            "player": player_index,
            "actions": check_only_cut(self, player_index),
        }

    def apply_turn_action(
        self,
        player_index: int,
        action: str,
        *,
        tile: Optional[int] = None,
        settlement: Optional[dict] = None,
    ) -> dict:
        """Apply one selected self/turn action and return the next response window."""
        from .action_check import check_action_after_cut, check_action_jiagang, refresh_waiting_tiles

        if action == "cut":
            if tile is None:
                raise ValueError("Discard action requires a tile.")
            cut_tile = self.record_discard(player_index, tile)
            for other in self.player_list:
                if other.player_index != player_index and not other.is_hu:
                    refresh_waiting_tiles(self, other.player_index)
            self.game_status = "waiting_discard_response"
            return {
                "status": self.game_status,
                "player": player_index,
                "tile": cut_tile,
                "actions": check_action_after_cut(self, cut_tile),
            }

        if action == "hu_self":
            win_tile = tile if tile is not None else self.player_list[player_index].hand_tiles[-1]
            self.record_self_draw_win(player_index, win_tile, settlement)
            if self.game_status == "END":
                return {"status": self.game_status, "player": player_index, "tile": win_tile, "actions": None}
            drawn_tile = self.draw_after_discard_resolution(player_index)
            if drawn_tile is None:
                return {"status": self.game_status, "player": None, "tile": None, "actions": None}
            next_window = self.begin_hand_action(self.current_player_index)
            next_window["drawn_tile"] = drawn_tile
            return next_window

        if action == "angang":
            if tile is None:
                raise ValueError("Concealed-kong action requires a tile.")
            result = self.declare_concealed_kong(player_index, tile)
            next_window = self.begin_hand_action(player_index, is_get_gang_tile=True)
            next_window["result"] = result
            return next_window

        if action == "jiagang":
            if tile is None:
                raise ValueError("Added-kong action requires a tile.")
            result = self.attempt_added_kong(player_index, tile)
            for other in self.player_list:
                if other.player_index != player_index and not other.is_hu:
                    refresh_waiting_tiles(self, other.player_index)
            return {
                "status": self.game_status,
                "player": player_index,
                "tile": tile,
                "result": result,
                "actions": check_action_jiagang(self, tile),
            }

        raise ValueError(f"Unsupported turn action: {action}")

    def _build_hu_settlement(
        self,
        winner_index: int,
        source: str,
        tile: int,
        *,
        payer_index: Optional[int] = None,
    ) -> dict:
        """Calculate deferred scoring details for a confirmed win."""
        from ...game_calculation.new_rule import HandContext, score_hand

        player = self.player_list[winner_index]
        hand_tiles = list(player.hand_tiles)
        if source != "self_draw":
            hand_tiles.append(tile)

        context = {
            "win_source": source,
            "chankan": source == "rob_kong",
        }
        if self.calculation_service is not None and hasattr(self.calculation_service, "NewRule_hepai_detail"):
            detail = self.calculation_service.NewRule_hepai_detail(
                hand_tiles,
                player.combination_tiles,
                [],
                tile,
                context,
            )
        else:
            result = score_hand(
                HandContext(
                    hand_tiles=hand_tiles,
                    meld_codes=player.combination_tiles,
                    winning_tile=tile,
                    win_source=source,
                    chankan=source == "rob_kong",
                )
            )
            detail = {
                "is_win": result.is_win,
                "points": result.points,
                "raw_points": result.raw_points,
                "fan_ids": list(result.fan_ids),
                "fan_names": list(result.fan_names),
            }
        if not detail["is_win"]:
            raise ValueError(f"Confirmed win for player {winner_index} is not a valid new-rule hand.")
        return {
            "is_win": detail["is_win"],
            "points": detail["points"],
            "raw_points": detail["raw_points"],
            "fan_ids": list(detail["fan_ids"]),
            "fan_names": list(detail["fan_names"]),
            "score_changes": self._score_changes_for_win(winner_index, source, detail["points"], payer_index),
        }

    def _score_changes_for_win(
        self,
        winner_index: int,
        source: str,
        points: int,
        payer_index: Optional[int] = None,
    ) -> list[int]:
        changes = [0 for _ in self.player_list]
        if points <= 0:
            return changes
        if source == "self_draw":
            payers = [
                player.player_index
                for player in self.player_list
                if player.player_index != winner_index and not player.is_hu
            ]
            if not payers:
                return changes
            if len(payers) == 3:
                payment = points * 2
            elif len(payers) == 2:
                payment = points * 3
            else:
                payment = points * 6
            for payer in payers:
                changes[payer] -= payment
                changes[winner_index] += payment
            return changes

        if payer_index is None:
            raise ValueError(f"{source} win needs a payer index for score changes.")
        payment = points * 6
        changes[payer_index] -= payment
        changes[winner_index] += payment
        return changes

    def continue_after_discard_responses(
        self,
        discarder_index: int,
        tile: int,
        win_responses: Dict[int, str],
        claim_responses: Optional[Dict[int, str]] = None,
        settlements: Optional[Dict[int, dict]] = None,
    ) -> dict:
        """Resolve a discard response window and return a consistent next window."""
        win_result = self.resolve_discard_win_responses(discarder_index, tile, win_responses, settlements)
        if win_result["winners"]:
            return self._window_after_draw_result(win_result, "discard_win", {"win_result": win_result})
        if self.game_status == "END":
            return self._end_window({"win_result": win_result})

        claim_result = self.resolve_discard_claim_responses(discarder_index, tile, claim_responses or {})
        if not claim_result["claimed"]:
            return self._window_after_draw_result(
                claim_result,
                "discard_no_claim",
                {"win_result": win_result, "claim_result": claim_result},
            )
        if claim_result["action"] == "gang":
            window = self.begin_hand_action(claim_result["claimant"], is_get_gang_tile=True)
            window["reason"] = "discard_gang"
            window["claim_result"] = claim_result
            return window
        window = self.begin_only_cut(claim_result["claimant"])
        window["reason"] = "discard_claim"
        window["claim_result"] = claim_result
        return window

    def continue_after_rob_kong_responses(
        self,
        kong_player_index: int,
        tile: int,
        responses: Dict[int, str],
        settlements: Optional[Dict[int, dict]] = None,
    ) -> dict:
        """Resolve a robbing-kong response window and return a consistent next window."""
        result = self.resolve_added_kong_responses(kong_player_index, tile, responses, settlements)
        if result["robbed"]:
            return self._window_after_draw_result(result, "rob_kong", {"rob_kong_result": result})
        if self.game_status == "END":
            return self._end_window({"rob_kong_result": result})
        window = self.begin_hand_action(kong_player_index, is_get_gang_tile=True)
        window["reason"] = "added_kong"
        window["drawn_tile"] = result.get("drawn_tile")
        window["rob_kong_result"] = result
        return window

    def next_active_index(self, from_index: int) -> Optional[int]:
        idx = from_index
        for _ in range(4):
            idx = (idx + 1) % 4
            if not self.player_list[idx].is_hu:
                return idx
        return None

    def mark_player_hu(self, player_index: int, settlement: Optional[dict] = None) -> None:
        player = self.player_list[player_index]
        if player.is_hu:
            return
        self.hu_order_counter += 1
        player.is_hu = True
        player.hu_order = self.hu_order_counter
        if settlement is not None:
            self.deferred_hu_settlements.append({**settlement, "winner": player_index, "hu_order": player.hu_order})
        if self.should_end_hand():
            self.ended_by = "win"
            self.game_status = "END"

    def apply_deferred_score_changes(self) -> None:
        """Apply accumulated settlement score changes exactly once at final reveal time."""
        if self.deferred_scores_applied:
            return
        for settlement in self.deferred_hu_settlements:
            changes = settlement.get("score_changes")
            if not changes:
                continue
            for player_index, change in enumerate(changes):
                if player_index < len(self.player_list):
                    self.player_list[player_index].score += change
        self.deferred_scores_applied = True

    def should_end_hand(self) -> bool:
        return self.hu_count >= 3 or len(self.tiles_list) <= self.dead_wall_count

    @property
    def hu_count(self) -> int:
        return sum(1 for player in self.player_list if player.is_hu)

    def advance_dealer_after_round(self) -> int:
        self.dealer_index = (self.dealer_index + 1) % 4
        self.current_round += 1
        self.round_index += 1
        return self.dealer_index

    def clear_lockout_on_discard(self, player_index: int, discarded_tile: int) -> None:
        self.player_list[player_index].discard_win_lockout_tiles = {discarded_tile}

    def add_discard_win_lockout(self, player_index: int, tile: int) -> None:
        self.player_list[player_index].discard_win_lockout_tiles.add(tile)

    def can_win_by_discard(self, player_index: int, tile: int) -> bool:
        return tile not in self.player_list[player_index].discard_win_lockout_tiles

    def record_discard(self, player_index: int, tile: int) -> int:
        """Apply a discard and start the next same-tile discard-win lockout window."""
        player = self.player_list[player_index]
        if player.is_hu:
            raise ValueError("A player who has already won cannot discard.")
        if tile not in player.hand_tiles:
            raise ValueError(f"Player {player_index} cannot discard tile {tile}; it is not in hand.")
        player.hand_tiles.remove(tile)
        player.discard_tiles.append(tile)
        player.discard_origin_tiles.append(tile)
        player.has_draw_slot = False
        self.current_player_index = player_index
        self.clear_lockout_on_discard(player_index, tile)
        return tile

    def record_discard_win_pass(self, player_index: int, tile: int) -> None:
        """Record that a player skipped a currently available discard win."""
        player = self.player_list[player_index]
        if player.is_hu:
            return
        if tile in player.waiting_tiles and self.can_win_by_discard(player_index, tile):
            self.add_discard_win_lockout(player_index, tile)

    def record_discard_win(
        self,
        winner_index: int,
        discarder_index: int,
        tile: int,
        settlement: Optional[dict] = None,
    ) -> None:
        """Record a discard win while deferring fan details until final settlement."""
        if not self.can_win_by_discard(winner_index, tile):
            raise ValueError(f"Player {winner_index} is locked out from winning on tile {tile}.")
        if settlement is None:
            settlement = self._build_hu_settlement(winner_index, "discard", tile, payer_index=discarder_index)
        self.mark_player_hu(
            winner_index,
            {
                "source": "discard",
                "discarder": discarder_index,
                "tile": tile,
                **settlement,
            },
        )

    def record_self_draw_win(self, winner_index: int, tile: int, settlement: Optional[dict] = None) -> None:
        """Record a self-draw win while deferring fan details until final settlement."""
        player = self.player_list[winner_index]
        if player.is_hu:
            return
        if tile not in player.hand_tiles:
            raise ValueError(f"Player {winner_index} cannot self-draw win on tile {tile}; it is not in hand.")
        if settlement is None:
            settlement = self._build_hu_settlement(winner_index, "self_draw", tile)
        self.mark_player_hu(
            winner_index,
            {
                "source": "self_draw",
                "tile": tile,
                **settlement,
            },
        )

    def draw_after_discard_resolution(self, discarder_index: int) -> Optional[int]:
        """Draw for the next active player after all discard responses resolve."""
        next_index = self.next_active_index(discarder_index)
        if next_index is None:
            return None
        self.current_player_index = next_index
        if self.should_end_hand():
            self.ended_by = self.ended_by or "wall"
            self.game_status = "END"
            return None
        return self.player_list[next_index].get_tile(self.tiles_list)

    def resolve_discard_win_responses(
        self,
        discarder_index: int,
        tile: int,
        responses: Dict[int, str],
        settlements: Optional[Dict[int, dict]] = None,
    ) -> dict:
        """Resolve discard-win/pass choices, then continue the blood-battle flow.

        This helper intentionally handles only discard wins and passes. Chi,
        peng, and kong resolution will be layered on later with their own
        priority and follow-up discard rules.
        """
        settlements = settlements or {}
        winners: list[int] = []
        passed: list[int] = []

        for player_index in sorted(responses):
            action = responses[player_index]
            if player_index == discarder_index or self.player_list[player_index].is_hu:
                continue
            if action == "pass":
                self.record_discard_win_pass(player_index, tile)
                passed.append(player_index)
            elif action == "hu":
                if tile not in self.player_list[player_index].waiting_tiles:
                    raise ValueError(f"Player {player_index} is not waiting on tile {tile}.")
                self.record_discard_win(
                    player_index,
                    discarder_index,
                    tile,
                    settlements.get(player_index),
                )
                winners.append(player_index)
            elif action in {"", "none"}:
                continue
            else:
                raise ValueError(f"Unsupported discard-win response: {action}")

        drawn_tile = None
        draw_player = None
        if self.game_status != "END" and winners:
            drawn_tile = self.draw_after_discard_resolution(discarder_index)
            draw_player = self.current_player_index if drawn_tile is not None else None

        return {
            "winners": winners,
            "passed": passed,
            "draw_player": draw_player,
            "drawn_tile": drawn_tile,
            "ended": self.game_status == "END",
        }

    def resolve_discard_claim_responses(
        self,
        discarder_index: int,
        tile: int,
        responses: Dict[int, str],
    ) -> dict:
        """Resolve chi/peng/gang claims after discard wins are declined."""
        claim = self._select_discard_claim(discarder_index, responses)
        if claim is None:
            drawn_tile = self.draw_after_discard_resolution(discarder_index)
            return {
                "claimed": False,
                "claimant": None,
                "action": None,
                "meld_code": None,
                "draw_player": self.current_player_index if drawn_tile is not None else None,
                "drawn_tile": drawn_tile,
                "next_status": self.game_status,
            }

        claimant_index, action = claim
        player = self.player_list[claimant_index]
        meld_code, combination_mask = self._apply_discard_claim(player, tile, action)
        self.current_player_index = claimant_index

        drawn_tile = None
        if action == "gang":
            if not self.tiles_list:
                raise ValueError("Cannot claim a discard kong when the wall is empty.")
            drawn_tile = player.get_tile(self.tiles_list)
            self.game_status = "waiting_hand_action"
        else:
            player.has_draw_slot = False
            self.game_status = "waiting_only_cut"

        return {
            "claimed": True,
            "claimant": claimant_index,
            "action": action,
            "meld_code": meld_code,
            "combination_mask": combination_mask,
            "draw_player": claimant_index if drawn_tile is not None else None,
            "drawn_tile": drawn_tile,
            "next_status": self.game_status,
        }

    def declare_concealed_kong(self, player_index: int, tile: int) -> dict:
        """Declare a concealed kong, store true tile server-side, and draw a supplement."""
        player = self.player_list[player_index]
        self._remove_tiles(player.hand_tiles, [tile, tile, tile, tile])
        player.combination_tiles.append(f"G{tile}")
        drawn_tile = self._draw_supplement_tile(player_index)
        return {
            "player": player_index,
            "action": "angang",
            "meld_code": f"G{tile}",
            "public_meld_code": "G0",
            "drawn_tile": drawn_tile,
            "next_status": self.game_status,
        }

    def attempt_added_kong(self, player_index: int, tile: int) -> dict:
        """Validate an added-kong attempt without mutating state before robbing responses."""
        player = self.player_list[player_index]
        if tile not in player.hand_tiles:
            raise ValueError(f"Player {player_index} cannot add kong tile {tile}; it is not in hand.")
        if f"k{tile}" not in player.combination_tiles:
            raise ValueError(f"Player {player_index} has no exposed triplet k{tile} to upgrade.")
        self.current_player_index = player_index
        self.game_status = "waiting_rob_kong"
        return {
            "player": player_index,
            "tile": tile,
            "action": "jiagang",
            "next_status": self.game_status,
        }

    def resolve_added_kong_responses(
        self,
        kong_player_index: int,
        tile: int,
        responses: Dict[int, str],
        settlements: Optional[Dict[int, dict]] = None,
    ) -> dict:
        """Resolve robbing-kong responses, or finalize the added kong and supplement draw."""
        settlements = settlements or {}
        winners: list[int] = []
        passed: list[int] = []

        for player_index in sorted(responses):
            action = responses[player_index]
            if player_index == kong_player_index or self.player_list[player_index].is_hu:
                continue
            if action == "pass":
                if tile in self.player_list[player_index].waiting_tiles and self.can_win_by_discard(player_index, tile):
                    self.add_discard_win_lockout(player_index, tile)
                passed.append(player_index)
            elif action == "hu":
                if tile not in self.player_list[player_index].waiting_tiles:
                    raise ValueError(f"Player {player_index} is not waiting on added-kong tile {tile}.")
                if not self.can_win_by_discard(player_index, tile):
                    raise ValueError(f"Player {player_index} is locked out from robbing kong tile {tile}.")
                self.mark_player_hu(
                    player_index,
                    {
                        "source": "rob_kong",
                        "kong_player": kong_player_index,
                        "tile": tile,
                        **(
                            settlements.get(player_index)
                            or self._build_hu_settlement(
                                player_index,
                                "rob_kong",
                                tile,
                                payer_index=kong_player_index,
                            )
                        ),
                    },
                )
                winners.append(player_index)
            elif action in {"", "none"}:
                continue
            else:
                raise ValueError(f"Unsupported robbing-kong response: {action}")

        if winners:
            drawn_tile = None
            draw_player = None
            if self.game_status != "END":
                drawn_tile = self.draw_after_discard_resolution(kong_player_index)
                draw_player = self.current_player_index if drawn_tile is not None else None
            return {
                "robbed": True,
                "winners": winners,
                "passed": passed,
                "draw_player": draw_player,
                "drawn_tile": drawn_tile,
                "ended": self.game_status == "END",
            }

        meld_code = self._finalize_added_kong(kong_player_index, tile)
        drawn_tile = self._draw_supplement_tile(kong_player_index)
        return {
            "robbed": False,
            "winners": [],
            "passed": passed,
            "meld_code": meld_code,
            "draw_player": kong_player_index,
            "drawn_tile": drawn_tile,
            "ended": self.game_status == "END",
        }

    def _select_discard_claim(self, discarder_index: int, responses: Dict[int, str]) -> Optional[tuple[int, str]]:
        candidates: list[tuple[int, int, int, str]] = []
        fixed_next_player = (discarder_index + 1) % 4
        priority = {
            "gang": 2,
            "peng": 2,
            "chi_left": 1,
            "chi_mid": 1,
            "chi_right": 1,
        }
        for player_index, action in responses.items():
            if action not in priority:
                continue
            if player_index == discarder_index or self.player_list[player_index].is_hu:
                continue
            if action.startswith("chi") and player_index != fixed_next_player:
                continue
            distance = (player_index - discarder_index) % 4
            candidates.append((-priority[action], distance, player_index, action))
        if not candidates:
            return None
        _, _, player_index, action = min(candidates)
        return player_index, action

    def _apply_discard_claim(self, player: NewRulePlayer, tile: int, action: str) -> tuple[str, list[int]]:
        if action == "peng":
            hand_tiles = [tile, tile]
            self._remove_tiles(player.hand_tiles, hand_tiles)
            meld_code = f"k{tile}"
            combination_mask = [1, tile, 0, hand_tiles[0], 0, hand_tiles[1]]
        elif action == "gang":
            hand_tiles = [tile, tile, tile]
            self._remove_tiles(player.hand_tiles, hand_tiles)
            meld_code = f"g{tile}"
            combination_mask = [1, tile, 0, hand_tiles[0], 0, hand_tiles[1], 0, hand_tiles[2]]
        elif action == "chi_left":
            hand_tiles = [tile - 2, tile - 1]
            self._remove_tiles(player.hand_tiles, hand_tiles)
            meld_code = f"s{tile - 2}"
            combination_mask = [1, tile, 0, hand_tiles[0], 0, hand_tiles[1]]
        elif action == "chi_mid":
            hand_tiles = [tile - 1, tile + 1]
            self._remove_tiles(player.hand_tiles, hand_tiles)
            meld_code = f"s{tile - 1}"
            combination_mask = [1, tile, 0, hand_tiles[0], 0, hand_tiles[1]]
        elif action == "chi_right":
            hand_tiles = [tile + 1, tile + 2]
            self._remove_tiles(player.hand_tiles, hand_tiles)
            meld_code = f"s{tile}"
            combination_mask = [1, tile, 0, hand_tiles[0], 0, hand_tiles[1]]
        else:
            raise ValueError(f"Unsupported discard claim action: {action}")
        player.combination_tiles.append(meld_code)
        player.combination_mask.append(combination_mask)
        return meld_code, combination_mask

    def _finalize_added_kong(self, player_index: int, tile: int) -> str:
        player = self.player_list[player_index]
        self._remove_tiles(player.hand_tiles, [tile])
        try:
            triplet_index = player.combination_tiles.index(f"k{tile}")
        except ValueError as exc:
            raise ValueError(f"Player {player_index} has no exposed triplet k{tile} to upgrade.") from exc
        player.combination_tiles[triplet_index] = f"g{tile}"
        return f"g{tile}"

    def _window_after_draw_result(self, result: dict, reason: str, extra: dict) -> dict:
        if result.get("ended") or self.game_status == "END":
            return self._end_window(extra)
        draw_player = result.get("draw_player")
        if draw_player is None:
            return self._end_window(extra)
        window = self.begin_hand_action(draw_player)
        window["reason"] = reason
        window["drawn_tile"] = result.get("drawn_tile")
        window.update(extra)
        return window

    def _end_window(self, extra: Optional[dict] = None) -> dict:
        payload = {"status": "END", "player": None, "actions": None, "ended_by": self.ended_by}
        if extra:
            payload.update(extra)
        return payload

    def _draw_supplement_tile(self, player_index: int) -> int:
        if not self.tiles_list:
            self.ended_by = self.ended_by or "wall"
            self.game_status = "END"
            raise ValueError("Cannot draw a supplement tile when the wall is empty.")
        self.current_player_index = player_index
        drawn_tile = self.player_list[player_index].get_tile(self.tiles_list)
        self.game_status = "waiting_hand_action"
        return drawn_tile

    @staticmethod
    def _remove_tiles(hand_tiles: list[int], tiles: list[int]) -> None:
        for tile in tiles:
            if tile not in hand_tiles:
                raise ValueError(f"Cannot remove tile {tile}; it is not in hand.")
        for tile in tiles:
            hand_tiles.remove(tile)
