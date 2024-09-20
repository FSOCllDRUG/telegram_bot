import asyncio
from functools import partial
from typing import Any

from aiogram.types import BotCommand, BotCommandScopeDefault
from sqlalchemy.ext.asyncio import AsyncSession

from create_bot import bot, dp, env_admins
from db.pg_engine import create_db
from db.pg_engine import session_maker
from db.pg_orm_query import orm_get_admins
from db.r_operations import redis_upd_admins
from handlers.admin_private import admin_private_router
from handlers.channels import channel_router
from handlers.user_router import user_router
from middlewares.db import DbSessionMiddleware
from tools.utils import Union, update_admins


async def set_commands():
    commands = [BotCommand(command="start", description="Старт"),
                BotCommand(command="profile", description="Мой профиль")]
    await bot.set_my_commands(commands, BotCommandScopeDefault())


async def start_bot(session: AsyncSession):
    await set_commands()
    admins = await update_admins(session, env_admins)
    try:
        for admin_id in admins:
            await bot.send_message(admin_id, f"Бот запущен🥳.{admins}")
    except:
        pass


async def stop_bot():
    try:
        for admin_id in env_admins:
            await bot.send_message(admin_id, "Бот остановлен.\n😴")
    except:
        pass


async def main():
    await create_db()
    dp.include_router(user_router)
    dp.include_router(admin_private_router)
    dp.include_router(channel_router)
    dp.update.middleware(DbSessionMiddleware(session_pool=session_maker))

    session = session_maker()  # Создаем сессию

    dp.startup.register(partial(start_bot, session))  # Передаем сессию в start_bot
    dp.shutdown.register(stop_bot)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
