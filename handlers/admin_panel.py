from aiogram import F, Router
from aiogram.types import Message
from aiogram.utils.chat_action import ChatActionSender
from sqlalchemy.ext.asyncio import AsyncSession

from create_bot import admins, bot
from db.orm_query import orm_get_last_10_users, orm_count_users
from keyboards.reply import get_keyboard

admin_router = Router()


@admin_router.message((F.text.endswith('Админ панель')) & (F.from_user.id.in_(admins)))
async def get_profile(message: Message, session: AsyncSession):
    async with ChatActionSender.typing(bot=bot, chat_id=message.from_user.id):
        count = await orm_count_users(session)

        last_users_data = await orm_get_last_10_users(session)
        last_users_data = last_users_data[::-1]
        admin_text = (
            f'👥 В базе данных <b>{count}</b> человек. Вот короткая информация по каждому:\n\n'
        )

        for user in last_users_data:
            user_link = f'<a href="tg://user?id={user.user_id}">{user.user_id}</a>'
            admin_text += (
                f'{user.id}. 👤 Телеграм ID: {user_link}\n'
                f'📝 Полное имя: {user.name}\n'
            )

            if user.username is not None:
                admin_text += f'🔑 Логин: @{user.username}\n'

    await message.answer(admin_text, reply_markup=get_keyboard('Главное меню'))

