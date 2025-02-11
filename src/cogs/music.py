import discord
from discord.ext import commands
import logging
from typing import Optional, List
import asyncio

from src.utils.url_utils import URLUtils
from src.utils.audio_utils import AudioUtils
from src.utils.youtube import YouTubeError

logger = logging.getLogger(__name__)

class MusicCog(commands.Cog):
    """Music commands for the bot."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.audio_manager = bot.audio_manager
        logger.info("MusicCog initialized")
    
    async def cog_check(self, ctx: commands.Context) -> bool:
        """Check if the command can be run in this context."""
        if not ctx.guild:
            raise commands.NoPrivateMessage("Music commands can't be used in DMs.")
        return True
    
    @commands.command(name='play', aliases=['p'])
    async def play(self, ctx: commands.Context, *, query: str):
        """Play a song from YouTube URL or search query."""
        logger.info(f"Received play command. Query: {query}")
        
        # Connect to voice immediately if not already connected
        if not ctx.voice_client:
            if ctx.author.voice:
                try:
                    await ctx.send("🔊 Connecting to voice channel...")
                    voice_client = await ctx.author.voice.channel.connect()
                    self.audio_manager.voice_clients[ctx.guild.id] = voice_client
                    logger.info(f"Connected to voice channel: {ctx.author.voice.channel.name}")
                except Exception as e:
                    logger.error(f"Failed to connect to voice channel: {str(e)}")
                    await ctx.send("❌ Failed to connect to voice channel.")
                    return
            else:
                await ctx.send("❌ You must be in a voice channel to play music.")
                return

        async with ctx.typing():
            try:
                # Check if the query is a URL
                is_url = URLUtils.is_youtube_url(query)
                logger.info(f"URL check result: {is_url}")
                
                if is_url:
                    # Handle playlist URLs
                    if URLUtils.is_playlist(query):
                        logger.info("Detected playlist URL")
                        await self._handle_playlist(ctx, query)
                        return
                    
                    # Handle single video URL
                    logger.info("Processing single video URL")
                    await self.audio_manager.play(ctx, query)
                    song = self.audio_manager.queue_manager.current
                    if song:
                        await ctx.send(f"🎵 Now playing: **{song.title}**")
                else:
                    # Search for the song
                    logger.info("Performing YouTube search")
                    results = await self.audio_manager.youtube.search(query, limit=1)
                    if not results:
                        await ctx.send("❌ No results found.")
                        return
                    
                    video = results[0]
                    await self.audio_manager.play(ctx, video['webpage_url'])
                    await ctx.send(f"🎵 Now playing: **{video['title']}**")
                    
            except YouTubeError as e:
                logger.error(f"YouTube error: {str(e)}")
                await ctx.send(f"❌ {str(e)}")
            except commands.CommandError as e:
                logger.error(f"Command error: {str(e)}")
                await ctx.send(f"❌ {str(e)}")
            except Exception as e:
                logger.error(f"Error in play command: {str(e)}")
                await ctx.send("❌ An error occurred while trying to play the song.")
    
    @commands.command(name='search', aliases=['s'])
    async def search(self, ctx: commands.Context, *, query: str):
        """Search for a song on YouTube."""
        async with ctx.typing():
            try:
                results = await self.audio_manager.youtube.search(query, limit=5)
                
                # Format search results
                message = "🔎 **Search Results:**\n\n"
                for i, video in enumerate(results, 1):
                    duration = AudioUtils.format_duration(video.get('duration'))
                    message += f"`{i}.` **{video['title']}** ({duration})\n"
                
                message += "\nType a number to play a song or `cancel` to cancel."
                await ctx.send(message)
                
                # Wait for user response
                try:
                    response = await self.bot.wait_for(
                        'message',
                        timeout=30.0,
                        check=lambda m: m.author == ctx.author and m.channel == ctx.channel
                    )
                    
                    if response.content.lower() == 'cancel':
                        await ctx.send("Search cancelled.")
                        return
                    
                    try:
                        choice = int(response.content)
                        if 1 <= choice <= len(results):
                            video = results[choice - 1]
                            await self.audio_manager.play(ctx, video['webpage_url'])
                            await ctx.send(f"🎵 Now playing: **{video['title']}**")
                        else:
                            await ctx.send("❌ Invalid choice.")
                    except ValueError:
                        await ctx.send("❌ Please enter a valid number.")
                        
                except asyncio.TimeoutError:
                    await ctx.send("❌ Search timed out.")
                    
            except YouTubeError as e:
                await ctx.send(f"❌ {str(e)}")
            except Exception as e:
                logger.error(f"Error in search command: {str(e)}")
                await ctx.send("❌ An error occurred while searching.")
    
    @commands.command(name='skip', aliases=['next'])
    async def skip(self, ctx: commands.Context):
        """Skip the current song."""
        if not ctx.voice_client:
            await ctx.send("❌ Nothing is playing right now.")
            return
        
        # Use the AudioManager's skip method
        next_song = await self.audio_manager.skip(ctx)
        
        if next_song:
            await ctx.send(f"⏭️ Skipped to: **{next_song.title}**")
        else:
            await ctx.send("⏭️ Skipped the current song. Queue is now empty.")
    
    @commands.command(name='queue', aliases=['q'])
    async def queue(self, ctx: commands.Context):
        """Show the current queue."""
        current = self.audio_manager.queue_manager.current
        queue = self.audio_manager.queue_manager.get_queue()
        
        if not current and not queue:
            await ctx.send("📪 The queue is empty.")
            return
        
        # Format the queue message
        message = "🎵 **Current Queue:**\n\n"
        
        if current:
            duration = AudioUtils.format_duration(current.duration)
            message += f"**Now Playing:**\n`⫸` {current.title} ({duration})\n\n"
        
        if queue:
            message += "**Up Next:**\n"
            for i, song in enumerate(queue, 1):
                duration = AudioUtils.format_duration(song.duration)
                message += f"`{i}.` {song.title} ({duration})\n"
        
        await ctx.send(message)
    
    @commands.command(name='clear')
    async def clear(self, ctx: commands.Context):
        """Clear the queue."""
        self.audio_manager.queue_manager.clear()
        await ctx.send("🗑️ Queue cleared.")
    
    @commands.command(name='leave', aliases=['disconnect', 'dc'])
    async def leave(self, ctx: commands.Context):
        """Leave the voice channel."""
        if ctx.voice_client:
            await self.audio_manager.stop(ctx)
            await ctx.send("👋 Left the voice channel.")
        else:
            await ctx.send("❌ I'm not in a voice channel.")
    
    @commands.command(name='pause')
    async def pause(self, ctx: commands.Context):
        """Pause the current song."""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("⏸️ Paused the current song.")
        else:
            await ctx.send("❌ Nothing is playing right now.")
    
    @commands.command(name='resume')
    async def resume(self, ctx: commands.Context):
        """Resume the current song."""
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("▶️ Resumed the current song.")
        else:
            await ctx.send("❌ Nothing is paused right now.")
    
    async def _handle_playlist(self, ctx: commands.Context, url: str):
        """Handle playing a YouTube playlist."""
        try:
            # Get playlist videos
            videos = await self.audio_manager.youtube.get_playlist_videos(url)
            
            if not videos:
                await ctx.send("❌ No videos found in the playlist.")
                return
            
            # Add all videos to the queue
            for video in videos:
                await self.audio_manager.play(ctx, video['webpage_url'])
            
            await ctx.send(f"📋 Added {len(videos)} songs from playlist to the queue.")
            
        except YouTubeError as e:
            await ctx.send(f"❌ Error loading playlist: {str(e)}")
        except Exception as e:
            logger.error(f"Error handling playlist: {str(e)}")
            await ctx.send("❌ An error occurred while loading the playlist.")

async def setup(bot: commands.Bot):
    """Add the cog to the bot."""
    await bot.add_cog(MusicCog(bot)) 