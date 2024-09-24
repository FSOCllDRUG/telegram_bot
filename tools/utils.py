from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from create_bot import bot
from db.pg_orm_query import orm_get_admins_id
from db.r_operations import redis_upd_admins


async def union_admins(lst1, lst2):
    final_list = list(set(lst1) | set(lst2))
    return final_list


async def update_admins(session: AsyncSession, old_admins: list):
    db_admins = await orm_get_admins_id(session)
    admins = await union_admins(old_admins, db_admins)
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


cbk_msg = ("Отправь содержание кнопок вида:\n"
           "текст кнопки:ссылка\n"
           "текст кнопки:ссылка\n\n"
           "Пример: \n<pre>Перейти на сайт:https://example.com\n"
           "Перейти к посту:https://t.me/for_test_ch/3</pre>"
           "\n\n"
           "Количество кнопок должно быть не более 10\n"
           "Кнопки присылать <b><u>ОДНИМ</u></b> сообщением, каждая кнопка с новой строки!")


async def msg_to_cbk(message: Message):
    raw_buttons = message.text.split("\n")
    clean_buttons = {}
    for btn in raw_buttons:
        text, link = btn.split(":", maxsplit=1)
        clean_buttons[text.strip()] = link.strip()
    return clean_buttons
