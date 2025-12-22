from nonebot import require

require("nonebot_plugin_orm")
from collections.abc import Sequence

from sqlalchemy import String, UniqueConstraint, func, delete, select
from sqlalchemy.orm import Mapped, mapped_column
from nonebot_plugin_orm import Model
from sqlalchemy.ext.asyncio import AsyncSession


class QuickReply(Model):
    __tablename__ = "nonebot_plugin_quickreply"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, index=True)
    group_id: Mapped[str] = mapped_column(String, index=True)  # 存储群号或 'private'
    message_json: Mapped[str] = mapped_column(String)
    creator_id: Mapped[str] = mapped_column(String)
    __table_args__ = (UniqueConstraint("key", "group_id", name="uq_key_group"),)


async def get_reply(
    session: AsyncSession, key: str, group_id: str
) -> QuickReply | None:
    """根据关键词和上下文ID获取回复。"""
    stmt = select(QuickReply).where(
        QuickReply.key == key, QuickReply.group_id == group_id
    )
    resp = await session.execute(stmt)
    return resp.scalar_one_or_none()


async def set_reply(
    session: AsyncSession, key: str, group_id: str, message_json: str, creator_id: str
) -> bool:
    """
    设置或更新一个快捷回复。
    如果回复是新创建的，返回 True；如果是更新的，返回 False。
    """
    existing_reply = await get_reply(session, key, group_id)
    if existing_reply:
        # 更新现有回复
        existing_reply.message_json = message_json
        existing_reply.creator_id = creator_id  # 也可以更新创建者
        await session.commit()
        return False
    else:
        # 创建新回复
        new_reply = QuickReply(
            key=key, group_id=group_id, message_json=message_json, creator_id=creator_id
        )
        session.add(new_reply)
        await session.commit()
        return True


async def delete_reply(session: AsyncSession, key: str, group_id: str) -> bool:
    """根据关键词和上下文ID删除回复，成功返回 True。"""
    stmt = (
        delete(QuickReply)
        .where(QuickReply.key == key, QuickReply.group_id == group_id)
        .returning(QuickReply.id)
    )
    result = await session.execute(stmt)
    await session.commit()
    deleted_ids = result.scalars().all()
    return len(deleted_ids) > 0


async def get_all_keywords_in_context(
    session: AsyncSession, group_id: str
) -> list[str]:
    """获取指定上下文中的所有关键词列表。"""
    stmt = (
        select(QuickReply.key)
        .where(QuickReply.group_id == group_id)
        .order_by(QuickReply.key)
    )
    return list((await session.execute(stmt)).scalars().all())


# --- 管理和统计函数 ---


async def delete_all_replies_in_context(session: AsyncSession, context_id: str) -> int:
    """根据上下文ID删除其创建的所有快捷回复。"""
    stmt = (
        delete(QuickReply)
        .where(QuickReply.group_id == context_id)
        .returning(QuickReply.id)
    )
    deleted_ids: Sequence[int] = (await session.execute(stmt)).scalars().all()
    await session.commit()
    return len(deleted_ids)


async def delete_all_replies_by_user(session: AsyncSession, user_id: str) -> int:
    """
    根据创建者ID删除其创建的所有快捷回复（全局）。
    返回删除的数量。
    """
    stmt = (
        delete(QuickReply)
        .where(QuickReply.creator_id == user_id)
        .returning(QuickReply.id)
    )
    deleted_ids: Sequence[int] = (await session.execute(stmt)).scalars().all()
    await session.commit()
    return len(deleted_ids)


async def count_replies_by_user(session: AsyncSession, user_id: str) -> int:
    """计算指定用户创建的快捷回复总数（全局）。"""
    stmt = select(func.count(QuickReply.id)).where(QuickReply.creator_id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one()


async def count_replies_by_context(session: AsyncSession, group_id: str) -> int:
    """计算指定上下文中的快捷回复总数。"""
    stmt = select(func.count(QuickReply.id)).where(QuickReply.group_id == group_id)
    result = await session.execute(stmt)
    return result.scalar_one()


async def delete_replies_by_user_in_context(
    session: AsyncSession, user_id: str, context_id: str
) -> int:
    """根据创建者ID和上下文ID删除其创建的所有快捷回复。"""
    stmt = (
        delete(QuickReply)
        .where(QuickReply.creator_id == user_id, QuickReply.group_id == context_id)
        .returning(QuickReply.id)
    )
    deleted_ids: Sequence[int] = (await session.execute(stmt)).scalars().all()
    await session.commit()
    return len(deleted_ids)


async def get_all_keywords_by_user(session: AsyncSession, user_id: str) -> list[str]:
    """获取指定用户创建的所有快捷回复关键词列表（全局）。"""
    stmt = (
        select(QuickReply.key)
        .where(QuickReply.creator_id == user_id)
        .order_by(QuickReply.key)
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_keywords_by_user_in_context(session, user_id, context_id) -> list[str]:
    """获取指定用户在指定上下文中创建的所有快捷回复关键词列表。"""
    stmt = (
        select(QuickReply.key)
        .where(QuickReply.creator_id == user_id, QuickReply.group_id == context_id)
        .order_by(QuickReply.key)
    )
    return list((await session.execute(stmt)).scalars().all())
