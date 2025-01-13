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

import os
import sys
import logging
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from bot import run_bot

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log')
    ]
)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_CACHE_DIR = "cache"
DEFAULT_CONFIG = {
    "command_prefix": "!",
    "max_queue_size": 100,
    "download_threads": 3,
    "buffer_size": 3,
}

def setup_directories():
    """Create necessary directories if they don't exist"""
    directories = [
        DEFAULT_CACHE_DIR,
        "logs",
        "config"
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        logger.info(f"Ensured directory exists: {directory}")

def main():
    try:
        # Load environment variables
        load_dotenv()
        token = os.getenv('DISCORD_TOKEN')
        if not token:
            raise ValueError("DISCORD_TOKEN not found in environment variables")
            
        # Setup directories
        setup_directories()
        
        # Start the bot
        logger.info("Starting bot...")
        run_bot(token)
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
