"""
Point d'entrée principal du bot Discord Café des Artistes.

Ce module initialise le bot et gère :
- La configuration du système de journalisation
- La gestion des signaux système
- Le démarrage et l'arrêt propre du bot

Notes:
    Le bot utilise asyncio pour la gestion asynchrone des événements
    et signal pour gérer proprement l'arrêt du programme.
"""

import asyncio
import signal
import logging
from bot.client import MusicBot
from utils.logging_config import setup_logging

# Initialize logging configuration
setup_logging()
logger = logging.getLogger(__name__)

async def main():
    """
    Fonction principale asynchrone qui initialise et exécute le bot.
    
    Cette fonction :
    1. Crée une instance du bot
    2. Configure les gestionnaires de signaux
    3. Démarre le bot
    4. Gère la fermeture propre
    
    Raises:
        Exception: Toute erreur non gérée pendant l'exécution
    """
    # Création d'une instance du bot
    bot = MusicBot()
    
    def signal_handler(sig, frame):
        """
        Gestionnaire des signaux d'arrêt
        Permet une fermeture propre du bot lors de l'arrêt du programme
        """
        logger.info("Signal d'arrêt reçu...")
        asyncio.create_task(bot.close())
    
    # Configuration des gestionnaires de signaux pour SIGINT (Ctrl+C) et SIGTERM
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Démarrage du bot avec le jeton d'authentification
        await bot.start(bot.config['bot_token'])
    except Exception as e:
        # Journalisation des erreurs lors du démarrage
        logger.error(f"Erreur lors du démarrage du bot : {e}")
    finally:
        # Assure la fermeture propre du bot dans tous les cas
        await bot.close()

if __name__ == "__main__":
    # Point d'entrée du programme
    # Exécute la fonction principale dans une boucle asyncio
    asyncio.run(main())
