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
            self._clear_remove_buttons()
            return embed
        
        # Calculate start and end indices for current page
        start_idx = (self.current_page - 1) * self.songs_per_page
        end_idx = min(start_idx + self.songs_per_page, len(self.queue_data))
        
        # Get songs for current page
        current_page_songs = self.queue_data[start_idx:end_idx]
        
        # Create description with 10 songs per page
        description_lines = []
        
        for i, song in enumerate(current_page_songs):
            song_number = start_idx + i + 1
            title = song.get('title', 'Unknown')
            duration = song.get('duration', 0)
            duration_str = self._format_duration(duration)
            requester = song.get('requester', 'Unknown')
            
            description_lines.append(f"{song_number}. [{title}]({song.get('url', '')}) - ({duration_str}) - Added by {requester}")
        
        # Fill remaining lines with placeholders to maintain constant height
        while len(description_lines) < self.songs_per_page:
            description_lines.append("-")
        
        embed.description = "\n".join(description_lines)
        
        # Set footer with page information
        embed.set_footer(text=f"Page {self.current_page}/{self.total_pages} • {len(self.queue_data)} total songs")
        
        # Update remove buttons for current page
        self._update_remove_buttons(current_page_songs, start_idx)
        
        return embed
    
    def _clear_remove_buttons(self):
        """Clear all remove buttons from the view"""
        # Remove all remove buttons (keep navigation buttons)
        items_to_remove = []
        for item in self.children:
            if hasattr(item, 'custom_id') and item.custom_id and item.custom_id.startswith('remove_song_'):
                items_to_remove.append(item)
        
        for item in items_to_remove:
            self.remove_item(item)
    
    def _update_remove_buttons(self, current_page_songs, start_idx):
        """Update remove buttons for the current page songs"""
        # Clear existing remove buttons
        self._clear_remove_buttons()
        
        # Add remove buttons for each song on current page
        for i, song in enumerate(current_page_songs):
            song_index = start_idx + i  # Actual index in the queue
            
            # Create remove button for this song
            remove_button = discord.ui.Button(
                label="❌",
                style=discord.ButtonStyle.danger,
                custom_id=f"remove_song_{song_index}",
                row=2 + (i // 5)  # Distribute across rows 2, 3, 4 (5 buttons per row)
            )
            
            # Create callback for this specific song
            def create_remove_callback(idx):
                async def remove_callback(interaction: discord.Interaction):
                    await self._handle_remove_song(interaction, idx)
                return remove_callback
            
            remove_button.callback = create_remove_callback(song_index)
            self.add_item(remove_button)
    
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
            raise ValueError(MESSAGES['VOICE_CHANNEL_REQUIRED'])
        
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
            await interaction.response.defer()
            await self.ensure_voice_channel(interaction)
            
            # Send command to Player Service via IPC
            result = await self.bot.ipc_manager.ipc_client.add_to_queue(
                interaction.guild.id, query, 1, interaction.user.display_name
            )
            
            if result['status'] == 'success':
                data = result.get('data', {})
                if data.get('status') == 'added':
                    embed = discord.Embed(
                        description=MESSAGES['SONG_ADDED'].format(
                            title=data.get('song_title', 'Unknown'),
                            queue_size=data.get('queue_size', 0)
                        ),
                        color=COLORS['SUCCESS']
                    )
                    await interaction.followup.send(embed=embed)
                else:
                    embed = discord.Embed(
                        description=f"Now playing: {data.get('song_title', 'Unknown')}",
                        color=COLORS['SUCCESS']
                    )
                    await interaction.followup.send(embed=embed)
            else:
                raise ValueError(result.get('message', 'Unknown error'))
                
        except Exception as e:
            embed = discord.Embed(
                title=MESSAGES['ERROR_TITLE'],
                description=str(e),
                color=COLORS['ERROR']
            )
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="skip", description="Skip the current song")
    async def skip(self, interaction: discord.Interaction):
        """Skip the current song"""
        try:
            await interaction.response.defer()
            
            result = await self.bot.ipc_manager.ipc_client.skip_song(interaction.guild.id)
            
            if result['status'] == 'success':
                data = result.get('data', {})
                if data.get('status') == 'skipped':
                    embed = discord.Embed(
                        description=MESSAGES['SKIPPED'],
                        color=COLORS['SUCCESS']
                    )
                    await interaction.followup.send(embed=embed)
                elif data.get('status') == 'nothing_playing':
                    await interaction.followup.send(MESSAGES['NOTHING_PLAYING'])
            else:
                raise ValueError(result.get('message', 'Unknown error'))
                
        except Exception as e:
            embed = discord.Embed(
                title=MESSAGES['ERROR_TITLE'],
                description=str(e),
                color=COLORS['ERROR']
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="leave", description="Disconnect the bot from voice channel")
    async def leave(self, interaction: discord.Interaction):
        """Disconnect the bot from voice channel and clear queue"""
        try:
            await interaction.response.defer()
            
            # Reset player and disconnect
            await self.bot.ipc_manager.ipc_client.reset_player(interaction.guild.id)
            await self.bot.ipc_manager.ipc_client.disconnect_from_voice(interaction.guild.id)
            
            # Disconnect from Discord voice
            if interaction.guild.voice_client:
                await interaction.guild.voice_client.disconnect()
            
            embed = discord.Embed(
                description=MESSAGES['GOODBYE'],
                color=COLORS['WARNING']
            )
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title=MESSAGES['ERROR_TITLE'],
                description=str(e),
                color=COLORS['ERROR']
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="p5", description="Play a song 5 times")
    @app_commands.describe(query="Song name, artist, or YouTube URL to play 5 times")
    async def p5(self, interaction: discord.Interaction, query: str):
        """Play a song 5 times"""
        try:
            await interaction.response.defer()
            await self.ensure_voice_channel(interaction)
            
            result = await self.bot.ipc_manager.ipc_client.add_to_queue(
                interaction.guild.id, query, 5, interaction.user.display_name
            )
            
            if result['status'] == 'success':
                data = result.get('data', {})
                embed = discord.Embed(
                    description=MESSAGES['SONGS_ADDED'].format(total=data.get('songs_added', 5)),
                    color=COLORS['SUCCESS']
                )
                await interaction.followup.send(embed=embed)
            else:
                raise ValueError(result.get('message', 'Unknown error'))
                
        except Exception as e:
            embed = discord.Embed(
                title=MESSAGES['ERROR_TITLE'],
                description=str(e),
                color=COLORS['ERROR']
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="reset", description="Clear the queue and stop playback")
    async def reset(self, interaction: discord.Interaction):
        """Clear the queue and stop playback"""
        try:
            # Defer the response as specified in the requirements
            await interaction.response.defer()
            
            # Send RESET_PLAYER command to the Player Service for the guild_id
            # This tells the player to clear its queue and stop playback
            result = await self.bot.ipc_manager.ipc_client.reset_player(interaction.guild.id)
            
            if result['status'] == 'success':
                # Find and clear the content of the Queue and Now Playing embeds 
                # in the control channel as specified in the requirements
                await self._clear_control_panel_embeds(interaction.guild.id)
                
                # Respond with confirmation message as specified
                embed = discord.Embed(
                    description="🔄 Queue cleared and playback stopped.",
                    color=COLORS['SUCCESS']
                )
                await interaction.followup.send(embed=embed)
            else:
                raise ValueError(result.get('message', 'Unknown error'))
                
        except Exception as e:
            embed = discord.Embed(
                title=MESSAGES['ERROR_TITLE'],
                description=str(e),
                color=COLORS['ERROR']
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

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
                        
                        # Clear now playing embed
                        try:
                            now_playing_message = await control_channel.fetch_message(guild_settings.now_playing_message_id)
                            # Use the new now playing embed generation
                            empty_now_playing_embed = self._generate_now_playing_embed()
                            await now_playing_message.edit(embed=empty_now_playing_embed)
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

    def _generate_now_playing_embed(self, song_data=None, start_time=None):
        """
        Generate the Now Playing embed for the control panel
        
        Args:
            song_data: Song information dict or None
            start_time: When the song started playing (for progress calculation)
            
        Returns:
            discord.Embed: The Now Playing embed
        """
        embed = discord.Embed(
            title="🎶 Now Playing",
            color=COLORS['INFO']
        )
        
        if not song_data:
            # No song playing state as specified in requirements
            embed.description = "No song playing"
            embed.set_footer(text="Use /play to start playing music")
            return embed
        
        # Song is playing - reuse existing design (title, progress bar, thumbnail, duration)
        # and add footer showing "Added by: [Requester Name]" as specified
        
        # Song title as description
        embed.description = song_data.get('title', 'Unknown')
        
        # Duration and progress calculation
        duration = song_data.get('duration', 0)
        current_time = 0
        
        if start_time:
            current_time = (discord.utils.utcnow() - start_time).total_seconds()
        
        # Add progress field if duration is available
        if duration and duration > 0:
            progress_text = (
                f"`{self._format_duration(int(current_time))} / "
                f"{self._format_duration(duration)}`\n"
                f"{self._create_progress_bar(current_time, duration)}"
            )
            embed.add_field(name="Progress", value=progress_text, inline=False)
        elif duration == 0:
            # Live stream
            embed.add_field(name="Status", value="🔴 LIVE", inline=False)
        
        # Channel info
        if channel := song_data.get('channel'):
            embed.add_field(name="Channel", value=channel, inline=True)
        
        # View count if available
        if view_count := song_data.get('view_count'):
            embed.add_field(name="Views", value=f"{view_count:,}", inline=True)
        
        # Thumbnail
        if thumbnail := song_data.get('thumbnail'):
            embed.set_thumbnail(url=thumbnail)
        
        # URL
        if url := song_data.get('webpage_url') or song_data.get('url'):
            embed.url = url
        
        # Footer showing "Added by: [Requester Name]" as specified in requirements
        requester = song_data.get('requester_name', song_data.get('requester', 'Unknown'))
        embed.set_footer(text=f"Added by: {requester}")
        
        return embed
    
    def _create_progress_bar(self, current, total, length=20):
        """Create a text-based progress bar"""
        if not total or total <= 0:
            return "▬" * length + " 🔴 LIVE"
        
        filled = int((current / total) * length)
        filled = max(0, min(filled, length))  # Clamp between 0 and length
        bar = "▰" * filled + "▱" * (length - filled)
        return f"{bar} 🔊"
    
    async def update_now_playing_display(self, guild_id: int, song_data=None, start_time=None):
        """Update the now playing embed with current song data"""
        try:
            from utils.database import get_guild_setup
            
            guild_settings = await get_guild_setup(guild_id)
            
            if guild_settings:
                guild = self.bot.get_guild(guild_id)
                if guild:
                    control_channel = guild.get_channel(guild_settings.control_channel_id)
                    
                    if control_channel:
                        try:
                            now_playing_message = await control_channel.fetch_message(guild_settings.now_playing_message_id)
                            
                            # Generate new now playing embed
                            embed = self._generate_now_playing_embed(song_data, start_time)
                            
                            # Update the message
                            await now_playing_message.edit(embed=embed)
                            
                        except discord.NotFound:
                            pass  # Message was deleted
                            
        except Exception as e:
            print(f"Error updating now playing display: {e}")

    async def start_now_playing_updates(self, guild_id: int, song_data: dict):
        """
        Start automatic progress updates for the now playing embed
        Updates every 5 seconds as specified in requirements
        """
        try:
            # Stop any existing update task for this guild
            await self.stop_now_playing_updates(guild_id)
            
            # Store the start time for progress calculation
            self.guild_song_start_times[guild_id] = discord.utils.utcnow()
            
            # Create and start the update task
            task = asyncio.create_task(self._update_now_playing_loop(guild_id, song_data))
            self.now_playing_update_tasks[guild_id] = task
            
        except Exception as e:
            print(f"Error starting now playing updates for guild {guild_id}: {e}")
    
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
        Background task that updates the now playing embed every 5 seconds
        This implements the requirement: "This embed should be updated every 5 seconds if a song is playing to show progress"
        """
        try:
            while True:
                await asyncio.sleep(5)  # Update every 5 seconds as specified
                
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
            print(f"Error in now playing update loop for guild {guild_id}: {e}")

    @app_commands.command(name="setup", description="Set up the bot's control panel in this server")
    async def setup(self, interaction: discord.Interaction):
        """Set up the bot's control panel - Admin only"""
        try:
            # Check if user has Administrator permissions
            if not interaction.user.guild_permissions.administrator:
                embed = discord.Embed(
                    title=MESSAGES['ERROR_TITLE'],
                    description="You need Administrator permissions to use this command.",
                    color=COLORS['ERROR']
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            await interaction.response.defer(ephemeral=True)
            
            # Check if guild is already set up
            from utils.database import guild_exists
            if await guild_exists(interaction.guild.id):
                embed = discord.Embed(
                    description="This server is already set up! The control panel is active.",
                    color=COLORS['WARNING']
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Send a DM to the interaction.user asking for channel name as specified
            try:
                # First, create the setup session in database for persistence across restarts
                from utils.database import get_database_manager
                db_manager = await get_database_manager()
                
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
                dm_embed = discord.Embed(
                    title="🎵 Music Bot Setup",
                    description=f"Hi {interaction.user.mention}! Let's set up the music control panel for **{interaction.guild.name}**.\n\n"
                               "Please reply with the name of the text channel you want to use for the music controls.\n\n"
                               "**Example:** `#music-controls`\n\n"
                               "⚠️ Make sure the channel name starts with `#` and that the channel exists in your server.",
                    color=COLORS['INFO']
                )
                dm_embed.set_footer(text="You have 5 minutes to respond.")
                
                await interaction.user.send(embed=dm_embed)
                logger.info(f"Setup DM sent successfully to user {interaction.user.id}")
                
                # Confirm DM was sent
                success_embed = discord.Embed(
                    description="📨 I've sent you a DM with setup instructions. Please check your direct messages!",
                    color=COLORS['SUCCESS']
                )
                await interaction.followup.send(embed=success_embed, ephemeral=True)
                
            except discord.Forbidden:
                # User has DMs disabled - clean up the session
                await db_manager.delete_setup_session(interaction.user.id)
                logger.warning(f"Failed to send setup DM to user {interaction.user.id} - DMs disabled")
                
                error_embed = discord.Embed(
                    title="❌ Setup Failed",
                    description="I couldn't send you a DM. Please enable DMs from server members and try again.",
                    color=COLORS['ERROR']
                )
                await interaction.followup.send(embed=error_embed, ephemeral=True)
            
            except Exception as e:
                # Any other error - clean up the session
                await db_manager.delete_setup_session(interaction.user.id)
                logger.error(f"Setup failed for user {interaction.user.id}: {e}")
                
                error_embed = discord.Embed(
                    title="❌ Setup Failed", 
                    description=f"An error occurred during setup: {str(e)}",
                    color=COLORS['ERROR']
                )
                await interaction.followup.send(embed=error_embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title=MESSAGES['ERROR_TITLE'],
                description=str(e),
                color=COLORS['ERROR']
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    # Additional slash commands for common functionality

    @app_commands.command(name="queue", description="Show the current music queue")
    async def queue(self, interaction: discord.Interaction):
        """Show the current music queue"""
        try:
            await interaction.response.defer()
            
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
                        embed.description = MESSAGES['QUEUE_EMPTY_SAD']
                
                await interaction.followup.send(embed=embed)
            else:
                raise ValueError(result.get('message', 'Unknown error'))
                
        except Exception as e:
            embed = discord.Embed(
                title=MESSAGES['ERROR_TITLE'],
                description=str(e),
                color=COLORS['ERROR']
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    # Support command (non-music functionality)
    @app_commands.command(name="support", description="Send a support message to the bot owner")
    @app_commands.describe(message="Your support message or bug report")
    async def support(self, interaction: discord.Interaction, message: str):
        """Send a support message to the bot owner"""
        try:
            # Get the effective owner (configured owner or guild owner)
            owner = await self.bot.get_effective_owner_async(interaction.guild)
            
            if not owner:
                error_embed = discord.Embed(
                    title=MESSAGES['ERROR_TITLE'],
                    description="No bot owner configured for support messages.",
                    color=COLORS['ERROR']
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
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
            
            success_embed = discord.Embed(
                description=MESSAGES['SUPPORT_SENT'],
                color=COLORS['SUCCESS']
            )
            await interaction.response.send_message(embed=success_embed, ephemeral=True)
            
        except discord.Forbidden:
            error_embed = discord.Embed(
                title=MESSAGES['ERROR_TITLE'],
                description=MESSAGES['DM_ERROR'],
                color=COLORS['ERROR']
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
        except Exception as e:
            error_embed = discord.Embed(
                title=MESSAGES['ERROR_TITLE'],
                description=MESSAGES['SUPPORT_ERROR'],
                color=COLORS['ERROR']
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

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
                recovery_embed = discord.Embed(
                    title="❓ Setup Session Not Found",
                    description="I don't have an active setup session for you. This could mean:\n\n"
                               "• The setup session expired (sessions last 5 minutes)\n"
                               "• The bot was restarted recently\n"
                               "• You already completed the setup\n\n"
                               "**To start a new setup, run `/setup` in your server.**",
                    color=COLORS['WARNING']
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
            
            timeout_embed = discord.Embed(
                title="⏰ Setup Timeout",
                description="The setup session has expired. Please run `/setup` again in your server.",
                color=COLORS['ERROR']
            )
            await message.channel.send(embed=timeout_embed)
            return
        
        # Validate input: it should start with #
        channel_input = message.content.strip()
        
        if not channel_input.startswith('#'):
            error_embed = discord.Embed(
                title="❌ Invalid Channel Name",
                description="Please provide a channel name that starts with `#`.\n\n**Example:** `#music-controls`",
                color=COLORS['ERROR']
            )
            await message.channel.send(embed=error_embed)
            return
        
        # Parse the string to get the channel name
        channel_name = channel_input[1:]  # Remove the #
        
        # Get the guild and find the channel
        guild = self.bot.get_guild(session['guild_id'])
        if not guild:
            error_embed = discord.Embed(
                title="❌ Server Not Found",
                description="I couldn't find the server. Please run `/setup` again.",
                color=COLORS['ERROR']
            )
            await message.channel.send(embed=error_embed)
            await db_manager.delete_setup_session(message.author.id)
            return
        
        # Use discord.utils.get to find the corresponding channel object
        channel = discord.utils.get(guild.text_channels, name=channel_name)
        
        if not channel:
            error_embed = discord.Embed(
                title="❌ Channel Not Found",
                description=f"I couldn't find a text channel named `#{channel_name}` in **{session['guild_name']}**.\n\n"
                           "Please make sure:\n"
                           "• The channel exists\n"
                           "• You spelled the name correctly\n"
                           "• It's a text channel (not voice)\n\n"
                           "Try again with a valid channel name.",
                color=COLORS['ERROR']
            )
            await message.channel.send(embed=error_embed)
            return
        
        # Check if it's a text channel
        if not isinstance(channel, discord.TextChannel):
            error_embed = discord.Embed(
                title="❌ Invalid Channel Type",
                description=f"`#{channel_name}` is not a text channel. Please provide a text channel name.",
                color=COLORS['ERROR']
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
            # 1. Create the Queue Embed (initially empty) as specified
            # Use the new QueueView for interactive pagination
            empty_queue_view = QueueView([], current_page=1, bot=self.bot, guild_id=guild.id)
            queue_embed = empty_queue_view._generate_queue_embed()
            
            # 2. Create the Now Playing Embed (initially showing "No song playing") as specified
            # Use the new now playing embed generation logic
            now_playing_embed = self._generate_now_playing_embed()
            
            # Send the embeds to the channel with the interactive view
            queue_message = await channel.send(embed=queue_embed, view=empty_queue_view)
            now_playing_message = await channel.send(embed=now_playing_embed)
            
            # 3. Pin both messages to the channel as specified
            try:
                await queue_message.pin()
                await now_playing_message.pin()
            except discord.Forbidden:
                # Bot doesn't have permission to pin messages
                error_embed = discord.Embed(
                    title="⚠️ Setup Warning",
                    description=f"Control panel created in {channel.mention}, but I couldn't pin the messages. "
                               "Please give me 'Manage Messages' permission to pin the control panel.",
                    color=COLORS['WARNING']
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
                success_embed = discord.Embed(
                    title="✅ Setup Complete!",
                    description=f"The music control panel has been successfully set up in {channel.mention} "
                               f"on **{guild.name}**.\n\n"
                               "The control panel will automatically update when songs are played, skipped, or queued.\n\n"
                               "**Features:**\n"
                               "🎵 **Queue Display** - Shows upcoming songs\n"
                               "🎶 **Now Playing** - Shows current song with progress\n"
                               "🔄 **Auto-Updates** - Real-time status updates",
                    color=COLORS['SUCCESS']
                )
                success_embed.set_footer(text="Control panel is ready to use!")
                await user.send(embed=success_embed)
                
                # Also send a message in the control channel
                welcome_embed = discord.Embed(
                    title="🎵 Music Control Panel",
                    description="This is your music control panel! The embeds above will automatically update "
                               "with queue and playback information.\n\n"
                               f"Set up by {user.mention}",
                    color=COLORS['INFO']
                )
                await channel.send(embed=welcome_embed)
                
            else:
                # Database error
                error_embed = discord.Embed(
                    title="❌ Setup Failed",
                    description="There was an error saving the setup to the database. Please try again.",
                    color=COLORS['ERROR']
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
            error_embed = discord.Embed(
                title="❌ Setup Failed",
                description=f"I don't have permission to send messages in {channel.mention}. "
                           "Please give me 'Send Messages' permission in that channel and try again.",
                color=COLORS['ERROR']
            )
            await user.send(embed=error_embed)
            
        except Exception as e:
            # General error
            error_embed = discord.Embed(
                title="❌ Setup Failed",
                description=f"An unexpected error occurred: {str(e)}\n\nPlease try again or contact support.",
                color=COLORS['ERROR']
            )
            await user.send(embed=error_embed)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Handle legacy command errors (if any remain)"""
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
    """Configure the music cog and sync slash commands"""
    await bot.add_cog(Music(bot))
    
    # Sync slash commands globally
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands globally")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")