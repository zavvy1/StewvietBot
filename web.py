from flask import Flask
import shared

from shared import BOT_STATUS, DAILY_MESSAGE_HOUR

app = Flask(__name__)

@app.route("/")
def home():
    return f"""
    <h1>Stewviet Bot Status</h1>
    <ul>
<form action="/send_daily_now" method="post">
    <button type="submit">Send Daily Message On Start</button>
</form>

        <li><b>Connected:</b> {BOT_STATUS['connected']}</li>
        <li><b>Bot Name:</b> {BOT_STATUS['bot_name']}</li>
        <li><b>Server:</b> {BOT_STATUS['guild_name']}</li>
        <li><b>Daily Channel:</b> {BOT_STATUS['daily_channel_name']}</li>
        <li><b>Daily Time:</b> {DAILY_MESSAGE_HOUR}:00 CST</li>
        <li><b>Last Daily Message:</b> {BOT_STATUS['last_daily_message']}</li>
    </ul>
    """
@app.route("/send_daily_now", methods=["POST"])
def send_daily_now():
    shared.FORCE_DAILY_MESSAGE_ON_START = True
    return {"status": "ok"}

