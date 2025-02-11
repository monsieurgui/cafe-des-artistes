from collections import deque
from threading import Lock
from typing import Optional, List
from .song import Song

class QueueManager:
    """Thread-safe queue manager for songs."""
    
    def __init__(self):
        self._queue = deque()
        self._lock = Lock()
        self._current_song: Optional[Song] = None
        self._loop = False
    
    @property
    def current(self) -> Optional[Song]:
        """Get the currently playing song."""
        with self._lock:
            return self._current_song
    
    @property
    def loop(self) -> bool:
        """Get the loop state."""
        return self._loop
    
    @loop.setter
    def loop(self, value: bool) -> None:
        """Set the loop state."""
        self._loop = value
    
    def add(self, song: Song) -> None:
        """Add a song to the queue."""
        with self._lock:
            self._queue.append(song)
    
    def get_next(self) -> Optional[Song]:
        """Get the next song from the queue."""
        with self._lock:
            if not self._queue and not self._loop:
                self._current_song = None
                return None
            
            if self._loop and self._current_song:
                # When looping, keep the current song
                return self._current_song
            
            if self._queue:
                self._current_song = self._queue.popleft()
                return self._current_song
            
            # If we get here, no song is available
            self._current_song = None
            return None
    
    def clear(self) -> None:
        """Clear the queue."""
        with self._lock:
            self._queue.clear()
            self._current_song = None
    
    def remove(self, index: int) -> Optional[Song]:
        """Remove a song at the specified index."""
        with self._lock:
            if 0 <= index < len(self._queue):
                return self._queue.pop(index)
        return None
    
    def get_queue(self) -> List[Song]:
        """Get a copy of the current queue."""
        with self._lock:
            return list(self._queue)
    
    def is_empty(self) -> bool:
        """Check if the queue is empty."""
        with self._lock:
            return len(self._queue) == 0 and self._current_song is None
    
    def skip(self) -> Optional[Song]:
        """Skip the current song and return the next one."""
        with self._lock:
            # Clear current song
            self._current_song = None
            
            # If queue is empty and not looping, return None
            if not self._queue:
                return None
            
            # Get next song from queue
            self._current_song = self._queue.popleft()
            return self._current_song
    
    @property
    def queue_length(self) -> int:
        """Get the number of songs in the queue."""
        with self._lock:
            return len(self._queue) 