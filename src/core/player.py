"""
Core music player component running in its own thread.
Handles actual playback and maintains a small buffer of ready-to-play songs.
"""

import threading
import queue
import asyncio
import time
import discord
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from collections import deque
import logging

from utils.constants import FFMPEG_OPTIONS
from core.interfaces import PlayerState, PlayerEvent, Song

logger = logging.getLogger(__name__)

class Player(threading.Thread):
    def __init__(self, bot, voice_client):
        super().__init__(daemon=True)
        self.bot = bot
        self.voice_client = voice_client
        self.state = PlayerState.IDLE
        self.buffer = deque(maxlen=3)  # Main buffer for ready-to-play songs
        self.current_song: Optional[Song] = None
        self._lock = threading.Lock()
        self._event_queue = asyncio.Queue()
        self._buffer_threshold = 2  # Trigger buffer refill when this many songs remain
        self.should_stop = False
        self.download_queue = asyncio.Queue()
        self._download_in_progress = False
        
    async def _emit_event(self, event: PlayerEvent, data: Any = None):
        """Emit an event to be handled by the controller"""
        await self._event_queue.put((event, data))
        
    def run(self):
        """Main player loop"""
        while not self.should_stop:
            try:
                self._check_buffer()
                self._handle_playback()
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"Player error: {e}")
                asyncio.run(self._emit_event(PlayerEvent.ERROR, str(e)))

    def _check_buffer(self):
        """Check buffer status and request refill if needed"""
        with self._lock:
            if len(self.buffer) <= self._buffer_threshold:
                asyncio.run(self._emit_event(PlayerEvent.BUFFER_LOW, len(self.buffer)))

    def _handle_playback(self):
        """Handle the actual playback logic"""
        if self.state != PlayerState.PLAYING and self.buffer:
            with self._lock:
                next_song = self.buffer.popleft()
            self._play_song(next_song)

    def add_to_buffer(self, song: Song):
        """Thread-safe method to add a song to the buffer"""
        with self._lock:
            if len(self.buffer) < self.buffer.maxlen:
                self.buffer.append(song)
                return True
            return False

    def _play_song(self, song: Dict):
        """Play a song that's ready in the buffer"""
        with self._lock:
            if self.voice_client and self.voice_client.is_connected():
                self.current_song = song
                self.is_playing = True
                
                audio = discord.FFmpegPCMAudio(
                    song['stream_url'],
                    **FFMPEG_OPTIONS
                )
                
                def after_playing(error):
                    self.is_playing = False
                    self.current_song = None
                    if error:
                        print(f"Playback error: {error}")
                
                self.voice_client.play(audio, after=after_playing) 

    async def stop(self):
        """Safely stop the player thread"""
        self.should_stop = True
        with self._lock:
            if self.voice_client and self.voice_client.is_playing():
                self.voice_client.stop()
        await self._emit_event(PlayerEvent.STATE_CHANGED, PlayerState.IDLE)
        
    async def pause(self):
        """Pause playback"""
        with self._lock:
            if self.voice_client and self.voice_client.is_playing():
                self.voice_client.pause()
                self.state = PlayerState.PAUSED
                await self._emit_event(PlayerEvent.STATE_CHANGED, self.state)
                
    async def resume(self):
        """Resume playback"""
        with self._lock:
            if self.voice_client and self.voice_client.is_paused():
                self.voice_client.resume()
                self.state = PlayerState.PLAYING
                await self._emit_event(PlayerEvent.STATE_CHANGED, self.state) 