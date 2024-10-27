import asyncio
import discord
from discord.ext import commands
import yt_dlp
import yaml
import signal
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import os
import gc
from discord.ui import View, Button
import math
import requests

# Configuration YT-DLP
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'opus',
    'noplaylist': True,  # Don't process playlists, only single videos
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'quiet': True,
    'no_warnings': True,
    'extract_flat': True,  # Only extract metadata initially
    'lazy_playlist': True,  # Only extract video information when needed
    'postprocessor_hooks': [],  # Reduce post-processing overhead
    'concurrent_fragment_downloads': 3,  # Download fragments concurrently
    'live_from_start': False,  # Don't download from start of livestreams
    'source_address': '0.0.0.0'  # Let system choose best interface
}

# Configuration FFMPEG
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -threads 3 -buffer_size 32768'
}

# Couleurs des Embeds Discord
COLORS = {
    'SUCCESS': 0x2ecc71,  # Vert
    'ERROR': 0xe74c3c,    # Rouge
    'WARNING': 0xf1c40f,  # Jaune
    'INFO': 0x3498db      # Bleu
}

# Messages du bot
MESSAGES = {
    'PLAYLIST_ADDED': "📑 Ajout a la queue",
    'SONGS_ADDED': "✅ {} chansons addées!",
    'SONG_ADDED': "✅ Ajoutée: {}",
    'ERROR_TITLE': "❌ Erreur",
    'GOODBYE': "On s'revoit bein tôt mon t'cham! 👋",
    'QUEUE_EMPTY': "La queue est vide. 🎵",
    'WAIT_MESSAGE': "⏰ Dans 30 minutes pas de son, chow",
    'QUEUE_EMPTY_SAD': "LLA queue est morte 😢",
    'NOW_PLAYING': "🎵 En lecture",
    'NEXT_SONGS': "Prochaine chanson",
    'REMAINING_SONGS': "+{} autres chanzons en attente",
    'SUPPORT_TITLE': "🆘 Demande de Support",
    'SUPPORT_SENT': "✅ Votre message a été envoyé au god du bot!",
    'DM_ERROR': "Je ne peux pas vous envoyer de messages privés. Veuillez activer les messages privés pour ce serveur.",
    'SUPPORT_ERROR': "Impossible d'envoyer le message de support. Veuillez réessayer plus tard.",
    'VOICE_CHANNEL_REQUIRED': "Ça prend un channel",
    'NOTHING_PLAYING': "Rian joue mon'homme",
    'SKIPPED': "Skippé",
    'QUEUE_PURGED': "Purge complete de la queue"
}

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
                # Start disconnect timer
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
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.stop()
            await self.ctx.send(MESSAGES['SKIPPED'])
        else:
            await self.ctx.send(MESSAGES['NOTHING_PLAYING'])
            
    async def purge(self):
        self.queue.clear()
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.stop()
        await self.cleanup()  # Disconnect after purging
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
            await asyncio.sleep(1800)
            if self.voice_client and not self.voice_client.is_playing() and len(self.queue) == 0:
                embed = discord.Embed(
                    description=MESSAGES['GOODBYE'],
                    color=COLORS['WARNING']  # Couleur jaune
                )
                await self.ctx.send(embed=embed)
                await self.cleanup()
        except asyncio.CancelledError:
            pass

    async def cleanup(self):
        """Clean up resources"""
        if self.processing_task:
            self.processing_task.cancel()
            self.processing_task = None
        self.thread_pool.shutdown(wait=False)
        
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

    def cleanup(self):
        """Clean up downloaded files and cached data"""
        # Clear downloaded files after playing
        if hasattr(self, 'current_file'):
            try:
                os.remove(self.current_file)
            except:
                pass
        
        # Clear memory cache
        gc.collect()

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

class QueueView(View):
    def __init__(self, pages, timeout=60):
        super().__init__(timeout=timeout)
        self.pages = pages  # Pre-generated pages
        self.current_page = 0
        
        # Add buttons with emojis
        prev_button = Button(emoji="⬅️", custom_id="prev", disabled=True)
        next_button = Button(emoji="➡️", custom_id="next", disabled=len(pages) <= 1)
        
        prev_button.callback = self.prev_callback
        next_button.callback = self.next_callback
        
        self.add_item(prev_button)
        self.add_item(next_button)
    
    async def prev_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()  # Acknowledge the interaction first
        self.current_page = max(0, self.current_page - 1)
        
        # Update button states
        self.children[0].disabled = self.current_page == 0
        self.children[1].disabled = self.current_page == len(self.pages) - 1
        
        await interaction.message.edit(
            embed=self.pages[self.current_page], 
            view=self
        )
    
    async def next_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()  # Acknowledge the interaction first
        self.current_page = min(len(self.pages) - 1, self.current_page + 1)
        
        # Update button states
        self.children[0].disabled = self.current_page == 0
        self.children[1].disabled = self.current_page == len(self.pages) - 1
        
        await interaction.message.edit(
            embed=self.pages[self.current_page], 
            view=self
        )

