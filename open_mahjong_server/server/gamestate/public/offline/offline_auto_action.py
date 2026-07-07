# 掉线玩家托管：与 AI 机器人逻辑分离，只摸切、不自动补花/和/杠
import asyncio
import logging

from ..ai.get_action import get_ai_action
from ..ai.smart_bot_logic import first_dingque_tile
from ..hand_slot_utils import has_draw_slot, infer_bot_cut_class

logger = logging.getLogger(__name__)

_PASS_WAIT_STATUSES = ("waiting_action_after_cut", "waiting_action_qianggang")
_OFFLINE_DELAY = 0.5


def _is_flower_tile(tile_id: int) -> bool:
    return tile_id >= 50


def _pick_offline_cut_tile(player):
    """掉线托管：摸切优先，不切花牌；定缺花色仍优先（与服务端 _enforce_dingque_first 一致）。"""
    hand = player.hand_tiles
    dingque = getattr(player, "dingque_suit", 0)
    dingque_tile = first_dingque_tile(hand, dingque)
    if dingque_tile is not None:
        tile_id = dingque_tile
        cut_index = next(i for i, t in enumerate(hand) if t == tile_id)
    else:
        cut_index = len(hand) - 1
        tile_id = hand[cut_index]
        if _is_flower_tile(tile_id):
            cut_index = -1
            tile_id = None
            for i in range(len(hand) - 1, -1, -1):
                if not _is_flower_tile(hand[i]):
                    tile_id = hand[i]
                    cut_index = i
                    break
            if tile_id is None:
                tile_id = hand[-1]
                cut_index = len(hand) - 1
    is_moqie = infer_bot_cut_class(hand, tile_id, cut_index, draw_slot=has_draw_slot(player))
    return tile_id, cut_index, is_moqie


async def _submit_pass_when_ready(game_state, player_index: int, action_list: list, current_player) -> bool:
    """鸣牌/抢杠询问：等 wait_action 建立 waiting_players_list 后立即 pass。"""
    if "pass" not in action_list:
        return False
    for _ in range(200):
        if player_index in getattr(game_state, "waiting_players_list", []):
            logger.info(f"掉线托管 {player_index} ({current_player.username}) 选择 pass")
            await get_ai_action(game_state, player_index, "pass", None, None, None, None)
            return True
        await asyncio.sleep(0.01)
    logger.warning(
        f"掉线托管失败：玩家 {player_index} ({current_player.username}) 未进入 waiting_players_list"
    )
    return False


async def offline_auto_action(game_state, player_index: int, action_list: list, game_status: str):
    """
    掉线玩家托管：鸣牌/抢杠/补花轮一律 pass，行牌只摸切，不自动补花/和/杠。
    """
    try:
        current_player = game_state.player_list[player_index]

        if game_status in _PASS_WAIT_STATUSES:
            await _submit_pass_when_ready(game_state, player_index, action_list, current_player)
            return

        if game_status == "waiting_buhua_round":
            await asyncio.sleep(_OFFLINE_DELAY)
            if "pass" in action_list:
                logger.info(f"掉线托管 {player_index} ({current_player.username}) 选择 pass（补花轮）")
                await get_ai_action(game_state, player_index, "pass", None, None, None, None)
            return

        if game_status == "waiting_hand_action":
            await asyncio.sleep(_OFFLINE_DELAY)
            if "cut" in action_list and current_player.hand_tiles:
                tile_id, cut_index, is_moqie = _pick_offline_cut_tile(current_player)
                logger.info(
                    f"掉线托管 {player_index} ({current_player.username}) 选择 cut, tile_id={tile_id}, moqie={is_moqie}"
                )
                await get_ai_action(game_state, player_index, "cut", is_moqie, tile_id, cut_index, None)
            return

        if game_status == "onlycut_after_action":
            cp = bool(getattr(game_state, "claim_protection", False))
            await asyncio.sleep(_OFFLINE_DELAY * (2 if cp else 1))
            if "cut" in action_list and current_player.hand_tiles:
                tile_id, cut_index, is_moqie = _pick_offline_cut_tile(current_player)
                logger.info(
                    f"掉线托管 {player_index} ({current_player.username}) 选择 cut, tile_id={tile_id}, moqie={is_moqie}"
                )
                await get_ai_action(game_state, player_index, "cut", is_moqie, tile_id, cut_index, None)
            return

        logger.warning(f"掉线托管 {player_index} 遇到未知游戏状态: {game_status}")

    except Exception as e:
        logger.error(f"掉线托管 {player_index} 自动操作失败: {e}", exc_info=True)
