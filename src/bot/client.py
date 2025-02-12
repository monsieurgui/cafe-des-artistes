import sys
import traceback
import discord
from discord.ext import commands
import yt_dlp
from utils.config import load_config
from utils.constants import YTDL_OPTIONS, MESSAGES, COLORS
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
        # ... code existant ...

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
