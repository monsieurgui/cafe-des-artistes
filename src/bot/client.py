import sys
import traceback
import discord
from discord.ext import commands
from utils.config import load_config
from utils.constants import YTDL_OPTIONS, MESSAGES, COLORS
from core.voice_manager import VoiceConnectionManager, ConnectionMonitor
from core.event_handlers import VoiceEventHandlers, BotEventHandlers
import logging

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
        
        # Storage for music players per server
        self.music_players = {}
        
        # Initialize voice connection manager
        self.voice_manager = VoiceConnectionManager(self)
        self.connection_monitor = ConnectionMonitor(self.voice_manager)
        
        # Initialize event handlers
        self.voice_event_handler = VoiceEventHandlers(self)
        self.bot_event_handler = BotEventHandlers(self)
        
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
        # Start voice connection monitoring
        self.connection_monitor.start_monitoring()

    async def on_ready(self):
        """Called when the bot is ready and connected"""
        await self.bot_event_handler.on_ready()
        
        # Set bot activity
        activity = discord.Activity(
            type=discord.ActivityType.listening,
            name=f"{self.config['command_prefix']}help"
        )
        await self.change_presence(activity=activity)

    async def on_voice_state_update(self, member, before, after):
        """Handle voice state updates for reconnection and monitoring"""
        await self.voice_event_handler.on_voice_state_update(member, before, after)

    async def on_command_error(self, ctx, error):
        """Handle command errors"""
        await self.bot_event_handler.on_command_error(ctx, error)

    async def on_error(self, event_method: str, *args, **kwargs):
        """Handle general bot errors"""
        await self.bot_event_handler.on_error(event_method, *args, **kwargs)

    def run(self):
        """Run the bot with the configured token"""
        super().run(self.config['bot_token'], log_handler=None)
