"""
Download management component running in its own thread.
Handles all YouTube-DL operations and file management.
"""

import threading
import time
import yt_dlp
from queue import Queue
from typing import Dict
import asyncio
import os
import hashlib
from typing import Optional
import logging

from utils.constants import YTDL_OPTIONS
from core.interfaces import Song

logger = logging.getLogger(__name__)

class Downloader(threading.Thread):
    def __init__(self, cache_dir: str = "cache"):
        super().__init__(daemon=True)
        self.cache_dir = cache_dir
        self.download_queue = asyncio.Queue()
        self.processed_songs = asyncio.Queue()
        self._setup_ytdl()
        self._setup_cache()
        self.should_stop = False
        self._current_downloads = set()
        self._download_semaphore = asyncio.Semaphore(3)  # Limit concurrent downloads
        
    def _setup_cache(self):
        """Setup cache directory"""
        os.makedirs(self.cache_dir, exist_ok=True)
        
    def _setup_ytdl(self):
        """Setup yt-dlp with optimal options"""
        self.ytdl = yt_dlp.YoutubeDL({
            **YTDL_OPTIONS,
            'cachedir': self.cache_dir,
            'progress_hooks': [self._progress_hook]
        })
        
    async def process_url(self, url: str) -> Optional[Song]:
        """Process a URL and return a Song object"""
        try:
            # Check cache first
            cache_key = self._get_cache_key(url)
            cached_song = self._get_from_cache(cache_key)
            if cached_song:
                return cached_song
                
            # Extract info without downloading
            info = await self._extract_info(url)
            if not info:
                return None
                
            song = Song(
                url=url,
                title=info.get('title', 'Unknown'),
                duration=info.get('duration', 0),
                stream_url=info.get('url'),
                metadata=info
            )
            
            # Cache the song info
            self._cache_song(cache_key, song)
            return song
            
        except Exception as e:
            logger.error(f"Error processing URL {url}: {e}")
            return None
            
    def _get_cache_key(self, url: str) -> str:
        """Generate a cache key for a URL"""
        return hashlib.md5(url.encode()).hexdigest()
    
    def run(self):
        """Main thread loop"""
        while not self.should_stop:
            if not self.download_queue.empty():
                song_info = self.download_queue.get()
                processed_song = self._process_song(song_info)
                if processed_song:
                    self.ready_songs.put(processed_song)
            time.sleep(0.1)
    
    def _process_song(self, song_info: Dict) -> Dict:
        """Process and prepare a song for playback"""
        try:
            info = self.ytdl.extract_info(song_info['url'], download=False)
            return {
                'url': song_info['url'],
                'stream_url': info['url'],
                'title': info['title'],
                'duration': info.get('duration', 0)
            }
        except Exception as e:
            print(f"Download error: {e}")
            return None 
    
    async def cancel_download(self, url: str):
        """Cancel a pending download"""
        with self._lock:
            if url in self._current_downloads:
                self._current_downloads.remove(url)
                await self._event_queue.put(("download_cancelled", url))
                
    def _progress_hook(self, d):
        """Handle download progress updates"""
        if d['status'] == 'downloading':
            progress = {
                'url': d['filename'],
                'downloaded_bytes': d['downloaded_bytes'],
                'total_bytes': d.get('total_bytes', 0),
                'speed': d.get('speed', 0),
                'eta': d.get('eta', 0)
            }
            asyncio.run(self._event_queue.put(("download_progress", progress))) 