# shared.py
# Single source of truth for shared state and configuration

# ======================
# Bot Status (read by web UI)
# ======================
BOT_STATUS = {
    "connected": False,
    "bot_name": None,
    "guild_name": None,
    "daily_channel_name": None,
    "last_daily_message": None,
}

# ======================
# Daily Message Settings
# ======================
DAILY_MESSAGE_TEXT = "Stewviets, awaken! It is a glorius day in the Stewviet Union to worship our Queen, Cookie."


DAILY_MESSAGE_HOUR = 8  # 8 AM CST

# ======================
# Control Flags
# ======================
# When True, the daily message will send on the next task tick
FORCE_DAILY_MESSAGE_ON_START = False













