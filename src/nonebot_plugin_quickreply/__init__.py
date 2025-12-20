import json

from nonebot import logger, require, on_command, on_message
from nonebot.params import Depends, CommandArg
from nonebot.plugin import PluginMetadata, get_plugin_config
from nonebot.matcher import Matcher
from nonebot.exception import FinishedException
from nonebot.permission import SUPERUSER
from sqlalchemy.ext.asyncio import AsyncSession
from nonebot.internal.params import Arg
from nonebot.adapters.onebot.v11 import (
    Bot,
    Message,
    MessageEvent,
    MessageSegment,
    GroupMessageEvent,
)

require("nonebot_plugin_orm")
from nonebot_plugin_orm import get_session
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN, GROUP_OWNER

from . import datasource
from .config import Config

__plugin_meta__ = PluginMetadata(
    name="快捷回复",
    description="一个功能强大的快捷回复插件，支持分群/私聊、配置化限制最大快捷回复数量。",
    usage=(
        "上下文相关指令 (仅在当前群聊/私聊生效):\n"
        "  /设置回复 <关键词> <内容>\n"
        "  /删除回复 <关键词>\n"
        "  /回复列表\n"
        "  /管理删除 <关键词> (群管/超管)\n"
        "\n全局指令 (影响您所有的回复):\n"
        "  /清空我的回复\n"
        "  /清空用户回复 <@用户或QQ> (超管)"
    ),
    type="application",
    homepage="https://github.com/FlanChanXwO/nonebot-plugin-quickreply",
    config=Config,
    supported_adapters={"~onebot.v11"},
    extra={"author": "FlanChanXwO", "version": "0.1.0"},
)

plugin_config = get_plugin_config(Config)


# --- 辅助函数：获取上下文ID ---
def get_context_id(event: MessageEvent) -> str:
    """获取上下文ID，群聊为群号，私聊为 'private_' + 用户号"""
    # 使用 isinstance 进行类型判断
    if isinstance(event, GroupMessageEvent):
        return str(event.group_id)
    elif event.message_type == "private":
        return f"private_{event.user_id}"
    return "unknown"


set_reply = on_command("设置回复", aliases={"setreply"}, priority=10, block=True)
del_reply = on_command("删除回复", aliases={"delreply"}, priority=10, block=True)
admin_del_reply = on_command(
    "管理删除",
    aliases={"admindel"},
    permission=GROUP_ADMIN | GROUP_OWNER | SUPERUSER,
    priority=10,
    block=True,
)
list_replies = on_command("回复列表", aliases={"listreply"}, priority=10, block=True)
clear_my_replies = on_command(
    "清空我的回复", aliases={"清空我的快捷回复"}, priority=1, block=True
)

clear_user_replies = on_command(
    "清空用户回复",
    aliases={"clear_user_replies"},
    permission=SUPERUSER,
    priority=5,
    block=True,
)
get_reply = on_message(priority=99, block=False)


