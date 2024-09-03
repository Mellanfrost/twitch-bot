import asyncio
import json
import requests
import websockets


class ChatListener():
    def __init__(self, access_token, client_id, user_id, broadcaster_id):
        self.access_token = access_token
        self.client_id = client_id
        self.user_id = user_id
        self.broadcaster_id = broadcaster_id

        self.listeners = []


    async def add_subscription(self, session_id):
        subscription_data = {
            "type": "channel.chat.message",
            "version": "1",
            "condition": {
                "broadcaster_user_id": self.broadcaster_id,
                "user_id": self.user_id,
            },
            "transport": {
                "method": "websocket",
                "session_id": f"{session_id}",
            }
        }

        response = requests.post(
            "https://api.twitch.tv/helix/eventsub/subscriptions",
            headers={
                "Authorization": f"Bearer {self.access_token}", 
                "Client-Id": self.client_id, 
                "Content-Type": "application/json",
                "Accept": "application/vnd.twitchtv.v5+json"
            },
            data=json.dumps(subscription_data)
        )

        if not response.ok:
            raise ValueError(f"Subscription request failed with status {response.status_code}")


    async def on_message(self, message):
        event = json.loads(message)
        event_type = event["metadata"]["message_type"]

        if event_type == "session_welcome":
            session_id = event["payload"]["session"]["id"]
            await self.add_subscription(session_id)

        elif event_type == "notification":
            for listener in self.listeners:
                asyncio.create_task(listener(event))

        elif event_type == "session_keepalive":
            pass

        else:
            print(f"Unhandled event:\n{event}")


    async def run_async(self):
        async with websockets.connect("wss://eventsub.wss.twitch.tv/ws") as websocket:
            self.websocket = websocket
            async for message_batch in self.websocket:
                await self.on_message(message_batch)


    def run(self):
        asyncio.run(self.run_async())