def load_config():
    """
    Charge la configuration du bot depuis le fichier config.yaml
    :return: Dictionnaire de configuration
    """
    with open('config.yaml', 'r') as f:
        return yaml.safe_load(f)

async def main():
    """
    Point d'entrée principal du bot
    Configure et démarre le bot avec tous les gestionnaires d'événements
    """
    config = load_config()
    
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix=config['command_prefix'], intents=intents)
    bot.ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)
    bot.music_players = {}

    @bot.event
    async def on_ready():
        print(f"Logged in as {bot.user}")

    async def cleanup_bot():
        """
        Nettoie toutes les connexions vocales lors de l'arrêt du bot
        """
        print("Cleaning up voice connections...")
        for player in bot.music_players.values():
            try:
                await player.cleanup()
            except:
                pass
        await bot.close()

    # Register signal handlers for graceful shutdown
    def signal_handler(sig, frame):
        print("Shutdown signal received...")
        asyncio.create_task(cleanup_bot())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    def get_music_player(ctx):
        """
        Récupère ou crée un lecteur de musique pour un serveur
        :param ctx: Contexte de la commande
        :return: Instance de MusicPlayer pour le serveur
        """
        if ctx.guild.id not in bot.music_players:
            bot.music_players[ctx.guild.id] = MusicPlayer(bot, ctx)
        return bot.music_players[ctx.guild.id]

    @bot.event
    async def on_voice_state_update(member, before, after):
        """
        Gère les changements d'état vocal (connexions/déconnexions)
        Nettoie les ressources quand le bot est seul ou déconnecté
        """
        if member.id == bot.user.id and after.channel is None:  # Bot was disconnected
            guild_id = before.channel.guild.id
            if guild_id in bot.music_players:
                player = bot.music_players[guild_id]
                await player.cleanup()
                del bot.music_players[guild_id]
        
        # If the bot is alone in a voice channel, disconnect
        if before.channel is not None:
            if len(before.channel.members) == 1 and bot.user in before.channel.members:
                for player in bot.music_players.values():
                    if player.voice_client and player.voice_client.channel == before.channel:
                        await player.cleanup()
                        guild_id = before.channel.guild.id
                        if guild_id in bot.music_players:
                            del bot.music_players[guild_id]

    @bot.command(name='p', aliases=['play'])
    async def play(ctx, *, query):  # Note the '*,' to capture the entire query as a string
        """Play a song or playlist from YouTube"""
        player = get_music_player(ctx)
        await player.add_to_queue(query)

    @bot.command(name='s', aliases=['skip'])
    async def skip(ctx):
        """Skip the current song"""
        player = get_music_player(ctx)
        await player.skip()

    @bot.command(name='purge')
    async def purge(ctx):
        """Clear the music queue"""
        player = get_music_player(ctx)
        await player.purge()

    @bot.command(name='support')
    async def support(ctx, *, message):
        """
        Envoie un message de support au propriétaire du bot
        :param message: Message de support à envoyer
        """
        try:
            # Remplacer par votre ID Discord
            owner = await bot.fetch_user("monsieurgui")
            
            # Créer un embed avec le message de support
            embed = discord.Embed(
                title=MESSAGES['SUPPORT_TITLE'],
                description=message,
                color=COLORS['ERROR']
            )
            embed.add_field(name="De", value=f"{ctx.author} (ID: {ctx.author.id})")
            embed.add_field(name="Serveur", value=f"{ctx.guild.name} (ID: {ctx.guild.id})")
            embed.add_field(name="Canal", value=f"{ctx.channel.name} (ID: {ctx.channel.id})")
            
            # Envoyer le message au propriétaire
            await owner.send(embed=embed)
            
            # Confirmer à l'utilisateur en privé
            confirm_embed = discord.Embed(
                description=MESSAGES['SUPPORT_SENT'],
                color=COLORS['SUCCESS']
            )
            await ctx.author.send(embed=confirm_embed)
            
            # Supprimer le message original pour la confidentialité
            await ctx.message.delete()
            
        except discord.Forbidden:
            error_embed = discord.Embed(
                title=MESSAGES['ERROR_TITLE'],
                description=MESSAGES['DM_ERROR'],
                color=COLORS['ERROR']
            )
            await ctx.send(embed=error_embed, delete_after=10)
        except Exception as e:
            error_embed = discord.Embed(
                title=MESSAGES['ERROR_TITLE'],
                description=MESSAGES['SUPPORT_ERROR'],
                color=COLORS['ERROR']
            )
            await ctx.send(embed=error_embed, delete_after=10)

    @bot.command(name='queue', aliases=['q'])
    async def queue(ctx, show_all: str = None):
        """Display the current queue"""
        player = get_music_player(ctx)
        embed, view = await player.get_detailed_queue(show_all == "all")
        await ctx.send(embed=embed, view=view)

    try:
        await bot.start(config['bot_token'])
    finally:
        await cleanup_bot()

if __name__ == "__main__":
    asyncio.run(main())
