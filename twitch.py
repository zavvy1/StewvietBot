import aiohttp
import os
import time

class TwitchClient:
    def __init__(self):
        self.client_id = os.getenv("TWITCH_CLIENT_ID")
        self.client_secret = os.getenv("TWITCH_CLIENT_SECRET")
        self.token = None
        self.token_expiry = 0

    async def get_token(self):
        if self.token and time.time() < self.token_expiry:
            return self.token

        url = "https://id.twitch.tv/oauth2/token"
        params = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials"
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, params=params) as resp:
                data = await resp.json()
                self.token = data["access_token"]
                self.token_expiry = time.time() + data["expires_in"] - 60
                return self.token

    async def get_stream_info(self, username):
        token = await self.get_token()
        headers = {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {token}"
        }

        url = f"https://api.twitch.tv/helix/streams?user_login={username}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                data = await resp.json()

                if not data["data"]:
                    return None

                stream = data["data"][0]
                return {
                    "title": stream["title"],
                    "game": stream["game_name"],
                    "url": f"https://twitch.tv/{username}"
                }