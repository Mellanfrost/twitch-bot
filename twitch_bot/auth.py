import asyncio

from twitch_bot import api
from twitch_bot.token_storage import DefaultTokenStorage

class TwitchAuthManager():
    def __init__(
            self,
            client_id:str,
            client_secret:str,
            access_token:str = None,
            refresh_token:str = None,
            token_storage = DefaultTokenStorage(),
        ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_storage = token_storage
        self.access_token:str = access_token
        self.refresh_token:str = refresh_token
        self.expires_in:int = None
        self.required_scopes = []

    async def keep_alive(self, tolerance = 10):
        while True:
            self.validate_tokens()
            if self.expires_in < 3600 - tolerance:
                self.refresh_tokens()
                self.token_storage.save_tokens(self.access_token, self.refresh_token)
            sleep_seconds = min(max(self.expires_in - tolerance, 0), 3600)
            await asyncio.sleep(sleep_seconds)

    def ensure_valid_tokens(self):
        """gets valid tokens for the required scopes"""
        if self.access_token == None or self.refresh_token == None:
            self.access_token, self.refresh_token = self.token_storage.load_tokens()
        try:
            self.validate_tokens()
            return
        except:
            pass
        try:
            self.refresh_tokens()
            self.token_storage.save_tokens(self.access_token, self.refresh_token)
            return
        except:
            pass
        try:
            self.generate_access_token()
            self.token_storage.save_tokens(self.access_token, self.refresh_token)
            return
        except:
            raise Exception("Failed to get valid tokens")

    def generate_access_token(self):
        raise NotImplementedError()

    def refresh_tokens(self):
        response = api.refresh_tokens(self.client_id, self.client_secret, self.refresh_token)
        json_response = response.json()
        self.access_token = json_response["access_token"]
        self.refresh_token = json_response["refresh_token"]
        self.expires_in = json_response["expires_in"]
        self.required_scopes = json_response["scope"]

    def validate_tokens(self):
        response = api.validate_tokens(self.access_token)
        json_response = response.json()
        token_scopes = json_response["scopes"]
        for scope in self.required_scopes:
            if scope not in token_scopes:
                raise Exception(f"Token missing required scope: {scope}")
        self.expires_in = json_response["expires_in"]
