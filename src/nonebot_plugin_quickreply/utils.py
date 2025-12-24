import re
import base64

import httpx
from nonebot import get_plugin_config
from nonebot.log import logger
from nonebot.permission import SUPERUSER
from nonebot.adapters.onebot.v11 import Bot as OneV11Bot
from nonebot.adapters.onebot.v11 import (
    Message,
    MessageEvent,
    MessageSegment,
    GroupMessageEvent,
)

from .config import Config

plugin_config = get_plugin_config(Config).quickreply


def is_only_contains_text(msg: Message | MessageSegment | str) -> bool:
    """检查消息是否仅包含纯文本内容。"""
    if isinstance(msg, str):
        # CQ码解析后仅包含文本
        pattern = "\\[CQ:.*?\\]"
        return not re.search(pattern, msg)
    if isinstance(msg, MessageSegment):
        return msg.type == "text"
    return msg.extract_plain_text().isspace()


async def check_permission_in_group(bot: OneV11Bot, event: MessageEvent) -> bool:
    """检查用户在群组中的权限，只有群主、管理员或超级用户才能通过检查。"""
    if not plugin_config.enable_permission_check:
        return True
    if isinstance(event, GroupMessageEvent):
        # 检查是否为超级用户
        if await SUPERUSER(bot, event):
            return True
        # 获取用户在群组中的角色
        sender_role = getattr(event.sender, "role", "member")
        # 如果是群主或管理员则通过
        return sender_role in ["owner", "admin"]
    # 私聊或非群聊事件，默认无权限（或根据你的逻辑返回True）
    return False


def get_context_id(event: MessageEvent) -> tuple[str, bool]:
    """获取上下文ID，群聊为群号，私聊为 'private_' + 用户号"""
    # 使用 isinstance 进行类型判断
    if isinstance(event, GroupMessageEvent):
        return str(event.group_id), True
    elif event.message_type == "private":
        return f"private_{event.user_id}", False
    return "unknown", False


async def download_image_as_base64(url: str) -> str | None:
    """下载图片并返回Base64编码的字符串"""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, timeout=20)
            resp.raise_for_status()  # 如果下载失败则抛出异常
            return f"base64://{base64.b64encode(resp.content).decode()}"
        except httpx.HTTPError as e:
            # 可以加入日志记录
            logger.error(f"Failed to download image from {url}: {e}")
            return None


async def process_message_for_storage(
    msg: Message,
) -> tuple[Message | None, str | None]:
    """
    处理要存储的消息。
    1. 检查消息是否符合 "文本/图片/图文" 的格式。
    2. 如果有图片，下载并转换为Base64。
    返回 (处理后的Message, 错误信息)
    """
    new_msg = Message()
    # has_image = False
    unsupported_segment = False

    for seg in msg:
        if seg.type == "text" and seg.data["text"].strip():
            new_msg += seg
        elif seg.type == "image":
            url = seg.data.get("url")
            if not url:
                return None, "无法获取图片链接。"

            # 将http/https链接的图片下载并转为base64
            if url.startswith("http"):
                base64_str = await download_image_as_base64(url)
                if not base64_str:
                    return None, "图片下载失败，可能链接已失效。"
                new_msg += MessageSegment.image(base64_str)
            else:  # 如果已经是base64或其他本地格式，直接使用
                new_msg += seg

        elif seg.type == "at":  # 允许 at
            new_msg += seg
        else:
            # 忽略空的文本段或纯粹的换行符
            if seg.type == "text" and not seg.data["text"].strip():
                continue
            unsupported_segment = True

    if unsupported_segment:
        return None, "只支持设置纯文本、单张图片或图文组合的回复。"

    if not new_msg:
        return None, "回复内容不能为空。"

    return new_msg, None
