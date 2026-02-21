from threading import Thread
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
CST  = ZoneInfo("America/Chicago")
import time
import asyncio
import aiohttp
import discord
from discord.ext import tasks

from shared import (
    BOT_STATUS,
    DAILY_MESSAGE_TEXT,
    DAILY_MESSAGE_HOUR,
    FORCE_DAILY_MESSAGE_ON_START,
)

# Discord targets
DAILY_MESSAGE_GUILD_ID = 1135060782812516373
DAILY_MESSAGE_CHANNEL_ID = 1135060785270370376

# State
last_daily_message_date = None
last_daily_log_hour = None

# Timezone
CST = ZoneInfo("America/Chicago")

# ======================
# DISCORD CONFIG
# ======================

DISCORD_TOKEN = "MTQ2MjcwODQ0MzU2NjU3NTcwMA.Gyvl3v.nnNNvXBrfQJPijICm3pSzpT-IAExie4CqLWvb0"

intents = discord.Intents.default()
client = discord.Client(intents=intents)

# ======================
# TWITCH CONFIG
# ======================

TWITCH_CLIENT_ID = "hp2mcz2rdnb4qsmqwtx2b7jpa5dn94"
TWITCH_CLIENT_SECRET = "un6ob5b8kjzhpfdndr7293q9w1gomh"

twitch_token = None
twitch_token_expiry = 0

# ======================
# SERVER CONFIG
# ======================

SERVERS = {
    1135060782812516373: {  # Stewviet Union
        "channel_id": 1440743455176527924,
        "role_id": None,
        "streamers": [
            "ohnoitsriley",
            "thebrandocus",
            "squishrat",
            "loosh",
            "RagerRedhead",
            "NickDrivesSlow",
            "WhizzyLL",
        ]
    },
    1462847794577543190: {  # Riley's Test Bed
        "channel_id": 1462847843495575603,
        "role_id": 1462847968330911925,
        "streamers": [
            "ohnoitsriley",
        ]
    }
}

CHECK_INTERVAL = 60  # seconds
live_status = {}

# ======================
# TWITCH FUNCTIONS
# ======================

async def get_twitch_token():
    global twitch_token, twitch_token_expiry

    if twitch_token and time.time() < twitch_token_expiry:
        return twitch_token

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://id.twitch.tv/oauth2/token",
            params={
                "client_id": TWITCH_CLIENT_ID,
                "client_secret": TWITCH_CLIENT_SECRET,
                "grant_type": "client_credentials"
            }
        ) as resp:
            data = await resp.json()
            twitch_token = data["access_token"]
            twitch_token_expiry = time.time() + data["expires_in"] - 60
            return twitch_token


async def check_twitch_stream(username):
    token = await get_twitch_token()

    headers = {
        "Client-ID": TWITCH_CLIENT_ID,
        "Authorization": f"Bearer {token}",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://api.twitch.tv/helix/streams",
            headers=headers,
            params={"user_login": username},
        ) as resp:
            data = await resp.json()
            if data.get("data"):
                return data["data"][0]
            return None

# ======================
# DISCORD LOOP
# ======================

@tasks.loop(seconds=CHECK_INTERVAL)
async def check_streams():
    for guild_id, cfg in SERVERS.items():
        guild = client.get_guild(guild_id)
        if not guild:
            continue

        channel = client.get_channel(cfg["channel_id"])
        if not channel:
            continue

        role_id = cfg.get("role_id")
        role_mention = f"<@&{role_id}>" if role_id else ""


        for name in cfg["streamers"]:
            key = f"{guild_id}:{name}"
            was_live = live_status.get(key, False)

            stream = await check_twitch_stream(name)

            if stream and not was_live:
                await channel.send(
                    f"{role_mention}\n" if role_mention else ""
                    f"?? **{name} is LIVE on Twitch!**\n"
                    f"?? **Game:** {stream['game_name']}\n"
                    f"?? **Title:** {stream['title']}\n"
                    f"?? https://twitch.tv/{name}"
                )
                live_status[key] = True

            if not stream:
                live_status[key] = False

# ======================
# EVENTS
# ======================

@client.event
async def on_ready():
    BOT_STATUS["connected"] = True
    BOT_STATUS["bot_name"] = str(client.user)

    guild = client.get_guild(DAILY_MESSAGE_GUILD_ID)
    if guild:
        BOT_STATUS["guild_name"] = guild.name

        channel = guild.get_channel(DAILY_MESSAGE_CHANNEL_ID)
        if channel:
            BOT_STATUS["daily_channel_name"] = channel.name

    print(f"Logged in as {client.user}")

    web_thread = Thread(target=run_web, daemon=True)
    web_thread.start()

    if not check_streams.is_running():
        check_streams.start()

    if not daily_message_task.is_running():
        daily_message_task.start()


# ======================
# START BOT
# ======================
@tasks.loop(minutes=1)
async def daily_message_task():
    from shared import (
        DAILY_MESSAGE_HOUR,
        DAILY_MESSAGE_TEXT,
        FORCE_DAILY_MESSAGE_ON_START,
        BOT_STATUS,
    )

    global last_daily_message_date, last_daily_log_hour

    now = datetime.now(CST)

    # Alive log every 3 hours
    if last_daily_log_hour != now.hour and now.hour % 3 == 0:
        print(f"[DailyTask] Alive check at {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        last_daily_log_hour = now.hour

    # Only run at scheduled time unless forced
    if not FORCE_DAILY_MESSAGE_ON_START:
        if now.hour != DAILY_MESSAGE_HOUR or now.minute != 0:
            return

    # Prevent duplicate sends
    if last_daily_message_date == now.date():
        return

    guild = client.get_guild(DAILY_MESSAGE_GUILD_ID)
    if not guild:
        print("[DailyTask] Guild not found")
        return

    channel = guild.get_channel(DAILY_MESSAGE_CHANNEL_ID)
    if not channel:
        print("[DailyTask] Channel not found")
        return

    await channel.send(DAILY_MESSAGE_TEXT)

    last_daily_message_date = now.date()
    FORCE_DAILY_MESSAGE_ON_START  = False
    BOT_STATUS["last_daily_message"] = now.strftime("%Y-%m-%d %H:%M:%S %Z")

    print("[DailyTask] Daily message sent")

def run_web():
    from web import app
    app.run(host="0.0.0.0", port=5000)

client.run(DISCORD_TOKEN)
