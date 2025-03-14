import json
import asyncio

import websockets

import twitch_bot.api as api
from twitch_bot.audio import AudioSubscription
from twitch_bot.events import EventSubscriptions
from twitch_bot.auth import TwitchAuthManager

class TwitchBot():
    def __init__(
        self,
        auth:TwitchAuthManager,
        user_name:str,
        broadcaster_name:str,
        user_id:str=None,
        broadcaster_id:str=None,
        bot_chat_prefix:str="🤖",
    ):
        self.auth = auth
        self.user_name = user_name
        self.broadcaster_name = broadcaster_name
        self.bot_chat_prefix = bot_chat_prefix

        # get IDs if not provided
        if user_id is None or broadcaster_id is None:
            auth.ensure_valid_tokens() # need valid access token to get IDs
        if user_id:
            self.user_id = user_id
        else:
            response = api.get_users(self.auth.client_id, self.auth.access_token, id=f"login={user_name}")
            self.user_id = response.json()["data"][0]["id"]
        if broadcaster_id:
            self.broadcaster_id = broadcaster_id
        else:
            response = api.get_users(self.auth.client_id, self.auth.access_token, id=f"login={broadcaster_name}")
            self.broadcaster_id = response.json()["data"][0]["id"]

        self.audio = AudioSubscription(self.broadcaster_name)
        self.events = EventSubscriptions(
            self.broadcaster_id,
            self.user_id,
            self.auth.client_id,
        )
        self.is_live = asyncio.Event()
        self.events.stream_online.add_callback(lambda event: self.is_live.set())
        self.events.stream_offline.add_callback(lambda event: self.is_live.clear())

    def send_chat_message(self, message):
        message_with_prefix = f"{self.bot_chat_prefix} {message}" if self.bot_chat_prefix else message
        api.send_chat_message(self.user_id, self.broadcaster_id, self.auth.client_id, self.auth.access_token, message_with_prefix)

    def run(self):
        required_scopes = set(scope for event in self.events if event.callbacks for scope in event.scopes)
        self.auth.required_scopes = required_scopes
        self.auth.ensure_valid_tokens()

        response = api.get_streams(self.broadcaster_id, self.auth.client_id, self.auth.access_token)
        live_data = response.json()["data"]
        self.is_live.set() if live_data else self.is_live.clear()

        asyncio.run(self.run_async())

    async def run_async(self):
        tasks = []
        tasks.append(asyncio.create_task(self.auth.keep_alive()))
        tasks.append(asyncio.create_task(self.run_websocket_events()))
        if self.audio.callbacks:
            tasks.append(asyncio.create_task(self.audio.run(self.is_live)))

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            print("Exited")
            return

    async def run_websocket_events(self):
        """https://dev.twitch.tv/docs/eventsub/handling-websocket-events/"""
        async with websockets.connect("wss://eventsub.wss.twitch.tv/ws") as websocket:

            # session welcome
            welcome_msg = await websocket.recv()
            data = json.loads(welcome_msg)
            message_type = data["metadata"]["message_type"]
            if message_type != "session_welcome":
                raise Exception("Did not recieve session welcome message")
            self.session_id = data["payload"]["session"]["id"]

            # set up event subscriptions
            for event in self.events:
                if event.callbacks:
                    event.setup(self.auth.client_id, self.auth.access_token, self.session_id)

            # handle events
            async for msg in websocket:
                data = json.loads(msg)
                message_type = data["metadata"]["message_type"]
                if message_type == "notification":
                    event_type = data["payload"]["subscription"]["type"]
                    event_handler = self.events[event_type]
                    if not event_handler:
                        raise Exception("No handler for event")
                    event_data = data["payload"]["event"]
                    event_handler.trigger_callbacks(event_data)
