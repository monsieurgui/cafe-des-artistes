"""
Queue management component running in its own thread.
Handles the main song queue and coordinates with the player's buffer.
"""

import threading
from queue import Queue
from collections import deque
import time
from typing import Dict, List
import asyncio
from core.interfaces import Song
from threading import Thread, Lock
import logging
import random

logger = logging.getLogger(__name__)

class QueueManager(Thread):
    def __init__(self, max_size=100):
        super().__init__(daemon=True)
        self.main_queue = deque(maxlen=max_size)
        self.processing_queue = deque(maxlen=10)  # Songs being processed
        self._lock = Lock()
        self._event_queue = asyncio.Queue()
        self.should_stop = False
        self._queue_empty_notified = False
        
    async def add_song(self, song: Song) -> bool:
        """Add a song to the queue"""
        with self._lock:
            if len(self.main_queue) < self.main_queue.maxlen:
                self.main_queue.append(song)
                await self._event_queue.put(("song_added", song))
                return True
            return False
            
    async def get_songs_for_buffer(self, count: int) -> list[Song]:
        """Get next songs for player buffer"""
        songs = []
        with self._lock:
            while len(songs) < count and self.main_queue:
                song = self.main_queue.popleft()
                self.processing_queue.append(song)
                songs.append(song)
        return songs
        
    async def remove_from_processing(self, song: Song):
        """Remove a song from processing queue once played"""
        with self._lock:
            try:
                self.processing_queue.remove(song)
            except ValueError:
                logger.warning(f"Song not found in processing queue: {song.title}") 
        
    async def clear(self):
        """Clear all queues"""
        with self._lock:
            self.main_queue.clear()
            self.processing_queue.clear()
            await self._event_queue.put(("queue_cleared", None))
            
    async def shuffle(self):
        """Shuffle the main queue"""
        with self._lock:
            queue_list = list(self.main_queue)
            random.shuffle(queue_list)
            self.main_queue.clear()
            self.main_queue.extend(queue_list)
            await self._event_queue.put(("queue_shuffled", None))
            
    def run(self):
        """Main thread loop"""
        while not self.should_stop:
            # Check queue state
            with self._lock:
                if not self._queue_empty_notified and len(self.main_queue) == 0:
                    asyncio.run(self._event_queue.put(("queue_empty", None)))
                    self._queue_empty_notified = True
                elif self._queue_empty_notified and len(self.main_queue) > 0:
                    self._queue_empty_notified = False
            time.sleep(0.1) 