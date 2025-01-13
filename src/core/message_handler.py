from discord.ext import commands
from typing import Optional
import discord
import asyncio
import logging

logger = logging.getLogger(__name__)

class MusicCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.controllers = {}  # Guild ID -> MusicController
        
    async def _get_controller(self, ctx) -> Optional[MusicController]:
        """Get or create a controller for the guild"""
        guild_id = ctx.guild.id
        if guild_id not in self.controllers:
            self.controllers[guild_id] = MusicController(self.bot, ctx)
            await self.controllers[guild_id].start()
        return self.controllers[guild_id]

    @commands.command(name='play', aliases=['p'])
    async def play(self, ctx, *, query: str):
        """Play a song or add it to queue"""
        controller = await self._get_controller(ctx)
        try:
            await controller.add_song(query)
            await ctx.send(f"✅ Added to queue: {query}")
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}")

    @commands.command()
    async def skip(self, ctx):
        """Skip the current song"""
        controller = await self._get_controller(ctx)
        await controller.player.stop()
        await ctx.send("⏭️ Skipped current song")

    @commands.command()
    async def pause(self, ctx):
        """Pause the current playback"""
        controller = await self._get_controller(ctx)
        await controller.player.pause()
        await ctx.send("⏸️ Paused")

    @commands.command()
    async def resume(self, ctx):
        """Resume playback"""
        controller = await self._get_controller(ctx)
        await controller.player.resume()
        await ctx.send("▶️ Resumed")

    @commands.command()
    async def queue(self, ctx):
        """Show the current queue"""
        controller = await self._get_controller(ctx)
        queue_manager = controller.queue_manager
        
        if not queue_manager.main_queue:
            await ctx.send("Queue is empty!")
            return
            
        # Create queue embed
        embed = discord.Embed(title="Current Queue", color=discord.Color.blue())
        
        # Add current song
        if controller.player.current_song:
            embed.add_field(
                name="Now Playing",
                value=f"🎵 {controller.player.current_song.title}",
                inline=False
            )
            
        # Add queued songs
        queue_list = []
        for i, song in enumerate(queue_manager.main_queue, 1):
            queue_list.append(f"{i}. {song.title}")
            
        queue_text = "\n".join(queue_list) if queue_list else "No songs in queue"
        embed.add_field(name="Up Next", value=queue_text, inline=False)
        
        await ctx.send(embed=embed)

    @commands.command()
    async def clear(self, ctx):
        """Clear the queue"""
        controller = await self._get_controller(ctx)
        await controller.queue_manager.clear()
        await ctx.send("🗑️ Queue cleared")

    @commands.command()
    async def shuffle(self, ctx):
        """Shuffle the queue"""
        controller = await self._get_controller(ctx)
        await controller.queue_manager.shuffle()
        await ctx.send("🔀 Queue shuffled")

    @commands.command()
    async def stop(self, ctx):
        """Stop playback and clear queue"""
        controller = await self._get_controller(ctx)
        await controller.queue_manager.clear()
        await controller.player.stop()
        await ctx.send("⏹️ Playback stopped")

    @commands.command()
    async def leave(self, ctx):
        """Disconnect the bot from voice"""
        controller = await self._get_controller(ctx)
        await controller._cleanup_voice_state()
        del self.controllers[ctx.guild.id]
        await ctx.send("👋 Disconnected")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Handle voice state updates"""
        if member.guild.id in self.controllers:
            controller = self.controllers[member.guild.id]
            await controller._handle_voice_state_update(member, before, after) 