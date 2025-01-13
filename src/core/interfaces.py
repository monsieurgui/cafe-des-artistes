"""
Interfaces and data structures for inter-component communication
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any

class PlayerState(Enum):
    IDLE = "idle"
    PLAYING = "playing"
    PAUSED = "paused"
    BUFFERING = "buffering"
    ERROR = "error"

@dataclass
class Song:
    url: str
    title: str
    duration: int
    stream_url: Optional[str] = None
    downloaded: bool = False
    error: Optional[str] = None
    metadata: Dict[str, Any] = None

class PlayerEvent(Enum):
    SONG_STARTED = "song_started"
    SONG_FINISHED = "song_finished"
    BUFFER_LOW = "buffer_low"
    ERROR = "error"
    STATE_CHANGED = "state_changed"
    QUEUE_EMPTY = "queue_empty"
    VOICE_DISCONNECTED = "voice_disconnected"
    DOWNLOAD_STARTED = "download_started"
    DOWNLOAD_COMPLETE = "download_complete"
    DOWNLOAD_ERROR = "download_error" 