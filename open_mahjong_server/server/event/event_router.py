"""
赛事相关 WebSocket 消息（type 以 event/ 开头）。
"""
import logging
from typing import Optional

from ..response import Response

logger = logging.getLogger(__name__)


def _require_login(game_server, Connect_id: str) -> Optional[tuple]:
    player = game_server.players.get(Connect_id)
    if not player or not player.user_id:
        return None
    return player.user_id, player.websocket


async def _send(websocket, response: Response):
    try:
        await websocket.send_json(response.dict(exclude_none=True))
    except Exception as exc:  # pragma: no cover
        logger.warning(f"event _send 失败: {exc}")


async def handle_event_message(game_server, Connect_id: str, message: dict, websocket):
    message_type = message.get("type", "").strip("/")

    auth = _require_login(game_server, Connect_id)
    if auth is None:
        await _send(
            websocket,
            Response(type=message_type, success=False, message="请先登录"),
        )
        return
    user_id, _ws = auth

    try:
        if message_type == "event/list_my_active":
            events = game_server.db_manager.list_user_active_events(user_id)
            await _send(
                websocket,
                Response(
                    type="event/list_my_active",
                    success=True,
                    message="ok",
                    event_list=events,
                ),
            )
        else:
            logger.warning(f"未知的赛事消息路径: {message_type}")
            await _send(
                websocket,
                Response(type=message_type, success=False, message="未知的赛事请求"),
            )
    except Exception as exc:
        logger.error(f"处理 {message_type} 失败: {exc}", exc_info=True)
        await _send(
            websocket,
            Response(type=message_type, success=False, message="服务器异常"),
        )
