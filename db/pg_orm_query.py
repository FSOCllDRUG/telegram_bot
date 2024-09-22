from sqlalchemy import select, func, update, insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.pg_models import User, Channel, user_channel_association


async def orm_get_admins(session: AsyncSession):
    query = select(User.user_id).where(User.is_admin == True)
    result = await session.execute(query)
    return result.scalars().all()


async def orm_user_start(session: AsyncSession, data: dict):
    obj = User(
        user_id=data.get("user_id"),
        username=data.get("username"),
        name=data.get("name"),
    )
    session.add(obj)
    await session.commit()


async def orm_user_get_data(session: AsyncSession, user_id: int):
    query = select(User).where(User.user_id == user_id)
    result = await session.execute(query)
    return result.scalar()


async def orm_count_users(session: AsyncSession):
    query = select(func.count(User.user_id))
    result = await session.execute(query)
    return result.scalar()


async def orm_get_all_users(session: AsyncSession):
    query = select(User).order_by(User.id)
    result = await session.execute(query)
    return result.scalars().all()


async def orm_get_last_10_users(session: AsyncSession):
    query = select(User).order_by(User.id.desc()).limit(10)
    result = await session.execute(query)
    return result.scalars().all()


async def orm_mailing_change(session: AsyncSession, user_id: int, mailing: bool):
    query = (
        update(User)
        .where(User.user_id == user_id)
        .values(mailing=mailing)
    )
    await session.execute(query)
    await session.commit()


async def orm_mailing_status(session: AsyncSession, user_id: int):
    query = select(User.mailing).where(User.user_id == user_id)
    result = await session.execute(query)
    return result.scalar()


async def orm_get_mailing_list(session: AsyncSession):
    query = select(User.user_id).where(User.mailing == True)
    result = await session.execute(query)
    return result.scalars().all()


async def orm_not_mailing_users(session: AsyncSession):
    query = select(func.count(User.id)).where(User.mailing == False)
    result = await session.execute(query)
    return result.scalar()


async def orm_add_channel(session: AsyncSession, channel_id: int):
    obj = Channel(channel_id=channel_id)
    session.add(obj)
    await session.commit()


async def orm_get_channels_for_admin(session: AsyncSession, admin_user_id: int):
    query = select(Channel).join(user_channel_association).join(User).where(User.user_id == admin_user_id,
                                                                            User.is_admin == True)
    result = await session.execute(query)
    return result.scalars().all()


async def orm_add_admin_to_channel(session: AsyncSession, user_id: int, channel_id: int):
    query = (
        insert(user_channel_association)
        .values(user_id=user_id, channel_id=channel_id)
    )
    await session.execute(query)
    await session.commit()
