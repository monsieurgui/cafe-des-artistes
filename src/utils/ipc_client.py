"""
IPC Client for Bot Client
========================

This module provides the IPC client that allows the Bot Client to communicate
with the Player Service via ZeroMQ. It handles sending commands and receiving
events from the Player Service.
"""

import asyncio
import zmq
import zmq.asyncio
import json
import logging
from typing import Dict, Any, Optional, Callable, Tuple
from utils.ipc_protocol import (
    Command, Event, CommandMessage, EventMessage, IPCMessage,
    BOT_CLIENT_CONFIG, create_connect_command, create_disconnect_command,
    create_add_to_queue_command, create_skip_command, create_get_state_command,
    create_reset_command, create_remove_from_queue_command, create_play_next_command
)


class IPCClient:
    """
    IPC Client for communicating with the Player Service
    
    This class manages the ZeroMQ connections and provides a high-level
    interface for sending commands and receiving events.
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None, bot=None):
        """
        Initialize the IPC Client
        
        Args:
            logger: Logger instance for debugging
        """
        self.logger = logger or logging.getLogger(__name__)
        self.bot = bot
        self.context = None
        self.command_socket = None
        self.event_socket = None
        self.event_handlers: Dict[str, Callable] = {}
        self.event_listener_task = None
        self.connected = False
        # Track last command channel and per-song start message for deletion
        self.last_command_channel_by_guild: Dict[int, int] = {}
        self.song_message_by_guild: Dict[int, Tuple[int, int]] = {}
        
    async def connect(self):
        """Initialize ZeroMQ connections to Player Service"""
        try:
            self.logger.info("Connecting to Player Service...")
            
            # Initialize ZeroMQ context
            self.context = zmq.asyncio.Context()
            
            # Setup command socket (sends commands to Player Service)
            self.command_socket = self.context.socket(zmq.REQ)
            self.command_socket.connect(BOT_CLIENT_CONFIG["command_address"])
            
            # Setup event socket (receives events from Player Service)
            self.event_socket = self.context.socket(zmq.SUB)
            self.event_socket.connect(BOT_CLIENT_CONFIG["event_address"])
            
            # Subscribe to all events
            self.event_socket.setsockopt(zmq.SUBSCRIBE, b"")
            
            # Set socket options
            self.command_socket.setsockopt(zmq.RCVTIMEO, BOT_CLIENT_CONFIG["socket_timeout"])
            self.command_socket.setsockopt(zmq.SNDTIMEO, BOT_CLIENT_CONFIG["socket_timeout"])
            
            self.connected = True
            
            # Start event listener
            self.event_listener_task = asyncio.create_task(self._event_listener())
            
            self.logger.info("Successfully connected to Player Service")
            
        except Exception as e:
            self.logger.error(f"Failed to connect to Player Service: {e}")
            await self.disconnect()
            raise
    
    async def disconnect(self):
        """Close ZeroMQ connections"""
        self.logger.info("Disconnecting from Player Service...")
        
        # Set disconnected state first
        self.connected = False
        
        # Stop event listener
        if self.event_listener_task:
            self.event_listener_task.cancel()
            try:
                # Wait for the task to complete with a timeout
                await asyncio.wait_for(self.event_listener_task, timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                # Task was cancelled or timed out, which is expected
                self.logger.debug("Event listener task cancelled or timed out")
            except Exception as e:
                self.logger.warning(f"Unexpected error stopping event listener: {e}")
            finally:
                self.event_listener_task = None
        
        # Close sockets
        if self.command_socket:
            self.command_socket.close()
            self.command_socket = None
            
        if self.event_socket:
            self.event_socket.close()
            self.event_socket = None
        
        # Terminate context
        if self.context:
            try:
                self.context.term()
            except Exception as e:
                self.logger.warning(f"Error terminating ZMQ context: {e}")
            finally:
                self.context = None
        
        self.logger.info("Disconnected from Player Service")
    
    async def _send_command(self, command_message: CommandMessage) -> Dict[str, Any]:
        """
        Send a command to the Player Service and wait for response
        
        Args:
            command_message: Command message to send
            
        Returns:
            Response from Player Service
        """
        if not self.connected or not self.command_socket:
            raise RuntimeError("Not connected to Player Service")
        
        try:
            # Send command
            await self.command_socket.send_string(command_message.to_json())
            
            # Wait for response
            response_data = await self.command_socket.recv_string()
            response = json.loads(response_data)
            
            return response
            
        except zmq.Again:
            raise TimeoutError("Timeout waiting for Player Service response")
        except Exception as e:
            self.logger.error(f"Error sending command: {e}")
            raise
    
    async def _event_listener(self):
        """Background task to listen for events from Player Service"""
        self.logger.info("Starting event listener...")
        
        try:
            while self.connected:
                try:
                    # Wait for event with timeout
                    event_data = await self.event_socket.recv_string(zmq.NOBLOCK)
                    
                    # Parse event
                    event_message = IPCMessage.from_json(event_data)
                    
                    # Handle event
                    await self._handle_event(event_message)
                    
                except zmq.Again:
                    # No message available, wait a bit
                    await asyncio.sleep(0.01)
                except zmq.ZMQError as e:
                    # Handle ZMQ errors during shutdown
                    if not self.connected:
                        self.logger.debug("ZMQ error during shutdown, ignoring")
                        break
                    else:
                        self.logger.error(f"ZMQ error in event listener: {e}")
                        break
                    
        except asyncio.CancelledError:
            self.logger.info("Event listener cancelled")
            raise  # Re-raise to properly handle cancellation
        except Exception as e:
            self.logger.error(f"Error in event listener: {e}")
        finally:
            self.logger.info("Event listener stopped")
    
    async def _handle_event(self, event_message: IPCMessage):
        """
        Handle an event from the Player Service
        
        Args:
            event_message: Event message from Player Service
        """
        try:
            event_type = event_message.action
            guild_id = event_message.guild_id
            data = event_message.data
            
            self.logger.debug(f"Received event {event_type} for guild {guild_id}")
            
            # Call registered event handler if exists
            if event_type in self.event_handlers:
                handler = self.event_handlers[event_type]
                await handler(guild_id, data)
            else:
                self.logger.warning(f"No handler registered for event type: {event_type}")
                
        except Exception as e:
            self.logger.error(f"Error handling event: {e}")
    
    def register_event_handler(self, event_type: Event, handler: Callable):
        """
        Register an event handler
        
        Args:
            event_type: Type of event to handle
            handler: Async function to call when event is received
        """
        self.event_handlers[event_type.value] = handler
        self.logger.debug(f"Registered handler for event type: {event_type.value}")
    
    # Helper methods for Start-of-Song Beacon
    def update_last_command_channel(self, guild_id: int, channel_id: int) -> None:
        """Store the most recent channel where a command was issued for a guild."""
        self.last_command_channel_by_guild[guild_id] = channel_id
        self.logger.debug(f"Updated last command channel for guild {guild_id} -> {channel_id}")
    
    async def _post_start_of_song_message(self, guild_id: int, song_data: Dict[str, Any]) -> None:
        """Post the start-of-song embed with ASCII time in the last command channel."""
        try:
            # Determine channel
            channel_id = self.last_command_channel_by_guild.get(guild_id)
            if not channel_id:
                self.logger.warning(f"No last command channel stored for guild {guild_id}; not posting song beacon")
                return
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                self.logger.warning(f"Channel {channel_id} not found for guild {guild_id}")
                return
            
            # Build embed
            import discord
            from utils.constants import COLORS
            from utils.ascii_time import render_ascii_time
            now_ascii = render_ascii_time()
            title = song_data.get('title', 'Unknown')
            embed = discord.Embed(
                title=f"**{title}**",
                description=f"```text\n{now_ascii}\n```",
                color=COLORS['INFO'],
                timestamp=discord.utils.utcnow()
            )
            # Optionally add URL
            url = song_data.get('webpage_url') or song_data.get('url')
            if url:
                embed.url = url
            
            message = await channel.send(embed=embed)
            self.song_message_by_guild[guild_id] = (channel_id, message.id)
            self.logger.info(f"Posted start-of-song beacon in guild {guild_id} channel {channel_id}")
        except Exception as e:
            self.logger.error(f"Failed to post start-of-song message for guild {guild_id}: {e}")
    
    async def _delete_start_of_song_message(self, guild_id: int) -> None:
        """Delete the previously posted start-of-song embed for a guild if it exists."""
        try:
            info = self.song_message_by_guild.get(guild_id)
            if not info:
                return
            channel_id, message_id = info
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                # Clear tracking if channel not found
                self.song_message_by_guild.pop(guild_id, None)
                return
            import discord
            try:
                message = await channel.fetch_message(message_id)
                await message.delete()
                self.logger.info(f"Deleted start-of-song beacon in guild {guild_id}")
            except discord.NotFound:
                pass
            finally:
                self.song_message_by_guild.pop(guild_id, None)
        except Exception as e:
            self.logger.error(f"Failed to delete start-of-song message for guild {guild_id}: {e}")
    
    # Command methods
    
    async def connect_to_voice(self, guild_id: int, channel_id: int, token: str, 
                              endpoint: str, session_id: str) -> Dict[str, Any]:
        """Send CONNECT command to Player Service"""
        command = create_connect_command(guild_id, channel_id, token, endpoint, session_id)
        return await self._send_command(command)
    
    async def disconnect_from_voice(self, guild_id: int) -> Dict[str, Any]:
        """Send DISCONNECT command to Player Service"""
        command = create_disconnect_command(guild_id)
        return await self._send_command(command)
    
    async def add_to_queue(self, guild_id: int, query: str, repeat_count: int = 1, 
                          requester_name: str = "Unknown") -> Dict[str, Any]:
        """Send ADD_TO_QUEUE command to Player Service"""
        command = create_add_to_queue_command(guild_id, query, repeat_count, requester_name)
        return await self._send_command(command)
    
    async def skip_song(self, guild_id: int) -> Dict[str, Any]:
        """Send SKIP_SONG command to Player Service"""
        command = create_skip_command(guild_id)
        return await self._send_command(command)
    
    async def get_player_state(self, guild_id: int) -> Dict[str, Any]:
        """Send GET_STATE command to Player Service"""
        command = create_get_state_command(guild_id)
        return await self._send_command(command)
    
    async def reset_player(self, guild_id: int) -> Dict[str, Any]:
        """Send RESET_PLAYER command to Player Service"""
        command = create_reset_command(guild_id)
        return await self._send_command(command)
    
    async def remove_from_queue(self, guild_id: int, song_index: int) -> Dict[str, Any]:
        """Send REMOVE_FROM_QUEUE command to Player Service"""
        command = create_remove_from_queue_command(guild_id, song_index)
        return await self._send_command(command)
    
    async def play_next(self, guild_id: int) -> Dict[str, Any]:
        """Send PLAY_NEXT command to Player Service"""
        command = create_play_next_command(guild_id)
        return await self._send_command(command)


class IPCManager:
    """
    High-level manager for IPC operations
    
    This class provides a simplified interface for the Bot Client to interact
    with the Player Service.
    """
    
    def __init__(self, bot, logger: Optional[logging.Logger] = None):
        """
        Initialize the IPC Manager
        
        Args:
            bot: Discord bot instance
            logger: Logger instance
        """
        self.bot = bot
        self.logger = logger or logging.getLogger(__name__)
        self.ipc_client = IPCClient(logger, bot)
        self.voice_states: Dict[int, Dict[str, Any]] = {}
        
    async def initialize(self):
        """Initialize the IPC connection and event handlers"""
        try:
            # Connect to Player Service
            await self.ipc_client.connect()
            
            # Register event handlers
            self.ipc_client.register_event_handler(Event.SONG_STARTED, self._on_song_started)
            self.ipc_client.register_event_handler(Event.SONG_ENDED, self._on_song_ended)
            self.ipc_client.register_event_handler(Event.QUEUE_UPDATED, self._on_queue_updated)
            self.ipc_client.register_event_handler(Event.PLAYER_IDLE, self._on_player_idle)
            self.ipc_client.register_event_handler(Event.PLAYER_STOP, self._on_player_stop)
            self.ipc_client.register_event_handler(Event.PLAYER_ERROR, self._on_player_error)
            self.ipc_client.register_event_handler(Event.STATE_UPDATE, self._on_state_update)
            
            self.logger.info("IPC Manager initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize IPC Manager: {e}")
            raise
    
    async def shutdown(self):
        """Shutdown the IPC connection"""
        await self.ipc_client.disconnect()
    
    def store_voice_state(self, guild_id: int, channel_id: int, token: str, 
                         endpoint: str, session_id: str):
        """Store voice connection parameters for a guild"""
        self.voice_states[guild_id] = {
            'channel_id': channel_id,
            'token': token,
            'endpoint': endpoint,
            'session_id': session_id
        }
        self.logger.debug(f"Stored voice state for guild {guild_id}")
    
    async def handle_voice_server_update(self, guild_id: int, token: str, endpoint: str):
        """Handle voice server update from Discord"""
        if guild_id in self.voice_states:
            self.voice_states[guild_id]['token'] = token
            self.voice_states[guild_id]['endpoint'] = endpoint
            
            # Send connect command to Player Service
            vs = self.voice_states[guild_id]
            try:
                result = await self.ipc_client.connect_to_voice(
                    guild_id, vs['channel_id'], vs['token'], 
                    vs['endpoint'], vs['session_id']
                )
                self.logger.info(f"Connected Player Service to voice: {result}")
            except Exception as e:
                self.logger.error(f"Failed to connect Player Service to voice: {e}")
    
    async def handle_voice_state_update(self, guild_id: int, session_id: str, channel_id: Optional[int]):
        """Handle voice state update from Discord"""
        if channel_id is None:
            # Bot was disconnected
            if guild_id in self.voice_states:
                del self.voice_states[guild_id]
                
            try:
                await self.ipc_client.disconnect_from_voice(guild_id)
            except Exception as e:
                self.logger.error(f"Failed to disconnect Player Service: {e}")
        else:
            # Bot was connected or moved
            if guild_id not in self.voice_states:
                self.voice_states[guild_id] = {}
            
            self.voice_states[guild_id]['channel_id'] = channel_id
            self.voice_states[guild_id]['session_id'] = session_id
    
    # Event handlers
    
    async def _on_song_started(self, guild_id: int, data: Dict[str, Any]):
        """Handle SONG_STARTED event - now includes audio source for streaming"""
        self.logger.info(f"Song started in guild {guild_id}: {data.get('title', 'Unknown')}")
        
        # Get the guild and voice client
        guild = self.bot.get_guild(guild_id)
        if not guild or not guild.voice_client:
            self.logger.warning(f"No voice client available for guild {guild_id}")
            return
        
        # Player service provides the audio source URL
        audio_url = data.get('audio_url')
        if not audio_url:
            self.logger.error(f"No audio URL provided for song in guild {guild_id}")
            return
        
        try:
            # Stop any currently playing audio first
            if guild.voice_client.is_playing():
                guild.voice_client.stop()
                self.logger.info(f"Stopped current audio in guild {guild_id}")
                # Wait a bit for the stop to take effect
                await asyncio.sleep(0.1)
            
            # Bot client streams the audio provided by player service
            from discord import FFmpegPCMAudio
            from utils.constants import FFMPEG_OPTIONS
            
            # Use consistent ffmpeg options for better termination handling
            ffmpeg_options = FFMPEG_OPTIONS.copy()
            
            audio_source = FFmpegPCMAudio(audio_url, **ffmpeg_options)
            
            def after_playing(error):
                # Always advance to next track, even if FFmpeg reports an error
                if error:
                    self.logger.warning(f"Audio playback ended with error in guild {guild_id}: {error}")
                else:
                    self.logger.info(f"Audio finished playing in guild {guild_id}")
                # Tell player service to play next using the bot's event loop
                try:
                    bot_loop = self.bot.loop
                    if bot_loop and not bot_loop.is_closed():
                        asyncio.run_coroutine_threadsafe(self._handle_audio_finished(guild_id), bot_loop)
                    else:
                        self.logger.warning(f"Bot event loop not available for guild {guild_id}")
                except Exception as e:
                    self.logger.error(f"Error scheduling audio finished handler: {e}")
            
            # Start streaming audio to Discord
            guild.voice_client.play(audio_source, after=after_playing)
            self.logger.info(f"Started streaming audio for guild {guild_id}")
            
            # Post Start-of-Song beacon
            await self._delete_start_of_song_message(guild_id)
            await self._post_start_of_song_message(guild_id, data)
                
        except Exception as e:
            self.logger.error(f"Error starting audio playback: {e}")
    
    async def _on_song_ended(self, guild_id: int, data: Dict[str, Any]):
        """Handle SONG_ENDED event"""
        self.logger.info(f"Song ended in guild {guild_id}: {data.get('title', 'Unknown')}")
        # Delete beacon
        await self._delete_start_of_song_message(guild_id)
    
    async def _on_queue_updated(self, guild_id: int, data: Dict[str, Any]):
        """Handle QUEUE_UPDATED event"""
        queue = data.get('queue', [])
        queue_size = len(queue)
        self.logger.info(f"Queue updated in guild {guild_id}: {queue_size} songs")
        # No persistent queue UI to update
    
    async def _on_player_idle(self, guild_id: int, data: Dict[str, Any]):
        """Handle PLAYER_IDLE event"""
        self.logger.info(f"Player idle in guild {guild_id}")
        # Delete beacon
        await self._delete_start_of_song_message(guild_id)
    
    async def _on_player_stop(self, guild_id: int, data: Dict[str, Any]):
        """Handle PLAYER_STOP event - stop voice playback immediately"""
        self.logger.info(f"Player stop requested for guild {guild_id}")
        
        # Get the guild and voice client
        guild = self.bot.get_guild(guild_id)
        if not guild or not guild.voice_client:
            self.logger.warning(f"No voice client available for guild {guild_id}")
            return
        
        try:
            # Safely stop any currently playing audio
            if guild.voice_client.is_playing():
                try:
                    guild.voice_client.stop()
                    self.logger.info(f"Stopped audio playback in guild {guild_id}")
                    # Wait a moment for the stop to take effect
                    await asyncio.sleep(0.2)
                except Exception as e:
                    self.logger.warning(f"Error stopping voice client in guild {guild_id}: {e}")
            
            # Delete beacon
            await self._delete_start_of_song_message(guild_id)
                
        except Exception as e:
            self.logger.error(f"Error stopping player for guild {guild_id}: {e}")
    
    async def _on_player_error(self, guild_id: int, data: Dict[str, Any]):
        """Handle PLAYER_ERROR event"""
        error_type = data.get('error_type', 'unknown')
        error_message = data.get('error_message', 'Unknown error')
        self.logger.error(f"Player error in guild {guild_id} ({error_type}): {error_message}")
        # Delete beacon on error
        await self._delete_start_of_song_message(guild_id)
    
    async def _on_state_update(self, guild_id: int, data: Dict[str, Any]):
        """Handle STATE_UPDATE event"""
        self.logger.debug(f"State update for guild {guild_id}")
        # TODO: Update all embeds based on full state
    
    async def _handle_audio_finished(self, guild_id: int):
        """Handle when audio finishes naturally - tell player service to play next"""
        try:
            # Add a small delay to let voice client transition to a stable state
            await asyncio.sleep(0.5)
            
            # Ensure voice client is in a stable state before sending commands
            guild = self.bot.get_guild(guild_id)
            if guild and guild.voice_client:
                # Wait for voice client to not be playing before proceeding
                max_wait = 5  # Maximum 5 seconds
                wait_time = 0
                while guild.voice_client.is_playing() and wait_time < max_wait:
                    await asyncio.sleep(0.1)
                    wait_time += 0.1
                
                self.logger.info(f"Voice client stable for guild {guild_id}, telling player service to play next")
            
            # Tell player service to play next song (without skip logic)
            await self.ipc_client.play_next(guild_id)
        except Exception as e:
            self.logger.error(f"Error handling audio finished for guild {guild_id}: {e}")