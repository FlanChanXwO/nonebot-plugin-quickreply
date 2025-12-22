import json

from nonebot import logger, require, on_command, on_message
from nonebot.params import Depends, CommandArg
from nonebot.plugin import PluginMetadata, get_plugin_config
from nonebot.matcher import Matcher
from nonebot.exception import FinishedException
from nonebot.permission import SUPERUSER
from sqlalchemy.ext.asyncio import AsyncSession
from nonebot.adapters.onebot.v11 import (
    Bot,
    Message,
    MessageEvent,
    MessageSegment,
)

require("nonebot_plugin_orm")
from nonebot_plugin_orm import get_session

from . import datasource
from .utils import (
    get_context_id,
    check_permission_in_group,
    process_message_for_storage,
)
from .config import Config

__plugin_meta__ = PluginMetadata(
    name="快捷回复",
    description="一个功能强大的快捷回复插件，支持分群/私聊、配置化限制最大快捷回复数量。",
    usage=(
        "上下文相关指令 (仅在当前群聊/私聊生效):\n"
        "  /设置回复 <关键词> <内容> (内容可以是文字、图片、at等)\n"
        "  (回复一条消息) /设置回复 <关键词> (将回复的消息作为内容)\n"
        "  /回复删除 <关键词>\n"
        "  /回复列表\n"
        "  /清空本群回复 (群管/超管)\n"
        "\n全局指令 (影响您所有的回复):\n"
        "  /清空我的回复\n"
        "  /清空用户回复 <@用户或QQ> (超管)"
    ),
    type="application",
    homepage="https://github.com/FlanChanXwO/nonebot-plugin-quickreply",
    config=Config,
    supported_adapters={"~onebot.v11"},
    extra={"author": "FlanChanXwO", "version": "0.1.13"},
)

plugin_config = get_plugin_config(Config).quickreply

set_reply = on_command("设置回复", aliases={"回复设置"}, priority=10, block=True)
del_reply = on_command(
    "删除回复", aliases={"回复删除", "清除回复"}, priority=10, block=True
)
clear_context_replies = on_command(
    "清空本会话回复",
    aliases={
        "清空本群回复",
        "清空本聊天回复",
        "清除本会话回复",
        "清除本群回复",
        "清除本聊天回复",
    },
    priority=5,
    block=True,
)
list_replies = on_command("回复列表", aliases={"本群回复"}, priority=10, block=True)
list_my_replies = on_command(
    "我的回复列表", aliases={"我的快捷回复"}, priority=10, block=True
)
list_my_replies_in_context = on_command(
    "我在本会话的回复列表",
    aliases={"我在本群的回复列表", "我在本聊天的回复列表"},
    priority=10,
    block=True,
)
clear_my_replies = on_command(
    "清空我的回复", aliases={"清空我的快捷回复"}, priority=10, block=True
)

clear_my_replies_in_context = on_command(
    "清空我在本会话的回复",
    aliases={"清空我在本群的回复", "清空我在本聊天的回复"},
    priority=10,
    block=True,
)

clear_user_replies = on_command(
    "清空用户回复",
    aliases={"清除用户回复"},
    permission=SUPERUSER,
    priority=5,
    block=True,
)
get_reply = on_message(priority=11, block=False)


