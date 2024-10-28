import sys
import traceback
import discord
from discord.ext import commands
import yt_dlp
from utils.config import load_config
from utils.constants import YTDL_OPTIONS, MESSAGES, COLORS

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
        Initialise le bot avec les configurations nécessaires.
        
        Configure:
        - Les intentions Discord requises
        - Le préfixe de commande
        - Le gestionnaire YouTube-DL
        - Le stockage des lecteurs de musique
        """
        self.config = load_config()
        
        # Configuration des intentions Discord nécessaires
        intents = discord.Intents.default()
        intents.message_content = True  # Permet la lecture du contenu des messages
        intents.voice_states = True     # Permet le suivi des états vocaux
        
        super().__init__(
            command_prefix=self.config['command_prefix'],
            intents=intents,
            help_command=None  # Désactive la commande d'aide par défaut
        )
        
        # Initialisation du gestionnaire YouTube-DL avec les options optimisées
        self.ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)
        
        # Stockage des lecteurs de musique par serveur
        self.music_players = {}

    async def setup_hook(self):
        """
        Configure les extensions du bot au démarrage.
        
        Cette méthode est appelée automatiquement par discord.py
        lors de l'initialisation du bot.
        
        Raises:
            ExtensionNotFound: Si le module music n'est pas trouvé
            ExtensionFailed: Si le chargement échoue
        """
        await self.load_extension('cogs.music')

    async def on_ready(self):
        """Appelé lorsque le bot est prêt et connecté"""
        print(f"Connecté en tant que {self.user}")

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

    async def on_error(self, event_method: str, *args, **kwargs):
        """
        Gestionnaire global des erreurs d'événements.
        
        Capture et journalise toutes les erreurs non gérées qui se produisent
        pendant le traitement des événements Discord.
        
        Args:
            event_method (str): Nom de la méthode d'événement qui a échoué
            *args: Arguments positionnels de l'événement
            **kwargs: Arguments nommés de l'événement
            
        Notes:
            - Journalise la trace complète de l'erreur
            - Permet la continuité du bot malgré les erreurs
        """
        print(f'Erreur dans {event_method}:', file=sys.stderr)
        traceback.print_exc()

    async def on_command_error(self, ctx, error):
        """
        Gestionnaire global des erreurs de commandes.
        
        Traite les erreurs qui se produisent lors de l'exécution des commandes
        et fournit des messages d'erreur appropriés aux utilisateurs.
        
        Args:
            ctx (Context): Contexte de la commande
            error (CommandError): L'erreur qui s'est produite
            
        Notes:
            - Gère spécifiquement les erreurs ValueError
            - Affiche des messages d'erreur conviviaux
            - Les messages d'erreur s'effacent automatiquement après 10 secondes
        """
        if isinstance(error, commands.CommandInvokeError):
            error = error.original
        
        if isinstance(error, ValueError):
            embed = discord.Embed(
                title=MESSAGES['ERROR_TITLE'],
                description=str(error),
                color=COLORS['ERROR']
            )
            await ctx.send(embed=embed, delete_after=10)
