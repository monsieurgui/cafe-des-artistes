import asyncio
import logging
from typing import Optional, Dict
import discord
from discord.ext import commands
import os
from pathlib import Path

from src.audio.queue_manager import QueueManager
from src.audio.song import Song
from src.utils.youtube import YouTubeUtils, YouTubeError

logger = logging.getLogger(__name__)

class AudioManager:
    """Manages audio playback and queue processing."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.queue_manager = QueueManager()
        self.youtube = YouTubeUtils()
        
        # Voice states
        self.voice_clients: Dict[int, discord.VoiceClient] = {}
        
        # FFmpeg configuration
        self.ffmpeg_path = self._get_ffmpeg_path()
        if not self.ffmpeg_path:
            logger.error("FFmpeg not found! Please install FFmpeg or set FFMPEG_PATH environment variable.")
        else:
            logger.info(f"Using FFmpeg from: {self.ffmpeg_path}")
    
    def _get_ffmpeg_path(self) -> Optional[str]:
        """Get the path to FFmpeg executable."""
        # First, check environment variable
        ffmpeg_path = os.getenv('FFMPEG_PATH')
        if ffmpeg_path and Path(ffmpeg_path).exists():
            return ffmpeg_path
            
        # Then check local bin directory
        local_ffmpeg = Path(__file__).parent.parent.parent / 'bin' / 'ffmpeg.exe'
        if local_ffmpeg.exists():
            return str(local_ffmpeg)
            
        # Then check common locations
        common_locations = [
            r'C:\ffmpeg\bin\ffmpeg.exe',  # Windows custom install
            r'C:\Program Files\ffmpeg\bin\ffmpeg.exe',  # Windows program files
            '/usr/bin/ffmpeg',  # Linux
            '/usr/local/bin/ffmpeg',  # macOS
        ]
        
        for location in common_locations:
            if Path(location).exists():
                return str(location)
        
        # Finally, check if it's in PATH
        try:
            import shutil
            return shutil.which('ffmpeg')
        except Exception:
            return None
    
    def _create_ffmpeg_audio_source(self, url: str) -> discord.FFmpegOpusAudio:
        """Create an FFmpeg audio source with the appropriate configuration."""
        try:
            ffmpeg_options = {
                'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin',
                'options': '-vn -acodec libopus -b:a 192k -loglevel warning'
            }
            
            if self.ffmpeg_path:
                ffmpeg_options['executable'] = self.ffmpeg_path
            
            return discord.FFmpegOpusAudio(url, **ffmpeg_options)
        except Exception as e:
            logger.error(f"Error creating FFmpeg audio source: {str(e)}", exc_info=True)
            raise

    async def _play_next(self, guild_id: int) -> None:
        """Play the next song in the queue."""
        try:
            voice_client = self.voice_clients.get(guild_id)
            if not voice_client or not voice_client.is_connected():
                return

            # Get next song
            next_song = self.queue_manager.get_next()
            if not next_song:
                return

            # Wait for stream URL to be ready
            await next_song.wait_for_stream()

            # Create and play audio source
            audio_source = self._create_ffmpeg_audio_source(next_song.stream_url)
            
            def after_callback(error):
                if error:
                    logger.error(f"Error during playback: {str(error)}")
                # Schedule playing next song in the bot's event loop
                asyncio.run_coroutine_threadsafe(
                    self._play_next(guild_id),
                    self.bot.loop
                )

            voice_client.play(audio_source, after=after_callback)
            logger.info(f"Now playing: {next_song.title}")

        except Exception as e:
            logger.error(f"Error in play_next: {str(e)}", exc_info=True)

    async def play(self, ctx: commands.Context, url: str) -> None:
        """Add a song to the queue and start playing if not already playing."""
        try:
            # Get video information
            info = await self.youtube.extract_info(url)
            
            # Create and add song to queue
            song = Song(
                url=url,
                title=info['title'],
                duration=info['duration'],
                requester=str(ctx.author),
                stream_url=info['stream_url']
            )
            song.set_stream_ready()
            self.queue_manager.add(song)
            
            # Store voice client reference
            if ctx.voice_client:
                self.voice_clients[ctx.guild.id] = ctx.voice_client
            
            # If nothing is playing, start playback
            if not ctx.voice_client or not ctx.voice_client.is_playing():
                await self._play_next(ctx.guild.id)
            
        except Exception as e:
            logger.error(f"Error in play command: {str(e)}")
            raise commands.CommandError(str(e))

    async def skip(self, ctx: commands.Context) -> Optional[Song]:
        """Skip the current song."""
        try:
            voice_client = ctx.voice_client
            if not voice_client:
                return None

            # Stop current playback
            if voice_client.is_playing():
                voice_client.stop()

            # Get and return next song (will be played by after_callback)
            return self.queue_manager.skip()

        except Exception as e:
            logger.error(f"Error in skip command: {str(e)}")
            return None

    async def stop(self, ctx: commands.Context) -> None:
        """Stop playing and clear the queue."""
        try:
            if ctx.voice_client:
                if ctx.voice_client.is_playing():
                    ctx.voice_client.stop()
                await ctx.voice_client.disconnect()
                self.voice_clients.pop(ctx.guild.id, None)
            self.queue_manager.clear()
        except Exception as e:
            logger.error(f"Error in stop command: {str(e)}")

    def cleanup(self) -> None:
        """Clean up resources."""
        self.queue_manager.clear()
    
    async def _stop_voice_client(self, voice_client: discord.VoiceClient) -> None:
        """Safely stop and cleanup the voice client."""
        try:
            if voice_client and voice_client.is_playing():
                # First stop any audio playing
                voice_client.stop()
                # Wait for the FFmpeg process to properly terminate
                await asyncio.sleep(0.2)
                # Clear any audio sources
                voice_client.cleanup()
                # Wait a bit more to ensure complete cleanup
                await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Error stopping voice client: {str(e)}")

    def _play_song(self, song: Song) -> None:
        """Play a song in the voice client."""
        try:
            logger.info(f"Attempting to play song: {song.title}")
            for voice_client in self.voice_clients.values():
                if voice_client and voice_client.is_connected():
                    logger.info("Found connected voice client")
                    
                    # Clear any existing song finished event
                    self._song_finished.clear()
                    
                    # Clean up any existing playback first
                    asyncio.run_coroutine_threadsafe(
                        self._stop_voice_client(voice_client),
                        self.bot.loop
                    ).result()
                    
                    # Create FFmpeg audio source
                    logger.info(f"Creating FFmpeg audio source with URL: {song.stream_url[:50]}...")
                    audio_source = self._create_ffmpeg_audio_source(song.stream_url)
                    logger.info("Created audio source")
                    
                    # Play the audio
                    voice_client.play(
                        audio_source,
                        after=lambda e: self._on_song_complete(e, voice_client)
                    )
                    logger.info("Started audio playback")
                    
                    # Wait for the song to finish
                    self._song_finished.wait()
                    logger.info("Song finished playing")
                    
        except Exception as e:
            logger.error(f"Error playing song: {str(e)}", exc_info=True)
            self._song_finished.set()
    
    def _on_song_complete(self, error: Optional[Exception], voice_client: discord.VoiceClient) -> None:
        """Callback when a song finishes playing."""
        try:
            if error:
                logger.error(f"Error during playback: {str(error)}")
            
            # Only process completion if the voice client exists and is not already playing
            if voice_client and not voice_client.is_playing():
                logger.info("Song complete callback triggered")
                # Signal that the song is finished and ready for the next one
                self._song_finished.set()
            else:
                logger.info("Ignoring duplicate song complete callback")
            
        except Exception as e:
            logger.error(f"Error in song complete callback: {str(e)}")
            self._song_finished.set()
    
    async def play(self, ctx: commands.Context, url: str) -> None:
        """
        Add a song to the queue and start playing if not already playing.
        
        Args:
            ctx: The command context
            url: The URL of the song to play
        """
        try:
            logger.info(f"Attempting to play URL: {url}")
            # Get video information
            info = await self.youtube.extract_info(url)
            logger.info(f"Got video info: {info.get('title')}")
            
            # Create and add the song to the queue
            song = Song(
                url=url,
                title=info['title'],
                duration=info['duration'],
                requester=str(ctx.author),
                stream_url=info['stream_url']
            )
            logger.info(f"Created song object with stream URL: {song.stream_url[:50]}...")
            
            self.queue_manager.add(song)
            logger.info("Added song to queue")
            
            # Signal that the song is ready to play
            song.set_stream_ready()
            logger.info("Song marked as ready to play")
            
        except YouTubeError as e:
            logger.error(f"YouTube error in play command: {str(e)}")
            raise commands.CommandError(str(e))
        except Exception as e:
            logger.error(f"Error in play command: {str(e)}")
            raise commands.CommandError("An error occurred while trying to play the song.")
    
    async def stop(self, ctx: commands.Context) -> None:
        """Stop playing and clear the queue."""
        if ctx.voice_client:
            ctx.voice_client.stop()
            await ctx.voice_client.disconnect()
            self.voice_clients.pop(ctx.guild.id, None)
        self.queue_manager.clear()
        self._song_finished.set()  # Signal to allow the player loop to continue
    
    def cleanup(self) -> None:
        """Clean up resources when shutting down."""
        self._shutdown.set()
        self._song_finished.set()
        
        if self._player_thread:
            self._player_thread.join(timeout=2)
        if self._processor_thread:
            self._processor_thread.join(timeout=2)
            
        self.queue_manager.clear()
    
    async def skip(self, ctx: commands.Context) -> Optional[Song]:
        """Skip the current song and start playing the next one."""
        try:
            logger.info("Attempting to skip current song")
            
            # Get the voice client
            voice_client = ctx.voice_client
            if not voice_client:
                logger.info("No voice client found")
                return None
            
            # Check if there's a next song before stopping current one
            next_song = self.queue_manager.skip()
            if not next_song:
                logger.info("No more songs in queue")
                if voice_client.is_playing():
                    await self._stop_voice_client(voice_client)
                self._song_finished.set()
                return None
            
            logger.info(f"Next song to play: {next_song.title}")
            
            # Stop current playback and signal for next song
            if voice_client.is_playing():
                logger.info("Stopping current playback")
                voice_client.stop()  # Just stop, don't do full cleanup
            
            # Signal the player loop to continue with the next song
            self._song_finished.set()
            
            return next_song
            
        except Exception as e:
            logger.error(f"Error skipping song: {str(e)}", exc_info=True)
            self._song_finished.set()
            return None 