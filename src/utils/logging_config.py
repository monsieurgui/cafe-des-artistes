import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logging():
    """
    Configure logging for the bot with both file and console output.
    Creates rotating log files with a max size of 10MB, keeping 5 backup files.
    """
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')

    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Format for logs
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # File handler with rotation
    file_handler = RotatingFileHandler(
        'logs/bot.log',
        maxBytes=10_000_000,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    # Add handlers to root logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler) 