@set_reply.handle()
async def handle_set_reply(
    matcher: Matcher,
    event: MessageEvent,
    args: Message = CommandArg(),
    session: AsyncSession = Depends(get_session),
):
    context_id = get_context_id(event)
    if context_id == "unknown":
        await matcher.finish("无法识别的会话上下文。")
    if event.reply:
        arg_text = args.extract_plain_text().strip()
        if not arg_text:
            await matcher.finish("用法: 回复消息后输入 /设置回复 <关键词>")
        key = arg_text
        value_msg = event.reply.message

    # --- 情况二：通过【发送长消息】来设置 ---
    else:
        raw_msg_str = event.raw_message
        command_parts = raw_msg_str.split(maxsplit=1)

        if len(command_parts) < 2:
            await matcher.finish("参数不足！\n用法: /设置回复 <关键词> <内容>")

        args_str = command_parts[1]
        value_parts = args_str.split(maxsplit=1)

        if len(value_parts) < 2:
            await matcher.finish(
                "参数不足！内容不能为空。\n用法: /设置回复 <关键词> <内容>"
            )

        key = value_parts[0]
        value_str = value_parts[1]
        value_msg = Message(value_str)

    if not key or not value_msg:
        await matcher.finish("关键词或回复内容不能为空！")

    is_new = not bool(await datasource.get_reply(session, key, context_id))
    if is_new:
        # 检查个人上限
        if plugin_config.quick_reply_max_per_user > 0:
            count = await datasource.count_replies_by_user(session, str(event.user_id))
            if count >= plugin_config.quick_reply_max_per_user:
                await matcher.finish(f"您创建的回复已达个人上限({count}条)，无法新增！")
        # 检查上下文上限
        if plugin_config.quick_reply_max_per_context > 0:
            count = await datasource.count_replies_by_context(session, context_id)
            if count >= plugin_config.quick_reply_max_per_context:
                await matcher.finish(f"本群(会话)的回复已达上限({count}条)，无法新增！")

    serializable_message = [segment.__dict__ for segment in value_msg]
    message_json = json.dumps(serializable_message, ensure_ascii=False)

    await datasource.set_reply(
        session, key, context_id, message_json, str(event.user_id)
    )
    await session.commit()

    reply_text = (
        f"快捷回复 '{key}' 已设置成功。" if is_new else f"快捷回复 '{key}' 已更新。"
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
    context_id = get_context_id(event)
    key = args.extract_plain_text().strip()
    if not key:
        await matcher.finish("请输入要删除的关键词！")

    reply_to_delete = await datasource.get_reply(session, key, context_id)
    if not reply_to_delete:
        await matcher.finish(f"在本群(会话)中未找到关键词为 '{key}' 的回复。")

    is_superuser = await SUPERUSER(bot, event)
    if reply_to_delete.creator_id == str(event.user_id) or is_superuser:
        await datasource.delete_reply(session, key, context_id)
        await session.commit()
        await matcher.finish(f"本群(会话)的快捷回复 '{key}' 已删除。")
    else:
        await matcher.finish("您没有权限删除此回复，因为它由其他用户创建。")


@admin_del_reply.handle()
async def handle_admin_del_reply(
    event: MessageEvent,
    matcher: Matcher,
    args: Message = CommandArg(),
    session: AsyncSession = Depends(get_session),
):
    context_id = get_context_id(event)
    key = args.extract_plain_text().strip()
    if not key:
        await matcher.finish("请输入要强制删除的关键词！")

    if await datasource.delete_reply(session, key, context_id):
        await session.commit()
        await matcher.finish(f"已强制删除本群(会话)的快捷回复 '{key}'。")
    else:
        await matcher.finish(f"在本群(会话)中未找到关键词为 '{key}' 的回复。")


@list_replies.handle()
async def handle_list_replies(
    event: MessageEvent,
    matcher: Matcher,
    session: AsyncSession = Depends(get_session),
):
    context_id = get_context_id(event)
    keywords = await datasource.get_all_keywords_in_context(session, context_id)
    if not keywords:
        await matcher.finish("本群(会话)尚未设置任何快捷回复。")

    reply_text = "本群(会话)已设置的关键词列表：\n" + "\n".join(
        f"- {key}" for key in keywords
    )
    await matcher.finish(reply_text)


@get_reply.handle()
async def handle_get_reply(
    event: MessageEvent,
    matcher: Matcher,
    session: AsyncSession = Depends(get_session),
):
    context_id = get_context_id(event)
    key = event.get_plaintext().strip()
    if not key or context_id == "unknown":
        return

    reply = await datasource.get_reply(session, key, context_id)
    if reply:
        try:
            # (你的反序列化逻辑，保持不变)
            loaded_list = json.loads(reply.message_json)
            reply_msg = Message([MessageSegment(**data) for data in loaded_list])
            await matcher.finish(reply_msg)
        except FinishedException:
            raise
        except Exception as e:
            logger.error(f"快捷回复 '{key}' (上下文: {context_id}) 解析失败: {e}")
            return


@clear_my_replies.got(
    "confirm",
    prompt="此操作将删除您在所有群聊/私聊中创建的全部快捷回复，且无法恢复！\n请输入“确认”以继续。",
)
async def handle_clear_my_replies_confirm(
    event: MessageEvent,
    confirm: Message = Arg(),
    session: AsyncSession = Depends(get_session),
):
    if confirm.extract_plain_text() != "确认":
        await clear_my_replies.finish("操作已取消。")
    user_id = str(event.user_id)
    deleted_count = await datasource.delete_all_replies_by_user(session, user_id)
    await session.commit()
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
    await session.commit()
    if deleted_count > 0:
        await matcher.finish(
            f"操作成功！已清空用户 {target_user_id} 创建的 {deleted_count} 条快捷回复。"
        )
    else:
        await matcher.finish(f"用户 {target_user_id} 没有创建过任何快捷回复。")
