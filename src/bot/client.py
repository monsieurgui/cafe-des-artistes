import sys
import traceback
import discord
from discord.ext import commands
import yt_dlp
from utils.config import load_config
from utils.constants import YTDL_OPTIONS, MESSAGES, COLORS
import logging
import asyncio

class MusicBot(commands.Bot):
    """
    Bot Discord spécialisé dans la lecture de musique.
    
    Cette classe étend discord.ext.commands.Bot avec des fonctionnalités
    spécifiques pour la gestion de la musique, incluant :
    - Gestion des lecteurs de musique par serveur
    - Traitement des commandes musicales
    - Gestion des événements vocaux
    - Système de gestion d'erreurs personnalisé
    
    Attributes:
        config (dict): Configuration du bot chargée depuis config.yaml
        ytdl (YoutubeDL): Instance de yt-dlp pour le téléchargement
        music_players (dict): Dictionnaire des lecteurs de musique par serveur
    """

    def __init__(self):
        """
        Initialize the bot with necessary configurations.
        
        Configures:
        - Required Discord intents
        - Command prefix
        - YouTube-DL manager
        - Music player storage
        """
        self.config = load_config()
        
        # Configure Discord intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        
        # Initialize the bot with configuration
        super().__init__(
            command_prefix=self.config['command_prefix'],
            intents=intents,
            help_command=None
        )
        
        # Initialize YouTube-DL with optimized options
        self.ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)
        
        # Storage for music players per server
        self.music_players = {}
        
        # Configure logging - use a safer way to get log level
        try:
            log_level = self.config.get('log_level', 'INFO').upper()
            level = getattr(logging, log_level, logging.INFO)
        except (AttributeError, KeyError):
            level = logging.INFO
            
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    async def setup_hook(self):
        """Configure bot extensions on startup"""
        await self.load_extension('cogs.music')

    async def on_ready(self):
        """Called when the bot is ready and connected"""
        logger = logging.getLogger(__name__)
        logger.info(f"Bot connected as {self.user}")
        logger.info(f"Bot ID: {self.user.id}")
        logger.info("Bot ready to receive commands!")
        
        # Set bot activity
        activity = discord.Activity(
            type=discord.ActivityType.listening,
            name=f"{self.config['command_prefix']}help"
        )
        await self.change_presence(activity=activity)

    async def on_voice_state_update(self, member, before, after):
        """
        Gère les changements d'état vocal des membres.
        
        Cette méthode surveille :
        - Les déconnexions des membres
        - Les changements de canal
        - L'isolement du bot
        
        Args:
            member (Member): Le membre dont l'état a changé
            before (VoiceState): État vocal précédent
            after (VoiceState): Nouvel état vocal
            
        Notes:
            - Déconnecte automatiquement le bot s'il est seul
            - Gère le nettoyage des ressources lors de la déconnexion
        """
        try:
            # Ignore bot's own voice state changes
            if member.id == self.user.id:
                return
                
            # Get the guild from the voice state
            guild = member.guild
            if guild.id not in self.music_players:
                return
                
            player = self.music_players[guild.id]
            
            # Check if bot is alone in the voice channel
            if player.voice_client and player.voice_client.channel:
                voice_members = [m for m in player.voice_client.channel.members if not m.bot]
                
                # If bot is alone, start disconnect timer
                if len(voice_members) == 0:
                    if player.disconnect_task:
                        player.disconnect_task.cancel()
                    player.disconnect_task = asyncio.create_task(player.delayed_disconnect())
                else:
                    # Cancel disconnect timer if people joined
                    if player.disconnect_task:
                        player.disconnect_task.cancel()
                        player.disconnect_task = None
            
            # Handle bot being moved or disconnected
            if member.id == self.user.id:
                if before.channel and not after.channel:
                    # Bot was disconnected
                    if guild.id in self.music_players:
                        await self.music_players[guild.id].cleanup()
                elif before.channel and after.channel and before.channel != after.channel:
                    # Bot was moved to different channel
                    # Update the voice client reference
                    if guild.id in self.music_players:
                        self.music_players[guild.id].voice_client = after.channel.guild.voice_client
        except Exception as e:
            print(f"Error in voice state update: {e}")

    async def on_disconnect(self):
        """
        Handle bot disconnection
        """
        print("Bot disconnected from Discord")
        
        # Clean up all voice clients
        for guild_id, player in self.music_players.items():
            try:
                if player.voice_client:
                    await player.voice_client.disconnect(force=True)
                    player.voice_client = None
            except Exception as e:
                print(f"Error cleaning up voice client for guild {guild_id}: {e}")

    async def on_resumed(self):
        """
        Handle bot reconnection
        """
        print("Bot reconnected to Discord")
        
        # Re-establish voice connections if needed
        for guild_id, player in self.music_players.items():
            try:
                if player.queue and not player.voice_client:
                    # Try to reconnect if there's a queue
                    await player.ensure_voice_client()
            except Exception as e:
                print(f"Error reconnecting voice client for guild {guild_id}: {e}")

    async def on_voice_client_error(self, voice_client, error):
        """
        Handle voice client errors
        """
        try:
            print(f"Voice client error: {error}")
            
            # Find the player for this voice client
            for guild_id, player in self.music_players.items():
                if player.voice_client == voice_client:
                    # Clear the voice client reference
                    player.voice_client = None
                    
                    # If there's a queue, try to reconnect
                    if player.queue:
                        try:
                            await player.ensure_voice_client()
                            if player.voice_client and player.voice_client.is_connected():
                                await player.play_next()
                        except Exception as e:
                            print(f"Failed to reconnect after voice error: {e}")
                    break
        except Exception as e:
            print(f"Error handling voice client error: {e}")

    async def on_command_error(self, ctx, error):
        """Global command error handler"""
        if isinstance(error, commands.CommandInvokeError):
            error = error.original
        
        if isinstance(error, ValueError):
            embed = discord.Embed(
                title=MESSAGES['ERROR_TITLE'],
                description=str(error),
                color=COLORS['ERROR']
            )
            await ctx.send(embed=embed, delete_after=10)
        elif self.config.get('debug', False):
            # In debug mode, show full error traceback
            traceback.print_exception(type(error), error, error.__traceback__)

    async def on_error(self, event_method: str, *args, **kwargs):
        """Global event error handler"""
        print(f'Error in {event_method}:', file=sys.stderr)
        traceback.print_exc()

    def run(self):
        """Run the bot with the configured token"""
        super().run(self.config['bot_token'], log_handler=None)
