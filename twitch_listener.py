import asyncio
import json
import requests
import websockets


class EventListener():
    def __init__(self, access_token, client_id, user_id, broadcaster_id):
        self.access_token = access_token
        self.client_id = client_id
        self.user_id = user_id
        self.broadcaster_id = broadcaster_id

        self.channel_chat_message = []
        self.channel_follow = []


    async def setup_subscriptions(self, session_id):
        events = [
            {"attribute": "channel_chat_message", "type": "channel.chat.message", "version": "1", "condition": {"broadcaster_user_id": self.broadcaster_id, "user_id": self.user_id}},
            {"attribute": "channel_follow", "type": "channel.follow", "version": "2", "condition": {"broadcaster_user_id": self.broadcaster_id, "moderator_user_id": self.user_id}},
        ]


        for event in events:
            if not getattr(self, event["attribute"], None):
                continue

            subscription_data = {
                "type": event["type"],
                "version": event["version"],
                "condition": event["condition"],
                "transport": {
                    "method": "websocket",
                    "session_id": session_id,
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
                raise ValueError(f"Subscription request failed for {event["type"]} with status {response.status_code}")


    async def on_event(self, event_str):
        event = json.loads(event_str)
        event_type = event["metadata"]["message_type"]

        if event_type == "session_welcome":
            session_id = event["payload"]["session"]["id"]
            await self.setup_subscriptions(session_id)

        elif event_type == "notification":
            notification_type = event["payload"]["subscription"]["type"].replace(".", "_")
            for listener in getattr(self, notification_type, None):
                asyncio.create_task(listener(event))

        elif event_type == "session_keepalive":
            pass

        else:
            print(f"Unhandled event:\n{event}")


    async def run_async(self):
        async with websockets.connect("wss://eventsub.wss.twitch.tv/ws") as websocket:
            async for event in websocket:
                await self.on_event(event)


    def run(self):
        asyncio.run(self.run_async())
