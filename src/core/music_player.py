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
                        # Traite l'URL de la chanson dans le pool de threads
                        video_data = await asyncio.get_event_loop().run_in_executor(
                            self.thread_pool,
                            self._process_url,
                            song['url']
                        )
                        # Met à jour les informations de la chanson
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
        Ajoute une chanson ou une playlist à la file d'attente
        :param query: URL ou terme de recherche YouTube
        """
        try:
            self.ensure_thread_pool()
            await self.ensure_voice_client()
            await self.start_processing()
            
            # Désactive la boucle si elle est active
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
                
                # Arrête la lecture en cours s'il y en a une
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
        Extrait les informations depuis YouTube (s'exécute dans le pool de threads)
        """
        is_url = query.startswith(('http://', 'https://', 'www.'))
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': 'in_playlist' if is_url else False,
            'format': 'bestaudio/best',
            'default_search': 'ytsearch' if not is_url else None,
            'concurrent_fragments': 3,  # Télécharge jusqu'à 3 fragments simultanément
            'postprocessor_args': {
                'ffmpeg': ['-threads', '3']  # Utilise 3 threads pour le traitement ffmpeg
            },
            'buffersize': 32768,  # Augmente la taille du tampon pour les opérations réseau
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
        Gère la déconnexion automatique si la file est vide
        """
        if self.loop and self.loop_song:
            await self.play_loop_song()
            return

        # Original play_next logic
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
                
                # Cancel any existing disconnect task
                if self.disconnect_task:
                    self.disconnect_task.cancel()
                
                # Start new disconnect task
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
        
        # Show next three songs
        if self.queue:
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
        # Annule la tâche de traitement
        if self.processing_task:
            self.processing_task.cancel()
            self.processing_task = None
        
        # Arrête le pool de threads
        if hasattr(self, 'thread_pool') and not self.thread_pool._shutdown:
            self.thread_pool.shutdown(wait=False)
        self.thread_pool = None  # Allow for recreation
        
        # Nettoie les fichiers téléchargés
        if hasattr(self, 'current_file'):
            try:
                os.remove(self.current_file)
            except:
                pass
        
        # Nettoie le cache mémoire
        gc.collect()
        
        # Déconnexion du vocal
        if self.voice_client:
            await self.voice_client.disconnect()
            self.voice_client = None

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
                    'duration': info.get('duration', 0)
                }
            elif not self.current:
                raise ValueError(MESSAGES['NOTHING_PLAYING'])
            else:
                self.loop_song = self.current.copy()

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
            self.thread_pool = ThreadPoolExecutor(max_workers=3)