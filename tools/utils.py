from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from create_bot import bot
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


async def get_channel_id(message: Message):
    if message.forward_from_chat:
        return message.forward_from_chat.id
    elif message.text and message.text.startswith("@"):
        channel_username = message.text
        chat = await bot.get_chat(channel_username)
        return chat.id
    elif message.text and message.text.startswith("https://t.me/"):
        channel_username = message.text.replace("https://t.me/", "@")
        chat = await bot.get_chat(channel_username)
        return chat.id
    else:
        return None
