# twitch-bot

Twitch bot software designed to be as easy as possible to implement custom functionality for  
Handles setting up and refreshing tokens, subscribing to twitch events, and in a modular way sending events to any custom actions implemented  

Use your own bot application and run it through this software  

## Contents

- [Installation](#installation)
- [How to Use](#how-to-use)
- [Implementation Examples](#implementation-examples)

## Installation

Install from requirements.txt  

Register your application here https://dev.twitch.tv/console  
This is how you get your own bot client_id and client_secret which are required for running a twitch bot  
Either do it using your own account (the bot will have your username), or set up a separate twitch account for the bot  

Create an .env file containing the following:  
```python
# from the dev console where you first registered your application:
CLIENT_ID="" # id of your application
CLIENT_SECRET="" # secret of your application

# optional: can be filled in manually, else  generated automatically when running the bot
# will open browser and prompt to manually accept scopes any time a token with new scopes is generated
# once added, the bot will automatically handle refreshing these tokens
ACCESS_TOKEN="" # optional
REFRESH_TOKEN="" # optional
```
Be very careful not to leak these to anyone else!

## How to Use

### 1. Initialize TwitchBot

```python
from bot import TwitchBot
bot = TwitchBot(
    user_id="id of bot account",
    broadcaster_id="id of channel to run in",
    browser_path, # optional, defaults to default browser
    port, # optional, defaults to 3000
)
```

### 2. Add Actions 

Specify which events to subscribe to and what happens when they occur  
For available events and what their notification payload, see https://dev.twitch.tv/docs/eventsub/eventsub-subscription-types/  
The entire notification payload is sent to listeners as a dict  

Example:  
Run `my_func` every time someone types a message in the broadcaster's channel  
```python
bot.channel_chat_message.listeners.append(my_func) # event named channel.chat.message -> channel_chat_message
```

### 3. Run Bot 

```python 
bot.run()
```

Sets up everything required to run (auth token, scopes, subscription to events)  
Runs asynchronously until stopped (handles refreshing tokens automatically)  

Whenever a subscribed event occurs, the event message is sent to all listeners of that event  

## Implementation Examples

A bot that will thank followers in twitch chat and print follows in your terminal

```python
bot = TwitchBot(user_id="my_id", broadcaster_id="channel_id")

# implement your own functionality, this can be anything you want
async def print_follows(event):
    """Print f"{username} followed" in terminal when someone follows"""
    print(f"\n{event["payload"]["event"]["user_name"]} followed")

# add the functionality to the bot
bot.channel_follow.listeners.append(print_follows)


# this function requires an additional parameter, callback, to send its output elsewhere
async def thank_follower(event, callback):
    """Send f"Thank you for the follow {username}!" in twitch chat when someone follows"""
    username = event["payload"]["event"]["user_name"]
    await callback(f"Thank you for the follow {username}!")

# additional parameters can be passed by appending a lambda function to listeners like so
bot.channel_follow.listeners.append(lambda event: thank_follower(event, bot.send_message))

bot.run()
```
