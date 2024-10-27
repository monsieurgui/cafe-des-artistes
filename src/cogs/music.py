import discord
from discord.ext import commands
from core.music_player import MusicPlayer
from utils.constants import MESSAGES, COLORS

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    def get_music_player(self, ctx):
        if ctx.guild.id not in self.bot.music_players:
            self.bot.music_players[ctx.guild.id] = MusicPlayer(self.bot, ctx)
        return self.bot.music_players[ctx.guild.id]

    @commands.command(name='p', aliases=['play'])
    async def play(self, ctx, *, query):
        """Play a song or playlist from YouTube"""
        player = self.get_music_player(ctx)
        await player.add_to_queue(query)

    @commands.command(name='s', aliases=['skip'])
    async def skip(self, ctx):
        """Skip the current song"""
        player = self.get_music_player(ctx)
        await player.skip()

    @commands.command(name='purge')
    async def purge(self, ctx):
        """Clear the music queue"""
        player = self.get_music_player(ctx)
        await player.purge()

    @commands.command(name='queue', aliases=['q'])
    async def queue(self, ctx, show_all: str = None):
        """Display the current queue"""
        player = self.get_music_player(ctx)
        embed, view = await player.get_detailed_queue(show_all == "all")
        await ctx.send(embed=embed, view=view)

    @commands.command(name='support')
    async def support(self, ctx, *, message):
        """Send support message to bot owner"""
        try:
            owner = await self.bot.fetch_user("monsieurgui")
            embed = discord.Embed(
                title=MESSAGES['SUPPORT_TITLE'],
                description=message,
                color=COLORS['ERROR']
            )
            embed.add_field(name="De", value=f"{ctx.author} (ID: {ctx.author.id})")
            embed.add_field(name="Serveur", value=f"{ctx.guild.name} (ID: {ctx.guild.id})")
            embed.add_field(name="Canal", value=f"{ctx.channel.name} (ID: {ctx.channel.id})")
            
            await owner.send(embed=embed)
            await ctx.author.send(embed=discord.Embed(
                description=MESSAGES['SUPPORT_SENT'],
                color=COLORS['SUCCESS']
            ))
            await ctx.message.delete()
            
        except discord.Forbidden:
            await ctx.send(embed=discord.Embed(
                title=MESSAGES['ERROR_TITLE'],
                description=MESSAGES['DM_ERROR'],
                color=COLORS['ERROR']
            ), delete_after=10)
        except Exception:
            await ctx.send(embed=discord.Embed(
                title=MESSAGES['ERROR_TITLE'],
                description=MESSAGES['SUPPORT_ERROR'],
                color=COLORS['ERROR']
            ), delete_after=10)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandInvokeError):
            error = error.original
        
        if isinstance(error, ValueError):
            embed = discord.Embed(
                title=MESSAGES['ERROR_TITLE'],
                description=str(error),
                color=COLORS['ERROR']
            )
            await ctx.send(embed=embed, delete_after=10)

async def setup(bot):
    await bot.add_cog(Music(bot))
