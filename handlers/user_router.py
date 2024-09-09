from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.utils.chat_action import ChatActionSender
from sqlalchemy.ext.asyncio import AsyncSession

from create_bot import admins
from create_bot import bot
from db.orm_query import (
    orm_user_start,
    orm_user_get_data,
    orm_mailing_change)
from keyboards.inline import get_callback_btns, change_mailing_buttons
from keyboards.reply import main_kb

user_router = Router()


# "/start" handler
@user_router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession):
    async with ChatActionSender.typing(bot=bot, chat_id=message.from_user.id):
        if await orm_user_get_data(session, user_id=message.from_user.id) is not None:
            await message.answer(f'Снова привет, {message.from_user.full_name}!',
                                 reply_markup=main_kb(message.from_user.id in admins))
        else:
            await orm_user_start(session, data={
                'user_id': message.from_user.id,
                'username': message.from_user.username,
                'name': message.from_user.full_name,
            })
            await message.answer(f'{message.from_user.full_name}, ты добавлен в базу данных.',
                                 reply_markup=main_kb(message.from_user.id in admins))


@user_router.message(F.text == 'Главное меню')
async def main_menu(message: Message):
    await message.answer('Ты в главном меню', reply_markup=main_kb(message.from_user.id in admins))


@user_router.message(F.text == 'Мои данные📝')
async def user_credentials(message: Message, session: AsyncSession):
    async with ChatActionSender.typing(bot=bot, chat_id=message.from_user.id):
        user = await orm_user_get_data(session, user_id=message.from_user.id)
        subscription_status = "Да" if user.mailing else "Нет"
        subscription_button_text = "Подписаться на рассылку" if not user.mailing else "Отписаться от рассылки"
        subscription_button_data = f"change_mailing_{user.user_id}_{str(int(not user.mailing))}"
        buttons = {
            subscription_button_text: subscription_button_data,
        }

        reply_text = (
            f"Ваш ID: {user.user_id}\n"
            f"Ваше имя: {user.name}\n"
            f"Ваш логин: @{user.username}\n"
            f"Вы получаете рассылку: {subscription_status}"
        )

        await message.answer(reply_text, reply_markup=get_callback_btns(btns=buttons))


@user_router.callback_query(F.data.startswith('change_mailing_'))
async def toggle_mailing_subscription(callback: CallbackQuery, session: AsyncSession):
    user_id = int(callback.data.split('_')[-2])
    sub_status = bool(int(callback.data.split('_')[-1]))
    new_buttons = change_mailing_buttons(user_id, sub_status)
    await orm_mailing_change(session, user_id=user_id, mailing=sub_status)

    # Fetch updated user data
    user = await orm_user_get_data(session, user_id=user_id)
    subscription_status = "Да" if user.mailing else "Нет"
    reply_text = (
        f"Ваш ID: {user.user_id}\n"
        f"Ваше имя: {user.name}\n"
        f"Ваш логин: @{user.username}\n"
        f"Вы получаете рассылку: {subscription_status}"
    )

    if sub_status:
        await callback.answer('Вы подписались на рассылку')
    else:
        await callback.answer('Вы отписались от рассылки')

    # Edit the message text and reply markup
    await callback.message.edit_text(reply_text, reply_markup=new_buttons)


@user_router.message(F.text == 'Информация о боте🤖')
async def bot_info(message: Message):
    await message.answer('Тут будет информация о боте')


@user_router.message(F.text == 'Информация о разработчике👨‍💻')
async def developer_info(message: Message):
    await message.answer(f'Контакты:\n'
                         f'Telegram: @xtc_hydra \n'
                         f'E-mail: vlad.a.borshch@gmail.com\n')
