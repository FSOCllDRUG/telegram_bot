from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery
from aiogram.utils.chat_action import ChatActionSender
from sqlalchemy.ext.asyncio import AsyncSession

from create_bot import bot, env_admins
from db.pg_orm_query import orm_count_users, orm_get_mailing_list, orm_not_mailing_users_count, \
    orm_add_channel, orm_add_admin_to_channel, orm_get_channels_for_admin, orm_get_user_data, \
    orm_add_admin
from db.r_operations import redis_set_mailing_users, redis_set_mailing_msg, redis_set_msg_from, redis_set_mailing_btns, \
    redis_check_channel, redis_check_admin, get_active_users_count
from filters.chat_type import ChatType
from filters.is_admin import IsAdmin, IsOwner
from keyboards.inline import get_callback_btns
from keyboards.reply import get_keyboard, admin_kb
from tools.mailing import simple_mailing
from tools.utils import update_admins, get_chat_id, cbk_msg, msg_to_cbk, link_to_dev, admins_list_text

admin_private_router = Router()
admin_private_router.message.filter(ChatType("private"), IsAdmin())


@admin_private_router.message(F.text == "Админ панель")
async def get_profile(message: Message, session: AsyncSession):
    async with ChatActionSender.typing(bot=bot, chat_id=message.from_user.id):
        count = await orm_count_users(session)
        mailing_count = await orm_not_mailing_users_count(session)
        admin_text = (
            f"👥\nВ базе данных <b>{count}</b> человек, из них отписаны от рассылки {mailing_count}. \n"
            f"\n\n"
        )

        active_users_day = await get_active_users_count(1)
        active_users_week = await get_active_users_count(7)
        active_users_month = await get_active_users_count(30)

        admin_text += (f"Количество активных пользователей:\n👥🗓\n"
                       f"День: {active_users_day}\n"
                       f"Неделя: {active_users_week}\n"
                       f"Месяц: {active_users_month}"
                       )

        if message.from_user.id in env_admins:
            admin_text += await admins_list_text(session)
    await message.answer(admin_text, reply_markup=admin_kb())