@set_reply.handle()
async def handle_set_reply(
    matcher: Matcher,
    event: MessageEvent,
    args: Message = CommandArg(),
    session: AsyncSession = Depends(get_session),
):
    context_id, _ = get_context_id(event)
    if context_id == "unknown":
        await matcher.finish("无法识别的会话上下文。")

    key_txt = ""
    value = Message()

    if event.reply:
        key_txt = args.extract_plain_text().strip()
        if not key_txt:
            await matcher.finish("用法: 回复消息后输入 /设置回复 <关键词>")
        if not event.reply.message:
            await matcher.finish("回复的消息内容为空，无法设置。")
        value = event.reply.message
    else:
        # 处理 /设置回复 <key> <value> 的情况
        if not args:
            await matcher.finish("参数不足！\n用法: /设置回复 <关键词> <内容>")

        # 尝试从参数的第一个文本段中分割出key
        if args[0].type == "text":
            first_text_segment = args[0].data.get("text", "")
            # 使用 split 分割第一个词作为 key
            parts = first_text_segment.strip().split(maxsplit=1)
            key_txt = parts[0]

            if not key_txt:
                await matcher.finish("关键词不能为空！")

            # 重建 value
            value_segments = []
            if len(parts) > 1:
                # 如果第一个文本段分割后还有剩余部分，则将其作为 value 的第一个文本段
                value_segments.append(MessageSegment.text(parts[1].lstrip()))

            # 添加 original_message 中剩余的 segments
            if len(args) > 1:
                value_segments.extend(args[1:])

            value = Message(value_segments)

        else:  # 如果第一个 segment 不是文本（例如图片），则无法作为 key
            await matcher.finish("关键词只能是纯文本内容！")

        if not value:
            await matcher.finish("内容不能为空！\n用法: /设置回复 <关键词> <内容>")

    processed_msg, error = (
        await process_message_for_storage(value)
        if plugin_config.enable_base64
        else (value, None)
    )
    if error:
        await matcher.finish(error)

    is_new = not bool(await datasource.get_reply(session, key_txt, context_id))
    if is_new:
        if plugin_config.max_per_user > 0:
            count = await datasource.count_replies_by_user(session, str(event.user_id))
            if count >= plugin_config.max_per_user:
                await matcher.finish(f"您创建的回复已达个人上限({count}条)，无法新增！")
        if plugin_config.max_per_context > 0:
            count = await datasource.count_replies_by_context(session, context_id)
            if count >= plugin_config.max_per_context:
                await matcher.finish(f"本会话的回复已达上限({count}条)，无法新增！")

    serializable_message = [segment.__dict__ for segment in processed_msg]
    message_json = json.dumps(serializable_message, ensure_ascii=False)

    await datasource.set_reply(
        session, key_txt, context_id, message_json, str(event.user_id)
    )

    reply_text = (
        f"快捷回复 '{key_txt}' 已设置成功。"
        if is_new
        else f"快捷回复 '{key_txt}' 已更新。"
    )
    await matcher.finish(reply_text)


@del_reply.handle()
async def handle_del_reply(
    bot: Bot,
    event: MessageEvent,
    matcher: Matcher,
    args: Message = CommandArg(),
    session: AsyncSession = Depends(get_session),
):
    context_id, _ = get_context_id(event)
    key = args.extract_plain_text().strip()
    if not key:
        await matcher.finish("请输入要删除的关键词！")

    reply_to_delete = await datasource.get_reply(session, key, context_id)
    if not reply_to_delete:
        await matcher.finish(f"在本群(会话)中未找到关键词为 '{key}' 的回复。")
    # 检查用户权限
    has_permission = await check_permission_in_group(bot, event)
    if reply_to_delete.creator_id == str(event.user_id) or has_permission:
        await datasource.delete_reply(session, key, context_id)

        await matcher.finish(f"本群(会话)的快捷回复 '{key}' 已删除。")
    else:
        await matcher.finish("您没有权限删除此回复，因为它由其他用户创建。")


@clear_context_replies.handle()
async def handle_clear_context_replies(
    event: MessageEvent,
    matcher: Matcher,
    bot: Bot,
    session: AsyncSession = Depends(get_session),
):
    context_id, is_group = get_context_id(event)

    # 检查用户权限
    if is_group and not await check_permission_in_group(bot, event):
        await matcher.finish(
            "权限不足，只有群主、管理员或超级用户才能清空本群的快捷回复。"
        )

    deleted_count = await datasource.delete_all_replies_in_context(session, context_id)
    if deleted_count > 0:
        await matcher.finish(f"操作成功！已清空本会话的 {deleted_count} 条快捷回复。")
    else:
        await matcher.finish("本会话之前没有创建过任何快捷回复。")


@clear_my_replies_in_context.handle()
async def handle_clear_my_replies_in_context(
    event: MessageEvent,
    matcher: Matcher,
    session: AsyncSession = Depends(get_session),
):
    context_id, _ = get_context_id(event)
    user_id = str(event.user_id)

    deleted_count = await datasource.delete_replies_by_user_in_context(
        session, user_id, context_id
    )

    if deleted_count > 0:
        await matcher.finish(
            f"操作成功！已清空您在本会话创建的 {deleted_count} 条快捷回复。"
        )
    else:
        await matcher.finish("您在本会话之前没有创建过任何快捷回复。")


