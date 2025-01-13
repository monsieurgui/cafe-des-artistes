from discord.ext import commands
from core.message_handler import MusicCommands
import discord
import logging

logger = logging.getLogger(__name__)

class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        
        super().__init__(
            command_prefix='!',  # or your preferred prefix
            intents=intents
        )
        
    async def setup_hook(self):
        await self.add_cog(MusicCommands(self))
        
    async def on_ready(self):
        logger.info(f'Bot is ready! Logged in as {self.user}')

def run_bot(token: str):
    bot = MusicBot()
    bot.run(token) 