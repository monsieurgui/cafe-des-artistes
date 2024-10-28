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
from core.queue_view import QueueView
from utils.constants import YTDL_OPTIONS, FFMPEG_OPTIONS, MESSAGES, COLORS

class MusicPlayer:
    """Gère la lecture de musique pour un serveur Discord spécifique"""
    
    def __init__(self, bot, ctx):
        """
        Initialise un nouveau lecteur de musique
        :param bot: Instance du bot Discord
        :param ctx: Contexte de la commande
        """
        self.bot = bot
        self.ctx = ctx
        self.queue = deque()
        self.current = None
        self.voice_client = None
        self.disconnect_task = None  # Tâche pour suivre le minuteur de déconnexion
        self.thread_pool = ThreadPoolExecutor(max_workers=2)  # Limit concurrent downloads
        self.processing_queue = asyncio.Queue()  # Queue for background processing
        self.processing_task = None
        self.preload_queue = deque(maxlen=3)  # Keep next 3 songs preloaded
        # Add these to existing attributes
        self.loop = False
        self.loop_message = None
        self.loop_song = None
        self.loop_start_time = None
        self.loop_user = None
        self.loop_task = None
        
    async def ensure_voice_client(self):
        """
        Vérifie et établit une connexion vocale si nécessaire
        """
        try:
            if not self.voice_client:
                if self.ctx.voice_client:
                    self.voice_client = self.ctx.voice_client
                elif self.ctx.author.voice:
                    self.voice_client = await self.ctx.author.voice.channel.connect(
                        timeout=60.0,
                        reconnect=True,
                        self_deaf=True
                    )
                else:
                    raise ValueError(MESSAGES['VOICE_CHANNEL_REQUIRED'])

        except Exception as e:
            print(f"Voice client initialization error: {str(e)}")
            raise

    async def start_processing(self):
        """Start background processing if not already running"""
        if not self.processing_task:
            self.processing_task = asyncio.create_task(self.process_queue_background())

    async def process_queue_background(self):
        """Background task to process songs in the queue"""
        try:
            while True:
                song = await self.processing_queue.get()
                if song.get('needs_processing', False):
                    try:
                        # Process the song URL in thread pool
                        video_data = await asyncio.get_event_loop().run_in_executor(
                            self.thread_pool,
                            self._process_url,
                            song['url']
                        )
                        # Update song info
                        song.update(video_data)
                        song['needs_processing'] = False
                    except Exception as e:
                        print(f"Error processing {song['url']}: {e}")
                        if song in self.queue:
                            self.queue.remove(song)
                self.processing_queue.task_done()
        except asyncio.CancelledError:
            pass

    def _process_url(self, url):
        """
        Process a single URL (runs in thread pool)
        """
        with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'url': info['url'],
                'title': info['title'],
                'duration': info.get('duration', 0)
            }

    async def add_to_queue(self, query):
        """
        Ajoute une chanson ou une playlist à la file d'attente
        :param query: URL ou terme de recherche YouTube
        """
        try:
            await self.ensure_voice_client()
            await self.start_processing()
            
            # Disable loop if active
            if self.loop:
                self.loop = False
                if self.loop_task:
                    self.loop_task.cancel()
                    self.loop_task = None
                if self.loop_message:
                    await self.loop_message.delete()
                    self.loop_message = None
                self.loop_song = None
                self.loop_start_time = None
                self.loop_user = None
                
                # Stop current playback if any
                if self.voice_client and self.voice_client.is_playing():
                    self.voice_client.stop()
            
            # Run initial info extraction in thread pool
            info = await asyncio.get_event_loop().run_in_executor(
                self.thread_pool,
                self._extract_info,
                query
            )
            
            if 'entries' in info:  # Playlist
                playlist_title = info.get('title', 'Liste de lecture')
                entries = [e for e in info['entries'] if e]
                
                embed = discord.Embed(
                    title=MESSAGES['PLAYLIST_ADDED'],
                    description=f"Ajout de {len(entries)} pièces de la liste:\n**{playlist_title}**",
                    color=COLORS['SUCCESS']
                )
                await self.ctx.send(embed=embed)
                
                # Add songs to queue and process them in background
                for entry in entries:
                    song = {
                        'url': f"https://www.youtube.com/watch?v={entry['id']}",
                        'title': entry.get('title', 'Unknown Title'),
                        'duration': entry.get('duration', 0),
                        'needs_processing': True
                    }
                    self.queue.append(song)
                    await self.processing_queue.put(song)
                
                success_embed = discord.Embed(
                    description=MESSAGES['SONGS_ADDED'].format(len(entries)),
                    color=COLORS['SUCCESS']
                )
                await self.ctx.send(embed=success_embed)
            
            else:  # Single video
                song = {
                    'url': info['webpage_url'],
                    'title': info['title'],
                    'duration': info.get('duration', 0),
                    'needs_processing': True
                }
                self.queue.append(song)
                await self.processing_queue.put(song)
                
                embed = discord.Embed(
                    description=MESSAGES['SONG_ADDED'].format(song['title']),
                    color=COLORS['SUCCESS']
                )
                await self.ctx.send(embed=embed)
            
            await self.ctx.send(embed=await self.get_queue_display())
            
            # Start playing if nothing is playing
            if not self.voice_client.is_playing():
                await self.play_next()
                    
        except Exception as e:
            error_embed = discord.Embed(
                title=MESSAGES['ERROR_TITLE'],
                description=str(e),
                color=COLORS['ERROR']
            )
            await self.ctx.send(embed=error_embed)

    def _extract_info(self, query):
        """
        Extracts info from YouTube (runs in thread pool)
        """
        is_url = query.startswith(('http://', 'https://', 'www.'))
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': 'in_playlist' if is_url else False,
            'format': 'bestaudio/best',
            'default_search': 'ytsearch' if not is_url else None,
            'concurrent_fragments': 3,  # Download up to 3 fragments simultaneously
            'postprocessor_args': {
                'ffmpeg': ['-threads', '3']  # Use 3 threads for ffmpeg processing
            },
            'buffersize': 32768,  # Increase buffer size for network operations
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(query, download=False)

    async def process_video(self, video_url):
        """
        Process video with optimized settings
        """
        try:
            loop = asyncio.get_running_loop()
            video_data = await loop.run_in_executor(
                None,
                lambda: self.bot.ytdl.extract_info(video_url, download=False)
            )
            
            # Pre-process the stream URL to reduce playback startup time
            if 'url' in video_data:
                await loop.run_in_executor(None, lambda: requests.head(video_data['url']))
            
            return {
                'url': video_data['url'],
                'title': video_data['title']
            }
        except Exception as e:
            raise e

    async def play_next(self):
        """
        Joue la prochaine chanson dans la file d'attente
        Gère la déconnexion automatique si la file est vide
        """
        if self.loop and self.loop_song:
            await self.play_loop_song()
            return

        # Original play_next logic
        if not self.queue:
            if not self.voice_client or len(self.voice_client.channel.members) <= 1:
                embed = discord.Embed(
                    description=MESSAGES['GOODBYE'],
                    color=COLORS['WARNING']
                )
                await self.ctx.send(embed=embed)
                await self.cleanup()
            else:
                embed = discord.Embed(
                    description=MESSAGES['QUEUE_EMPTY'],
                    color=COLORS['WARNING']
                )
                await self.ctx.send(embed=embed)
                if self.disconnect_task:
                    self.disconnect_task.cancel()
                self.disconnect_task = asyncio.create_task(self.delayed_disconnect())
            return

        song = self.queue.popleft()
        self.current = song

        # Wait for processing to complete if needed
        while song.get('needs_processing', False):
            await asyncio.sleep(0.5)
            
        try:
            audio = discord.FFmpegPCMAudio(song['url'], **FFMPEG_OPTIONS)
            self.voice_client.play(audio, after=lambda e: 
                asyncio.run_coroutine_threadsafe(self.play_next(), self.bot.loop))
            await self.ctx.send(embed=await self.get_queue_display())
        except Exception as e:
            error_embed = discord.Embed(
                title=MESSAGES['ERROR_TITLE'],
                description=f"{song['title']}: {str(e)}",
                color=COLORS['ERROR']
            )
            await self.ctx.send(embed=error_embed)

    async def skip(self):
        """Skip the current song"""
        if self.voice_client and self.voice_client.is_playing():
            # Disable loop if active
            if self.loop:
                self.loop = False
                if self.loop_task:
                    self.loop_task.cancel()
                    self.loop_task = None
                if self.loop_message:
                    await self.loop_message.delete()
                    self.loop_message = None
                self.loop_song = None
                self.loop_start_time = None
                self.loop_user = None
            
            self.voice_client.stop()
            await self.ctx.send(embed=discord.Embed(
                description=MESSAGES['SKIPPED'],
                color=COLORS['SUCCESS']
            ))
        else:
            await self.ctx.send(MESSAGES['NOTHING_PLAYING'])
            
    async def purge(self):
        """Clear the music queue"""
        self.queue.clear()
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.stop()
        
        # Start disconnect timer
        if self.disconnect_task:
            self.disconnect_task.cancel()
        self.disconnect_task = asyncio.create_task(self.delayed_disconnect())
        
        await self.ctx.send(MESSAGES['QUEUE_PURGED'])

    async def get_queue_display(self):
        embed = discord.Embed(color=COLORS['INFO'])
        
        def format_duration(seconds):
            minutes, seconds = divmod(seconds, 60)
            hours, minutes = divmod(minutes, 60)
            if hours > 0:
                return f"`{hours:02d}:{minutes:02d}:{seconds:02d}`"
            return f"`{minutes:02d}:{seconds:02d}`"
        
        if self.current:
            duration = format_duration(self.current.get('duration', 0))
            embed.add_field(
                name=MESSAGES['NOW_PLAYING'],
                value=f"{self.current['title']} {duration}",
                inline=False
            )
        
        # Show only next song
        if self.queue:
            next_song = self.queue[0]
            duration = format_duration(next_song.get('duration', 0))
            embed.add_field(
                name=MESSAGES['NEXT_SONGS'],
                value=f"{next_song['title']} {duration}",
                inline=False
            )
            
            remaining = len(self.queue) - 1
            if remaining > 0:
                embed.set_footer(text=MESSAGES['REMAINING_SONGS'].format(remaining))
                
        if not self.current and not self.queue:
            embed.description = MESSAGES['QUEUE_EMPTY_SAD']
            
        return embed

    async def delayed_disconnect(self):
        """
        Déconnecte le bot après 30 minutes d'inactivité
        Peut être annulé si une nouvelle chanson est ajoutée
        """
        try:
            await asyncio.sleep(1800)  # 30 minutes
            if (self.voice_client and 
                not self.voice_client.is_playing() and 
                len(self.queue) == 0 and 
                self.voice_client.channel and 
                len(self.voice_client.channel.members) <= 1):
                
                embed = discord.Embed(
                    description=MESSAGES['GOODBYE'],
                    color=COLORS['WARNING']
                )
                await self.ctx.send(embed=embed)
                await self.cleanup()
                
        except asyncio.CancelledError:
            pass

    async def cleanup(self):
        """Clean up resources and downloaded files"""
        # Cancel processing task
        if self.processing_task:
            self.processing_task.cancel()
            self.processing_task = None
        
        # Shutdown thread pool
        self.thread_pool.shutdown(wait=False)
        
        # Clear downloaded files
        if hasattr(self, 'current_file'):
            try:
                os.remove(self.current_file)
            except:
                pass
        
        # Clear memory cache
        gc.collect()
        
        # Disconnect from voice
        if self.voice_client:
            await self.voice_client.disconnect()
            self.voice_client = None

    async def preload_next_songs(self):
        """Pre-download next few songs in queue"""
        while len(self.preload_queue) < 3 and self.queue:
            next_song = self.queue[0]
            future = self.thread_pool.submit(self.download_song, next_song)
            self.preload_queue.append(future)

    async def get_detailed_queue(self, show_all=False):
        def format_duration(seconds):
            minutes, seconds = divmod(seconds, 60)
            hours, minutes = divmod(minutes, 60)
            if hours > 0:
                return f"`{hours:02d}:{minutes:02d}:{seconds:02d}`"
            return f"`{minutes:02d}:{seconds:02d}`"
        
        if not show_all:
            # Original behavior for !queue
            embed = discord.Embed(title="File d'attente détaillée", color=COLORS['INFO'])
            
            if self.current:
                duration = format_duration(self.current.get('duration', 0))
                embed.add_field(
                    name=MESSAGES['NOW_PLAYING'],
                    value=f"{self.current['title']} {duration}",
                    inline=False
                )
            
            queue_list = list(self.queue)[:10]
            if queue_list:
                queue_text = "\n".join(
                    f"`{i}.` {song['title']} {format_duration(song.get('duration', 0))}"
                    for i, song in enumerate(queue_list, 1)
                )
                embed.add_field(
                    name=f"Prochaines chansons ({len(self.queue)} au total)",
                    value=queue_text,
                    inline=False
                )
                
                remaining = len(self.queue) - 10
                if remaining > 0:
                    embed.set_footer(text=MESSAGES['REMAINING_SONGS'].format(remaining))
            else:
                embed.description = MESSAGES['QUEUE_EMPTY_SAD']
                
            return embed, None
        
        else:
            # New paginated behavior for !queue all
            pages = []
            queue_list = list(self.queue)
            songs_per_page = 20
            total_pages = math.ceil(len(queue_list) / songs_per_page)
            
            for page in range(total_pages):
                start_idx = page * songs_per_page
                end_idx = start_idx + songs_per_page
                current_page_songs = queue_list[start_idx:end_idx]
                
                embed = discord.Embed(
                    title="File d'attente complète",
                    color=COLORS['INFO']
                )
                
                # Add current song to first page only
                if page == 0 and self.current:
                    duration = format_duration(self.current.get('duration', 0))
                    embed.add_field(
                        name=MESSAGES['NOW_PLAYING'],
                        value=f"{self.current['title']} {duration}",
                        inline=False
                    )
                
                if current_page_songs:
                    queue_text = "\n".join(
                        f"`{i}.` {song['title']} {format_duration(song.get('duration', 0))}"
                        for i, song in enumerate(current_page_songs, start_idx + 1)
                    )
                    embed.add_field(
                        name=f"Chansons ({len(self.queue)} au total)",
                        value=queue_text,
                        inline=False
                    )
                    
                embed.set_footer(text=f"Page {page + 1}/{total_pages}")
                pages.append(embed)
                
            if not pages:
                embed = discord.Embed(
                    title="File d'attente complète",
                    description=MESSAGES['QUEUE_EMPTY_SAD'],
                    color=COLORS['INFO']
                )
                pages.append(embed)
                
            return pages[0], QueueView(pages) if len(pages) > 1 else None

    def _format_duration(self, seconds):
        """Format seconds into HH:MM:SS"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    async def toggle_loop(self, ctx, query=None):
        """Toggle loop mode for current song or start looping a new song"""
        await self.ensure_voice_client()

        if self.loop:
            # Disable loop
            self.loop = False
            if self.loop_task:
                self.loop_task.cancel()
                self.loop_task = None
            if self.loop_message:
                await self.loop_message.delete()
                self.loop_message = None
            self.loop_song = None
            self.loop_start_time = None
            self.loop_user = None
            await ctx.send(embed=discord.Embed(
                description=MESSAGES['LOOP_DISABLED'],
                color=COLORS['INFO']
            ))
            return

        # Enable loop
        try:
            if query:
                # Process the new song
                info = await asyncio.get_event_loop().run_in_executor(
                    self.thread_pool,
                    lambda: self.bot.ytdl.extract_info(query, download=False)
                )
                
                if 'entries' in info:  # It's a playlist
                    raise ValueError("Cannot loop a playlist. Please provide a single video URL.")
                
                self.loop_song = {
                    'url': info.get('webpage_url', query),  # Use webpage_url as fallback
                    'title': info.get('title', 'Unknown Title'),
                    'duration': info.get('duration', 0)
                }
            elif not self.current:
                raise ValueError(MESSAGES['NOTHING_PLAYING'])
            else:
                self.loop_song = self.current.copy()

            # Stop current playback if any
            if self.voice_client and self.voice_client.is_playing():
                self.voice_client.stop()
                await asyncio.sleep(0.5)  # Add delay before starting new playback

            # Set loop parameters
            self.loop = True
            self.loop_start_time = discord.utils.utcnow()
            self.loop_user = ctx.author
            self.queue.clear()  # Clear the queue
            
            # Create initial loop message
            embed = self._create_loop_embed()
            self.loop_message = await ctx.send(embed=embed)
            
            # Start loop update task
            if self.loop_task:
                self.loop_task.cancel()
            self.loop_task = asyncio.create_task(self._update_loop_message())
            
            # Start playing the loop song
            await self.play_loop_song()

        except Exception as e:
            self.loop = False
            if self.loop_task:
                self.loop_task.cancel()
            error_embed = discord.Embed(
                title=MESSAGES['ERROR_TITLE'],
                description=str(e),
                color=COLORS['ERROR']
            )
            await ctx.send(embed=error_embed)

    def _create_loop_embed(self):
        """Create the loop status embed"""
        if not self.loop_song or not self.loop_start_time:
            return None
            
        embed = discord.Embed(color=COLORS['INFO'])
        duration = (discord.utils.utcnow() - self.loop_start_time).total_seconds()
        
        embed.add_field(
            name=MESSAGES['LOOP_ENABLED'].format(self.loop_song['title']),
            value=f"{MESSAGES['LOOP_SINCE'].format(self._format_duration(duration))}\n"
                 f"{MESSAGES['LOOP_BY'].format(self.loop_user.name)}",
            inline=False
        )
        return embed

    async def _update_loop_message(self):
        """Update the loop message every second"""
        try:
            while self.loop and self.loop_message:
                embed = self._create_loop_embed()
                if embed:
                    await self.loop_message.edit(embed=embed)
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Error updating loop message: {e}")

    async def play_loop_song(self):
        """Helper method to play the loop song"""
        if not self.voice_client or not self.loop_song:
            return

        try:
            if self.voice_client.is_playing():
                self.voice_client.stop()
                await asyncio.sleep(0.5)  # Add small delay to ensure cleanup
            
            # Get fresh URL for the audio
            info = await asyncio.get_event_loop().run_in_executor(
                self.thread_pool,
                lambda: self.bot.ytdl.extract_info(self.loop_song['url'], download=False)
            )
            
            if info.get('url'):
                audio = discord.FFmpegPCMAudio(
                    info['url'],
                    **FFMPEG_OPTIONS,
                    executable=self.bot.config.get('ffmpeg_path', 'ffmpeg')
                )
                self.voice_client.play(
                    audio,
                    after=lambda e: asyncio.run_coroutine_threadsafe(
                        self._handle_loop_playback(e), 
                        self.bot.loop
                    )
                )
        except Exception as e:
            print(f"Error in play_loop_song: {e}")
            self.loop = False
            if self.loop_task:
                self.loop_task.cancel()

    async def _handle_loop_playback(self, error):
        """Handle loop playback completion or errors"""
        if error:
            print(f"Error in loop playback: {error}")
            return
        
        if self.loop:
            # Schedule next loop playback with a small delay
            await asyncio.sleep(0.5)
            await self.play_loop_song()