"""
Event Handlers for Discord Music Bot
Handles voice state changes and bot events for robust connection management
"""

import asyncio
import logging
import discord
from discord.ext import commands
from typing import Optional

logger = logging.getLogger(__name__)


class VoiceEventHandlers:
    """
    Handles Discord voice-related events for the music bot.
    Implements automatic reconnection and state recovery.
    """
    
    def __init__(self, bot):
        self.bot = bot
        
    async def on_voice_state_update(
        self, 
        member: discord.Member, 
        before: discord.VoiceState, 
        after: discord.VoiceState
    ) -> None:
        """
        Handle voice state updates for bot and users.
        
        Args:
            member: The member whose voice state changed
            before: Voice state before the change
            after: Voice state after the change
        """
        # Only handle bot's own voice state changes
        if member.id != self.bot.user.id:
            return
            
        try:
            guild_id = member.guild.id
            
            # Bot was disconnected from voice
            if before.channel and not after.channel:
                await self._handle_bot_disconnect(guild_id, before.channel)
                
            # Bot was moved to a different channel
            elif before.channel and after.channel and before.channel != after.channel:
                await self._handle_bot_moved(guild_id, before.channel, after.channel)
                
            # Bot connected to voice (shouldn't normally happen automatically)
            elif not before.channel and after.channel:
                await self._handle_bot_connect(guild_id, after.channel)
                
        except Exception as e:
            logger.error(f"Error handling voice state update: {e}")
    
    async def _handle_bot_disconnect(self, guild_id: int, channel: discord.VoiceChannel) -> None:
        """
        Handle bot disconnection from voice channel.
        
        Args:
            guild_id: Guild where disconnection occurred
            channel: Channel bot was disconnected from
        """
        logger.warning(f"Bot disconnected from voice channel {channel.name} in guild {guild_id}")
        
        # Notify voice manager about disconnection
        if hasattr(self.bot, 'voice_manager'):
            await self.bot.voice_manager.handle_disconnect(guild_id, "Disconnected from voice channel")
        
        # Check if we have a music player for this guild
        music_player = self.bot.music_players.get(guild_id)
        if music_player:
            # Save current queue state
            if hasattr(music_player, 'queue_manager'):
                await music_player.queue_manager.persistence.save_queue_state(
                    music_player.queue_manager.queue,
                    music_player.queue_manager.current_song,
                    {'disconnect_time': asyncio.get_event_loop().time()}
                )
            
            # Stop current playback display
            if music_player.current_display:
                await music_player.current_display.stop()
                music_player.current_display = None
    
    async def _handle_bot_moved(
        self, 
        guild_id: int, 
        old_channel: discord.VoiceChannel, 
        new_channel: discord.VoiceChannel
    ) -> None:
        """
        Handle bot being moved to a different voice channel.
        
        Args:
            guild_id: Guild where move occurred
            old_channel: Previous voice channel
            new_channel: New voice channel
        """
        logger.info(f"Bot moved from {old_channel.name} to {new_channel.name} in guild {guild_id}")
        
        # Update voice manager connection tracking
        if hasattr(self.bot, 'voice_manager'):
            voice_client = self.bot.voice_manager.get_voice_client(guild_id)
            if voice_client:
                # Update the tracked connection
                self.bot.voice_manager.connections[guild_id] = voice_client
    
    async def _handle_bot_connect(self, guild_id: int, channel: discord.VoiceChannel) -> None:
        """
        Handle bot connection to voice channel.
        
        Args:
            guild_id: Guild where connection occurred
            channel: Channel bot connected to
        """
        logger.info(f"Bot connected to voice channel {channel.name} in guild {guild_id}")
        
        # Check if we should restore queue state
        music_player = self.bot.music_players.get(guild_id)
        if music_player and hasattr(music_player, 'queue_manager'):
            restored = await music_player.queue_manager.restore_from_persistence()
            if restored:
                logger.info(f"Restored queue state for guild {guild_id}")
                # Resume playback if there were songs in queue
                if music_player.queue_manager.queue:
                    if not getattr(music_player, 'voice_client', None) or not music_player.voice_client.is_connected():
                        try:
                            await music_player.ensure_voice_client()
                        except Exception:
                            return
                    if not music_player.voice_client.is_playing():
                        await music_player.play_next()
    
    async def on_guild_join(self, guild: discord.Guild) -> None:
        """
        Handle bot joining a new guild.
        
        Args:
            guild: Guild that was joined
        """
        logger.info(f"Bot joined guild: {guild.name} (ID: {guild.id})")
        
        # Initialize voice manager tracking for this guild
        if hasattr(self.bot, 'voice_manager'):
            # Reset any existing tracking for this guild
            await self.bot.voice_manager._cleanup_connection(guild.id)
    
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        """
        Handle bot being removed from a guild.
        
        Args:
            guild: Guild that was left
        """
        logger.info(f"Bot left guild: {guild.name} (ID: {guild.id})")
        
        # Cleanup voice manager tracking
        if hasattr(self.bot, 'voice_manager'):
            await self.bot.voice_manager._cleanup_connection(guild.id)
        
        # Cleanup music player
        if guild.id in self.bot.music_players:
            music_player = self.bot.music_players[guild.id]
            
            # Save final queue state
            if hasattr(music_player, 'queue_manager'):
                await music_player.queue_manager.cleanup()
            
            # Cleanup the player
            if hasattr(music_player, 'cleanup'):
                await music_player.cleanup()
            
            # Remove from tracking
            del self.bot.music_players[guild.id]


