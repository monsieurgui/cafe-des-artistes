from dataclasses import dataclass
from typing import Optional
import asyncio
from datetime import datetime

@dataclass
class Song:
    """Represents a song in the queue."""
    url: str
    title: Optional[str] = None
    duration: Optional[int] = None
    requester: Optional[str] = None
    stream_url: Optional[str] = None
    added_at: datetime = datetime.now()
    
    # Event to signal when the stream URL is ready
    _stream_ready = None
    
    def __post_init__(self):
        """Initialize the stream ready event."""
        self._stream_ready = asyncio.Event()
        if self.stream_url:
            self._stream_ready.set()
    
    async def wait_for_stream(self) -> None:
        """Wait until the stream URL is available."""
        await self._stream_ready.wait()
    
    def set_stream_ready(self) -> None:
        """Signal that the stream URL is ready."""
        self._stream_ready.set()
    
    def is_stream_ready(self) -> bool:
        """Check if the stream URL is ready."""
        return self._stream_ready.is_set() 