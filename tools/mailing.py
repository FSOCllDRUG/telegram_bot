import asyncio
import datetime
import json
import logging
import re

import tqdm

from create_bot import bot
from db.r_engine import redis_conn
from db.r_operations import redis_delete_user
from keyboards.inline import get_callback_btns
from loggers.setup_logger import module_logger

logger_name = "tools.mailing"
logger = logging.getLogger(logger_name)
module_logger(logger_name, "logs_mailing", "mailing.log", logging.INFO, console=True, detail=False)


async def format_timedelta(td, lang="en"):
    translations = {
        "en": {
            "hours": "hour(s)",
            "minutes": "minute(s)",
            "seconds": "second(s)"
        },
        "ru": {
            "hours": "часа(ов)",
            "minutes": "минут(ы)",
            "seconds": "секунд(ы)"
        }
    }

    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if hours > 0:
        parts.append(f"{hours} {translations[lang]["hours"]}")
    if minutes > 0:
        parts.append(f"{minutes} {translations[lang]["minutes"]}")
    if seconds > 0:
        parts.append(f"{seconds} {translations[lang]["seconds"]}")

    return " ".join(parts)


async def get_users_for_mailing():
    users = await redis_conn.smembers("users_for_mailing")
    return {user.decode("utf-8") for user in users}


async def get_msg_for_mailing():
    return (await redis_conn.get("msg_for_mailing")).decode("utf-8")


async def get_msg_from():
    return (await redis_conn.get("msg_from")).decode("utf-8")


async def get_btns_for_mailing():
    btns_str = (await redis_conn.get("btns_for_mailing")).decode("utf-8")
    btns_dict = json.loads(btns_str)
    return btns_dict


async def simple_mailing():
    logger.info("=== MAILING STARTED ===")

    users = await get_users_for_mailing()
    msg_id = await get_msg_for_mailing()
    ch_id = await get_msg_from()
    btns: dict = await get_btns_for_mailing()
    print(btns)
    total_users = len(users)

    pbar = tqdm.tqdm(total=total_users, desc="Mailing progress")
    progress_text = f"Прогресс рассылки:\n0%|{"⬜️" * 10}|\n{pbar.n}/{total_users}"
    progress_msg = await bot.send_message(chat_id=ch_id, text=f"{progress_text}")
    prgss_msg_id = progress_msg.message_id

    start_time = datetime.datetime.now()
    last_update_time = start_time

    success, notsuccess, blocked = 0, 0, 0

    for user in users:
        try:
            if btns:
                await bot.copy_message(chat_id=str(user), from_chat_id=str(ch_id), message_id=str(msg_id),
                                       reply_markup=get_callback_btns(btns=btns))
            else:
                await bot.copy_message(chat_id=str(user), from_chat_id=str(ch_id), message_id=str(msg_id))
            logger.info(f"Sent message to {user}")
            success += 1
            await redis_delete_user(user)
        except Exception as e:
            error_message = str(e)
            if re.search(r"Forbidden: bot was blocked by the user", error_message):
                logger.warning(f"User {user} blocked the bot. Removing from mailing list.")
                await redis_delete_user(user)
                blocked += 1
            else:
                logger.error(f"Failed to send message to {user}: {e}")
                notsuccess += 1

        pbar.update(1)
        await asyncio.sleep(1 / 10)
        """
        For 09.2024 Telegram API limit is 30 messages per second
        Tests on local machine showed these results for 150 messages:
        1/10 = 25s
        1/15 = 26s
        1/20 = 27s
        1/25 = 29s
        1/30 = >29s
        """
        if (datetime.datetime.now() - last_update_time).total_seconds() >= 1:
            progress = pbar.n / total_users * 100
            bar_length = 10
            filled_length = int(bar_length * pbar.n // total_users)
            bar = "🟩" * filled_length + "⬜️" * (bar_length - filled_length)
            progress_text = f"Прогресс рассылки:\n{progress:.2f}%|{bar}|\n{pbar.n}/{total_users}"
            await bot.edit_message_text(chat_id=ch_id, message_id=prgss_msg_id, text=progress_text)
            last_update_time = datetime.datetime.now()

    end_time = datetime.datetime.now()
    elapsed_time = end_time - start_time
    elapsed_time_str = await format_timedelta(elapsed_time)
    if elapsed_time_str == "":
        elapsed_time_str = "<1 second"

    logger.info("=== MAILING FINISHED ===")
    logger.info(
        f"Sent messages to {success}, failed to send to {notsuccess}, bot blocked by {blocked}. "
        f"Time taken: {elapsed_time_str}"
    )
    elapsed_time_str_ru = await format_timedelta(elapsed_time, lang="ru")
    pbar.close()
    await bot.delete_message(chat_id=ch_id, message_id=prgss_msg_id)
    return success, notsuccess, blocked, elapsed_time_str_ru
