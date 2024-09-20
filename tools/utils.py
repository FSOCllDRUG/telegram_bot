from sqlalchemy.ext.asyncio import AsyncSession
from db.pg_orm_query import orm_get_admins
from db.r_operations import redis_upd_admins


async def Union(lst1, lst2):
    final_list = list(set(lst1) | set(lst2))
    return final_list


async def update_admins(session: AsyncSession, old_admins: list):
    db_admins = await orm_get_admins(session)
    admins = await Union(old_admins, db_admins)
    await redis_upd_admins(admins)
    return admins
