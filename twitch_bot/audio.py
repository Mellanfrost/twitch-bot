import asyncio

import numpy as np
from twitchrealtimehandler import TwitchAudioGrabber

class AudioSubscription():
    def __init__(self, broadcaster_name:str, segment_duration_seconds=1, sample_rate=44100, channels=1, dtype:type=np.float32):
        self.broadcaster_name = broadcaster_name
        self.segment_duration_seconds = segment_duration_seconds
        self.sample_rate = sample_rate
        self.channels = channels
        self.dtype = dtype
        self.callbacks = []

    def add_callback(self, callback):
        self.callbacks.append(callback)
    
    def trigger_callbacks(self, audio_data):
        """Passes audio data to registered callback functions"""
        for callback in self.callbacks:
            if asyncio.iscoroutinefunction(callback):
                asyncio.create_task(callback(audio_data))
            else:
                callback(audio_data)

    async def run(self, is_live:asyncio.Event):
        """https://pypi.org/project/twitchrealtimehandler/"""
        if not is_live.is_set():
            await is_live.wait()
        grabber = TwitchAudioGrabber(
            twitch_url = f"https://www.twitch.tv/{self.broadcaster_name}",
            blocking = False,
            segment_length = self.segment_duration_seconds,
            rate = self.sample_rate,
            channels = self.channels,
            dtype = self.dtype,
        )
        while True:
            if not is_live.is_set():
                await is_live.wait()
                grabber = TwitchAudioGrabber(
                    twitch_url = f"https://www.twitch.tv/{self.broadcaster_name}",
                    blocking = False,
                    segment_length = self.segment_duration_seconds,
                    rate = self.sample_rate,
                    channels = self.channels,
                    dtype = self.dtype,
                )
            audio = grabber.grab()
            if audio is not None:
                self.trigger_callbacks(audio)
            await asyncio.sleep(self.segment_duration_seconds)
