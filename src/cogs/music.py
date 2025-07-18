import discord
import asyncio
import logging
from datetime import datetime
from discord.ext import commands
from discord import app_commands
from utils.constants import MESSAGES, COLORS


class QueueView(discord.ui.View):
    """UI Component for paginated queue display with Previous/Next Page buttons"""
    
    def __init__(self, queue_data, current_page=1, bot=None, guild_id=None):
        super().__init__(timeout=None)  # Persistent view
        self.queue_data = queue_data
        self.current_page = current_page
        self.bot = bot
        self.guild_id = guild_id
        self.songs_per_page = 10
        
        # Calculate total pages
        self.total_pages = max(1, (len(queue_data) + self.songs_per_page - 1) // self.songs_per_page)
        
        # Update button states
        self._update_button_states()
    
    def _update_button_states(self):
        """Update the enabled/disabled state of navigation buttons"""
        # Previous button - disabled on page 1
        self.previous_page_button.disabled = (self.current_page <= 1)
        
        # Next button - disabled on last page
        self.next_page_button.disabled = (self.current_page >= self.total_pages)
        
        # If queue is empty, disable both buttons
        if not self.queue_data:
            self.previous_page_button.disabled = True
            self.next_page_button.disabled = True
    
    @discord.ui.button(label="◀ Previous Page", style=discord.ButtonStyle.secondary, custom_id="queue_prev", row=0)
    async def previous_page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle previous page button click"""
        if self.current_page > 1:
            self.current_page -= 1
            self._update_button_states()
            
            # Generate new embed for current page
            embed = self._generate_queue_embed()
            
            # Update the message
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(label="Next Page ▶", style=discord.ButtonStyle.secondary, custom_id="queue_next", row=0)
    async def next_page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle next page button click"""
        if self.current_page < self.total_pages:
            self.current_page += 1
            self._update_button_states()
            
            # Generate new embed for current page
            embed = self._generate_queue_embed()
            
            # Update the message
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()
    
    def _generate_queue_embed(self):
        """Generate the queue embed for the current page"""
        embed = discord.Embed(
            title="🎵 Music Queue",
            color=COLORS['INFO']
        )
        
        if not self.queue_data:
            embed.description = "Queue is empty"
            embed.set_footer(text="Use /play to add songs to the queue")
            self._add_disabled_select_menu()
            return embed
        
        # Calculate start and end indices for current page
        start_idx = (self.current_page - 1) * self.songs_per_page
        end_idx = min(start_idx + self.songs_per_page, len(self.queue_data))
        
        # Get songs for current page
        current_page_songs = self.queue_data[start_idx:end_idx]
        
        # Create description with 10 songs per page using new rich format
        description_lines = []
        
        for i, song in enumerate(current_page_songs):
            song_number = start_idx + i + 1
            title = song.get('title', 'Unknown')
            duration = song.get('duration', 0)
            duration_str = self._format_duration(duration)
            requester = song.get('requester_name', song.get('requester', 'Unknown'))
            webpage_url = song.get('webpage_url', song.get('url', ''))
            
            # New rich format with hyperlinked title and metadata line with better spacing
            description_lines.append(f"**{song_number}.** [{title}]({webpage_url})")
            description_lines.append(f"> └─ 🕒 `{duration_str}`  •  👤 `{requester}`")
            
            # Add separator line between songs (except for the last song)
            if i < len(current_page_songs) - 1:
                description_lines.append("")  # Empty line for spacing
        
        embed.description = "\n".join(description_lines)
        
        # Set footer with page information
        embed.set_footer(text=f"Page {self.current_page}/{self.total_pages} • {len(self.queue_data)} total songs")
        
        # Update remove select menu for current page
        self._update_remove_select_menu(current_page_songs, start_idx)
        
        return embed
    
    def _clear_remove_select_menu(self):
        """Clear the remove select menu from the view"""
        items_to_remove = []
        for item in self.children:
            if hasattr(item, 'custom_id') and item.custom_id == 'remove_song_select':
                items_to_remove.append(item)
        
        for item in items_to_remove:
            self.remove_item(item)
    
    def _add_disabled_select_menu(self):
        """Add a disabled select menu for empty queue state"""
        # Clear any existing select menu first
        self._clear_remove_select_menu()
        
        # Create a disabled select menu with placeholder message
        disabled_select = discord.ui.Select(
            placeholder="The queue is currently empty.",
            custom_id="remove_song_select",
            options=[discord.SelectOption(label="No songs", description="Queue is empty", value="empty")],
            disabled=True,
            row=2
        )
        
        self.add_item(disabled_select)
    
    def _update_remove_select_menu(self, current_page_songs, start_idx):
        """Update remove select menu for the current page songs"""
        # Clear existing select menu
        self._clear_remove_select_menu()
        
        if not current_page_songs:
            return
        
        # Create select options for each song on current page
        options = []
        for i, song in enumerate(current_page_songs):
            song_index = start_idx + i  # Actual index in the queue
            title = song.get('title', 'Unknown')
            requester = song.get('requester_name', song.get('requester', 'Unknown'))
            
            # Truncate title if too long for select option
            if len(title) > 90:
                title = title[:87] + "..."
            
            option = discord.SelectOption(
                label=title,
                description=f"Position: {song_index + 1} | Added by: {requester}",
                value=str(song_index),
                emoji="🗑️"
            )
            options.append(option)
        
        # Create the select menu
        remove_select = discord.ui.Select(
            placeholder="Select a song to remove from the queue...",
            custom_id="remove_song_select",
            options=options,
            row=2  # Place in row 2 (below navigation buttons)
        )
        
        # Set the callback
        remove_select.callback = self._handle_remove_song_select
        self.add_item(remove_select)
    
    async def _handle_remove_song(self, interaction: discord.Interaction, song_index: int):
        """Handle remove song button click"""
        try:
            if self.bot and self.guild_id:
                # Send REMOVE_FROM_QUEUE command to Player Service
                result = await self.bot.ipc_manager.ipc_client.remove_from_queue(self.guild_id, song_index)
                
                if result['status'] == 'success':
                    # Get updated queue state
                    state_result = await self.bot.ipc_manager.ipc_client.get_player_state(self.guild_id)
                    
                    if state_result['status'] == 'success':
                        updated_queue = state_result.get('data', {}).get('state', {}).get('queue', [])
                        
                        # Update the view with new queue data
                        self.queue_data = updated_queue
                        self.total_pages = max(1, (len(updated_queue) + self.songs_per_page - 1) // self.songs_per_page)
                        
                        # Adjust current page if necessary
                        if self.current_page > self.total_pages:
                            self.current_page = max(1, self.total_pages)
                        
                        # Update button states and generate new embed
                        self._update_button_states()
                        embed = self._generate_queue_embed()
                        
                        # Update the message
                        await interaction.response.edit_message(embed=embed, view=self)
                    else:
                        await interaction.response.send_message("❌ Failed to get updated queue state.", ephemeral=True)
                else:
                    await interaction.response.send_message(f"❌ Failed to remove song: {result.get('message', 'Unknown error')}", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Unable to remove song - no connection to player service.", ephemeral=True)
                
        except Exception as e:
            await interaction.response.send_message(f"❌ Error removing song: {str(e)}", ephemeral=True)
    
    async def _handle_remove_song_select(self, interaction: discord.Interaction):
        """Handle song removal from select menu"""
        try:
            from utils.embeds import success, error
            
            # Get the selected song index
            selected_value = interaction.data['values'][0]
            song_index = int(selected_value)
            
            # Get song title for feedback message
            song_title = "Unknown"
            if self.queue_data and 0 <= song_index < len(self.queue_data):
                song_title = self.queue_data[song_index].get('title', 'Unknown')
            
            if self.bot and self.guild_id:
                # Send REMOVE_FROM_QUEUE command to Player Service
                result = await self.bot.ipc_manager.ipc_client.remove_from_queue(self.guild_id, song_index)
                
                if result['status'] == 'success':
                    # Get updated queue state
                    state_result = await self.bot.ipc_manager.ipc_client.get_player_state(self.guild_id)
                    
                    if state_result['status'] == 'success':
                        updated_queue = state_result.get('data', {}).get('state', {}).get('queue', [])
                        
                        # Update the view with new queue data
                        self.queue_data = updated_queue
                        self.total_pages = max(1, (len(updated_queue) + self.songs_per_page - 1) // self.songs_per_page)
                        
                        # Adjust current page if necessary
                        if self.current_page > self.total_pages:
                            self.current_page = max(1, self.total_pages)
                        
                        # Update button states and generate new embed
                        self._update_button_states()
                        embed = self._generate_queue_embed()
                        
                        # Update the message with new embed
                        await interaction.response.edit_message(embed=embed, view=self)
                        
                        # Send ephemeral success message
                        await interaction.followup.send(
                            embed=success(f"Successfully removed \"{song_title}\" from the queue."),
                            ephemeral=True
                        )
                    else:
                        await interaction.response.send_message(
                            embed=error("Failed to get updated queue state."),
                            ephemeral=True
                        )
                else:
                    await interaction.response.send_message(
                        embed=error(f"Failed to remove song: {result.get('message', 'Unknown error')}"),
                        ephemeral=True
                    )
            else:
                await interaction.response.send_message(
                    embed=error("Unable to remove song - no connection to player service."),
                    ephemeral=True
                )
                
        except Exception as e:
            await interaction.response.send_message(
                embed=error(f"Error removing song: {str(e)}"),
                ephemeral=True
            )
    
    def _format_duration(self, seconds: float) -> str:
        """Format a duration in seconds to a readable HH:MM:SS format"""
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
            
            # First, stop any currently playing audio on the bot client
            if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
                interaction.guild.voice_client.stop()
            
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
                # Stop any now playing updates
                await self.stop_now_playing_updates(interaction.guild.id)
                
                # Find and clear the content of the Queue and Now Playing embeds 
                # in the control channel as specified in the requirements
                await self._clear_control_panel_embeds(interaction.guild.id)
                
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

    async def _clear_control_panel_embeds(self, guild_id: int):
        """Clear the content of Queue and Now Playing embeds in control channel"""
        try:
            # Import database utilities
            from utils.database import get_guild_setup
            
            # Get guild settings
            guild_settings = await get_guild_setup(guild_id)
            
            if guild_settings:
                # Get the control channel
                guild = self.bot.get_guild(guild_id)
                if guild:
                    control_channel = guild.get_channel(guild_settings.control_channel_id)
                    
                    if control_channel:
                        # Clear queue embed with new QueueView
                        try:
                            queue_message = await control_channel.fetch_message(guild_settings.queue_message_id)
                            # Create empty queue view
                            empty_queue_view = QueueView([], current_page=1, bot=self.bot, guild_id=guild_id)
                            empty_queue_embed = empty_queue_view._generate_queue_embed()
                            await queue_message.edit(embed=empty_queue_embed, view=empty_queue_view)
                        except discord.NotFound:
                            pass  # Message was deleted
                        
                        # Clear now playing embed - generate idle image
                        try:
                            now_playing_message = await control_channel.fetch_message(guild_settings.now_playing_message_id)
                            # Generate idle state image
                            from utils.image_generator import create_now_playing_image
                            idle_image_buffer = await create_now_playing_image(None, 0)
                            discord_file = discord.File(idle_image_buffer, filename="now_playing.png")
                            embed = self._create_image_embed()
                            await now_playing_message.edit(embed=embed, attachments=[discord_file])
                        except discord.NotFound:
                            pass  # Message was deleted
                            
        except Exception as e:
            # Log error but don't fail the command
            print(f"Error clearing control panel embeds: {e}")

    async def update_queue_display(self, guild_id: int, queue_data: list):
        """Update the queue embed with current queue data"""
        try:
            from utils.database import get_guild_setup
            
            guild_settings = await get_guild_setup(guild_id)
            
            if guild_settings:
                guild = self.bot.get_guild(guild_id)
                if guild:
                    control_channel = guild.get_channel(guild_settings.control_channel_id)
                    
                    if control_channel:
                        try:
                            queue_message = await control_channel.fetch_message(guild_settings.queue_message_id)
                            
                            # Create new queue view with updated data
                            queue_view = QueueView(queue_data, current_page=1, bot=self.bot, guild_id=guild_id)
                            queue_embed = queue_view._generate_queue_embed()
                            
                            # Update the message with new data and view
                            await queue_message.edit(embed=queue_embed, view=queue_view)
                            
                        except discord.NotFound:
                            pass  # Message was deleted
                            
        except Exception as e:
            print(f"Error updating queue display: {e}")

    def _create_image_embed(self):
        """
        Create a simplified embed container for the dynamically generated Now Playing image.
        This replaces the complex text-based embed with a simple container for the image.
        
        Returns:
            discord.Embed: Simple embed that displays the attached image
        """
        embed = discord.Embed(color=COLORS['INFO'])
        embed.set_image(url="attachment://now_playing.png")
        return embed
    
    
    async def update_now_playing_display(self, guild_id: int, song_data=None, start_time=None):
        """Update the now playing display with dynamically generated image"""
        try:
            from utils.database import get_guild_setup
            from utils.image_generator import create_now_playing_image
            
            logger = logging.getLogger(__name__)
            logger.info(f"Updating now playing display for guild {guild_id}")
            
            guild_settings = await get_guild_setup(guild_id)
            
            if guild_settings:
                guild = self.bot.get_guild(guild_id)
                if guild:
                    control_channel = guild.get_channel(guild_settings.control_channel_id)
                    
                    if control_channel:
                        try:
                            now_playing_message = await control_channel.fetch_message(guild_settings.now_playing_message_id)
                            
                            # Calculate current time for progress bar
                            current_time = 0
                            if start_time and song_data:
                                current_time = int((discord.utils.utcnow() - start_time).total_seconds())
                            
                            # Generate the now playing image
                            image_buffer = await create_now_playing_image(song_data, current_time)
                            
                            # Create Discord file from image buffer
                            discord_file = discord.File(image_buffer, filename="now_playing.png")
                            
                            # Create simple embed container for the image
                            embed = self._create_image_embed()
                            
                            # Update the message with new image and embed
                            await now_playing_message.edit(embed=embed, attachments=[discord_file])
                            logger.info(f"Successfully updated now playing image for guild {guild_id}")
                            
                        except discord.NotFound:
                            logger.warning(f"Now playing message not found for guild {guild_id}")
                        except discord.Forbidden:
                            logger.error(f"No permission to edit now playing message for guild {guild_id}")
                    else:
                        logger.warning(f"Control channel not found for guild {guild_id}")
                else:
                    logger.warning(f"Guild {guild_id} not found")
            else:
                logger.warning(f"No guild settings found for guild {guild_id}")
                            
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error updating now playing display: {e}")

    async def start_now_playing_updates(self, guild_id: int, song_data: dict):
        """
        Start automatic progress updates for the now playing embed
        Updates every 5 seconds as specified in requirements
        """
        try:
            logger = logging.getLogger(__name__)
            logger.info(f"Starting now playing updates for guild {guild_id}")
            
            # Stop any existing update task for this guild
            await self.stop_now_playing_updates(guild_id)
            
            # Store the start time for progress calculation
            start_time = discord.utils.utcnow()
            self.guild_song_start_times[guild_id] = start_time
            
            # Immediately update the now playing embed with the new song
            await self.update_now_playing_display(guild_id, song_data, start_time)
            
            # Create and start the update task for periodic updates
            task = asyncio.create_task(self._update_now_playing_loop(guild_id, song_data))
            self.now_playing_update_tasks[guild_id] = task
            
            logger.info(f"Now playing updates task started for guild {guild_id}")
            
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error starting now playing updates for guild {guild_id}: {e}")
    
    async def stop_now_playing_updates(self, guild_id: int):
        """Stop automatic progress updates for a guild"""
        try:
            # Cancel existing update task
            if guild_id in self.now_playing_update_tasks:
                task = self.now_playing_update_tasks[guild_id]
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                del self.now_playing_update_tasks[guild_id]
            
            # Clear start time
            if guild_id in self.guild_song_start_times:
                del self.guild_song_start_times[guild_id]
                
        except Exception as e:
            print(f"Error stopping now playing updates for guild {guild_id}: {e}")
    
    async def _update_now_playing_loop(self, guild_id: int, song_data: dict):
        """
        Background task that updates the now playing embed every 20 seconds
        This implements the requirement: "This embed should be updated every 20 seconds if a song is playing to show progress"
        """
        try:
            while True:
                await asyncio.sleep(20)  # Update every 20 seconds for better CPU performance
                
                # Get the start time for this guild
                start_time = self.guild_song_start_times.get(guild_id)
                if not start_time:
                    break  # No start time means we should stop
                
                # Update the now playing display with current progress
                await self.update_now_playing_display(guild_id, song_data, start_time)
                
        except asyncio.CancelledError:
            # Task was cancelled, which is normal
            pass
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error in now playing update loop for guild {guild_id}: {e}")

    @app_commands.command(name="setup", description="Set up the bot's control panel in this server")
    async def setup(self, interaction: discord.Interaction):
        """Set up the bot's control panel - Admin only"""
        try:
            from utils.embeds import error, info, success
            
            # Check if user has Administrator permissions
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    embed=error("You do not have the required permissions to use this command."),
                    ephemeral=True
                )
                return
            
            await interaction.response.defer(ephemeral=True)
            
            # Allow re-setup - this will override existing configuration
            
            # Send a DM to the interaction.user asking for channel name as specified
            try:
                # First, create the setup session in database for persistence across restarts
                from utils.database import get_database_manager
                db_manager = await get_database_manager()
                
                # Delete any existing setup session for this user to allow re-setup
                await db_manager.delete_setup_session(interaction.user.id)
                
                started_at = discord.utils.utcnow().isoformat()
                session_created = await db_manager.create_setup_session(
                    interaction.user.id,
                    interaction.guild.id, 
                    interaction.guild.name,
                    started_at
                )
                
                logger = logging.getLogger(__name__)
                logger.info(f"Setup session created for user {interaction.user.id} in guild {interaction.guild.id}: {session_created}")
                
                if not session_created:
                    error_embed = discord.Embed(
                        title="❌ Setup Failed",
                        description="Failed to initialize setup session. Please try again.",
                        color=COLORS['ERROR']
                    )
                    await interaction.followup.send(embed=error_embed, ephemeral=True)
                    return
                
                # Now send the DM
                # Use standardized info embed for setup instructions
                from utils.embeds import create_info_embed
                dm_embed = create_info_embed(
                    title="🎵 Music Bot Setup",
                    description=f"Hi {interaction.user.mention}! Let's set up the music control panel for **{interaction.guild.name}**.\n\n"
                               "Please reply with the name of the text channel you want to use for the music controls.\n\n"
                               "**Example:** `#music-controls`\n\n"
                               "⚠️ Make sure the channel name starts with `#` and that the channel exists in your server.",
                    footer="You have 5 minutes to respond."
                )
                
                await interaction.user.send(embed=dm_embed)
                logger.info(f"Setup DM sent successfully to user {interaction.user.id}")
                
                # Confirm DM was sent
                await interaction.followup.send(
                    embed=success("Setup instructions sent to your DMs."),
                    ephemeral=True
                )
                
            except discord.Forbidden:
                # User has DMs disabled - clean up the session
                await db_manager.delete_setup_session(interaction.user.id)
                logger.warning(f"Failed to send setup DM to user {interaction.user.id} - DMs disabled")
                
                await interaction.followup.send(
                    embed=error("Cannot send DM. Please enable direct messages and try again."),
                    ephemeral=True
                )
            
            except Exception as e:
                # Any other error - clean up the session
                await db_manager.delete_setup_session(interaction.user.id)
                logger.error(f"Setup failed for user {interaction.user.id}: {e}")
                
                await interaction.followup.send(
                    embed=error(f"Setup failed: {str(e)}"),
                    ephemeral=True
                )
            
        except Exception as e:
            await interaction.followup.send(
                embed=error(f"An error occurred during setup: {str(e)}"),
                ephemeral=True
            )

    # Additional slash commands for common functionality

    @app_commands.command(name="queue", description="Show the current music queue")
    async def queue(self, interaction: discord.Interaction):
        """Show the current music queue"""
        try:
            from utils.embeds import info, error
            
            result = await self.bot.ipc_manager.ipc_client.get_player_state(interaction.guild.id)
            
            if result['status'] == 'success':
                state = result.get('data', {}).get('state', {})
                current_song = state.get('current_song')
                queue = state.get('queue', [])
                
                embed = discord.Embed(
                    title="🎵 Music Queue",
                    color=COLORS['INFO']
                )
                
                if current_song:
                    duration = self._format_duration(current_song.get('duration', 0))
                    embed.add_field(
                        name=MESSAGES['NOW_PLAYING'],
                        value=f"{current_song['title']} {duration}",
                        inline=False
                    )
                
                if queue:
                    # Show next 5 songs
                    queue_text = "\n".join(
                        f"{i+1}. {song['title']} {self._format_duration(song.get('duration', 0))}"
                        for i, song in enumerate(queue[:5])
                    )
                        
                    embed.add_field(
                        name=MESSAGES['NEXT_SONGS'],
                        value=queue_text,
                        inline=False
                    )
                    
                    remaining = len(queue) - 5
                    if remaining > 0:
                        embed.set_footer(text=MESSAGES['REMAINING_SONGS'].format(remaining))
                else:
                    if not current_song:
                        embed.description = "The queue is currently empty."
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                raise ValueError(result.get('message', 'Unknown error'))
                
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
    async def on_message(self, message):
        """Handle DM responses for setup process"""
        # Ignore bot messages
        if message.author.bot:
            return
        
        # Only handle DMs
        if not isinstance(message.channel, discord.DMChannel):
            return
        
        # Add logging for debugging
        logger = logging.getLogger(__name__)
        logger.debug(f"Received DM from {message.author} ({message.author.id}): {message.content}")
        
        # Check if user has an active setup session in database
        from utils.database import get_database_manager
        db_manager = await get_database_manager()
        
        session = await db_manager.get_setup_session(message.author.id)
        if not session:
            logger.debug(f"No setup session found for user {message.author.id}")
            
            # Send a helpful message if they seem to be trying to respond to setup
            if message.content.strip().startswith('#'):
                from utils.embeds import create_warning_embed
                recovery_embed = create_warning_embed(
                    title="Setup Session Not Found",
                    description="I don't have an active setup session for you. This could mean:\n\n"
                               "• The setup session expired (sessions last 5 minutes)\n"
                               "• The bot was restarted recently\n"
                               "• You already completed the setup\n\n"
                               "**To start a new setup, run `/setup` in your server.**"
                )
                await message.channel.send(embed=recovery_embed)
            return
        
        # Check if session is expired (5 minutes)
        started_at = datetime.fromisoformat(session['started_at'])
        # Ensure both datetimes are timezone-aware for proper comparison
        current_time = discord.utils.utcnow()
        time_elapsed = current_time - started_at
        if time_elapsed.total_seconds() > 300:  # 5 minutes
            await db_manager.delete_setup_session(message.author.id)
            
            from utils.embeds import create_warning_embed
            timeout_embed = create_warning_embed(
                title="Setup Timeout",
                description="The setup session has expired. Please run `/setup` again in your server."
            )
            await message.channel.send(embed=timeout_embed)
            return
        
        # Validate input: it should start with #
        channel_input = message.content.strip()
        
        if not channel_input.startswith('#'):
            from utils.embeds import create_error_embed
            error_embed = create_error_embed(
                title="Invalid Channel Name",
                description="Please provide a channel name that starts with `#`.\n\n**Example:** `#music-controls`"
            )
            await message.channel.send(embed=error_embed)
            return
        
        # Parse the string to get the channel name
        channel_name = channel_input[1:]  # Remove the #
        
        # Get the guild and find the channel
        guild = self.bot.get_guild(session['guild_id'])
        if not guild:
            from utils.embeds import create_error_embed
            error_embed = create_error_embed(
                title="Server Not Found",
                description="I couldn't find the server. Please run `/setup` again."
            )
            await message.channel.send(embed=error_embed)
            await db_manager.delete_setup_session(message.author.id)
            return
        
        # Use discord.utils.get to find the corresponding channel object
        channel = discord.utils.get(guild.text_channels, name=channel_name)
        
        if not channel:
            from utils.embeds import create_error_embed
            error_embed = create_error_embed(
                title="Channel Not Found",
                description=f"I couldn't find a text channel named `#{channel_name}` in **{session['guild_name']}**.\n\n"
                           "Please make sure:\n"
                           "• The channel exists\n"
                           "• You spelled the name correctly\n"
                           "• It's a text channel (not voice)\n\n"
                           "Try again with a valid channel name."
            )
            await message.channel.send(embed=error_embed)
            return
        
        # Check if it's a text channel
        if not isinstance(channel, discord.TextChannel):
            from utils.embeds import create_error_embed
            error_embed = create_error_embed(
                title="Invalid Channel Type",
                description=f"`#{channel_name}` is not a text channel. Please provide a text channel name."
            )
            await message.channel.send(embed=error_embed)
            return
        
        # Valid channel found, proceed with control panel creation
        await self._create_control_panel(message.author, guild, channel)
        
        # Clean up the setup session
        await db_manager.delete_setup_session(message.author.id)

    async def _create_control_panel(self, user: discord.User, guild: discord.Guild, channel: discord.TextChannel):
        """Create the control panel with Queue and Now Playing embeds"""
        try:
            # Check for existing setup and clean up old control panel messages
            from utils.database import get_guild_setup
            existing_setup = await get_guild_setup(guild.id)
            
            if existing_setup:
                # Try to delete old control panel messages
                old_guild = self.bot.get_guild(guild.id)
                if old_guild:
                    old_channel = old_guild.get_channel(existing_setup.control_channel_id)
                    if old_channel:
                        try:
                            # Delete old queue message
                            old_queue_message = await old_channel.fetch_message(existing_setup.queue_message_id)
                            await old_queue_message.delete()
                        except:
                            pass  # Message might already be deleted
                        
                        try:
                            # Delete old now playing message
                            old_now_playing_message = await old_channel.fetch_message(existing_setup.now_playing_message_id)
                            await old_now_playing_message.delete()
                        except:
                            pass  # Message might already be deleted
            # 1. Create the Queue Embed (initially empty) as specified
            # Use the new QueueView for interactive pagination
            empty_queue_view = QueueView([], current_page=1, bot=self.bot, guild_id=guild.id)
            queue_embed = empty_queue_view._generate_queue_embed()
            
            # 2. Create the Now Playing Embed (initially showing "No song playing") as specified
            # Generate initial idle state image
            from utils.image_generator import create_now_playing_image
            idle_image_buffer = await create_now_playing_image(None, 0)
            discord_file = discord.File(idle_image_buffer, filename="now_playing.png")
            now_playing_embed = self._create_image_embed()
            
            # Send the embeds to the channel with the interactive view
            queue_message = await channel.send(embed=queue_embed, view=empty_queue_view)
            now_playing_message = await channel.send(embed=now_playing_embed, file=discord_file)
            
            # 3. Pin both messages to the channel as specified
            try:
                await queue_message.pin()
                await now_playing_message.pin()
            except discord.Forbidden:
                # Bot doesn't have permission to pin messages
                from utils.embeds import create_warning_embed
                error_embed = create_warning_embed(
                    title="Setup Warning",
                    description=f"Control panel created in {channel.mention}, but I couldn't pin the messages. "
                               "Please give me 'Manage Messages' permission to pin the control panel."
                )
                await user.send(embed=error_embed)
            
            # 4. Store the guild_id, control_channel_id, queue_message_id, and now_playing_message_id
            # in the SQLite database as specified
            from utils.database import set_guild_setup
            
            success = await set_guild_setup(
                guild.id,
                channel.id,
                queue_message.id,
                now_playing_message.id
            )
            
            if success:
                # 5. DM the user a success message as specified
                from utils.embeds import create_success_embed
                setup_type = "reconfigured" if existing_setup else "set up"
                success_embed = create_success_embed(
                    title="Setup Complete!",
                    description=f"The music control panel has been successfully {setup_type} in {channel.mention} "
                               f"on **{guild.name}**.\n\n"
                               "The control panel will automatically update when songs are played, skipped, or queued.\n\n"
                               "**Features:**\n"
                               "🎵 **Queue Display** - Shows upcoming songs\n"
                               "🎶 **Now Playing** - Shows current song with progress\n"
                               "🔄 **Auto-Updates** - Real-time status updates",
                    footer="Control panel is ready to use!"
                )
                await user.send(embed=success_embed)
                
            else:
                # Database error
                from utils.embeds import create_error_embed
                error_embed = create_error_embed(
                    title="Setup Failed",
                    description="There was an error saving the setup to the database. Please try again."
                )
                await user.send(embed=error_embed)
                
                # Clean up the messages
                try:
                    await queue_message.delete()
                    await now_playing_message.delete()
                except:
                    pass
                    
        except discord.Forbidden:
            # Bot doesn't have permission to send messages in the channel
            from utils.embeds import create_error_embed
            error_embed = create_error_embed(
                title="Setup Failed",
                description=f"I don't have permission to send messages in {channel.mention}. "
                           "Please give me 'Send Messages' permission in that channel and try again."
            )
            await user.send(embed=error_embed)
            
        except Exception as e:
            # General error
            from utils.embeds import create_error_embed
            error_embed = create_error_embed(
                title="Setup Failed",
                description=f"An unexpected error occurred: {str(e)}\n\nPlease try again or contact support."
            )
            await user.send(embed=error_embed)

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