"""
Music Player Service for Player Service Application
==================================================

This is an adapted version of the MusicPlayer class that works independently
of the Discord bot client. It manages audio playback for a specific guild
and communicates with the Bot Client via IPC events.

Key differences from the original MusicPlayer:
- Works with guild_id instead of Guild/Context objects  
- Uses voice connection parameters instead of Discord objects
- Sends IPC events instead of Discord messages
- No direct Discord API interactions
"""

import asyncio
import discord
from discord import FFmpegPCMAudio
from concurrent.futures import ThreadPoolExecutor
from collections import deque
import gc
import os
import math
import yt_dlp
import requests
import aiohttp
import async_timeout
from typing import Optional, Dict, Any, List
import time
import random
import json

from utils.constants import YTDL_OPTIONS, FFMPEG_OPTIONS, MESSAGES, COLORS
from utils.ipc_protocol import (
    Event, create_song_started_event, create_song_ended_event,
    create_queue_updated_event, create_player_idle_event, 
    create_player_error_event, create_state_update_event,
    SongData, StateData
)


class MusicPlayerService:
    """
    Music Player Service for headless audio playback
    
    This class manages audio playback for a specific guild without requiring
    Discord bot context. It communicates state changes via IPC events.
    """
    
    def __init__(self, guild_id: int, config: dict, event_socket, logger):
        """
        Initialize the Music Player Service
        
        Args:
            guild_id: Discord guild ID
            config: Application configuration
            event_socket: ZeroMQ socket for sending events
            logger: Logger instance
        """
        self.guild_id = guild_id
        self.config = config
        self.event_socket = event_socket
        self.logger = logger
        
        # Voice client will be received from bot client via IPC
        self.voice_client = None
        
        # Audio state
        self.queue = deque()
        self.current = None
        
        # Connection state
        self.is_connected = False
        self.channel_id = None
        
        # Background processing
        self.thread_pool = ThreadPoolExecutor(max_workers=2)
        self.search_pool = ThreadPoolExecutor(max_workers=1)
        self.processing_queue = asyncio.Queue()
        self.processing_task = None
        
        # Caching
        self._cached_urls = {}
        self._song_cache = {}
        self._preload_task = None
        self._processing_lock = asyncio.Lock()
        self._playing_lock = False
        self._connection_lock = asyncio.Lock()
        self._connecting = False
        self._keepalive_task = None
        
        # Cleanup tracking
        self.disconnect_task = None
        self.session = aiohttp.ClientSession()

    async def set_voice_client(self, voice_client) -> dict:
        """
        Receive voice client from bot client for direct audio operations
        
        Args:
            voice_client: Discord VoiceClient instance from bot client
            
        Returns:
            dict: Result of setting voice client
        """
        try:
            self.voice_client = voice_client
            self.is_connected = voice_client.is_connected() if voice_client else False
            self.channel_id = voice_client.channel.id if voice_client and voice_client.channel else None
            
            if self.is_connected:
                # Start processing if not already running
                if not self.processing_task:
                    self.processing_task = asyncio.create_task(self.process_queue_background())
                
                # Send state update event
                await self._send_state_update()
                
                self.logger.info(f"Voice client set for guild {self.guild_id}, channel {self.channel_id}")
                return {"status": "connected", "channel_id": self.channel_id}
            else:
                self.logger.warning(f"Received disconnected voice client for guild {self.guild_id}")
                return {"status": "disconnected"}
                
        except Exception as e:
            self.logger.error(f"Failed to set voice client: {e}")
            return {"status": "error", "message": str(e)}

    async def connect(self, channel_id: int) -> dict:
        """
        Signal that bot client should connect to voice channel
        Player service will receive voice client via set_voice_client()
        
        Args:
            channel_id: Voice channel ID to connect to
            
        Returns:
            dict: Connection result
        """
        try:
            self.channel_id = channel_id
            self.logger.info(f"Requesting voice connection to channel {channel_id} in guild {self.guild_id}")
            
            # Bot client should handle the actual connection and call set_voice_client()
            # This is just a placeholder response
            return {"status": "connection_requested", "channel_id": channel_id}
            
        except Exception as e:
            self.logger.error(f"Failed to request voice connection: {e}")
            return {"status": "error", "message": str(e)}
    
    async def disconnect(self) -> dict:
        """
        Disconnect from the voice channel
        
        Returns:
            dict: Disconnection result
        """
        try:
            self.logger.info(f"Disconnecting from voice channel in guild {self.guild_id}")
            
            # Stop current playback
            if self.voice_client and hasattr(self.voice_client, 'stop'):
                self.voice_client.stop()
            
            # Clear connection state
            self.is_connected = False
            self.channel_id = None
            self.voice_token = None
            self.voice_endpoint = None
            self.voice_session_id = None
            self.voice_client = None
            
            # Send state update
            await self._send_state_update()
            
            self.logger.info(f"Successfully disconnected from voice channel")
            return {"status": "disconnected"}
            
        except Exception as e:
            self.logger.error(f"Error during disconnection: {e}")
            return {"status": "error", "message": str(e)}
    
    async def add_to_queue(self, query: str, repeat_count: int = 1, requester_name: str = "Unknown") -> dict:
        """
        Add song(s) to the queue
        
        Args:
            query: Search query or URL
            repeat_count: Number of times to add the song
            requester_name: Name of the user who requested the song
            
        Returns:
            dict: Result of adding to queue
        """
        try:
            async with self._processing_lock:
                self.logger.info(f"Adding '{query}' to queue (x{repeat_count}) for guild {self.guild_id}")
                
                # Check if query is a URL
                is_url = query.startswith(('http://', 'https://', 'www.', 'youtube.com', 'youtu.be'))
                search_query = query if is_url else f"ytsearch:{query}"
                
                # Use minimal ytdl options for fast initial search
                ytdl_opts = {
                    'format': 'bestaudio/best',
                    'quiet': True,
                    'no_warnings': True,
                    'noplaylist': True,
                    'default_search': 'ytsearch',
                    'extract_flat': True,
                    'skip_download': True,
                    'force_generic_extractor': False,
                    'socket_timeout': 5,
                    'retries': 1
                }
                
                # Check cache first
                if search_query in self._cached_urls:
                    info = self._cached_urls[search_query].copy()
                else:
                    # Extract info
                    async with async_timeout.timeout(10):
                        info = await asyncio.get_event_loop().run_in_executor(
                            self.search_pool,
                            lambda: yt_dlp.YoutubeDL(ytdl_opts).extract_info(search_query, download=False)
                        )
                        
                        if not info:
                            raise ValueError("Video unavailable")
                        
                        # Handle search results
                        if 'entries' in info:
                            if not info['entries']:
                                raise ValueError("No results found")
                            info = info['entries'][0]
                        
                        self._cached_urls[search_query] = info
                
                # Create song data
                song_data = SongData(
                    url=info.get('webpage_url', info.get('url', search_query)),
                    title=info.get('title', 'Unknown'),
                    duration=info.get('duration', 0),
                    thumbnail=info.get('thumbnail'),
                    webpage_url=info.get('webpage_url'),
                    channel=info.get('channel', info.get('uploader')),
                    view_count=info.get('view_count'),
                    requester_name=requester_name
                )
                
                songs_added = 0
                for _ in range(repeat_count):
                    # Convert to dict for queue storage
                    song_dict = {
                        'url': song_data.url,
                        'title': song_data.title,
                        'duration': song_data.duration,
                        'thumbnail': song_data.thumbnail,
                        'webpage_url': song_data.webpage_url,
                        'channel': song_data.channel,
                        'view_count': song_data.view_count,
                        'requester_name': song_data.requester_name,
                        'needs_processing': True
                    }
                    
                    self.queue.append(song_dict)
                    songs_added += 1
                
                # Start playing only if nothing is currently playing
                if not self._playing_lock and not self.current:
                    # Don't send queue update here - play_next() will handle it
                    await self.play_next()
                else:
                    # Only send queue update if we're not starting playback
                    await self._send_queue_update()
                
                self.logger.info(f"Added {songs_added} song(s) to queue")
                return {
                    "status": "added",
                    "songs_added": songs_added,
                    "song_title": song_data.title,
                    "queue_size": len(self.queue)
                }
                
        except Exception as e:
            self.logger.error(f"Error adding to queue: {e}")
            await self._send_error_event("add_to_queue_error", str(e))
            return {"status": "error", "message": str(e)}
    
    async def skip(self) -> dict:
        """
        Skip the current song and play next if available
        
        Returns:
            dict: Skip result
        """
        try:
            if self.current is None:
                return {"status": "nothing_playing"}
            
            skipped_song = self.current.get('title', 'Unknown')
            self.logger.info(f"Skipping current song '{skipped_song}' in guild {self.guild_id}")
            
            # Clear current song
            self.current = None
            
            # Check if there's a next song in the queue
            if self.queue:
                # Start next song automatically
                await self.play_next()
                return {"status": "skipped", "song_title": skipped_song}
            else:
                # No more songs, send idle event
                await self._send_player_idle()
                return {"status": "skipped", "song_title": skipped_song}
                
        except Exception as e:
            self.logger.error(f"Error skipping song: {e}")
            return {"status": "error", "message": str(e)}
    
    async def reset(self) -> dict:
        """
        Reset the player - clear queue and stop playback
        
        Returns:
            dict: Reset result
        """
        try:
            self.logger.info(f"Resetting player for guild {self.guild_id}")
            
            # Clear queue
            self.queue.clear()
            
            # Stop current playback
            if self.voice_client and hasattr(self.voice_client, 'stop'):
                self.voice_client.stop()
            
            self.current = None
            
            # Send events
            await self._send_queue_update()
            await self._send_player_idle()
            
            return {"status": "reset"}
            
        except Exception as e:
            self.logger.error(f"Error resetting player: {e}")
            return {"status": "error", "message": str(e)}
    
    async def remove_from_queue(self, song_index: int) -> dict:
        """
        Remove a song from the queue by index
        
        Args:
            song_index: Index of song to remove (0-based)
            
        Returns:
            dict: Removal result
        """
        try:
            if 0 <= song_index < len(self.queue):
                queue_list = list(self.queue)
                removed_song = queue_list.pop(song_index)
                self.queue = deque(queue_list)
                
                await self._send_queue_update()
                
                return {
                    "status": "removed",
                    "song_title": removed_song.get('title', 'Unknown'),
                    "queue_size": len(self.queue)
                }
            else:
                return {"status": "invalid_index"}
                
        except Exception as e:
            self.logger.error(f"Error removing from queue: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_state(self) -> dict:
        """
        Get current player state
        
        Returns:
            dict: Current state
        """
        current_song = None
        if self.current:
            current_song = SongData(
                url=self.current['url'],
                title=self.current['title'],
                duration=self.current.get('duration', 0),
                thumbnail=self.current.get('thumbnail'),
                webpage_url=self.current.get('webpage_url'),
                channel=self.current.get('channel'),
                view_count=self.current.get('view_count'),
                requester_name=self.current.get('requester_name', 'Unknown'),
                audio_url=self.current.get('audio_url')
            )
        
        state = StateData(
            current_song=current_song,
            queue=[song for song in self.queue],
            is_playing=self.current is not None and self.is_connected,
            is_connected=self.is_connected,
            channel_id=self.channel_id
        )
        
        return {"status": "success", "state": state.__dict__}
    
    async def play_next(self):
        """Process the next song and provide audio URL to bot client"""
        if self._playing_lock:
            return
        
        self._playing_lock = True
        try:
            if not self.queue:
                self.current = None
                await self._send_player_idle()
                return
            
            next_song = self.queue.popleft()
            self.logger.info(f"Processing next song: {next_song.get('title', 'Unknown')}")
            
            # Extract audio URL using yt-dlp (player service handles audio processing)
            audio_url = await self._extract_audio_url(next_song['url'])
            if not audio_url:
                self.logger.error(f"Failed to extract audio URL for {next_song.get('title', 'Unknown')}")
                # Try next song
                asyncio.create_task(self.play_next())
                return
            
            # Update current song info
            self.current = next_song
            self.current['audio_url'] = audio_url
            
            # Convert to SongData for event sending
            song_data = SongData(
                url=self.current['url'],
                title=self.current['title'],
                duration=self.current['duration'],
                thumbnail=self.current.get('thumbnail'),
                webpage_url=self.current.get('webpage_url'),
                channel=self.current.get('channel'),
                view_count=self.current.get('view_count'),
                requester_name=self.current.get('requester_name', 'Unknown'),
                audio_url=audio_url
            )
            
            # Send SONG_STARTED event with audio URL for bot client to stream
            await self._send_song_started(song_data)
            
            # Update queue display
            await self._send_queue_update()
            
        except Exception as e:
            self.logger.error(f"Error in play_next: {e}")
        finally:
            self._playing_lock = False
    
    async def _extract_audio_url(self, url: str) -> str:
        """Extract streamable audio URL from video URL"""
        try:
            # Use yt-dlp to extract the direct audio stream URL
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(
                self.thread_pool,
                lambda: yt_dlp.YoutubeDL(YTDL_OPTIONS).extract_info(url, download=False)
            )
            
            if not info:
                return None
                
            # Get the audio stream URL
            audio_url = info.get('url')
            if not audio_url:
                self.logger.error(f"No stream URL found for {url}")
                return None
                
            return audio_url
            
        except Exception as e:
            self.logger.error(f"Failed to extract audio URL from {url}: {e}")
            return None
                
        finally:
            self._playing_lock = False
    
    async def _simulate_playback(self, duration: int):
        """Simulate song playback for the given duration"""
        await asyncio.sleep(min(duration, 10))  # Simulate max 10 seconds for testing
        
        if self.current:
            # Send song ended event
            song_data = SongData(
                url=self.current['url'],
                title=self.current['title'],
                duration=self.current['duration'],
                thumbnail=self.current['thumbnail'],
                webpage_url=self.current['webpage_url'],
                channel=self.current['channel'],
                view_count=self.current['view_count'],
                requester_name=self.current['requester_name']
            )
            
            await self._send_song_ended(song_data)
            
            # Play next song
            await self.play_next()
    
    async def delayed_disconnect(self):
        """Disconnect after a period of inactivity"""
        await asyncio.sleep(self.config.get('disconnection_delay', 300))  # 5 minutes default
        
        if not self.current and not self.queue:
            await self.disconnect()
    
    async def process_queue_background(self):
        """Background task for processing songs in the queue"""
        try:
            while True:
                song = await self.processing_queue.get()
                if song.get('needs_processing', False):
                    try:
                        # Process song metadata in background
                        if song['url'] not in self._cached_urls:
                            video_data = await asyncio.get_event_loop().run_in_executor(
                                self.thread_pool,
                                self._process_url,
                                song['url']
                            )
                            song.update(video_data)
                            self._cached_urls[song['url']] = video_data
                        
                        song['needs_processing'] = False
                    except Exception as e:
                        self.logger.error(f"Error processing {song['url']}: {e}")
                        
                self.processing_queue.task_done()
        except asyncio.CancelledError:
            pass
    
    def _process_url(self, url):
        """Process a URL to get video information (runs in thread pool)"""
        with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'url': info['url'],
                'title': info['title'],
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail'),
                'webpage_url': info.get('webpage_url'),
                'channel': info.get('uploader', info.get('channel')),
                'view_count': info.get('view_count')
            }
    
    # Event sending methods
    
    async def _send_song_started(self, song_data: SongData):
        """Send SONG_STARTED event"""
        event = create_song_started_event(self.guild_id, song_data)
        await self._send_event(event.to_json())
    
    async def _send_song_ended(self, song_data: SongData):
        """Send SONG_ENDED event"""
        event = create_song_ended_event(self.guild_id, song_data)
        await self._send_event(event.to_json())
    
    async def _send_queue_update(self):
        """Send QUEUE_UPDATED event"""
        queue_data = [song for song in self.queue]
        event = create_queue_updated_event(self.guild_id, queue_data)
        await self._send_event(event.to_json())
    
    async def _send_player_idle(self):
        """Send PLAYER_IDLE event"""
        event = create_player_idle_event(self.guild_id)
        await self._send_event(event.to_json())
    
    async def _send_error_event(self, error_type: str, error_message: str, song_data: Optional[SongData] = None):
        """Send PLAYER_ERROR event"""
        event = create_player_error_event(self.guild_id, error_type, error_message, song_data)
        await self._send_event(event.to_json())
    
    async def _send_state_update(self):
        """Send STATE_UPDATE event"""
        state_result = await self.get_state()
        state_data = StateData(**state_result['state'])
        event = create_state_update_event(self.guild_id, state_data)
        await self._send_event(event.to_json())
    
    async def _send_event(self, event_json: str):
        """Send an event via the IPC socket"""
        try:
            await self.event_socket.send_string(event_json)
        except Exception as e:
            self.logger.error(f"Error sending event: {e}")
    
    async def cleanup(self):
        """Clean up all resources"""
        self.logger.info(f"Cleaning up player for guild {self.guild_id}")
        
        # Stop tasks
        tasks = [self.disconnect_task, self.processing_task, self._preload_task, self._keepalive_task]
        for task in tasks:
            if task:
                task.cancel()
        
        # Stop playback
        if self.voice_client and hasattr(self.voice_client, 'stop'):
            self.voice_client.stop()
        
        # Clear state
        self.queue.clear()
        self.current = None
        self.is_connected = False
        
        # Close session
        if self.session and not self.session.closed:
            await self.session.close()
        
        # Shutdown thread pools
        try:
            self.thread_pool.shutdown(wait=False, cancel_futures=True)
            self.search_pool.shutdown(wait=False, cancel_futures=True)
        except Exception as e:
            self.logger.error(f"Error shutting down thread pools: {e}")
        
        # Garbage collection
        gc.collect()
        
        self.logger.info(f"Cleanup complete for guild {self.guild_id}")