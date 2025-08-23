import discord
import asyncio
import logging
from discord.ext import commands
from discord import app_commands
from utils.constants import MESSAGES, COLORS


 


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.guild_song_start_times = {}  # Track when songs started for progress calculation
        self.now_playing_update_tasks = {}  # Track background update tasks per guild
    
    async def ensure_voice_channel(self, interaction: discord.Interaction):
        """Ensure the bot is connected to the user's voice channel"""
        if not interaction.user.voice:
            raise ValueError("You must be in a voice channel to use this command.")
        
        channel = interaction.user.voice.channel
        
        # Connect to voice channel if not already connected
        # Bot client maintains the voice connection, player service provides audio sources
        if not interaction.guild.voice_client:
            await channel.connect()
        elif interaction.guild.voice_client.channel != channel:
            await interaction.guild.voice_client.move_to(channel)
        
        return channel

    def _format_duration(self, seconds: float) -> str:
        """
        Format a duration in seconds to a readable HH:MM:SS format.
        """
        if seconds is None:
            return "00:00"
            
        try:
            seconds = int(float(seconds))
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            seconds = seconds % 60
            
            if hours > 0:
                return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            return f"{minutes:02d}:{seconds:02d}"
        except (ValueError, TypeError):
            return "00:00"

    # Slash Commands

    @app_commands.command(name="play", description="Play a song or playlist from YouTube")
    @app_commands.describe(query="Song name, artist, or YouTube URL to play")
    async def play(self, interaction: discord.Interaction, query: str):
        """Play a song or playlist from YouTube"""
        try:
            from utils.embeds import loading, success, error
            # Track last command channel for start-of-song beacon
            self.bot.ipc_manager.ipc_client.update_last_command_channel(interaction.guild.id, interaction.channel.id)
            
            # Initial ephemeral response with loading message
            await interaction.response.send_message(
                embed=loading("Searching for your song..."),
                ephemeral=True
            )
            
            await self.ensure_voice_channel(interaction)
            
            # Send command to Player Service via IPC
            result = await self.bot.ipc_manager.ipc_client.add_to_queue(
                interaction.guild.id, query, 1, interaction.user.display_name
            )
            
            if result['status'] == 'success':
                data = result.get('data', {})
                if data.get('status') == 'added':
                    # Song added to queue
                    message = f"Added **{data.get('song_title', 'Unknown')}** to the queue."
                    await interaction.edit_original_response(embed=success(message))
                else:
                    # Now playing
                    message = f"Added **{data.get('song_title', 'Unknown')}** to the queue."
                    await interaction.edit_original_response(embed=success(message))
            else:
                raise ValueError(result.get('message', 'Unknown error'))
                
        except Exception as e:
            # Handle voice channel error specifically
            if "voice channel" in str(e).lower():
                await interaction.edit_original_response(
                    embed=error("You must be in a voice channel to use this command.")
                )
            else:
                await interaction.edit_original_response(
                    embed=error(f"Failed to play song: {str(e)}")
                )

    @app_commands.command(name="skip", description="Skip the current song")
    async def skip(self, interaction: discord.Interaction):
        """Skip the current song"""
        try:
            from utils.embeds import success, warning, error
            # Track last command channel for start-of-song beacon
            self.bot.ipc_manager.ipc_client.update_last_command_channel(interaction.guild.id, interaction.channel.id)
            
            # First, safely stop any currently playing audio on the bot client
            if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
                try:
                    interaction.guild.voice_client.stop()
                    # Wait a moment for the stop to take effect
                    await asyncio.sleep(0.2)
                except Exception as e:
                    # Log but don't fail if stopping fails
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Error stopping voice client in guild {interaction.guild.id}: {e}")
            
            # Then send skip command to player service
            result = await self.bot.ipc_manager.ipc_client.skip_song(interaction.guild.id)
            
            if result['status'] == 'success':
                data = result.get('data', {})
                if data.get('status') == 'skipped':
                    await interaction.response.send_message(
                        embed=success("The current song has been skipped."),
                        ephemeral=True
                    )
                elif data.get('status') == 'nothing_playing':
                    await interaction.response.send_message(
                        embed=warning("No song is currently playing."),
                        ephemeral=True
                    )
            else:
                raise ValueError(result.get('message', 'Unknown error'))
                
        except Exception as e:
            await interaction.response.send_message(
                embed=error(f"Failed to skip song: {str(e)}"),
                ephemeral=True
            )

    @app_commands.command(name="leave", description="Disconnect the bot from voice channel")
    async def leave(self, interaction: discord.Interaction):
        """Disconnect the bot from voice channel and clear queue"""
        try:
            from utils.embeds import success, error
            # Track last command channel for start-of-song beacon
            self.bot.ipc_manager.ipc_client.update_last_command_channel(interaction.guild.id, interaction.channel.id)
            
            # Reset player and disconnect
            await self.bot.ipc_manager.ipc_client.reset_player(interaction.guild.id)
            await self.bot.ipc_manager.ipc_client.disconnect_from_voice(interaction.guild.id)
            
            # Disconnect from Discord voice
            if interaction.guild.voice_client:
                await interaction.guild.voice_client.disconnect()
            
            await interaction.response.send_message(
                embed=success("Disconnected from the voice channel."),
                ephemeral=True
            )
            
        except Exception as e:
            await interaction.response.send_message(
                embed=error(f"Failed to disconnect: {str(e)}"),
                ephemeral=True
            )

    @app_commands.command(name="p5", description="Play a song 5 times")
    @app_commands.describe(query="Song name, artist, or YouTube URL to play 5 times")
    async def p5(self, interaction: discord.Interaction, query: str):
        """Play a song 5 times"""
        try:
            from utils.embeds import loading, success, error
            # Track last command channel for start-of-song beacon
            self.bot.ipc_manager.ipc_client.update_last_command_channel(interaction.guild.id, interaction.channel.id)
            
            # Initial ephemeral response with loading message
            await interaction.response.send_message(
                embed=loading("Searching for your song..."),
                ephemeral=True
            )
            
            await self.ensure_voice_channel(interaction)
            
            result = await self.bot.ipc_manager.ipc_client.add_to_queue(
                interaction.guild.id, query, 5, interaction.user.display_name
            )
            
            if result['status'] == 'success':
                data = result.get('data', {})
                song_title = data.get('song_title', 'Unknown')
                message = f"Added **{song_title}** to the queue (5 times)."
                await interaction.edit_original_response(embed=success(message))
            else:
                raise ValueError(result.get('message', 'Unknown error'))
                
        except Exception as e:
            # Handle voice channel error specifically
            if "voice channel" in str(e).lower():
                await interaction.edit_original_response(
                    embed=error("You must be in a voice channel to use this command.")
                )
            else:
                await interaction.edit_original_response(
                    embed=error(f"Failed to play song: {str(e)}")
                )

    @app_commands.command(name="reset", description="Clear the queue and stop playback")
    async def reset(self, interaction: discord.Interaction):
        """Clear the queue and stop playback"""
        from utils.embeds import success, error
        # Track last command channel for start-of-song beacon
        self.bot.ipc_manager.ipc_client.update_last_command_channel(interaction.guild.id, interaction.channel.id)
        
        # Respond immediately to prevent timeout
        await interaction.response.send_message(
            embed=success("Resetting player..."),
            ephemeral=True
        )
        
        try:
            # Send RESET_PLAYER command to the Player Service for the guild_id
            # This tells the player to clear its queue and stop playback
            result = await self.bot.ipc_manager.ipc_client.reset_player(interaction.guild.id)
            
            if result['status'] == 'success':
                # Update the response with success message
                await interaction.edit_original_response(
                    embed=success("The player has been reset. The queue is now empty.")
                )
            else:
                await interaction.edit_original_response(
                    embed=error(f"Failed to reset player: {result.get('message', 'Unknown error')}")
                )
                
        except Exception as e:
            await interaction.edit_original_response(
                embed=error(f"Failed to reset player: {str(e)}")
            )

    # Additional slash commands

    @app_commands.command(name="queue", description="Show a snapshot of the next 20 songs")
    async def queue(self, interaction: discord.Interaction):
        """Show a public, single-embed snapshot of up to 20 upcoming songs"""
        try:
            from utils.embeds import error
            
            # Track last command channel
            self.bot.ipc_manager.ipc_client.update_last_command_channel(interaction.guild.id, interaction.channel.id)
            
            result = await self.bot.ipc_manager.ipc_client.get_player_state(interaction.guild.id)
            
            if result['status'] != 'success':
                raise ValueError(result.get('message', 'Unknown error'))
            
            state = result.get('data', {}).get('state', {})
            queue = state.get('queue', [])
            
            embed = discord.Embed(
                title="🎵 Queue Snapshot",
                color=COLORS['INFO'],
                timestamp=discord.utils.utcnow()
            )
            
            if not queue:
                embed.description = "The queue is currently empty."
                await interaction.response.send_message(embed=embed)
                return
            
            # Build up to 20 items
            lines = []
            limit = min(20, len(queue))
            for i in range(limit):
                song = queue[i]
                title = song.get('title', 'Unknown')
                duration = self._format_duration(song.get('duration', 0))
                requester = song.get('requester_name', song.get('requester', 'Unknown'))
                url = song.get('webpage_url', song.get('url', ''))
                
                if url:
                    lines.append(f"**{i+1}.** [{title}]({url})")
                else:
                    lines.append(f"**{i+1}.** {title}")
                lines.append(f"> ⏱ `{duration}` • 👤 `{requester}`")
                if i < limit - 1:
                    lines.append("")
            
            embed.description = "\n".join(lines)
            if len(queue) > limit:
                embed.set_footer(text=f"…and {len(queue) - limit} more")
            
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message(
                embed=error(f"Failed to get queue: {str(e)}"),
                ephemeral=True
            )

    # Support command (non-music functionality)
    @app_commands.command(name="support", description="Send a support message to the bot owner")
    @app_commands.describe(message="Your support message or bug report")
    async def support(self, interaction: discord.Interaction, message: str):
        """Send a support message to the bot owner"""
        try:
            from utils.embeds import success, error
            
            # Get the effective owner (configured owner or guild owner)
            owner = await self.bot.get_effective_owner_async(interaction.guild)
            
            if not owner:
                await interaction.response.send_message(
                    embed=error("No bot owner configured for support messages."),
                    ephemeral=True
                )
                return
            
            embed = discord.Embed(
                title=MESSAGES['SUPPORT_TITLE'],
                description=message,
                color=COLORS['ERROR']
            )
            embed.add_field(name="From", value=f"{interaction.user} (ID: {interaction.user.id})")
            embed.add_field(name="Server", value=f"{interaction.guild.name} (ID: {interaction.guild.id})")
            embed.add_field(name="Channel", value=f"{interaction.channel.name} (ID: {interaction.channel.id})")
            
            # Add information about who the message is being sent to
            embed.add_field(
                name="Sent to", 
                value=f"{'Bot Owner' if self.bot.config.get('owner_id') else 'Server Owner'}: {owner}",
                inline=False
            )
            
            await owner.send(embed=embed)
            
            await interaction.response.send_message(
                embed=success("Your support message has been sent to the bot owner."),
                ephemeral=True
            )
            
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=error("Cannot send support message. The bot owner has disabled DMs."),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=error("Failed to send support message. Please try again later."),
                ephemeral=True
            )

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Handle legacy command errors (if any remain)"""
        if isinstance(error, commands.CommandInvokeError):
            error = error.original
        
        if isinstance(error, ValueError):
            from utils.embeds import create_error_embed
            embed = create_error_embed(
                description=str(error)
            )
            await ctx.send(embed=embed, delete_after=10)



async def setup(bot):
    """Configure the music cog and sync slash commands"""
    await bot.add_cog(Music(bot))
    
    # Sync slash commands globally
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands globally")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")