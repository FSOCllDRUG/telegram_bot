import json

from db.r_engine import redis_conn


# Add group of users to redis
async def redis_mailing_users(users):
    for user_id in users:
        await redis_conn.sadd("users_for_mailing", user_id)


async def redis_mailing_msg(msg_id):
    await redis_conn.set("msg_for_mailing", msg_id, ex=21600)


async def redis_mailing_from(ch_id):
    await redis_conn.set("msg_from", ch_id, ex=21600)


async def redis_mailing_btns(btns):
    await redis_conn.set("btns_for_mailing", json.dumps(btns), ex=21600)


# Delete user from redis after successful mailing
async def redis_delete_user(user):
    await redis_conn.srem("users_for_mailing", user)
