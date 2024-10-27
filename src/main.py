import asyncio
import signal
import logging
from bot.client import MusicBot

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    bot = MusicBot()
    
    def signal_handler(sig, frame):
        logger.info("Shutdown signal received...")
        asyncio.create_task(bot.close())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await bot.start(bot.config['bot_token'])
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
    finally:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())
