"""
Main controller that coordinates all components and handles commands.
"""

from core.interfaces import PlayerEvent, PlayerState, Song
from core.player import Player
from core.queue_manager import QueueManager
from core.downloader import Downloader
import asyncio
import logging

logger = logging.getLogger(__name__)

class MusicController:
    def __init__(self, bot, ctx):
        self.bot = bot
        self.ctx = ctx
        self.player = None
        self.queue_manager = QueueManager()
        self.downloader = Downloader()
        self._setup_event_handlers()
        self._voice_state_lock = asyncio.Lock()
        self._download_cache = {}
        
    def _setup_event_handlers(self):
        """Setup event handlers for all components"""
        self._event_handlers = {
            PlayerEvent.BUFFER_LOW: self._handle_buffer_low,
            PlayerEvent.SONG_FINISHED: self._handle_song_finished,
            PlayerEvent.ERROR: self._handle_error
        }
        
    async def start(self):
        """Initialize and start all components"""
        # Start background components
        self.queue_manager.start()
        self.downloader.start()
        
        # Setup voice client and player
        await self._setup_voice()
        
        # Start event handling loop
        asyncio.create_task(self._event_loop())
        
    async def add_song(self, url: str):
        """Add a song to the queue"""
        # Process the URL
        song = await self.downloader.process_url(url)
        if not song:
            raise ValueError(f"Could not process URL: {url}")
            
        # Add to queue
        success = await self.queue_manager.add_song(song)
        if not success:
            raise ValueError("Queue is full")
            
        # If player buffer is low, trigger immediate buffer fill
        if len(self.player.buffer) < 2:
            await self._fill_player_buffer()
            
    async def _event_loop(self):
        """Main event handling loop"""
        while True:
            event = await self.player._event_queue.get()
            handler = self._event_handlers.get(event[0])
            if handler:
                await handler(event[1]) 
        
    async def _handle_voice_state_update(self, member, before, after):
        """Handle voice state changes"""
        async with self._voice_state_lock:
            if member.id == self.bot.user.id:
                if after.channel is None:  # Bot was disconnected
                    await self._cleanup_voice_state()
                    
    async def _cleanup_voice_state(self):
        """Clean up voice state when disconnected"""
        if self.player:
            await self.player.stop()
        if self.voice_client:
            try:
                await self.voice_client.disconnect()
            except:
                pass
        self.voice_client = None
        
    async def _handle_download_progress(self, progress_data):
        """Handle download progress updates"""
        # Implement progress tracking and UI updates
        pass 