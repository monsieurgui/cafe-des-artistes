import os
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv
import asyncio
from pathlib import Path

from src.audio.audio_manager import AudioManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('discord_bot.log')
    ]
)
logger = logging.getLogger('DiscordBot')

# Load environment variables
def load_environment():
    """Load environment variables from the appropriate .env file."""
    env_file = '.env.dev' if os.getenv('BOT_ENV') == 'development' else '.env'
    env_path = Path(env_file)
    
    logger.info(f"Loading environment from: {env_path.absolute()}")
    
    if not env_path.exists():
        raise FileNotFoundError(f"Environment file {env_file} not found!")
    
    # Read the file directly first to debug
    with open(env_path, 'r') as f:
        content = f.read()
        logger.info(f"Raw env file content:\n{content}")
    
    # Check for any existing env vars before loading
    prefix_before = os.getenv('COMMAND_PREFIX')
    logger.info(f"Command prefix before loading .env: '{prefix_before}'")
    
    # Now load with python-dotenv
    load_dotenv(env_file, override=True)  # Force override existing variables
    
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        raise ValueError(f"No Discord token found in {env_file}")
    
    # Get command prefix and strip any whitespace
    prefix = os.getenv('COMMAND_PREFIX', '?').strip()
    logger.info(f"Command prefix raw value: '{os.getenv('COMMAND_PREFIX')}'")
    logger.info(f"Command prefix after stripping: '{prefix}'")
    
    # Check if there's a system environment variable that might be interfering
    import subprocess
    try:
        env_vars = subprocess.check_output('set', shell=True).decode()
        logger.info("System environment variables:")
        for line in env_vars.splitlines():
            if 'COMMAND_PREFIX' in line:
                logger.info(f"Found system env var: {line}")
    except Exception as e:
        logger.warning(f"Could not check system environment variables: {e}")
    
    return token, prefix

# Load configuration
try:
    TOKEN, COMMAND_PREFIX = load_environment()
    logger.info(f"Successfully loaded configuration. Command prefix: {COMMAND_PREFIX}")
except Exception as e:
    logger.error(f"Failed to load configuration: {str(e)}")
    raise

# Log token length and first/last few characters for debugging
logger.info(f"Token length: {len(TOKEN)}")
logger.info(f"Token starts with: {TOKEN[:10]}...")
logger.info(f"Token ends with: ...{TOKEN[-10:]}")

# Define intents
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True

class MusicBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=COMMAND_PREFIX,
            intents=intents,
            description='A modular YouTube streaming Discord bot'
        )
        self.audio_manager = None

    async def setup_hook(self):
        """Initialize the bot and load all cogs."""
        # Initialize AudioManager
        self.audio_manager = AudioManager(self)
        
        # Load all cogs from the cogs directory
        cogs_dir = Path(__file__).parent / 'cogs'
        cogs_dir.mkdir(exist_ok=True)
        
        for cog_file in cogs_dir.glob('*.py'):
            if cog_file.name != '__init__.py':
                try:
                    await self.load_extension(f'cogs.{cog_file.stem}')
                    logger.info(f'Loaded extension: {cog_file.stem}')
                except Exception as e:
                    logger.error(f'Failed to load extension {cog_file.stem}: {e}')

    async def on_ready(self):
        """Called when the bot is ready and connected to Discord."""
        env_type = "Development" if os.getenv('BOT_ENV') == 'development' else "Production"
        logger.info(f'{env_type} bot {self.user} has connected to Discord!')
        logger.info(f'Bot is in {len(self.guilds)} guilds')
        
        # Set custom status
        status_prefix = '[DEV] ' if os.getenv('BOT_ENV') == 'development' else ''
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name=f'{status_prefix}{COMMAND_PREFIX}help'
            )
        )
    
    async def close(self):
        """Clean up resources when shutting down."""
        if self.audio_manager:
            self.audio_manager.cleanup()
        await super().close()

async def main():
    """Main entry point for the bot."""
    # Create bot instance
    bot = MusicBot()
    
    # Start the bot
    async with bot:
        try:
            await bot.start(TOKEN)
        except Exception as e:
            logger.error(f'Error running bot: {e}')

if __name__ == '__main__':
    # Run the bot
    asyncio.run(main()) 