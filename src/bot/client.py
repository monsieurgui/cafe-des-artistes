import sys
import traceback
import discord
from discord.ext import commands
import yt_dlp
from utils.config import load_config
from utils.constants import YTDL_OPTIONS, MESSAGES, COLORS

class MusicBot(commands.Bot):
    def __init__(self):
        self.config = load_config()
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True  # Add this
        
        super().__init__(
            command_prefix=self.config['command_prefix'],
            intents=intents,
            help_command=None  # Add this line to disable default help command
        )
        
        self.ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)
        self.music_players = {}

    async def setup_hook(self):
        await self.load_extension('cogs.music')
        
    async def on_ready(self):
        print(f"Logged in as {self.user}")

    async def on_voice_state_update(self, member, before, after):
        """Reference from original code"""

    async def on_error(self, event_method: str, *args, **kwargs):
        """Global error handler for events"""
        print(f'Error in {event_method}:', file=sys.stderr)
        traceback.print_exc()

    async def on_command_error(self, ctx, error):
        """Global error handler for commands"""
        if isinstance(error, commands.CommandInvokeError):
            error = error.original
        
        if isinstance(error, ValueError):
            embed = discord.Embed(
                title=MESSAGES['ERROR_TITLE'],
                description=str(error),
                color=COLORS['ERROR']
            )
            await ctx.send(embed=embed, delete_after=10)
