import asyncio
import datetime
import logging
import re

from create_bot import bot
from db.r_engine import redis_conn
from db.r_operations import redis_delete_user
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


async def simple_mailing():
    success = 0
    notsuccess = 0
    blocked = 0
    start_time = datetime.datetime.now()

    users = await redis_conn.smembers("users_for_mailing")
    users = {user.decode("utf-8") for user in users}
    msg_id = (await redis_conn.get("msg_for_mailing")).decode("utf-8")
    ch_id = (await redis_conn.get("msg_from")).decode("utf-8")

    logger.info("=== MAILING STARTED ===")
    for user in users:
        try:
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
        await asyncio.sleep(1/25)  # For 09.2024 Telegram API limit is 30 messages per second
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

    return success, notsuccess, blocked, elapsed_time_str_ru
