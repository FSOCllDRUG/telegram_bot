from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User


async def orm_user_start(session: AsyncSession, data: dict):
    obj = User(
        user_id=data.get('user_id'),
        username=data.get('username'),
        name=data.get('name'),
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


async def orm_count_users(session: AsyncSession):
    query = select(func.count(User.id))
    result = await session.execute(query)
    return result.scalar()


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
