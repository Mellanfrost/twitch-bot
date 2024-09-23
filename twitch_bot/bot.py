import asyncio
import json
import os
import secrets
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import dotenv
import numpy as np
import requests
import websockets
from twitchrealtimehandler import TwitchAudioGrabber

dotenv.load_dotenv(override=True)


class UnauthorizedError(Exception):
    """Error for 401 status code on requests -> access token is either expired, does not have the correct scopes, or is invalid"""
    pass

class EventSubscription:
    def __init__(self, name, version, conditions, scopes):
        self.name = name
        self.version = version
        self.conditions = conditions
        self.scopes = scopes
        self.listeners = []

class AudioSubscription:
    def __init__(self, segment_duration_seconds=1, sample_rate=44100, channels=1):
        self.segment_duration_seconds = segment_duration_seconds
        self.sample_rate = sample_rate
        self.channels = channels
        self.listeners = []

class TwitchBot():
    def __init__(self, user_id:str, broadcaster_id:str, browser_path=None, port=3000, prefix="🤖"):
        self.default_scopes = [
            "user:write:chat",
        ]
        self.client_id = os.getenv("CLIENT_ID")
        self.client_secret = os.getenv("CLIENT_SECRET")
        self.access_token = os.getenv("ACCESS_TOKEN") # = None if not set -> will be generated when running bot
        self.refresh_token = os.getenv("REFRESH_TOKEN")
        self.token_scopes = self.default_scopes

        self.user_id = user_id
        self.user_name = None
        self.broadcaster_id = broadcaster_id
        self.broadcaster_name = None
        
        self.browser_path = browser_path
        self.port = port
        self.prefix = prefix

        self.channel_chat_message = EventSubscription(
            name="channel.chat.message",
            version="1",
            conditions={"broadcaster_user_id": self.broadcaster_id, "user_id": self.user_id},
            scopes=["user:read:chat", "user:bot", "channel:bot"],
        )
        self.channel_follow = EventSubscription(
            name="channel.follow",
            version="2",
            conditions={"broadcaster_user_id": self.broadcaster_id, "moderator_user_id": self.user_id},
            scopes=["moderator:read:followers"],
        )

        self.audio = AudioSubscription()

    def generate_access_token(self):
        active_scopes = set(self.default_scopes)
        for subscription in self.__dict__.values():
            if not isinstance(subscription, EventSubscription):
                continue
            if not subscription.listeners:
                continue
            active_scopes.update(subscription.scopes)
        scope = " ".join(active_scopes)
        expected_state = secrets.token_urlsafe(32)
        authorization_url = (
            f"https://id.twitch.tv/oauth2/authorize"
            f"?response_type=code"
            f"&client_id={self.client_id}"
            f"&redirect_uri=http://localhost:{self.port}"
            f"&scope={scope}"
            f"&state={expected_state}"
        )

        class TwitchRedirectHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                parsed_url = urllib.parse.urlparse(self.path)
                query_params = urllib.parse.parse_qs(parsed_url.query)

                state = query_params.get("state", [None])[0]
                if state != expected_state:
                    raise ValueError("Invalid state parameter - does not match original state")

                code = query_params.get("code", [None])[0]
                self.server.code = code

        server_address = ("", self.port)
        httpd = HTTPServer(server_address, TwitchRedirectHandler)
        if self.browser_path:
            webbrowser.register("specified_browser", None, webbrowser.BackgroundBrowser(self.browser_path))
            webbrowser.get("specified_browser").open(authorization_url)
        else:
            webbrowser.open(authorization_url)
        httpd.handle_request()
        code = httpd.code

        token_url = "https://id.twitch.tv/oauth2/token"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": f"http://localhost:{self.port}"
        }
        response = requests.post(token_url, data=payload)
        if response.status_code == 401:
            raise UnauthorizedError()
        response_data = response.json()
        access_token = response_data.get("access_token")
        refresh_token = response_data.get("refresh_token")
        token_scopes = response_data["scope"]

        self.valid_access_token(access_token)
        
        dotenv_path = dotenv.find_dotenv()
        dotenv.set_key(dotenv_path, "ACCESS_TOKEN", access_token)
        dotenv.set_key(dotenv_path, "REFRESH_TOKEN", refresh_token)

        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_scopes = token_scopes

    def refresh_access_token(self):
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        response = requests.post("https://id.twitch.tv/oauth2/token", headers=headers, data=data)
        if response.status_code == 401:
            raise UnauthorizedError()
        elif response.status_code != 200:
            raise ValueError()
        response_data = response.json()
        access_token = response_data.get("access_token")
        refresh_token = response_data.get("refresh_token")
        token_scopes = response_data["scope"]

        self.valid_access_token(access_token)
        
        dotenv_path = dotenv.find_dotenv()
        dotenv.set_key(dotenv_path, "ACCESS_TOKEN", access_token)
        dotenv.set_key(dotenv_path, "REFRESH_TOKEN", refresh_token)

        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_scopes = token_scopes

    def valid_access_token(self, access_token):
        headers = {"Authorization": f"OAuth {access_token}"}
        response = requests.get("https://id.twitch.tv/oauth2/validate", headers=headers)
        if response.status_code == 401:
            raise UnauthorizedError()
        if response.status_code != 200:
            raise ValueError()
        response_data = response.json()
        token_scopes = response_data["scopes"]
        required_scopes = set(self.default_scopes)
        for subscription in self.__dict__.values():
            if not isinstance(subscription, EventSubscription):
                continue
            if not subscription.listeners:
                continue
            required_scopes.update(subscription.scopes)
        for scope in required_scopes:
            if scope not in token_scopes:
                raise UnauthorizedError("Token scopes does not match required scopes")
        if token_scopes != self.token_scopes:
            self.token_scopes = token_scopes
            print("Updated token scopes")

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
            "message": f"{self.prefix} {message}"
        }
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 401:
            raise UnauthorizedError()
        if response.status_code != 200:
            raise ValueError(f"Send message request failed for {message} with status {response.status_code}")

    def id_to_username(self, user_id):
        """
        https://dev.twitch.tv/docs/api/reference/#get-users
        """
        url = f"https://api.twitch.tv/helix/users?id={user_id}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Client-Id": self.client_id
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 401:
            raise UnauthorizedError()
        if response.status_code != 200:
            raise ValueError(f"Username request failed for {user_id} with status {response.status_code}")
        response_data = response.json()
        username = response_data["data"][0]["login"]
        return username

    async def setup_event_subscriptions(self, session_id):
        url = "https://api.twitch.tv/helix/eventsub/subscriptions"
        headers = {
            "Authorization": f"Bearer {self.access_token}", 
            "Client-Id": self.client_id, 
            "Content-Type": "application/json",
            "Accept": "application/vnd.twitchtv.v5+json"
        }
        for subscription in self.__dict__.values():
            if not isinstance(subscription, EventSubscription):
                continue
            if not subscription.listeners:
                continue
            subscription_data = {
                "type": subscription.name,
                "version": subscription.version,
                "condition": subscription.conditions,
                "transport": {
                    "method": "websocket",
                    "session_id": session_id,
                }
            }
            response = requests.post(url, headers=headers, json=subscription_data)
            if response.status_code == 401:
                raise UnauthorizedError()
            if response.status_code != 202:
                raise ValueError(f"Subscription request failed for {subscription.name} with status {response.status_code}")

    async def on_event(self, event_str):
        event = json.loads(event_str)
        event_type = event["metadata"]["message_type"]
        if event_type == "session_welcome":
            session_id = event["payload"]["session"]["id"]
            await self.setup_event_subscriptions(session_id)
        elif event_type == "notification":
            notification_type = event["payload"]["subscription"]["type"].replace(".", "_")
            event_listener = getattr(self, notification_type, None)
            for listener in event_listener.listeners:
                asyncio.create_task(listener(event))
        elif event_type == "session_keepalive":
            pass
        else:
            print(f"Unhandled event:\n{event}")

    async def run_event_listener(self):
        async with websockets.connect("wss://eventsub.wss.twitch.tv/ws") as websocket:
            async for event in websocket:
                await self.on_event(event)

    async def grab_audio(self):
        grabber = TwitchAudioGrabber(
            twitch_url=f"https://www.twitch.tv/{self.broadcaster_name}",
            blocking=True,
            segment_length=self.audio.segment_duration_seconds,
            rate=self.audio.sample_rate,
            channels=self.audio.channels,
            dtype=np.int16
        )
        while True:
            audio = grabber.grab()
            if audio is None:
                continue
            for listener in self.audio.listeners:
                asyncio.create_task(listener(audio))
            await asyncio.sleep(self.audio.segment_duration_seconds)


    def update_access_token(self):
        print("Access token failed, attempting to update...")
        try:
            self.refresh_access_token()
            print("Refreshed access token")
        except:
            try:
                self.generate_access_token()
                print("Generated new access token")
            except:
                raise ValueError("Failed to generate valid access token")

    async def run_async(self):
        tasks = []
        while True:
            try:
                self.valid_access_token(self.access_token)
                print("Got a valid access token, running bot...")
                for subscription in self.__dict__.values():
                    if isinstance(subscription, EventSubscription) and subscription.listeners:
                        tasks.append(asyncio.create_task(self.run_event_listener()))
                        break
                if self.audio.listeners:
                    if not self.broadcaster_name:
                        self.broadcaster_name = self.id_to_username(self.broadcaster_id)
                    tasks.append(asyncio.create_task(self.grab_audio()))
                await asyncio.gather(*tasks)
            except UnauthorizedError:
                self.update_access_token()
            except asyncio.CancelledError:
                print("Exited")
                break

    def run(self):
        asyncio.run(self.run_async())
