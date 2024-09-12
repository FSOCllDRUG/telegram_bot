from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery
from aiogram.utils.chat_action import ChatActionSender
from sqlalchemy.ext.asyncio import AsyncSession


from db.pg_orm_query import orm_get_last_10_users, orm_count_users, orm_get_mailing_list, orm_mailing_users
from filters.chat_type import ChatType
from filters.is_admin import IsAdmin
from keyboards.inline import get_callback_btns
from keyboards.reply import get_keyboard
from create_bot import bot
from tools.mailing import simple_mailing
from db.r_operations import redis_mailing_users, redis_mailing_msg, redis_mailing_from
admin_private_router = Router()
admin_private_router.message.filter(ChatType("private"), IsAdmin())


@admin_private_router.message(F.text == "Админ панель")
async def get_profile(message: Message, session: AsyncSession):
    async with ChatActionSender.typing(bot=bot, chat_id=message.from_user.id):
        count = await orm_count_users(session)
        mailing_count = await orm_mailing_users(session)

        last_users_data = await orm_get_last_10_users(session)
        last_users_data = last_users_data[::-1]
        admin_text = (
            f"👥 В базе данных <b>{count}</b> человек, из них подписаны на рассылку {mailing_count}. \n"
            f"Вот последние 10 пользователей:\n\n"
        )

        for user in last_users_data:
            user_link = f"<a href='tg://user?id={user.user_id}'>{user.user_id}</a>"
            admin_text += (
                f"{user.id}. 👤 Телеграм ID: {user_link}\n"
                f"📝 Полное имя: {user.name}\n"
            )

            if user.username is not None:
                admin_text += f"🔑 Логин: @{user.username}\n"

    await message.answer(admin_text, reply_markup=get_keyboard("Главное меню", "Сделать рассылку"))


@admin_private_router.message(StateFilter("*"), F.text.casefold() == "отмена")
async def cancel_fsm(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Действие отменено", reply_markup=get_keyboard("Главное меню", "Сделать рассылку"))


class Mailing(StatesGroup):
    message = State()


@admin_private_router.message(StateFilter(None), F.text == "Сделать рассылку")
async def make_mailing(message: Message, state: FSMContext):
    await message.answer("Отправь сообщение, которое ты хочешь рассылать", reply_markup=get_keyboard(
        "Отмена",
        placeholder="Отправьте сообщение, для рассылки"
    ))
    await state.set_state(Mailing.message)


@admin_private_router.message(StateFilter(Mailing.message))
async def get_message_for_mailing(message: Message, state: FSMContext):
    await state.update_data(message=message.message_id)
    await message.answer(f"{await state.get_data()}")
    await state.set_state(None)
    await message.reply("Разослать это сообщение?", reply_markup=get_callback_btns(
        btns={"Да": "confirm_mailing",
              "Переделать": "cancel_mailing"}
    )
                        )


@admin_private_router.callback_query(StateFilter("*"), F.data == "cancel_mailing")
async def cancel_mailing(callback: CallbackQuery, state: FSMContext):
    await callback.answer("")
    current_state = await state.get_state()

    if current_state is None:
        await state.set_state(Mailing.message)
        await callback.message.answer("Отправь сообщение, которое ты хочешь рассылать")


@admin_private_router.callback_query(StateFilter("*"), F.data == "confirm_mailing")
async def confirm_mailing(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    async with ChatActionSender.typing(bot=bot, chat_id=callback.message.from_user.id):
        await callback.answer("")
        await redis_mailing_users(await orm_get_mailing_list(session))
        data = await state.get_data()
        await redis_mailing_msg(str(data.get("message")))
        await redis_mailing_from(str(callback.message.chat.id))

        success, notsuccess, blocked, elapsed_time_str = await simple_mailing()
        if elapsed_time_str == "":
            elapsed_time_str = "менее секунды"

        await callback.message.answer(
            text=f"Рассылка успешна.\n\nРезультаты:\nУспешно - {success}\nНеудачно - {notsuccess}\n\n"
                 f"Затрачено времени: <b>{elapsed_time_str}</b>\n\n"
                 f"<span class='tg-spoiler'>Бот заблокирован у {blocked} пользователя(ей)</span>",
                 reply_markup=get_keyboard("Главное меню", "Сделать рассылку")
        )
