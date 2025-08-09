"""
Advanced Queue Management System for Discord Music Bot
Implements queue persistence, validation, and intelligent preloading
"""

import asyncio
import json
import logging
import time
from collections import deque
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import aiofiles
import yt_dlp

logger = logging.getLogger(__name__)


class QueuePersistence:
    """
    Handles saving and restoring queue state on disconnects.
    Ensures seamless playback continuation after bot restarts or reconnections.
    """
    
    def __init__(self, guild_id: int, data_dir: str = "data"):
        self.guild_id = guild_id
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.queue_file = self.data_dir / f"queue_{guild_id}.json"
        
    async def save_queue_state(self, queue: deque, current_song: Optional[Dict], metadata: Dict = None) -> bool:
        """
        Save current queue state to persistent storage.
        
        Args:
            queue: Current queue of songs
            current_song: Currently playing song info
            metadata: Additional metadata (position, timestamp, etc.)
            
        Returns:
            bool: True if save was successful
        """
        try:
            state = {
                'guild_id': self.guild_id,
                'timestamp': time.time(),
                'current_song': current_song,
                'queue': list(queue),
                'metadata': metadata or {}
            }
            
            async with aiofiles.open(self.queue_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(state, indent=2, ensure_ascii=False))
                
            logger.info(f"Queue state saved for guild {self.guild_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save queue state for guild {self.guild_id}: {e}")
            return False
    
    async def restore_queue_state(self, max_age_hours: int = 24) -> Optional[Dict]:
        """
        Restore queue state from persistent storage.
        
        Args:
            max_age_hours: Maximum age of saved state to restore (hours)
            
        Returns:
            Optional[Dict]: Restored state or None if not available/expired
        """
        try:
            if not self.queue_file.exists():
                return None
                
            async with aiofiles.open(self.queue_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                state = json.loads(content)
            
            # Check if state is too old
            age_hours = (time.time() - state.get('timestamp', 0)) / 3600
            if age_hours > max_age_hours:
                logger.info(f"Queue state too old ({age_hours:.1f}h), ignoring")
                await self.clear_saved_state()
                return None
                
            logger.info(f"Restored queue state for guild {self.guild_id} (age: {age_hours:.1f}h)")
            return state
            
        except Exception as e:
            logger.error(f"Failed to restore queue state for guild {self.guild_id}: {e}")
            return None
    
    async def clear_saved_state(self) -> bool:
        """
        Clear saved queue state.
        
        Returns:
            bool: True if clearing was successful
        """
        try:
            if self.queue_file.exists():
                self.queue_file.unlink()
                logger.info(f"Cleared queue state for guild {self.guild_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear queue state for guild {self.guild_id}: {e}")
            return False


class ExtractionCache:
    """
    Caches yt-dlp extraction results to avoid redundant API calls.
    Improves performance and reduces rate limiting.
    """
    
    def __init__(self, max_size: int = 1000, ttl_minutes: int = 60):
        self.max_size = max_size
        self.ttl_seconds = ttl_minutes * 60
        self.cache: Dict[str, Tuple[Dict, float]] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._start_cleanup_task()
    
    def _start_cleanup_task(self):
        """Start periodic cache cleanup."""
        if not self._cleanup_task:
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
    
    async def _periodic_cleanup(self):
        """Periodically clean expired cache entries."""
        try:
            while True:
                await asyncio.sleep(300)  # Cleanup every 5 minutes
                await self.cleanup_expired()
        except asyncio.CancelledError:
            pass
    
    def get(self, url: str) -> Optional[Dict]:
        """
        Get cached extraction result.
        
        Args:
            url: The URL to get cached result for
            
        Returns:
            Optional[Dict]: Cached result or None if not found/expired
        """
        if url not in self.cache:
            return None
            
        result, timestamp = self.cache[url]
        
        # Check if expired
        if time.time() - timestamp > self.ttl_seconds:
            del self.cache[url]
            return None
            
        return result
    
    def set(self, url: str, result: Dict) -> None:
        """
        Cache extraction result.
        
        Args:
            url: The URL to cache result for
            result: The extraction result to cache
        """
        # Remove oldest entries if cache is full
        if len(self.cache) >= self.max_size:
            oldest_url = min(self.cache.keys(), key=lambda k: self.cache[k][1])
            del self.cache[oldest_url]
        
        self.cache[url] = (result.copy(), time.time())
        logger.debug(f"Cached extraction result for {url}")
    
    async def cleanup_expired(self) -> int:
        """
        Remove expired cache entries.
        
        Returns:
            int: Number of entries removed
        """
        current_time = time.time()
        expired_keys = [
            url for url, (_, timestamp) in self.cache.items()
            if current_time - timestamp > self.ttl_seconds
        ]
        
        for url in expired_keys:
            del self.cache[url]
            
        if expired_keys:
            logger.debug(f"Cleaned {len(expired_keys)} expired cache entries")
            
        return len(expired_keys)
    
    def clear(self) -> None:
        """Clear all cache entries."""
        self.cache.clear()
        logger.debug("Cache cleared")
    
    def stop_cleanup(self) -> None:
        """Stop cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            self._cleanup_task = None


class SmartPreloader:
    """
    Intelligent preloading system that adapts based on queue size and network conditions.
    """
    
    def __init__(self, extraction_cache: ExtractionCache):
        self.cache = extraction_cache
        self.preload_tasks: Dict[str, asyncio.Task] = {}
        self.max_concurrent_preloads = 2
        self.preload_ahead_count = 3
        
    async def preload_next_songs(self, queue: deque, ytdl_options: Dict) -> None:
        """
        Preload the next few songs in the queue.
        
        Args:
            queue: The current queue
            ytdl_options: yt-dlp options to use for extraction
        """
        if not queue:
            return
            
        # Determine how many songs to preload based on queue size
        songs_to_preload = min(len(queue), self.preload_ahead_count)
        
        # Get next songs that need preloading
        songs_to_process = []
        for i, song in enumerate(list(queue)[:songs_to_preload]):
            url = song.get('url', '')
            if url and not self.cache.get(url) and url not in self.preload_tasks:
                songs_to_process.append(song)
        
        # Limit concurrent preloads
        available_slots = self.max_concurrent_preloads - len(self.preload_tasks)
        songs_to_process = songs_to_process[:available_slots]
        
        # Start preload tasks
        for song in songs_to_process:
            url = song.get('url', '')
            if url:
                task = asyncio.create_task(self._preload_song(url, ytdl_options))
                self.preload_tasks[url] = task
                logger.debug(f"Started preloading {song.get('title', 'Unknown')}")
    
    async def _preload_song(self, url: str, ytdl_options: Dict) -> None:
        """
        Preload a single song.
        
        Args:
            url: Song URL to preload
            ytdl_options: yt-dlp options
        """
        try:
            # Check if already cached
            if self.cache.get(url):
                return
            
            # Extract info using yt-dlp
            with yt_dlp.YoutubeDL(ytdl_options) as ydl:
                info = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: ydl.extract_info(url, download=False)
                )
                
            # Cache the result
            if info:
                self.cache.set(url, info)
                logger.debug(f"Successfully preloaded: {info.get('title', 'Unknown')}")
                
        except Exception as e:
            logger.warning(f"Failed to preload {url}: {e}")
        finally:
            # Remove from active tasks
            self.preload_tasks.pop(url, None)
    
    def cancel_preloading(self, url: str = None) -> None:
        """
        Cancel preloading tasks.
        
        Args:
            url: Specific URL to cancel, or None to cancel all
        """
        if url:
            task = self.preload_tasks.pop(url, None)
            if task:
                task.cancel()
        else:
            # Cancel all preload tasks
            for task in self.preload_tasks.values():
                task.cancel()
            self.preload_tasks.clear()
    
    def get_preload_status(self) -> Dict[str, Any]:
        """
        Get current preloading status.
        
        Returns:
            Dict: Status information
        """
        return {
            'active_preloads': len(self.preload_tasks),
            'cache_size': len(self.cache.cache),
            'preloading_urls': list(self.preload_tasks.keys())
        }


class QueueValidator:
    """
    Validates queue integrity and removes invalid/expired entries.
    """
    
    def __init__(self, extraction_cache: ExtractionCache):
        self.cache = extraction_cache
    
    async def validate_queue(self, queue: deque, ytdl_options: Dict) -> Tuple[deque, List[Dict]]:
        """
        Validate all songs in the queue and remove invalid ones.
        
        Args:
            queue: Queue to validate
            ytdl_options: yt-dlp options for validation
            
        Returns:
            Tuple[deque, List[Dict]]: (valid_queue, removed_songs)
        """
        valid_queue = deque()
        removed_songs = []
        
        # Iterate over a snapshot to avoid 'deque mutated during iteration'
        for song in list(queue):
            try:
                if await self._validate_song(song, ytdl_options):
                    valid_queue.append(song)
                else:
                    removed_songs.append(song)
                    logger.warning(f"Removed invalid song: {song.get('title', 'Unknown')}")
                    
            except Exception as e:
                logger.error(f"Error validating song {song.get('title', 'Unknown')}: {e}")
                removed_songs.append(song)
        
        if removed_songs:
            logger.info(f"Queue validation removed {len(removed_songs)} invalid songs")
        
        return valid_queue, removed_songs
    
    async def _validate_song(self, song: Dict, ytdl_options: Dict) -> bool:
        """
        Validate a single song.
        
        Args:
            song: Song to validate
            ytdl_options: yt-dlp options
            
        Returns:
            bool: True if song is valid
        """
        url = song.get('url', '')
        if not url:
            return False
        
        # Check cache first
        cached_info = self.cache.get(url)
        if cached_info:
            return True
        
        # Quick validation without full extraction
        try:
            with yt_dlp.YoutubeDL({**ytdl_options, 'quiet': True, 'simulate': True}) as ydl:
                info = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: ydl.extract_info(url, download=False)
                )
                return info is not None
                
        except Exception:
            return False


class AdvancedQueueManager:
    """
    Complete queue management system combining all optimization features.
    """
    
    def __init__(self, guild_id: int, ytdl_options: Dict):
        self.guild_id = guild_id
        self.ytdl_options = ytdl_options
        
        # Initialize components
        self.persistence = QueuePersistence(guild_id)
        self.cache = ExtractionCache()
        self.preloader = SmartPreloader(self.cache)
        self.validator = QueueValidator(self.cache)
        
        # Queue state
        self.queue: deque = deque()
        self.current_song: Optional[Dict] = None
        
    async def add_song(self, song: Dict, preload: bool = True) -> bool:
        """
        Add a song to the queue with validation and optional preloading.
        
        Args:
            song: Song to add
            preload: Whether to trigger preloading
            
        Returns:
            bool: True if song was added successfully
        """
        try:
            # Validate the song first
            if not await self.validator._validate_song(song, self.ytdl_options):
                logger.warning(f"Failed to add invalid song: {song.get('title', 'Unknown')}")
                return False
            
            # Add to queue
            self.queue.append(song)
            
            # Save state
            await self.persistence.save_queue_state(self.queue, self.current_song)
            
            # Trigger preloading if requested
            if preload:
                await self.preloader.preload_next_songs(self.queue, self.ytdl_options)
            
            logger.info(f"Added song to queue: {song.get('title', 'Unknown')}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add song to queue: {e}")
            return False
    
    async def get_next_song(self) -> Optional[Dict]:
        """
        Get the next song from the queue with cached extraction if available.
        
        Returns:
            Optional[Dict]: Next song info or None if queue is empty
        """
        if not self.queue:
            return None
        
        song = self.queue.popleft()
        self.current_song = song
        
        # Check if we have cached extraction info
        url = song.get('url', '')
        cached_info = self.cache.get(url)
        if cached_info:
            # Merge cached info with song info
            song.update(cached_info)
            logger.debug(f"Used cached extraction for: {song.get('title', 'Unknown')}")
        
        # Save updated state
        await self.persistence.save_queue_state(self.queue, self.current_song)
        
        # Trigger preloading for remaining songs
        await self.preloader.preload_next_songs(self.queue, self.ytdl_options)
        
        return song
    
    async def restore_from_persistence(self) -> bool:
        """
        Restore queue from persistent storage.
        
        Returns:
            bool: True if restoration was successful
        """
        try:
            state = await self.persistence.restore_queue_state()
            if not state:
                return False
            
            # Restore queue
            # Restore from persisted list safely
            restored_list = list(state.get('queue', []))
            self.queue = deque(restored_list)
            self.current_song = state.get('current_song')
            
            # Validate restored queue
            self.queue, removed = await self.validator.validate_queue(self.queue, self.ytdl_options)
            
            if removed:
                logger.info(f"Removed {len(removed)} invalid songs during restoration")
                # Save cleaned state
                await self.persistence.save_queue_state(self.queue, self.current_song)
            
            # Start preloading
            await self.preloader.preload_next_songs(self.queue, self.ytdl_options)
            
            logger.info(f"Restored queue with {len(self.queue)} songs")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore queue from persistence: {e}")
            return False
    
    def get_queue_info(self) -> Dict[str, Any]:
        """
        Get comprehensive queue information.
        
        Returns:
            Dict: Queue status and statistics
        """
        return {
            'queue_length': len(self.queue),
            'current_song': self.current_song,
            'cache_stats': {
                'size': len(self.cache.cache),
                'ttl_seconds': self.cache.ttl_seconds
            },
            'preload_status': self.preloader.get_preload_status()
        }
    
    async def cleanup(self) -> None:
        """Clean up resources and save final state."""
        try:
            # Save final state
            await self.persistence.save_queue_state(self.queue, self.current_song)
            
            # Cancel preloading
            self.preloader.cancel_preloading()
            
            # Stop cache cleanup
            self.cache.stop_cleanup()
            
            logger.info(f"Queue manager cleanup completed for guild {self.guild_id}")
            
        except Exception as e:
            logger.error(f"Error during queue manager cleanup: {e}")
