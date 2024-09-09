import asyncio
import os

import requests
from dotenv import load_dotenv

from twitch_listener import EventListener

load_dotenv(override=True)


class TwitchBot():
    def __init__(self, username:str, broadcaster_username:str):
        self.access_token = os.getenv("ACCESS_TOKEN")
        self.client_id = os.getenv("CLIENT_ID")

        self.broadcaster_username = broadcaster_username
        self.username = username

        self.user_id = self.username_to_id(username)
        if broadcaster_username == username:
            self.broadcaster_id = self.user_id
        else:
            self.broadcaster_id = self.username_to_id(broadcaster_username)

        self.events = EventListener(
            access_token = self.access_token,
            client_id = self.client_id,
            user_id = self.user_id,
            broadcaster_id = self.broadcaster_id,
        )

    async def send_message(self, message):
        """
        https://dev.twitch.tv/docs/api/reference/#send-chat-message
        """

        url = "https://api.twitch.tv/helix/chat/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Client-Id": self.client_id,
            "Content-Type": "application/json"
        }
        data = {
            "broadcaster_id": self.broadcaster_id,
            "sender_id": self.user_id,
            "message": message
        }
        response = requests.post(url, headers=headers, json=data)
        if response.status_code != 200:
            raise ValueError(f"Send message request failed for {message} with status {response.status_code}")

    def username_to_id(self, username):
        """
        https://dev.twitch.tv/docs/api/reference/#get-users
        """

        url = f"https://api.twitch.tv/helix/users?login={username}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Client-Id": self.client_id
        }
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            raise ValueError(f"User ID request failed for {username} with status {response.status_code}")
        data = response.json()
        user_id = data["data"][0]["id"]
        return user_id

    async def run_async(self):
        tasks = []
        tasks.append(asyncio.create_task(self.events.run_async()))
        await asyncio.gather(*tasks)

    def run(self):
        asyncio.run(self.run_async())
