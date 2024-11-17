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
        self.thread_pool = ThreadPoolExecutor(max_workers=3)  # Limite les téléchargements simultanés
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
        """
        Ajoute une chanson ou une playlist à la file d'attente avec rate limiting
        """
        try:
            current_time = asyncio.get_event_loop().time()
            if current_time - self.last_add_time < self.add_cooldown:
                return
            self.last_add_time = current_time

            self.ensure_thread_pool()
            await self.ensure_voice_client()
            await self.start_processing()
            
            async with self.batch_lock:
                # Handle loop mode disabling
                if self.loop:
                    await self.toggle_loop(self.ctx)  # Use toggle_loop to properly cleanup
                    await asyncio.sleep(0.5)  # Wait for cleanup to complete
                    
                # Add to batch queue
                self.batch_queue.append(query)
                
                # Start or restart batch processing
                if not self.batch_task or self.batch_task.done():
                    self.batch_task = asyncio.create_task(self._process_batch())

        except Exception as e:
            error_embed = discord.Embed(
                title=MESSAGES['ERROR_TITLE'],
                description=str(e),
                color=COLORS['ERROR']
            )
            await self.ctx.send(embed=error_embed)

    async def _process_batch(self):
        """Process batched song additions"""
        try:
            await asyncio.sleep(0.5)  # Wait for more potential additions
            
            async with self.batch_lock:
                queries = self.batch_queue.copy()
                self.batch_queue.clear()
            
            total_songs_added = 0
            
            for query in queries:
                info = await asyncio.get_event_loop().run_in_executor(
                    self.thread_pool,
                    self._extract_info,
                    query
                )
                
                if 'entries' in info:  # Playlist
                    entries = [e for e in info['entries'] if e]
                    total_songs_added += len(entries)
                    for entry in entries:
                        song = {
                            'url': f"https://www.youtube.com/watch?v={entry['id']}",
                            'title': entry.get('title', 'Unknown Title'),
                            'duration': entry.get('duration', 0),
                            'needs_processing': True
                        }
                        self.queue.append(song)
                        await self.processing_queue.put(song)
                else:  # Single video
                    total_songs_added += 1
                    song = {
                        'url': info['webpage_url'],
                        'title': info['title'],
                        'duration': info.get('duration', 0),
                        'needs_processing': True
                    }
                    self.queue.append(song)
                    await self.processing_queue.put(song)

            # Send confirmation message without the "Prochaine Chanson" embed
            if total_songs_added > 0:
                message = (MESSAGES['PLAYLIST_ADDED'].format(total_songs_added) 
                          if total_songs_added > 1 
                          else MESSAGES['SONG_ADDED'])
                
                embed = discord.Embed(
                    description=message,
                    color=COLORS['SUCCESS']
                )
                await self.ctx.send(embed=embed)
                
                # Start playing if nothing is playing
                if not self.voice_client.is_playing():
                    await self.play_next()
                    
        except Exception as e:
            print(f"Error in batch processing: {e}")

    def _extract_info(self, query):
        """
        Extrait les informations depuis YouTube (s'exécute dans le pool de threads)
        """
        is_url = query.startswith(('http://', 'https://', 'www.'))
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': 'in_playlist' if is_url else False,
            'format': 'ba[ext=webm]',  # Prefer webm audio format
            'default_search': 'ytsearch' if not is_url else None,
            'concurrent_fragments': 10,  # Increased from 5
            'postprocessor_args': {
                'ffmpeg': ['-threads', '3']
            },
            'buffersize': 131072,  # Doubled buffer size
            'socket_timeout': 2,
            'extractor_retries': 1,  # Reduced retries
            'nocheckcertificate': True,
            'prefer_insecure': True,
            'http_chunk_size': 20971520,  # 20MB chunks
            'live_from_start': False,
            'cachedir': False,  # Disable cache
            'progress_hooks': [],  # Disable progress hooks
            'no_color': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(query, download=False)

    async def process_video(self, video_url):
        """
        Traite la vidéo avec des paramètres optimisés
        """
        try:
            loop = asyncio.get_running_loop()
            video_data = await loop.run_in_executor(
                None,
                lambda: self.bot.ytdl.extract_info(video_url, download=False)
            )
            
            # Pré-traite l'URL du flux pour réduire le temps de démarrage de la lecture
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
        """
        # Prevent multiple simultaneous calls
        if hasattr(self, '_playing_lock') and self._playing_lock:
            return
        self._playing_lock = True
        
        try:
            if self.loop and self.loop_song:
                await self.play_loop_song()
                return

            if not self.queue:
                if not self.voice_client:
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

            try:
                # Get fresh audio URL
                info = await asyncio.get_event_loop().run_in_executor(
                    self.thread_pool,
                    lambda: self.bot.ytdl.extract_info(song['url'], download=False)
                )
                
                if info.get('url'):
                    audio = discord.FFmpegPCMAudio(
                        info['url'],
                        **FFMPEG_OPTIONS
                    )
                    
                    def after_callback(error):
                        if error:
                            print(f"Error in playback: {error}")
                        asyncio.run_coroutine_threadsafe(self.play_next(), self.bot.loop)
                    
                    self.voice_client.play(audio, after=after_callback)
                    await self.ctx.send(embed=await self.get_queue_display())
                    
            except Exception as e:
                error_embed = discord.Embed(
                    title=MESSAGES['ERROR_TITLE'],
                    description=f"{song['title']}: {str(e)}",
                    color=COLORS['ERROR']
                )
                await self.ctx.send(embed=error_embed)
                await self.play_next()
        finally:
            self._playing_lock = False

    async def skip(self):
        """Passe à la chanson suivante"""
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
        
        # Show next three songs only if something is currently playing
        if self.queue and self.current:
            next_songs = list(self.queue)[:3]
            next_songs_text = "\n".join(
                f"{i+1}. {song['title']} {format_duration(song.get('duration', 0))}"
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
            
            # Stop thread pool safely
            if hasattr(self, 'thread_pool'):
                if self.thread_pool and not getattr(self.thread_pool, '_shutdown', True):
                    self.thread_pool.shutdown(wait=False)
                self.thread_pool = None
            
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
            
            # Force garbage collection
            gc.collect()
            
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
        def format_duration(seconds):
            minutes, seconds = divmod(seconds, 60)
            hours, minutes = divmod(minutes, 60)
            if hours > 0:
                return f"`{hours:02d}:{minutes:02d}:{seconds:02d}`"
            return f"`{minutes:02d}:{seconds:02d}`"
        
        if not show_all:
            # Comportement original pour !queue
            embed = discord.Embed(title="File d'attente détaillée", color=COLORS['INFO'])
            
            if self.current:
                duration = format_duration(self.current.get('duration', 0))
                embed.add_field(
                    name=MESSAGES['NOW_PLAYING'],
                    value=f"{self.current['title']} {duration}",
                    inline=False
                )
            
            queue_list = list(self.queue)[:10]  # Affiche les 10 premières chansons
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

    def _format_duration(self, seconds: int) -> str:
        """
        Formate une durée en secondes en format lisible HH:MM:SS.
        
        Args:
            seconds (int): Nombre de secondes à formater
        
        Returns:
            str: Durée formatée en HH:MM:SS ou MM:SS si moins d'une heure
        
        Examples:
            >>> _format_duration(3665)
            '01:01:05'
            >>> _format_duration(185)
            '03:05'
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

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
        try:
            self.ensure_thread_pool()
            await self.ensure_voice_client()
            await self.start_processing()
            
            # Extract info only once
            info = await asyncio.get_event_loop().run_in_executor(
                self.thread_pool,
                self._extract_info,
                query
            )
            
            total_songs_added = 0
            
            if 'entries' in info:  # Playlist
                entries = [e for e in info['entries'] if e]
                for _ in range(repeat_count):
                    for entry in entries:
                        song = {
                            'url': f"https://www.youtube.com/watch?v={entry['id']}",
                            'title': entry.get('title', 'Unknown Title'),
                            'duration': entry.get('duration', 0),
                            'needs_processing': True
                        }
                        self.queue.append(song)
                        await self.processing_queue.put(song)
                        total_songs_added += 1
            else:  # Single video
                song_template = {
                    'url': info['webpage_url'],
                    'title': info['title'],
                    'duration': info.get('duration', 0),
                    'needs_processing': True
                }
                for _ in range(repeat_count):
                    song = song_template.copy()
                    self.queue.append(song)
                    await self.processing_queue.put(song)
                    total_songs_added += 1
            
            # Start playing if nothing is playing
            if not self.voice_client.is_playing():
                await self.play_next()
            else:
                # Send confirmation message with correct formatting
                embed = discord.Embed(
                    description=MESSAGES['SONGS_ADDED'].format(total=total_songs_added),
                    color=COLORS['SUCCESS']
                )
                await self.ctx.send(embed=embed)
        
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