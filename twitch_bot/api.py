import json
import requests


def create_eventsub_subscription(client_id:str, access_token:str, session_id:str, name:str, version:str, condition:dict[str, str]):
    """https://dev.twitch.tv/docs/api/reference/#create-eventsub-subscription"""
    url = "https://api.twitch.tv/helix/eventsub/subscriptions"
    headers = {
        "Authorization": f"Bearer {access_token}", 
        "Client-Id": client_id, 
        "Content-Type": "application/json",
        "Accept": "application/vnd.twitchtv.v5+json"
    }
    data = {
        "type": name,
        "version": version,
        "condition": condition,
        "transport": {
            "method": "websocket",
            "session_id": session_id,
        },
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code != 202:
        raise Exception(f"Invalid response with status code {response.status_code}: {response.text}")
    return response

def get_streams(broadcaster_id:str, client_id:str, access_token:str):
        """https://dev.twitch.tv/docs/api/reference/#get-streams"""
        url = "https://api.twitch.tv/helix/streams"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Client-Id": client_id,
        }
        params = {
            "user_id": broadcaster_id
        }
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            message = json.loads(response.text)["message"]
            raise Exception(f"Request failed with status code {response.status_code}: {message}")
        return response

def get_users(client_id:str, access_token:str, id:str=None, login:str=None) -> requests.Response:
    """
    https://dev.twitch.tv/docs/api/reference/#get-users

    Provide user id(s) and/or login(s) to get information about them  
    Include parameter for each user to get, separated by '&'

    example:  
    id = "id=1234&id=5678"  
    login = "login=foo&login=bar"  
    """
    url = f"https://api.twitch.tv/helix/users?{"&".join([x for x in [id, login] if x])}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Client-Id": client_id
    }
    response = requests.get(url, headers=headers)
    return response

def refresh_tokens(client_id:str, client_secret:str, refresh_token:str):
    """https://dev.twitch.tv/docs/authentication/refresh-tokens/"""
    url = "https://id.twitch.tv/oauth2/token"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
    }
    response = requests.post(url, headers=headers, data=data)
    return response

def send_chat_message(user_id:str, broadcaster_id:str, client_id:str, access_token:str, message:str):
    """https://dev.twitch.tv/docs/api/reference/#send-chat-message"""
    url = "https://api.twitch.tv/helix/chat/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Client-Id": client_id,
        "Content-Type": "application/json"
    }
    data = {
        "broadcaster_id": broadcaster_id,
        "sender_id": user_id,
        "message": message
    }
    response = requests.post(url, headers=headers, json=data)
    return response

def validate_tokens(access_token):
    """https://dev.twitch.tv/docs/authentication/validate-tokens/"""
    url = "https://id.twitch.tv/oauth2/validate"
    headers = {
        "Authorization": f"OAuth {access_token}",
    }
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        message = json.loads(response.text)["message"]
        raise Exception(f"Request failed with status code {response.status_code}: {message}")
    return response
