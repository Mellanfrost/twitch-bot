# Twitch Bot Library

A Python library for building and managing Twitch bots with ease. This library provides an interface for connecting to Twitch's EventSub via WebSocket and interacting with Twitch's API. It simplifies the process of creating custom Twitch bots by allowing you to focus on implementing your own custom functionality.

### ⚠️ Project Status: Early Work in Progress (WIP) ⚠️  
This project is currently in its early stages of development. Not all features are fully implemented. Use it at your own risk and expect frequent breaking changes. Feel free to reach out to provide feedback and to help shape its future!

## Features
- **EventSub Integration:** Automatically subscribes to specified EventSub events using WebSockets.
- **Twitch API Interface:** Built-in support for calling Twitch API endpoints.
- **Authentication Management:** Handles OAuth token refreshing and validation, ensuring you always have valid tokens.
- **Custom Event Handlers:** Easily add your own custom functions to handle specific events.

## Installation
You can install the library via pip:
```
pip install git+https://github.com/Mellanfrost/twitch-bot.git
```

## Running the Bot
To get started, initialize a bot instance, add any custom event handlers, and run the bot:
```python
from twitch_bot import TwitchBot, TwitchAuthManager

auth_manager = TwitchAuthManager(
    client_id = "your-client-id",
    client_secret = "your-client-secret",
)

bot = TwitchBot(
    auth = auth_manager,
    user_name = "your-bot-name",
    broadcaster_name = "streamer-name",
)

# add any custom event handlers to the bot instance here

bot.run()
```
By default, the bot will attempt to save and load access and refresh tokens as `ACCESS_TOKEN` and `REFRESH_TOKEN` to/from a `.env` file.

To change this behaviour, implement a custom version of `TokenStorage`:
```python
from twitch_bot.token_storage import AbstractTokenStorage

class MyTokenStorage(AbstractTokenStorage):
    def save_tokens(self, access_token, refresh_token):
        # your custom logic to save tokens
        pass

    def load_tokens(self):
        # your custom logic to load tokens
        pass

auth = TwitchAuthManager(
    client_id = "your-client-id",
    client_secret = "your-client-secret",
    token_storage = MyTokenStorage(),
)
```

## Adding Event Handlers
This is where you add your own bot features!

To see which events exist and what they return, see Twitch's documentation:  
https://dev.twitch.tv/docs/eventsub/eventsub-subscription-types

See a few example implementations below:

### 1. Thank Followers
Create a function to send a thank-you message triggered on the `channel_follow` event:
```python
def thank_follower(event):
    bot.send_chat_message(f"Thank you for following, {event["user_name"]}!")

bot.events.channel_follow.add_callback(thank_follower)
```
To explicitly pass the bot instance, use a lambda function:
```python
def thank_follower(event, bot:TwitchBot):
    bot.send_chat_message(f"Thank you for following, {event["user_name"]}!")

bot.events.channel_follow.add_callback(lambda event: thank_follower(event, bot))
```

### 2. Reply to Commands
```python
def reply_to_commands(event):
    # avoid replying to its own commands
    if event["chatter_user_login"] == bot.user_name:
        return

    message = event["message"]["text"]
    if message.startswith("!ping"):
        bot.send_chat_message("pong")
```

### 3. Stream Live Notification
Do something on stream start/end, for example notifying people on Discord:
```python
def notify_discord_online(event):
    your_send_to_discord_func("Stream is now live!") # your own implemented discord API logic

bot.event.stream_online.add_listener(notify_discord_online)    
```

### 4. Process Stream Audio
Access stream audio, for example for passing to a Speech-to-Text (STT) model for subtitles:
```python
def speech_to_text(audio):
    your_stt_func(audio) # send audio through your own STT pipeline

bot.audio.add_callback(speech_to_text)

# optionally, specify properties of audio to grab
bot.audio.segment_duration_seconds = 4
```

## Access Twitch API Endpoints
To see which API endpoints exist and how they work, see Twitch's documentation:  
https://dev.twitch.tv/docs/api/reference

This library provides interfaces to several of Twitch's API endpoints, which can be used as follows:
```python
from twitch_bot import api

api.send_chat_message(
    bot.user_id,
    bot.broadcaster_id,
    bot.auth.client_id,
    bot.auth.access_token,
    "your message",
)
```