class BotEventHandlers:
    """
    Handles general bot events and lifecycle management.
    """
    
    def __init__(self, bot):
        self.bot = bot
        
    async def on_ready(self) -> None:
        """Handle bot ready event."""
        logger.info(f"Bot is ready! Logged in as {self.bot.user}")
        logger.info(f"Connected to {len(self.bot.guilds)} guilds")
        
        # Start connection monitoring if not already started
        if hasattr(self.bot, 'connection_monitor'):
            if not self.bot.connection_monitor.is_monitoring:
                self.bot.connection_monitor.start_monitoring()
        
        # Attempt to restore queue states for all guilds
        await self._restore_all_guild_states()
    
    async def _restore_all_guild_states(self) -> None:
        """Restore queue states for all guilds on bot startup."""
        logger.info("Attempting to restore queue states for all guilds...")
        
        restored_count = 0
        for guild in self.bot.guilds:
            try:
                # Ensure a player exists for the guild
                if guild.id not in self.bot.music_players:
                    from core.music_player import MusicPlayer  # lazy import to avoid cycles
                    dummy_ctx = type('Ctx', (), {'guild': guild, 'send': lambda *a, **k: None})
                    self.bot.music_players[guild.id] = MusicPlayer(self.bot, dummy_ctx)

                music_player = self.bot.music_players[guild.id]
                if hasattr(music_player, 'queue_manager'):
                    restored = await music_player.queue_manager.restore_from_persistence()
                    if restored:
                        restored_count += 1
                        logger.info(f"Restored queue for guild {guild.name}")

            except Exception as e:
                logger.error(f"Failed to restore queue for guild {guild.name}: {e}")
        
        if restored_count > 0:
            logger.info(f"Successfully restored queues for {restored_count} guilds")
        else:
            logger.info("No queue states to restore")
    
    async def on_disconnect(self) -> None:
        """Handle bot disconnect event."""
        logger.warning("Bot disconnected from Discord")
        
        # Save all queue states before disconnect
        await self._save_all_guild_states()
    
    async def on_connect(self) -> None:
        """Handle bot connect/reconnect event."""
        logger.info("Bot connected to Discord")
    
    async def on_resumed(self) -> None:
        """Handle bot resume event."""
        logger.info("Bot resumed connection to Discord")
        
        # Validate all voice connections after resume
        if hasattr(self.bot, 'voice_manager'):
            await self.bot.voice_manager.validate_all_connections()
    
    async def _save_all_guild_states(self) -> None:
        """Save queue states for all guilds."""
        logger.info("Saving queue states for all guilds...")
        
        save_tasks = []
        for guild_id, music_player in self.bot.music_players.items():
            if hasattr(music_player, 'queue_manager'):
                task = music_player.queue_manager.persistence.save_queue_state(
                    music_player.queue_manager.queue,
                    music_player.queue_manager.current_song,
                    {'save_time': asyncio.get_event_loop().time()}
                )
                save_tasks.append(task)
        
        if save_tasks:
            await asyncio.gather(*save_tasks, return_exceptions=True)
            logger.info(f"Saved states for {len(save_tasks)} guilds")
    
    async def on_error(self, event: str, *args, **kwargs) -> None:
        """Handle general bot errors."""
        logger.error(f"Bot error in event {event}: {args}, {kwargs}")
    
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        """Handle command errors."""
        if isinstance(error, commands.CommandNotFound):
            return  # Ignore command not found errors
            
        logger.error(f"Command error in {ctx.command}: {error}")
        
        # Send user-friendly error message
        try:
            embed = discord.Embed(
                title="❌ Command Error",
                description=str(error),
                color=0xff6b6b
            )
            await ctx.send(embed=embed, delete_after=15)
        except Exception:
            pass  # Don't let error handling cause more errors
