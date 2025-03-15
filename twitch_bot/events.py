import asyncio
from typing import Iterator

from twitch_bot.api import create_eventsub_subscription


class EventSubscription():
    def __init__(self, name:str, version:str, condition:dict[str, str], scopes:list[str]):
        self.name = name
        self.version = version
        self.condition = condition
        self.scopes = scopes
        self.callbacks = []

    def add_callback(self, callback):
        self.callbacks.append(callback)

    def trigger_callbacks(self, event_data):
        """Passes event data to registered callback functions"""
        for callback in self.callbacks:
            if asyncio.iscoroutinefunction(callback):
                asyncio.create_task(callback(event_data))
            else:
                callback(event_data)

    def setup(self, client_id, access_token, session_id):
        create_eventsub_subscription(client_id, access_token, session_id, self.name, self.version, self.condition)


class EventSubscriptions:
    """
    Aggregates all event subscription types described at:  
    https://dev.twitch.tv/docs/eventsub/eventsub-subscription-types/

    Stores instances of 'EventSubscription' for each event subscription type  
    Provides an easy way to reference and iterate over event types
    """
    def __init__(self, broadcaster_id, user_id, client_id):
        self.channel_chat_message = EventSubscription(
            name = "channel.chat.message",
            version = "1",
            condition = {
                "broadcaster_user_id": broadcaster_id,
                "user_id": user_id,
            },
            scopes = ["user:read:chat", "user:bot", "channel:bot"],
        )

        self.channel_follow = EventSubscription(
            name = "channel.follow",
            version = "2",
            condition = {
                "broadcaster_user_id": broadcaster_id,
                "moderator_user_id": user_id,
            },
            scopes = ["moderator:read:followers"],
        )

        self.stream_offline = EventSubscription(
            name = "stream.offline",
            version = "1",
            condition = {
                "broadcaster_user_id": broadcaster_id,
            },
            scopes = ["user:bot"],
        )

        self.stream_online = EventSubscription(
            name = "stream.online",
            version = "1",
            condition = {
                "broadcaster_user_id": broadcaster_id,
            },
            scopes = ["user:bot"],
        )

        self.event_map = {
            event.name: event
            for event in vars(self).values() if isinstance(event, EventSubscription)
        }

    def __getitem__(self, key):
        return self.event_map[key]

    def __iter__(self) -> Iterator[EventSubscription]:
        return iter(self.event_map.values())
