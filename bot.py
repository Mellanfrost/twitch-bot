import asyncio
import json
import os
import secrets
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import dotenv
import requests
import websockets

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

class TwitchBot():
    def __init__(self, username:str, broadcaster_username:str, browser_path=None, port=3000):
        self.client_id = os.getenv("CLIENT_ID")
        self.client_secret = os.getenv("CLIENT_SECRET")
        self.access_token = os.getenv("ACCESS_TOKEN") # = None if not set -> will be generated when running bot
        self.refresh_token = os.getenv("REFRESH_TOKEN")

        if not self.valid_access_token(self.access_token):
            self.update_access_token()

        self.broadcaster_username = broadcaster_username
        self.username = username
        self.user_id = self.username_to_id(self.username)
        if self.broadcaster_username == self.username:
            self.broadcaster_id = self.user_id
        else:
            self.broadcaster_id = self.username_to_id(self.broadcaster_username)

        self.browser_path = browser_path
        self.port = port

        self.channel_chat_message = EventSubscription(
            name="channel.chat.message",
            version="1",
            conditions={"broadcaster_user_id": self.broadcaster_id, "user_id": self.user_id},
            scopes=[],
        )
        self.channel_follow = EventSubscription(
            name="channel.follow",
            version="2",
            conditions={"broadcaster_user_id": self.broadcaster_id, "moderator_user_id": self.user_id},
            scopes=[],
        )

        self.scopes = [
            "user:read:chat",
            "user:bot",
            "channel:bot",
            "user:write:chat",
            "moderator:read:followers",
        ]

    def generate_access_token(self):
        scope = " ".join(self.scopes)
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

        if not self.valid_access_token(access_token):
            raise ValueError(f"Failed to generate a valid token: {access_token}")
        
        dotenv_path = dotenv.find_dotenv()
        dotenv.set_key(dotenv_path, "ACCESS_TOKEN", access_token)
        dotenv.set_key(dotenv_path, "REFRESH_TOKEN", refresh_token)

        self.access_token = access_token
        self.refresh_token = refresh_token

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

        if not self.valid_access_token(access_token):
            raise ValueError()
        
        dotenv_path = dotenv.find_dotenv()
        dotenv.set_key(dotenv_path, "ACCESS_TOKEN", access_token)
        dotenv.set_key(dotenv_path, "REFRESH_TOKEN", refresh_token)

        self.access_token = access_token
        self.refresh_token = refresh_token

    def valid_access_token(self, access_token, raise_on_fail=False):
        headers = {"Authorization": f"OAuth {access_token}"}
        response = requests.get("https://id.twitch.tv/oauth2/validate", headers=headers)
        if response.status_code == 200:
            return True
        if not raise_on_fail:
            return False
        elif response.status_code == 401:
            raise UnauthorizedError()
        else:
            raise ValueError()

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
        if response.status_code == 401:
            raise UnauthorizedError()
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
        if response.status_code == 401:
            raise UnauthorizedError()
        if response.status_code != 200:
            raise ValueError(f"User ID request failed for {username} with status {response.status_code}")
        response_data = response.json()
        user_id = response_data["data"][0]["id"]
        return user_id

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


    def update_access_token(self):
        print("Access token failed, attempting to update...")
        try:
            self.refresh_access_token()
            print("Refreshed access token")
        except UnauthorizedError:
            try:
                self.generate_access_token()
                print("Generated new access token")
            except:
                raise ValueError("Failed to generate valid access token")

    async def run_async(self):
        if not self.valid_access_token(self.access_token):
            self.update_access_token()
        
        tasks = []
        tasks.append(asyncio.create_task(self.run_event_listener()))

        while True:
            try:
                self.valid_access_token(self.access_token, raise_on_fail=True)
                print("Got a valid access token, running bot...")
                await asyncio.gather(*tasks)

            except UnauthorizedError:
                self.update_access_token()
            except asyncio.CancelledError:
                print("Exited")
                break

    def run(self):
        asyncio.run(self.run_async())