@admin_private_router.message(StateFilter("*"), F.text.casefold() == "отмена")
async def cancel_fsm(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Действие отменено", reply_markup=admin_kb())


class Mailing(StatesGroup):
    message = State()
    buttons = State()


# Mailing handlers starts
@admin_private_router.message(StateFilter(None), F.text == "Рассылка")
async def make_mailing(message: Message, state: FSMContext):
    await message.answer("Отправь сообщение, которое ты хочешь рассылать\n\n"
                         "<b>ВАЖНО</b>\n\n"
                         "В рассылке может быть приложен только <u>один</u> файл*!\n"
                         "<i>Файл— фото/видео/документ/голосовое сообщение/видео сообщение</i>",
                         reply_markup=get_keyboard("Отмена",
                                                   placeholder="Отправьте сообщение, для рассылки"
                                                   )
                         )
    await state.set_state(Mailing.message)


@admin_private_router.message(StateFilter(Mailing.message))
async def get_message_for_mailing(message: Message, state: FSMContext):
    await state.update_data(message=message.message_id)
    await state.set_state(Mailing.buttons)
    await message.reply("Будем добавлять URLкнопки к сообщению?", reply_markup=get_callback_btns(
        btns={"Добавить кнопки": "add_btns",
              "Приступить к рассылке": "confirm_mailing", "Сделать другое сообщение для рассылки": "cancel_mailing"}
    )
                        )


@admin_private_router.callback_query(StateFilter(Mailing.buttons), F.data == "add_btns")
async def add_btns_mailing(callback: CallbackQuery):
    await callback.answer("")
    await callback.message.answer(cbk_msg)


@admin_private_router.message(StateFilter(Mailing.buttons), F.text.contains(":"))
async def btns_to_data(message: Message, state: FSMContext):
    await state.update_data(buttons=await msg_to_cbk(message))
    data = await state.get_data()
    await message.answer(f"Вот как будет выглядеть сообщение в рассылке:"
                         f"\n⬇️")
    await bot.copy_message(chat_id=message.from_user.id, from_chat_id=message.chat.id, message_id=data[
        "message"],
                           reply_markup=get_callback_btns(btns=data["buttons"]))
    await message.answer("Приступим к рассылке?", reply_markup=get_callback_btns(btns={"Да": "confirm_mailing",
                                                                                       "Переделать": "cancel_mailing"}))


@admin_private_router.callback_query(StateFilter(Mailing.message), F.data == "cancel_mailing")
@admin_private_router.callback_query(StateFilter(Mailing.buttons), F.data == "cancel_mailing")
async def cancel_mailing(callback: CallbackQuery, state: FSMContext):
    await callback.answer("")
    current_state = await state.get_state()

    if current_state is not None:
        await state.set_state(Mailing.message)
        await callback.message.answer("Отправь сообщение, которое ты хочешь рассылать")


@admin_private_router.callback_query(StateFilter("*"), F.data == "confirm_mailing")
async def confirm_mailing(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    async with ChatActionSender.typing(bot=bot, chat_id=callback.message.from_user.id):
        await callback.answer("")
        await redis_set_mailing_users(await orm_get_mailing_list(session))
        data = await state.get_data()
        await redis_set_mailing_msg(str(data.get("message")))
        await redis_set_msg_from(str(callback.message.chat.id))
        await redis_set_mailing_btns(data.get("buttons"))
        await state.clear()

        success, notsuccess, blocked, elapsed_time_str = await simple_mailing()
        if elapsed_time_str == "":
            elapsed_time_str = "менее секунды"

        await callback.message.answer(
            text=f"Рассылка успешна.\n\nРезультаты:\nУспешно - {success}\nНеудачно - {notsuccess}\n\n"
                 f"Затрачено времени: <b>{elapsed_time_str}</b>\n\n"
                 f"<span class='tg-spoiler'>Бот заблокирован у {blocked} пользователя(ей)</span>",
            reply_markup=get_keyboard("Главное меню", "Сделать рассылку")
        )


# Mailing handlers ends


# Update admins list in Redis
@admin_private_router.message(F.text == "/admin")
async def upd_admin_list(message: Message, session: AsyncSession):
    admins = await update_admins(session, env_admins)
    await message.answer(f'{admins}')


# Add channel handlers


@admin_private_router.message(F.text == "Мои каналы")
async def get_user_channels(message: Message, session: AsyncSession, state: FSMContext):
    user_id = message.from_user.id
    channels = await orm_get_channels_for_admin(session, user_id)
    if not channels:
        await message.answer("У тебя нет каналов 🫥",
                             reply_markup=get_callback_btns(btns={"Добавить канал": "add_channel"}))
        return
    channels_str = ""
    btns = {}
    for channel in channels:
        chat = await bot.get_chat(channel.channel_id)
        channels_str += f"<a href='{chat.invite_link}'>{chat.title}</a>\n"
        btns[chat.title] = f"channel_{channel.channel_id}"
    await message.answer(f"Твои каналы:\n{channels_str}",
                         reply_markup=get_callback_btns(btns=btns))
    await message.answer("Нужно добавить новый канал?",
                         reply_markup=get_callback_btns(btns={"Добавить канал": "add_channel"}))


class AddChannel(StatesGroup):
    admin_id = State()
    channel_id = State()


@admin_private_router.callback_query(F.data == "add_channel")
async def start_add_channel(callback: CallbackQuery, state: FSMContext):
    await state.update_data(admin_id=callback.from_user.id)
    await callback.answer("")
    await callback.message.answer("Добавь меня в <b>свой</b> канал с <b><i><u>правами администратора</u></i></b>\n\n"
                                  "Необходимые права для работы бота:\n"
                                  "\n✅ Отправка сообщений"
                                  "\n✅ Удаление сообщений"
                                  "\n✅ Редактирование сообщений\n\n"
                                  "После того как добавишь меня в канал, нажми на кнопку⬇️",
                                  reply_markup=get_callback_btns(btns={"Я добавил бота!": "added_to_channel"}))
    await state.set_state(AddChannel.channel_id)


@admin_private_router.callback_query(StateFilter(AddChannel.channel_id), F.data == "added_to_channel")
async def bot_added_to_channel(callback: CallbackQuery):
    await callback.answer("")
    await callback.message.answer("Супер!\n"
                                  "Теперь перешли любой пост из канала в диалог с ботом, "
                                  "либо отправь публичную ссылку или айди начинающийся с @ твоего канала")


@admin_private_router.message(StateFilter(AddChannel.channel_id))
async def check_channel(message: Message, session: AsyncSession, state: FSMContext):
    channel_id = await get_chat_id(message)
    user_id = message.from_user.id
    if channel_id:
        await message.reply(f"ID канала: {channel_id}")
        check = await redis_check_channel(user_id, channel_id)
        if check:
            await orm_add_channel(session, channel_id)
            await orm_add_admin_to_channel(session, user_id, channel_id)
            await message.answer("Канал добавлен успешно!")
            await state.clear()
        else:
            await message.answer("Либо ты меня ещё не добавил в канал, либо что-то пошло не так :(")
    else:
        await message.answer("Я не смог разобрать твоё сообщение, пожалуйста, следуй условиям описанным выше!")


@admin_private_router.message(F.text == "Список админов", IsOwner())
async def add_admin_to_bot(message: Message, session: AsyncSession):
    text: str = "Владелец бота:\n"
    owner: int = env_admins[1]
    id_for_query = int(owner)
    user = await orm_get_user_data(session, id_for_query)
    user_link = f"<a href='tg://user?id={user.user_id}'>{user.user_id}</a>"
    text += (
        f"👤 Телеграм ID: {user_link}\n"
        f"📝 Полное имя: {user.name}\n"
    )

    if user.username is not None:
        text += f"🔑 Логин: @{user.username}\n"

    if message.from_user.id in env_admins:
        text += await admins_list_text(session)
    await message.answer(text=text,
                         reply_markup=get_callback_btns(btns={"Добавить админа": "add_admin",
                                                              "Стукнуть разраба":
                                                                  link_to_dev},
                                                        sizes=(1,)))


class AddAdmin(StatesGroup):
    user_id = State()
    confirm = State()


@admin_private_router.callback_query(F.data == "add_admin")
async def add_admin(callback: CallbackQuery, state: FSMContext):
    await callback.answer("")
    await state.set_state(AddAdmin.user_id)
    await callback.message.answer("Перешли сообщение от юзера, которого хочешь сделать админом\n\n"
                                  "‼️<b><u>ВАЖНО</u></b>‼️\n"
                                  "Это должен быть пользователь, который взаимодействовал с ботом",
                                  reply_markup=get_keyboard("Отмена"))


@admin_private_router.message(AddAdmin.user_id)
async def get_admin_id(message: Message, state: FSMContext, session: AsyncSession):
    try:
        text = "Ты хочешь сделать администратором пользователя:\n\n"
        user_id = await get_chat_id(message)
        await state.update_data(user_id=user_id)
        user = await orm_get_user_data(session, user_id)
        if user is None:
            await message.answer("Пользователь ещё не запускал бота!")
            return
        elif await redis_check_admin(user_id):
            await message.answer("Пользователь уже админ!\n"
                                 "Возвращаю тебя в админ панель", reply_markup=admin_kb())
            await state.clear()
            return
        user_link = f"<a href='tg://user?id={user.user_id}'>{user.user_id}</a>"
        text += (
            f"👤 Телеграм ID: {user_link}\n"
            f"📝 Полное имя: {user.name}\n"
        )

        if user.username is not None:
            text += f"🔑 Логин: @{user.username}\n"
        await message.answer(text=text,
                             reply_markup=get_callback_btns(btns={"Подтвердить":
                                                                      "confirm"}))
        await state.set_state(AddAdmin.confirm)
    except ValueError:
        await message.answer("Некорректный ID админа, попробуй снова!")


@admin_private_router.callback_query(F.data == "confirm", StateFilter(AddAdmin.confirm))
async def add_admin_done(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    await callback.answer("")
    data = await state.get_data()
    admin_id = data.get("user_id")
    await orm_add_admin(session, admin_id)
    text = "Администратор добавлен в базу данных!"
    text += await admins_list_text(session)
    await callback.message.answer(text=text, reply_markup=admin_kb())
    await update_admins(session, env_admins)
    await state.clear()


@admin_private_router.callback_query(F.data.startswith("channel_"))
async def channel_choosen(callback: CallbackQuery):
    channel_id = int(callback.data.split("_")[1])
    await callback.answer("")
    await callback.message.answer(
        "Выберите действие:\n"
        "1. Создать пост для канала\n"
        "2. Добавить другого администратора в канал\n",
        reply_markup=get_callback_btns(
            btns={
                "1. Создать пост для канала": f"create_post_{channel_id}",
                "2. Добавить другого администратора в канал": f"add_admin_to_channel_{channel_id}"
            }
        )
    )


class CreatePost(StatesGroup):
    channel_id = State()
    message = State()
    buttons = State()


# Channel post handlers starts
@admin_private_router.callback_query(StateFilter(None), F.data.startswith("create_post_"))
async def make_mailing(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CreatePost.channel_id)
    await callback.answer("")
    channel_id = int(callback.data.split("_")[2])
    await state.update_data(channel_id=channel_id)
    await callback.message.answer("Отправь сообщение, которое будем постить\n\n"
                                  "<b>ВАЖНО</b>\n\n"
                                  "В посте может быть приложен только <u>один</u> файл*!\n"
                                  "<i>Файл— фото/видео/документ/голосовое сообщение/видео сообщение</i>",
                                  reply_markup=get_keyboard("Отмена",
                                                            placeholder="Отправь сообщение, для поста"
                                                            )
                                  )
    await state.set_state(CreatePost.message)


@admin_private_router.message(StateFilter(CreatePost.message))
async def get_message_for_post(message: Message, state: FSMContext):
    await state.update_data(message=message.message_id)
    await state.set_state(CreatePost.buttons)
    await message.reply("Будем добавлять URL-кнопки к посту?", reply_markup=get_callback_btns(
        btns={"Да": "add_btns",
              "Пост без кнопок": "confirm_post", "Сделать другое сообщение для рассылки": "cancel_post"}
    )
                        )


@admin_private_router.callback_query(StateFilter(CreatePost.buttons), F.data == "add_btns")
async def add_btns_post(callback: CallbackQuery):
    await callback.answer("")
    await callback.message.answer(cbk_msg)


@admin_private_router.message(StateFilter(CreatePost.buttons), F.text.contains(":"))
async def btns_to_data(message: Message, state: FSMContext):
    await state.update_data(buttons=await msg_to_cbk(message))
    data = await state.get_data()
    await message.answer(f"Вот как будет выглядеть пост в канале:"
                         f"\n⬇️")
    await bot.copy_message(chat_id=message.from_user.id, from_chat_id=message.chat.id, message_id=data[
        "message"],
                           reply_markup=get_callback_btns(btns=data["buttons"]))
    await message.answer("Приступим к постингу?", reply_markup=get_callback_btns(btns={"Да": "confirm_post",
                                                                                       "Переделать": "cancel_post"}))


@admin_private_router.callback_query(StateFilter(CreatePost.message), F.data == "cancel_post")
@admin_private_router.callback_query(StateFilter(CreatePost.buttons), F.data == "cancel_post")
async def cancel_mailing(callback: CallbackQuery, state: FSMContext):
    await callback.answer("")
    current_state = await state.get_state()

    if current_state is not None:
        await state.set_state(CreatePost.message)
        await callback.message.answer("Отправь сообщение, которое будем постить")


@admin_private_router.callback_query(StateFilter("*"), F.data == "confirm_post")
async def confirm_mailing(callback: CallbackQuery, state: FSMContext):
    async with ChatActionSender.typing(bot=bot, chat_id=callback.message.from_user.id):
        await callback.answer("")
        data = await state.get_data()
        if "buttons" not in data:
            await bot.copy_message(chat_id=data["channel_id"], from_chat_id=callback.message.chat.id,
                                   message_id=data["message"])
        else:
            await bot.copy_message(chat_id=data["channel_id"], from_chat_id=callback.message.chat.id,
                                   message_id=data["message"],
                                   reply_markup=get_callback_btns(btns=data["buttons"]))
        await callback.message.answer("Пост успешно создан!")

        await state.clear()



