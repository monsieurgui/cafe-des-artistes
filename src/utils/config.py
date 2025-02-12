import yaml
import os
import logging
from dotenv import load_dotenv

"""
Module de gestion de la configuration du bot.

Ce module gère le chargement de la configuration depuis un fichier YAML
et fournit les paramètres nécessaires au fonctionnement du bot.
"""

def setup_ffmpeg_environment():
    """
    Set up the FFmpeg environment by adding the bin directory to PATH
    so FFmpeg can find its DLL dependencies.
    """
    logger = logging.getLogger(__name__)
    
    # Get the absolute path to the bin directory
    bin_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'bin'))
    
    if os.path.exists(bin_dir):
        # Get current PATH
        current_path = os.environ.get('PATH', '')
        
        # Add bin directory to PATH if not already there
        if bin_dir not in current_path:
            logger.debug(f"Adding FFmpeg bin directory to PATH: {bin_dir}")
            os.environ['PATH'] = f"{bin_dir}{os.pathsep}{current_path}"
            
        return True
    return False

def get_ffmpeg_path():
    """
    Get the FFmpeg path, checking multiple locations in order.
    """
    logger = logging.getLogger(__name__)
    
    # Set up FFmpeg environment first
    setup_ffmpeg_environment()
    
    # Check bin directory in project root first
    bin_ffmpeg = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'bin', 'ffmpeg.exe'))
    logger.debug(f"Checking for FFmpeg in bin directory: {bin_ffmpeg}")
    if os.path.exists(bin_ffmpeg):
        logger.info(f"Found FFmpeg in bin directory: {bin_ffmpeg}")
        return bin_ffmpeg
        
    # Then check environment variable
    env_ffmpeg = os.getenv('FFMPEG_PATH')
    if env_ffmpeg:
        logger.debug(f"Checking FFmpeg from environment variable: {env_ffmpeg}")
        if os.path.exists(env_ffmpeg):
            logger.info(f"Found FFmpeg from environment variable: {env_ffmpeg}")
            return env_ffmpeg
    
    # Check common Windows installation paths
    windows_paths = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        os.path.expanduser("~\\ffmpeg\\bin\\ffmpeg.exe"),
        os.path.expandvars("%PROGRAMFILES%\\ffmpeg\\bin\\ffmpeg.exe"),
        os.path.expandvars("%PROGRAMFILES(X86)%\\ffmpeg\\bin\\ffmpeg.exe")
    ]
    
    for path in windows_paths:
        logger.debug(f"Checking FFmpeg in Windows path: {path}")
        if os.path.exists(path):
            logger.info(f"Found FFmpeg in Windows path: {path}")
            return path
    
    # Finally, try system-wide ffmpeg
    logger.warning("No FFmpeg found in specific paths, falling back to system-wide 'ffmpeg'")
    return 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg'

def load_config() -> dict:
    """
    Loads configuration from either .env file (development) or config.yaml (production).
    
    Returns:
        dict: Dictionary containing bot configuration
    """
    # Configure logging first
    logging.basicConfig(
        level=logging.DEBUG if os.getenv('DEBUG', '').lower() == 'true' else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # Load .env file if it exists
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    if os.path.exists(env_path):
        logger.debug(f"Loading .env file from: {env_path}")
        load_dotenv(env_path)
    
    # Determine if we're in development mode
    is_dev = os.getenv('BOT_ENV', '').lower() == 'development'
    logger.info(f"Running in {'development' if is_dev else 'production'} mode")
    
    # Default configuration that applies to both dev and prod
    default_config = {
        'command_prefix': os.getenv('BOT_PREFIX', '!'),
        'ffmpeg_path': get_ffmpeg_path(),
        'owner_id': int(os.getenv('OWNER_ID', 0)),
        'log_level': os.getenv('LOG_LEVEL', 'INFO'),
        'max_queue_size': int(os.getenv('MAX_QUEUE_SIZE', 1000)),
        'timeout_duration': int(os.getenv('TIMEOUT_DURATION', 1800)),
        'debug': os.getenv('DEBUG', 'false').lower() == 'true'
    }
    
    config = {}
    
    if is_dev:
        # Load configuration from environment variables
        config = default_config.copy()
        config['bot_token'] = os.getenv('DISCORD_TOKEN')
    else:
        # Load configuration from yaml in production
        try:
            config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    yaml_config = yaml.safe_load(f)
                    # Merge yaml config with defaults
                    config = {**default_config, **(yaml_config or {})}
            else:
                # If no yaml file exists, use environment variables with defaults
                config = default_config.copy()
                config['bot_token'] = os.getenv('DISCORD_TOKEN')
        except Exception as e:
            logger.error(f"Error loading config.yaml: {e}")
            # Fallback to environment variables with defaults
            config = default_config.copy()
            config['bot_token'] = os.getenv('DISCORD_TOKEN')
    
    # Validate required configuration
    if not config.get('bot_token'):
        raise ValueError("Bot token is required in configuration")
    
    # Validate FFmpeg path and ensure environment is set up
    ffmpeg_path = config.get('ffmpeg_path')
    if ffmpeg_path != 'ffmpeg' and ffmpeg_path != 'ffmpeg.exe' and not os.path.exists(ffmpeg_path):
        logger.warning(f"FFmpeg not found at {ffmpeg_path}, falling back to system-wide 'ffmpeg'")
        config['ffmpeg_path'] = 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg'
    
    return config