@list_my_replies.handle()
async def handle_list_my_replies(
    event: MessageEvent,
    matcher: Matcher,
    session: AsyncSession = Depends(get_session),
):
    user_id = str(event.user_id)
    keywords = await datasource.get_all_keywords_by_user(session, user_id)
    if not keywords:
        await matcher.finish("您尚未设置任何快捷回复。")

    reply_text = "您已设置的关键词列表：\n" + "\n".join(f"- {key}" for key in keywords)
    await matcher.finish(reply_text)


@list_replies.handle()
async def handle_list_replies(
    event: MessageEvent,
    matcher: Matcher,
    session: AsyncSession = Depends(get_session),
):
    context_id, _ = get_context_id(event)
    keywords = await datasource.get_all_keywords_in_context(session, context_id)
    if not keywords:
        await matcher.finish("本群(会话)尚未设置任何快捷回复。")

    reply_text = "本群(会话)已设置的关键词列表：\n" + "\n".join(
        f'- "{key}"' for key in keywords
    )
    await matcher.finish(reply_text)


@list_my_replies_in_context.handle()
async def handle_list_my_replies_in_context(
    event: MessageEvent,
    matcher: Matcher,
    session: AsyncSession = Depends(get_session),
):
    context_id, _ = get_context_id(event)
    user_id = str(event.user_id)
    keywords = await datasource.get_keywords_by_user_in_context(
        session, user_id, context_id
    )
    if not keywords:
        await matcher.finish("您在本群(会话)尚未设置任何快捷回复。")

    reply_text = "您在本群(会话)已设置的关键词列表：\n" + "\n".join(
        f"- {key}" for key in keywords
    )
    await matcher.finish(reply_text)


@get_reply.handle()
async def handle_get_reply(
    event: MessageEvent,
    matcher: Matcher,
    session: AsyncSession = Depends(get_session),
):
    context_id, _ = get_context_id(event)
    key = event.get_plaintext().strip()
    if not key or context_id == "unknown":
        return
    reply = await datasource.get_reply(session, key, context_id)
    if reply:
        try:
            # 1. 将 JSON 字符串解析为 Python 列表
            loaded_list = json.loads(reply.message_json)
            # 2. 列表推导，将列表中的每个字典都转回 MessageSegment 对象
            # 3. 将 MessageSegment 对象的列表组合成一个可发送的 Message 对象
            reply_msg = Message([MessageSegment(**data) for data in loaded_list])
            # 4. 发送恢复的消息
            await matcher.finish(reply_msg)
        except FinishedException:
            raise
        except Exception as e:
            logger.error(f"快捷回复 '{key}' (上下文: {context_id}) 解析失败: {e}")
            return


@clear_my_replies.handle()
async def clear_my_replies_start(matcher: Matcher):
    await matcher.pause(
        "此操作将删除您在所有群聊/私聊中创建的全部快捷回复，且无法恢复！\n请输入“确认”以继续。"
    )


@clear_my_replies.handle()
async def handle_clear_my_replies_confirm(
    event: MessageEvent,
    session: AsyncSession = Depends(get_session),
):
    if event.get_plaintext() != "确认":
        await clear_my_replies.finish("操作已取消。")

    user_id = str(event.user_id)
    deleted_count = await datasource.delete_all_replies_by_user(session, user_id)

    if deleted_count > 0:
        await clear_my_replies.finish(
            f"操作成功！已清空您创建的 {deleted_count} 条快捷回复。"
        )
    else:
        await clear_my_replies.finish("您之前没有创建过任何快捷回复。")


@clear_user_replies.handle()
async def handle_clear_user_replies(
    matcher: Matcher,
    args: Message = CommandArg(),
    session: AsyncSession = Depends(get_session),
):
    target_user_id = ""
    for seg in args:
        if seg.type == "at":
            target_user_id = str(seg.data.get("qq", ""))
            break
    if not target_user_id:
        target_user_id = args.extract_plain_text().strip()

    if not target_user_id or not target_user_id.isdigit():
        await matcher.finish("参数错误！请提供用户的QQ号或@对方。")

    deleted_count = await datasource.delete_all_replies_by_user(session, target_user_id)

    if deleted_count > 0:
        await matcher.finish(
            f"操作成功！已清空用户 {target_user_id} 创建的 {deleted_count} 条快捷回复。"
        )
    else:
        await matcher.finish(f"用户 {target_user_id} 没有创建过任何快捷回复。")
