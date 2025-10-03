"""
Simple Queue Management System for Discord Music Bot
Lightweight implementation without persistence or caching for speed
"""

import logging
from collections import deque
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class SimpleQueueManager:
    """
    Simple queue management system without persistence or caching.
    Fast and lightweight for quick song additions.
    """
    
    def __init__(self, guild_id: int, ytdl_options: Dict = None):
        self.guild_id = guild_id
        self.ytdl_options = ytdl_options or {}
        
        # Queue state
        self.queue: deque = deque()
        self.current_song: Optional[Dict] = None
        
    async def add_song(self, song: Dict, preload: bool = True) -> bool:
        """
        Add a song to the queue.
        
        Args:
            song: Song to add
            preload: Ignored (kept for compatibility)
            
        Returns:
            bool: True if song was added successfully
        """
        try:
            # Simple add to queue
            self.queue.append(song)
            logger.info(f"[QUEUE] Added song to queue: {song.get('title', 'Unknown')} | Queue size now: {len(self.queue)}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add song to queue: {e}")
            return False
    
    async def get_next_song(self) -> Optional[Dict]:
        """
        Get the next song from the queue.
        
        Returns:
            Optional[Dict]: Next song info or None if queue is empty
        """
        if not self.queue:
            logger.info("[QUEUE] get_next_song called but queue is empty")
            return None
        
        song = self.queue.popleft()
        self.current_song = song
        logger.info(f"[QUEUE] Popped song: {song.get('title', 'Unknown')} | Queue size now: {len(self.queue)}")
        return song
    
    def get_queue_info(self) -> Dict[str, Any]:
        """
        Get queue information.
        
        Returns:
            Dict: Queue status and statistics
        """
        return {
            'queue_length': len(self.queue),
            'current_song': self.current_song
        }
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        try:
            # Clear queue
            self.queue.clear()
            self.current_song = None
            logger.info(f"Queue manager cleanup completed for guild {self.guild_id}")
            
        except Exception as e:
            logger.error(f"Queue manager cleanup failed for guild {self.guild_id}: {e}")


# Keep the old name for backward compatibility
AdvancedQueueManager = SimpleQueueManager
