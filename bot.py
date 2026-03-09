import os
import sys
import time
import fcntl
import asyncio
import aiohttp
import discord
from threading import Thread
from datetime import datetime, date
from zoneinfo import ZoneInfo
from discord.ext import tasks

# ======================
# PROCESS LOCK
# ======================
# Prevents two instances of the bot from running at the same time
lock_file = open('.bot.lock', 'w')
try:
    fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
except IOError:
    print("Another instance of the bot is already running. Exiting.")
    sys.exit(1)

# Import shared state explicitly so we can safely modify it later
import shared

# Discord targets
DAILY_MESSAGE_GUILD_ID = 1135060782812516373
DAILY_MESSAGE_CHANNEL_ID = 1135060785270370376

# State
last_daily_log_hour = None

# Timezone
CST = ZoneInfo("America/Chicago")

# ======================
# DISCORD CONFIG
# ======================

DISCORD_TOKEN = ""

intents = discord.Intents.default()
client = discord.Client(intents=intents)

# ======================
# TWITCH CONFIG
# ======================

TWITCH_CLIENT_ID = ""
TWITCH_CLIENT_SECRET = ""

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
# HELPERS
# ======================

def has_sent_today():
    """Reads the persistence file to check if a message went out today."""
    today = str(date.today())
    file_path = "last_daily_sent.txt"
    if not os.path.exists(file_path):
        return False
    with open(file_path, "r") as f:
        return f.read().strip() == today

def mark_as_sent():
    """Writes today's date to the persistence file."""
    today = str(date.today())
    file_path = "last_daily_sent.txt"
    with open(file_path, "w") as f:
        f.write(today)

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
    shared.BOT_STATUS["connected"] = True
    shared.BOT_STATUS["bot_name"] = str(client.user)

    guild = client.get_guild(DAILY_MESSAGE_GUILD_ID)
    if guild:
        shared.BOT_STATUS["guild_name"] = guild.name

        channel = guild.get_channel(DAILY_MESSAGE_CHANNEL_ID)
        if channel:
            shared.BOT_STATUS["daily_channel_name"] = channel.name

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
    global last_daily_log_hour
    now = datetime.now(CST)

    # Alive log every 3 hours
    if last_daily_log_hour != now.hour and now.hour % 3 == 0:
        print(f"[DailyTask] Alive check at {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        last_daily_log_hour = now.hour

    is_forced = shared.FORCE_DAILY_MESSAGE_ON_START

    # 1. Decide if we should run right now
    if not is_forced:
        # Not forced, so check if it's 8:00 AM
        if now.hour != shared.DAILY_MESSAGE_HOUR or now.minute != 0:
            return
        
        # It IS 8:00 AM, but did we already send it today?
        if has_sent_today():
            return
    else:
        print("[DailyTask] Daily message forced sent")

    # 2. Attempt to gather Discord objects
    guild = client.get_guild(DAILY_MESSAGE_GUILD_ID)
    if not guild:
        print("[DailyTask] Guild not found")
        return

    channel = guild.get_channel(DAILY_MESSAGE_CHANNEL_ID)
    if not channel:
        print("[DailyTask] Channel not found")
        return

    # 3. Send the message
    await channel.send(shared.DAILY_MESSAGE_TEXT)

    # 4. Mark it as done and clear flags
    mark_as_sent()
    shared.FORCE_DAILY_MESSAGE_ON_START = False
    shared.BOT_STATUS["last_daily_message"] = now.strftime("%Y-%m-%d %H:%M:%S %Z")

    print("[DailyTask] Daily message sent")


def run_web():
    from web import app
    app.run(host="0.0.0.0", port=5000)

if __name__ == "__main__":
    client.run(DISCORD_TOKEN)