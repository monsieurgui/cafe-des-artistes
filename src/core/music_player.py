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
from core.queue_view import QueueView
from core.now_playing import NowPlayingDisplay
from utils.constants import YTDL_OPTIONS, FFMPEG_OPTIONS, MESSAGES, COLORS

class MusicPlayer:
    """
    Gère la lecture de musique pour un serveur Discord spécifique.
    
    Cette classe s'occupe de :
    - La gestion de la file d'attente de musique
    - La lecture et le contrôle des flux audio
    - La gestion des états de connexion vocale
    - Le préchargement des chansons
    - La gestion du mode boucle
    
    Attributes:
        bot (commands.Bot): Instance du bot Discord
        ctx (commands.Context): Contexte de la commande
        queue (deque): File d'attente des chansons
        current (dict): Chanson en cours de lecture
        voice_client (VoiceClient): Client vocal Discord
        disconnect_task (Task): Tâche de déconnexion automatique
        thread_pool (ThreadPoolExecutor): Pool de threads pour le traitement parallèle
        search_pool (ThreadPoolExecutor): Pool de threads dédié pour les recherches
        processing_queue (Queue): File d'attente pour le traitement asynchrone
        preload_queue (deque): File d'attente pour le préchargement
        loop (bool): État du mode boucle
        last_add_time (float): Temps de la dernière addition de chanson
        add_cooldown (float): Cooldown entre les additions de chansons
        batch_queue (list): File d'attente pour les additions par lots
        batch_task (Task): Tâche pour les additions par lots
        batch_lock (Lock): Verrou pour les additions par lots
        live_stream (dict): Informations de la diffusion en direct
        live_embed (Message): Embed de la diffusion en direct
        live_task (Task): Tâche pour la mise à jour de l'embed de la diffusion en direct
        current_display (NowPlayingDisplay): Instance de la mise en cours de lecture
    """
    
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
        self.disconnect_task = None  # Tâche pour le minuteur de déconnexion
        self.thread_pool = ThreadPoolExecutor(max_workers=2)  # For playback operations
        self.search_pool = ThreadPoolExecutor(max_workers=1)  # Dedicated pool for search operations
        self.processing_queue = asyncio.Queue()  # File d'attente pour le traitement en arrière-plan
        self.processing_task = None
        self.preload_queue = deque(maxlen=3)  # Garde les 3 prochaines chansons préchargées
        self.loop = False
        self.loop_message = None
        self.loop_song = None
        self.loop_start_time = None
        self.loop_user = None
        self.loop_task = None
        self.last_add_time = 0
        self.add_cooldown = 1.0  # 1 second cooldown between adds
        self.batch_queue = []
        self.batch_task = None
        self.batch_lock = asyncio.Lock()
        self.live_stream = None
        self.live_embed = None
        self.live_task = None
        self._cached_urls = {}
        self._song_cache = {}
        self._preload_task = None
        self._processing_lock = asyncio.Lock()
        self._playing_lock = False
        self.session = aiohttp.ClientSession()
        self.current_display = None
        
    async def ensure_voice_client(self):
        """
        Vérifie et établit une connexion vocale si nécessaire
        """
        try:
            # Check if current voice client is valid
            if self.voice_client and self.voice_client.is_connected():
                return
                
            # Clear any existing invalid voice client
            self.voice_client = None
            
            # Try to get voice client from context
            if self.ctx.voice_client and self.ctx.voice_client.is_connected():
                self.voice_client = self.ctx.voice_client
                return
                
            # Try to connect to author's voice channel
            if self.ctx.author.voice:
                self.voice_client = await self.ctx.author.voice.channel.connect(
                    timeout=60.0,
                    reconnect=True,
                    self_deaf=True
                )
                return
                
            raise ValueError(MESSAGES['VOICE_CHANNEL_REQUIRED'])

        except Exception as e:
            print(f"Voice client initialization error: {str(e)}")
            raise

    async def start_processing(self):
        """Démarre le traitement en arrière-plan s'il n'est pas déjà en cours"""
        if not self.processing_task:
            self.processing_task = asyncio.create_task(self.process_queue_background())

    async def process_queue_background(self):
        """Tâche en arrière-plan pour traiter les chansons dans la file d'attente"""
        try:
            while True:
                song = await self.processing_queue.get()
                if song.get('needs_processing', False):
                    try:
                        # Use cached data if available
                        if hasattr(self, '_cached_urls') and song['url'] in self._cached_urls:
                            song.update(self._cached_urls[song['url']])
                        else:
                            video_data = await asyncio.get_event_loop().run_in_executor(
                                self.thread_pool,
                                self._process_url,
                                song['url']
                            )
                            song.update(video_data)
                            # Cache the result
                            if not hasattr(self, '_cached_urls'):
                                self._cached_urls = {}
                            self._cached_urls[song['url']] = video_data
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
        Traite une seule URL (s'exécute dans le pool de threads)
        """
        with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'url': info['url'],
                'title': info['title'],
                'duration': info.get('duration', 0)
            }

    async def add_to_queue(self, query):
        try:
            async with self._processing_lock:
                # Check if query is a URL
                is_url = query.startswith(('http://', 'https://', 'www.', 'youtube.com', 'youtu.be'))
                
                # Prepare search query if not a URL
                search_query = query if is_url else f"ytsearch:{query}"
                
                # Use minimal ytdl options for fast initial search
                ytdl_opts = {
                    'format': 'bestaudio/best',
                    'quiet': True,
                    'no_warnings': True,
                    'noplaylist': True,
                    'default_search': 'ytsearch',
                    'extract_flat': True,  # Only fetch metadata initially
                    'skip_download': True,
                    'force_generic_extractor': False,
                    'socket_timeout': 1,  # Reduced timeout
                    'retries': 1
                }
                
                # Check cache first
                if search_query in self._cached_urls:
                    song = self._cached_urls[search_query].copy()
                else:
                    # Use dedicated search pool with shorter timeout
                    try:
                        async with async_timeout.timeout(5):  # Reduced timeout
                            info = await asyncio.get_event_loop().run_in_executor(
                                self.search_pool, 
                                lambda: yt_dlp.YoutubeDL(ytdl_opts).extract_info(search_query, download=False)
                            )
                            
                            if not info:
                                raise ValueError(MESSAGES['VIDEO_UNAVAILABLE'])

                            # Handle search results
                            if 'entries' in info:
                                if not info['entries']:
                                    raise ValueError(MESSAGES['VIDEO_UNAVAILABLE'])
                                info = info['entries'][0]

                            # Create minimal song info initially
                            song = {
                                'url': info.get('webpage_url', info.get('url', search_query)),
                                'title': info.get('title', 'Unknown'),
                                'duration': info.get('duration', 0),
                                'needs_processing': True  # Mark for background processing
                            }
                            self._cached_urls[search_query] = song.copy()
                            
                            # Start background processing for full metadata
                            asyncio.create_task(self._process_song_metadata(song))
                    except Exception as e:
                        print(f"Search error: {e}")
                        raise

                self.queue.append(song)
                
                # Start playing immediately if nothing is playing
                if not self.voice_client or not self.voice_client.is_playing():
                    await self.play_next()
                else:
                    embed = discord.Embed(
                        description=MESSAGES['SONG_ADDED'].format(song['title']),
                        color=COLORS['SUCCESS']
                    )
                    await self.ctx.send(embed=embed)

        except asyncio.TimeoutError:
            error_embed = discord.Embed(
                title=MESSAGES['ERROR_TITLE'],
                description=MESSAGES['TIMEOUT_ERROR'],
                color=COLORS['ERROR']
            )
            await self.ctx.send(embed=error_embed)
        except Exception as e:
            error_embed = discord.Embed(
                title=MESSAGES['ERROR_TITLE'],
                description=str(e),
                color=COLORS['ERROR']
            )
            await self.ctx.send(embed=error_embed)

    async def _process_song_metadata(self, song):
        """Process full song metadata in the background"""
        try:
            # Use full options for complete metadata
            ytdl_opts = YTDL_OPTIONS.copy()
            info = await asyncio.get_event_loop().run_in_executor(
                self.thread_pool,
                lambda: yt_dlp.YoutubeDL(ytdl_opts).extract_info(song['url'], download=False)
            )
            
            if info:
                # Update song with full metadata
                song.update({
                    'thumbnail': info.get('thumbnail'),
                    'webpage_url': info.get('webpage_url'),
                    'channel': info.get('channel', info.get('uploader')),
                    'view_count': info.get('view_count'),
                    'needs_processing': False
                })
                self._cached_urls[song['url']] = song.copy()
        except Exception as e:
            print(f"Error processing metadata: {e}")

    async def _preload_next(self):
        """Preload the next song in the queue"""
        try:
            if not self.queue:
                return

            next_song = self.queue[0]
            if next_song['url'] not in self._song_cache:
                async with async_timeout.timeout(30):
                    info = await asyncio.get_event_loop().run_in_executor(
                        self.thread_pool,
                        lambda: yt_dlp.YoutubeDL(YTDL_OPTIONS).extract_info(next_song['url'], download=False)
                    )
                    if info:
                        self._song_cache[next_song['url']] = info
        except Exception as e:
            print(f"Preload error: {e}")

    async def play_next(self):
        if self._playing_lock:
            return
        
        self._playing_lock = True
        try:
            if self.voice_client is None or not self.voice_client.is_connected():
                await self.ensure_voice_client()

            if not self.queue and not self.loop:
                self.current = None
                # Start disconnect timer instead of immediate cleanup
                if self.disconnect_task:
                    self.disconnect_task.cancel()
                self.disconnect_task = asyncio.create_task(self.delayed_disconnect())
                return

            # Stop current display if exists
            if self.current_display:
                await self.current_display.stop()
                self.current_display = None

            if self.loop and self.loop_song:
                next_song = self.loop_song
            else:
                if not self.queue:
                    self.current = None
                    return
                next_song = self.queue.popleft()

            # Use cached info if available
            if next_song['url'] in self._song_cache:
                info = self._song_cache[next_song['url']]
            else:
                info = await asyncio.get_event_loop().run_in_executor(
                    self.thread_pool,
                    lambda: yt_dlp.YoutubeDL(YTDL_OPTIONS).extract_info(next_song['url'], download=False)
                )

            if info is None:
                await self.ctx.send(embed=discord.Embed(
                    description=MESSAGES['SONG_UNAVAILABLE'],
                    color=COLORS['ERROR']
                ))
                await self.play_next()
                return

            # Store full info for display
            self.current = {
                'url': info.get('webpage_url', next_song['url']),  # Use webpage_url first
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail', info.get('thumbnails', [{'url': None}])[0]['url']),
                'webpage_url': info.get('webpage_url', info.get('url', next_song['url'])),
                'channel': info.get('uploader', info.get('channel', 'Unknown')),
                'view_count': info.get('view_count', 0)
            }

            # Get the stream URL (this is different from webpage_url)
            stream_url = info.get('url', info.get('formats', [{}])[0].get('url'))
            if not stream_url:
                raise ValueError(MESSAGES['VIDEO_UNAVAILABLE'])
            
            # Create FFmpeg audio source
            audio = FFmpegPCMAudio(stream_url, **FFMPEG_OPTIONS)
            
            def after_playing(error):
                if error:
                    print(f"Error in playback: {error}")
                asyncio.run_coroutine_threadsafe(self.play_next(), self.bot.loop)

            self.voice_client.play(audio, after=after_playing)

            # Create and start the now playing display
            self.current_display = NowPlayingDisplay(self.ctx, self.current)
            await self.current_display.start()

        except Exception as e:
            print(f"Error in play_next: {e}")
            error_embed = discord.Embed(
                title=MESSAGES['ERROR_TITLE'],
                description=str(e),
                color=COLORS['ERROR']
            )
            await self.ctx.send(embed=error_embed)
            
        finally:
            self._playing_lock = False

    async def skip(self):
        """Skip the current song"""
        if self.voice_client and self.voice_client.is_playing():
            # Stop current display
            if self.current_display:
                await self.current_display.stop()
                self.current_display = None
                
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
        """Vide la file d'attente de musique"""
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
        
        if self.current:
            duration = self._format_duration(self.current.get('duration', 0))
            embed.add_field(
                name=MESSAGES['NOW_PLAYING'],
                value=f"{self.current['title']} {duration}",
                inline=False
            )
        
        # Show next three songs only if something is currently playing
        if self.queue and self.current:
            next_songs = list(self.queue)[:3]
            next_songs_text = "\n".join(
                f"{i+1}. {song['title']} {self._format_duration(song.get('duration', 0))}"
                for i, song in enumerate(next_songs)
            )
            embed.add_field(
                name=MESSAGES['NEXT_SONGS'],
                value=next_songs_text,
                inline=False
            )
            
            remaining = len(self.queue) - 3
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
            # Send warning message
            warning_embed = discord.Embed(
                description=MESSAGES['WAIT_MESSAGE'],
                color=COLORS['WARNING']
            )
            await self.ctx.send(embed=warning_embed)
            
            # Wait 30 minutes
            await asyncio.sleep(1800)  # 30 minutes
            
            # Check conditions for disconnect
            should_disconnect = (
                self.voice_client and 
                not self.voice_client.is_playing() and 
                len(self.queue) == 0
            )
            
            if should_disconnect:
                embed = discord.Embed(
                    description=MESSAGES['GOODBYE'],
                    color=COLORS['WARNING']
                )
                await self.ctx.send(embed=embed)
                await self.cleanup()
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Error in delayed_disconnect: {e}")

    async def cleanup(self):
        """Nettoie les ressources et les fichiers téléchargés"""
        try:
            # Cancel all tasks first
            if self.processing_task:
                self.processing_task.cancel()
                self.processing_task = None
                
            if self.batch_task:
                self.batch_task.cancel()
                self.batch_task = None
                
            if self.loop_task:
                self.loop_task.cancel()
                self.loop_task = None
                
            if self.disconnect_task:
                self.disconnect_task.cancel()
                self.disconnect_task = None
            
            # Clear all queues
            self.queue.clear()
            self.batch_queue.clear()
            if hasattr(self, 'preload_queue'):
                self.preload_queue.clear()
            
            # Handle voice client
            if self.voice_client:
                try:
                    if self.voice_client.is_playing():
                        self.voice_client.stop()
                    if self.voice_client.is_connected():
                        await self.voice_client.disconnect()
                except:
                    pass
                self.voice_client = None
            
            # Stop thread pools safely
            if hasattr(self, 'thread_pool'):
                if self.thread_pool and not getattr(self.thread_pool, '_shutdown', True):
                    self.thread_pool.shutdown(wait=False)
                self.thread_pool = None
                
            if hasattr(self, 'search_pool'):
                if self.search_pool and not getattr(self.search_pool, '_shutdown', True):
                    self.search_pool.shutdown(wait=False)
                self.search_pool = None
            
            # Clear all state variables
            self.current = None
            self._playing_lock = False if hasattr(self, '_playing_lock') else False
            self.loop = False
            self.loop_message = None
            self.loop_song = None
            self.loop_start_time = None
            self.loop_user = None
            
            # Clear caches
            if hasattr(self, '_cached_urls'):
                self._cached_urls.clear()
            if hasattr(self, '_song_cache'):
                self._song_cache.clear()
            
            # Close aiohttp session
            if not self.session.closed:
                await self.session.close()
            
            # Force garbage collection
            gc.collect()
            
            # Stop current display
            if self.current_display:
                await self.current_display.stop()
                self.current_display = None
            
        except Exception as e:
            print(f"Error during cleanup: {e}")
            raise

    async def preload_next_songs(self):
        """
        Précharge les prochaines chansons de la file d'attente.
        
        Cette méthode optimise la lecture en :
        - Préchargeant jusqu'à 3 chansons à l'avance
        - Vérifiant la validité des URLs
        - Mettant en cache les informations des vidéos
        
        Notes:
            - Utilise un système de cache pour éviter les requêtes répétées
            - Gère automatiquement la mémoire en limitant le nombre de préchargements
            - S'exécute de manière asynchrone pour ne pas bloquer la lecture
        """
        while len(self.preload_queue) < 3 and self.queue:
            next_song = self.queue[0]
            future = self.thread_pool.submit(self.download_song, next_song)
            self.preload_queue.append(future)

    async def get_detailed_queue(self, show_all=False):
        """Obtient l'affichage détaillé de la file d'attente"""
        if not show_all:
            # Comportement original pour !queue
            embed = discord.Embed(title="File d'attente détaillée", color=COLORS['INFO'])
            
            if self.current:
                duration = self._format_duration(self.current.get('duration', 0))
                embed.add_field(
                    name=MESSAGES['NOW_PLAYING'],
                    value=f"{self.current['title']} {duration}",
                    inline=False
                )
            
            queue_list = list(self.queue)[:10]  # Affiche les 10 premières chansons
            if queue_list:
                queue_text = "\n".join(
                    f"`{i}.` {song['title']} {self._format_duration(song.get('duration', 0))}"
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
            # Nouveau comportement paginé pour !queue all
            pages = []
            queue_list = list(self.queue)
            songs_per_page = 20  # Nombre de chansons par page
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
                    duration = self._format_duration(self.current.get('duration', 0))
                    embed.add_field(
                        name=MESSAGES['NOW_PLAYING'],
                        value=f"{self.current['title']} {duration}",
                        inline=False
                    )
                
                if current_page_songs:
                    queue_text = "\n".join(
                        f"`{i}.` {song['title']} {self._format_duration(song.get('duration', 0))}"
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

    def _format_duration(self, seconds: float) -> str:
        """
        Formate une durée en secondes en format lisible HH:MM:SS.
        
        Args:
            seconds (float): Nombre de secondes à formater
        
        Returns:
            str: Durée formatée en HH:MM:SS ou MM:SS si moins d'une heure
        
        Examples:
            >>> _format_duration(3665.5)
            '01:01:05'
            >>> _format_duration(185.3)
            '03:05'
        """
        if seconds is None:
            return "00:00"
            
        try:
            seconds = int(float(seconds))
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            seconds = seconds % 60
            
            if hours > 0:
                return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            return f"{minutes:02d}:{seconds:02d}"
        except (ValueError, TypeError):
            return "00:00"

    async def toggle_loop(self, ctx, query=None):
        """Active/désactive le mode boucle pour la chanson actuelle ou démarre la boucle d'une nouvelle chanson"""
        await self.ensure_voice_client()

        if self.loop:
            # Disable loop and properly cleanup
            self.loop = False
            if self.loop_task:
                self.loop_task.cancel()
                self.loop_task = None
            if self.loop_message:
                await self.loop_message.delete()
                self.loop_message = None
            
            # Important: Add current loop song to queue before stopping
            if self.loop_song:
                self.queue.appendleft(self.loop_song.copy())
            
            self.loop_song = None
            self.loop_start_time = None
            self.loop_user = None
            
            # Stop current playback to trigger play_next
            if self.voice_client and self.voice_client.is_playing():
                self.voice_client.stop()
            
            await ctx.send(embed=discord.Embed(
                description=MESSAGES['LOOP_DISABLED'],
                color=COLORS['INFO']
            ))
            return

        try:
            # Clear queue and stop current playback first
            self.queue.clear()
            if self.voice_client and self.voice_client.is_playing():
                self.voice_client.stop()
                await asyncio.sleep(0.5)  # Wait for playback to fully stop

            # Set up the song to loop
            if query:
                # Extract info with updated options
                info = await asyncio.get_event_loop().run_in_executor(
                    self.thread_pool,
                    lambda: self.bot.ytdl.extract_info(query, download=False)
                )
                
                if 'entries' in info:
                    raise ValueError(MESSAGES['PLAYLIST_ERROR'])
                
                self.loop_song = {
                    'url': info.get('webpage_url', query),
                    'title': info.get('title', 'Unknown Title'),
                    'duration': info.get('duration', 0),
                    'needs_processing': False  # Important: Set to False since we already processed it
                }
            elif not self.current:
                raise ValueError(MESSAGES['NOTHING_PLAYING'])
            else:
                self.loop_song = self.current.copy()
                self.loop_song['needs_processing'] = False  # Important: Set to False

            # Enable loop before starting playback
            self.loop = True
            self.loop_start_time = discord.utils.utcnow()
            self.loop_user = ctx.author

            # Create and send the loop message
            embed = self._create_loop_embed()
            self.loop_message = await ctx.send(embed=embed)

            # Start the loop update task
            if self.loop_task:
                self.loop_task.cancel()
            self.loop_task = asyncio.create_task(self._update_loop_message())

            # Start the loop playback
            await self.play_loop_song()

        except Exception as e:
            self.loop = False
            if self.loop_task:
                self.loop_task.cancel()
                self.loop_task = None
            error_embed = discord.Embed(
                title=MESSAGES['ERROR_TITLE'],
                description=str(e),
                color=COLORS['ERROR']
            )
            await ctx.send(embed=error_embed)

    def _create_loop_embed(self):
        """Crée l'embed de statut de la boucle"""
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
        """Met à jour le message de boucle chaque seconde"""
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
        """Méthode auxiliaire pour jouer la chanson en boucle"""
        if not self.voice_client or not self.loop_song:
            return

        try:
            if self.voice_client.is_playing():
                self.voice_client.stop()
                await asyncio.sleep(0.5)  # Ajoute un petit délai pour assurer le nettoyage
            
            # Obtient une nouvelle URL pour l'audio
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
        """Gère la fin de lecture en boucle ou les erreurs"""
        if error:
            print(f"Erreur dans la lecture en boucle : {error}")  # Traduit le message d'erreur
            return
        
        if self.loop:
            # Planifie la prochaine lecture en boucle avec un petit délai
            await asyncio.sleep(0.5)
            await self.play_loop_song()

    def ensure_thread_pool(self):
        """Ensures the thread pool is initialized and active"""
        if not hasattr(self, 'thread_pool') or self.thread_pool is None or self.thread_pool._shutdown:
            self.thread_pool = ThreadPoolExecutor(
                max_workers=2,  # Reduced from 3 to 2
                thread_name_prefix='music_worker'
            )

    async def add_multiple_to_queue(self, query, repeat_count=1):
        """Add multiple copies of a song or playlist to the queue"""
        try:
            await self.ensure_voice_client()
            
            # Use the same optimized options as regular play
            ytdl_opts = {
                'format': 'bestaudio',
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'skip_download': True,
                'force_generic_extractor': True,
                'socket_timeout': 2,
                'retries': 1
            }

            # Check cache first
            if query in self._cached_urls:
                info = self._cached_urls[query]
            else:
                # Extract info with fast options
                async with async_timeout.timeout(10):
                    info = await asyncio.get_event_loop().run_in_executor(
                        self.thread_pool,
                        lambda: yt_dlp.YoutubeDL(ytdl_opts).extract_info(query, download=False)
                    )
                    if info:
                        self._cached_urls[query] = info

            total_songs_added = 0
            
            if 'entries' in info:  # Playlist
                entries = [e for e in info['entries'] if e]
                for _ in range(repeat_count):
                    for entry in entries:
                        song = {
                            'url': entry.get('url', f"https://www.youtube.com/watch?v={entry['id']}"),
                            'title': entry.get('title', 'Unknown Title'),
                            'duration': entry.get('duration', 0),
                            'needs_processing': False
                        }
                        self.queue.append(song)
                        total_songs_added += 1
                        
                        # Start preloading if this is the first song and nothing is playing
                        if total_songs_added == 1 and not self.current:
                            self._preload_task = asyncio.create_task(self._preload_next())
            else:  # Single video
                song_template = {
                    'url': info.get('url', info.get('webpage_url', query)),
                    'title': info.get('title', 'Unknown Title'),
                    'duration': info.get('duration', 0),
                    'needs_processing': False
                }
                
                for _ in range(repeat_count):
                    song = song_template.copy()
                    self.queue.append(song)
                    total_songs_added += 1
                    
                    # Start preloading if this is the first song and nothing is playing
                    if total_songs_added == 1 and not self.current:
                        self._preload_task = asyncio.create_task(self._preload_next())
            
            # Start playing if nothing is playing
            if not self.voice_client.is_playing():
                await self.play_next()
            else:
                embed = discord.Embed(
                    description=MESSAGES['SONGS_ADDED'].format(total=total_songs_added),
                    color=COLORS['SUCCESS']
                )
                await self.ctx.send(embed=embed)
        
        except asyncio.TimeoutError:
            error_embed = discord.Embed(
                title=MESSAGES['ERROR_TITLE'],
                description=MESSAGES['TIMEOUT_ERROR'],
                color=COLORS['ERROR']
            )
            await self.ctx.send(embed=error_embed)
        except Exception as e:
            error_embed = discord.Embed(
                title=MESSAGES['ERROR_TITLE'],
                description=str(e),
                color=COLORS['ERROR']
            )
            await self.ctx.send(embed=error_embed)

    async def _prefetch_song(self, song):
        """Pre-fetch song data to reduce loading time"""
        try:
            if not hasattr(self, '_song_cache'):
                self._song_cache = {}
                
            if song['url'] not in self._song_cache:
                info = await asyncio.get_event_loop().run_in_executor(
                    self.thread_pool,
                    lambda: self.bot.ytdl.extract_info(song['url'], download=False)
                )
                self._song_cache[song['url']] = info
                
                # Pre-warm connection
                if 'url' in info:
                    await asyncio.get_event_loop().run_in_executor(
                        self.thread_pool,
                        lambda: requests.head(info['url'], timeout=2)
                    )
        except Exception as e:
            print(f"Prefetch error: {e}")

    async def start_live(self, url):
        """Start a live stream"""
        try:
            # Stop current playback and clear queue
            if self.voice_client and self.voice_client.is_playing():
                self.voice_client.stop()
            self.queue.clear()
            
            # Ensure voice connection
            await self.ensure_voice_client()
            
            # Extract live stream info
            loop = asyncio.get_running_loop()
            info = await loop.run_in_executor(
                self.thread_pool,
                lambda: self.bot.ytdl.extract_info(url, download=False)
            )
            
            if not info.get('is_live', False):
                raise ValueError(MESSAGES['LIVE_NOT_FOUND'])
                
            # Store live stream info
            self.live_stream = {
                'url': info['url'],
                'title': info['title'],
                'start_time': discord.utils.utcnow()
            }
            
            # Create and send live embed
            self.live_embed = await self._create_live_embed()
            self.live_embed = await self.ctx.send(embed=self.live_embed)
            
            # Start live stream
            audio = discord.FFmpegPCMAudio(
                self.live_stream['url'],
                **FFMPEG_OPTIONS,
                executable=self.bot.config.get('ffmpeg_path', 'ffmpeg')
            )
            self.voice_client.play(audio)
            
            # Start update task
            self.live_task = asyncio.create_task(self._update_live_embed())
            
        except Exception as e:
            await self.stop_live()
            raise ValueError(f"{MESSAGES['LIVE_ERROR']}: {str(e)}")
            
    async def stop_live(self):
        """Stop the live stream"""
        if self.live_stream:
            if self.voice_client and self.voice_client.is_playing():
                self.voice_client.stop()
            if self.live_task:
                self.live_task.cancel()
            if self.live_embed:
                await self.live_embed.delete()
            self.live_stream = None
            self.live_embed = None
            self.live_task = None
            
    async def _create_live_embed(self):
        """Create the live stream embed"""
        if not self.live_stream:
            return None
            
        embed = discord.Embed(
            title=f"🔴 {self.live_stream['title']}",
            color=COLORS['ERROR']  # Red color for live
        )
        duration = discord.utils.utcnow() - self.live_stream['start_time']
        embed.add_field(
            name="En direct depuis",
            value=self._format_duration(int(duration.total_seconds()))
        )
        return embed
        
    async def _update_live_embed(self):
        """Update the live embed every second"""
        try:
            while self.live_stream and self.live_embed:
                embed = await self._create_live_embed()
                await self.live_embed.edit(embed=embed)
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    async def stop(self):
        """Stops current playback and cleans up"""
        # Stop loop if active
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

        # Stop live if active
        await self.stop_live()

        # Stop current playback
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.stop()

    def _extract_info(self, query):
        """
        Extract information from YouTube (runs in thread pool)
        
        Args:
            query (str): URL or search query
            
        Returns:
            dict: Video information from YouTube
        """
        # Check if query is a URL
        is_url = query.startswith(('http://', 'https://', 'www.', 'youtube.com', 'youtu.be'))
        
        # Prepare search query if not a URL
        if not is_url:
            query = f"ytsearch:{query}"
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': 'in_playlist' if is_url else False,
            'format': 'bestaudio/best',
            'default_search': 'ytsearch',  # Enable YouTube search
            'concurrent_fragments': 5,
            'postprocessor_args': {
                'ffmpeg': ['-threads', '2']
            },
            'socket_timeout': 2,
            'retries': 1,
            'nocheckcertificate': True,
            'prefer_insecure': True,
            'http_chunk_size': 10485760,  # 10MB chunks
            'cachedir': False,
            'progress_hooks': [],
            'no_color': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(query, download=False)
                # If it's a search result, get the first entry
                if not is_url and 'entries' in info:
                    if not info['entries']:
                        raise ValueError(MESSAGES['VIDEO_UNAVAILABLE'])
                    return info['entries'][0]
                return info
            except Exception as e:
                print(f"Error extracting info: {e}")
                raise ValueError(MESSAGES['VIDEO_UNAVAILABLE'])