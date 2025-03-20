import asyncio
import json
import time
import websockets
from twitch_bot import TwitchBot


class WebsocketHandler:
    """https://dev.twitch.tv/docs/eventsub/handling-websocket-events"""
    def __init__(self, bot:TwitchBot, keepalive_timeout_seconds=10):
        self.bot = bot
        self.keepalive_timeout_seconds = keepalive_timeout_seconds
        self.session_id = None
        self.ws = None
        self.old_ws = None
        self.last_message = None
    
    def start(self):
        asyncio.create_task(self.keepalive_check())
        asyncio.create_task(self.run_ws(f"wss://eventsub.wss.twitch.tv/ws?keepalive_timeout_seconds={self.keepalive_timeout_seconds}"))
    
    async def keepalive_check(self):
        while True:
            if time.time() - self.last_message > self.keepalive_timeout_seconds:
                await self.close(self.ws)
                self.ws, self.old_ws = None, None
                asyncio.create_task(self.run_ws(f"wss://eventsub.wss.twitch.tv/ws?keepalive_timeout_seconds={self.keepalive_timeout_seconds}"))
                await asyncio.sleep(10) # allow some time for new ws connection to set up
            await asyncio.sleep(1)

    async def run_ws(self, url):
        self.ws = await websockets.connect(url)
        async for msg in self.ws:
            data = json.loads(msg)
            message_type = data["metadata"]["message_type"]
            if message_type == "notification":
                self.handle_notification(data)
            elif message_type == "session_welcome":
                self.handle_session_welcome(data)
            elif message_type == "session_reconnect":
                self.handle_session_reconnect(data)
            elif message_type == "session_keepalive":
                self.handle_session_keepalive(data)
            elif message_type == "revocation":
                self.handle_revocation(data)

    def handle_notification(self, data):
        self.last_message = data["metadata"]["message_timestamp"]
        message_type = data["payload"]["subscription"]["type"]
        event_data = data["payload"]["event"]
        self.bot.events[message_type].trigger_callbacks(event_data)

    def handle_session_welcome(self, data):
        self.session_id = data["payload"]["session"]["id"]
        if self.old_ws:
            asyncio.create_task(self.close(self.old_ws))
            self.old_ws = None
        else:
            self.subscribe_to_events()

    def handle_session_reconnect(self, data):
        self.old_ws = self.ws
        url = data["payload"]["session"]["reconnect_url"]
        asyncio.create_task(self.run_ws(url))
    
    def handle_session_keepalive(self, data):
        self.last_message = data["metadata"]["message_timestamp"]

    def handle_revocation(self, data):
        pass

    async def close(self, ws:websockets.WebSocketClientProtocol, delay=1):
        await asyncio.sleep(delay)
        await ws.close()

    def subscribe_to_events(self):
        for event in self.bot.events:
            if event.callbacks:
                event.setup(
                    self.bot.auth.client_id,
                    self.bot.auth.access_token,
                    self.session_id,
                )
