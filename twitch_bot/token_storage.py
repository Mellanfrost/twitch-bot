import os
from abc import ABC, abstractmethod

import dotenv


class AbstractTokenStorage(ABC):
    def __init__(self):
        super().__init__()
    
    @abstractmethod
    def save_tokens(self, access_token:str, refresh_token:str, expires_at:str):
        """Saves tokens to persistent storage"""
        pass

    @abstractmethod
    def load_tokens(self):
        """Loads tokens from persistent storage"""
        pass


class DefaultTokenStorage(AbstractTokenStorage):
    """Uses dotenv to save and load tokens to/from .env"""
    def __init__(
            self,
            env_path=None,
            access_token_name="ACCESS_TOKEN",
            refresh_token_name="REFRESH_TOKEN",
        ):
        super().__init__()

        self.access_token_name = access_token_name
        self.refresh_token_name = refresh_token_name
        self.dotenv_path = env_path if env_path else dotenv.find_dotenv()
        dotenv.load_dotenv(
            dotenv_path = self.dotenv_path,
            override = True,
        )

    def save_tokens(self, access_token, refresh_token):
        dotenv.set_key(self.dotenv_path, self.access_token_name, access_token)
        dotenv.set_key(self.dotenv_path, self.refresh_token_name, refresh_token)
    
    def load_tokens(self):
        return (
            os.getenv(self.access_token_name),
            os.getenv(self.refresh_token_name),
        )
