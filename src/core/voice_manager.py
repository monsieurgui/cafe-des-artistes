"""
Voice Connection Manager for handling robust Discord voice connections
Addresses random disconnections and implements automatic recovery
"""

import asyncio
import logging
import discord
from typing import Optional, Dict, Any
from discord.ext import commands

logger = logging.getLogger(__name__)


class VoiceConnectionManager:
    """
    Handles all voice connection operations with automatic recovery.
    Addresses the core issues with random disconnections and failed reconnections.
    """
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.connections: Dict[int, discord.VoiceClient] = {}
        self.reconnect_attempts: Dict[int, int] = {}
        self.max_reconnect_attempts = 3
        self.reconnect_delay_base = 2  # Base delay in seconds for exponential backoff
        
    async def ensure_connected(self, channel: discord.VoiceChannel, *, timeout: float = 60.0) -> discord.VoiceClient:
        """
        Ensures bot is connected to voice channel with retry logic and validation.
        
        Args:
            channel: The voice channel to connect to
            timeout: Connection timeout in seconds
            
        Returns:
            discord.VoiceClient: Valid and connected voice client
            
        Raises:
            discord.DiscordException: If connection fails after all retry attempts
        """
        guild_id = channel.guild.id
        
        # Check if we already have a valid connection
        existing_voice_client = self.connections.get(guild_id)
        if existing_voice_client and self._is_connection_valid(existing_voice_client, channel):
            logger.debug(f"Using existing valid connection for guild {guild_id}")
            return existing_voice_client
            
        # Clean up invalid connections
        if existing_voice_client:
            await self._cleanup_connection(guild_id)
            
        # Attempt connection with retry logic
        attempt = 0
        while attempt < self.max_reconnect_attempts:
            try:
                logger.info(f"Attempting to connect to voice channel {channel.name} (attempt {attempt + 1})")
                
                # Connect to voice channel
                voice_client = await channel.connect(timeout=timeout, reconnect=True)
                
                # Validate connection
                if not self._is_connection_valid(voice_client, channel):
                    raise discord.DiscordException("Connection validation failed")
                    
                # Store successful connection
                self.connections[guild_id] = voice_client
                self.reconnect_attempts[guild_id] = 0
                
                logger.info(f"Successfully connected to voice channel {channel.name}")
                return voice_client
                
            except Exception as e:
                attempt += 1
                logger.warning(f"Voice connection attempt {attempt} failed: {e}")
                
                if attempt < self.max_reconnect_attempts:
                    # Exponential backoff delay
                    delay = self.reconnect_delay_base ** attempt
                    logger.info(f"Retrying connection in {delay} seconds...")
                    await asyncio.sleep(delay)
                else:
                    # Final attempt failed
                    await self._cleanup_connection(guild_id)
                    raise discord.DiscordException(f"Failed to connect after {self.max_reconnect_attempts} attempts: {e}")
    
    async def handle_disconnect(self, guild_id: int, reason: str = "Unknown") -> bool:
        """
        Handles unexpected disconnections with automatic recovery.
        
        Args:
            guild_id: Guild where disconnection occurred
            reason: Reason for disconnection
            
        Returns:
            bool: True if recovery was successful, False otherwise
        """
        logger.warning(f"Handling disconnect for guild {guild_id}: {reason}")
        
        # Clean up the old connection
        await self._cleanup_connection(guild_id)
        
        # Check if we should attempt reconnection
        attempts = self.reconnect_attempts.get(guild_id, 0)
        if attempts >= self.max_reconnect_attempts:
            logger.error(f"Max reconnection attempts reached for guild {guild_id}")
            return False
            
        # Increment attempt counter
        self.reconnect_attempts[guild_id] = attempts + 1
        
        # Attempt to find the last known voice channel
        # This would typically be stored in the music player state
        # For now, we'll return False and let the music player handle reconnection
        return False
    
    def _is_connection_valid(self, voice_client: discord.VoiceClient, target_channel: discord.VoiceChannel) -> bool:
        """
        Validates if a voice connection is still valid and connected to the correct channel.
        
        Args:
            voice_client: The voice client to validate
            target_channel: The expected voice channel
            
        Returns:
            bool: True if connection is valid, False otherwise
        """
        try:
            # Check basic connection state
            if not voice_client or not voice_client.is_connected():
                return False
                
            # Check if connected to correct channel
            if voice_client.channel != target_channel:
                return False
                
            # Avoid direct websocket introspection; rely on public state
            # Additional lightweight validation could be added here if needed

            return True
            
        except Exception as e:
            logger.warning(f"Error validating voice connection: {e}")
            return False
    
    async def _cleanup_connection(self, guild_id: int) -> None:
        """
        Safely cleanup voice connection for a guild.
        
        Args:
            guild_id: Guild ID to cleanup
        """
        try:
            voice_client = self.connections.get(guild_id)
            if voice_client:
                logger.debug(f"Cleaning up voice connection for guild {guild_id}")
                
                # Disconnect if still connected
                if voice_client.is_connected():
                    await voice_client.disconnect(force=True)
                
                # Remove from our tracking
                del self.connections[guild_id]
                
        except Exception as e:
            logger.error(f"Error during voice connection cleanup for guild {guild_id}: {e}")
            # Ensure cleanup even if error occurs
            self.connections.pop(guild_id, None)
    
    async def disconnect_all(self) -> None:
        """
        Disconnect from all voice channels and cleanup.
        Useful for bot shutdown or reset.
        """
        logger.info("Disconnecting from all voice channels")
        
        for guild_id in list(self.connections.keys()):
            await self._cleanup_connection(guild_id)
            
        # Clear all tracking data
        self.connections.clear()
        self.reconnect_attempts.clear()
    
    def get_voice_client(self, guild_id: int) -> Optional[discord.VoiceClient]:
        """
        Get the voice client for a guild if it exists and is valid.
        
        Args:
            guild_id: Guild ID to get voice client for
            
        Returns:
            Optional[discord.VoiceClient]: Voice client if valid, None otherwise
        """
        voice_client = self.connections.get(guild_id)
        if voice_client and voice_client.is_connected():
            return voice_client
        return None
    
    async def validate_all_connections(self) -> None:
        """
        Validate all stored connections and cleanup invalid ones.
        Should be called periodically by a connection monitor.
        """
        invalid_guilds = []
        
        for guild_id, voice_client in self.connections.items():
            try:
                if not voice_client.is_connected():
                    invalid_guilds.append(guild_id)
            except Exception:
                invalid_guilds.append(guild_id)
        
        # Cleanup invalid connections
        for guild_id in invalid_guilds:
            logger.warning(f"Found invalid connection for guild {guild_id}, cleaning up")
            await self._cleanup_connection(guild_id)


class ConnectionMonitor:
    """
    Monitors voice connection health and triggers recovery when needed.
    """
    
    def __init__(self, voice_manager: VoiceConnectionManager):
        self.voice_manager = voice_manager
        self.monitor_task: Optional[asyncio.Task] = None
        self.monitor_interval = 30  # Check every 30 seconds
        self.is_monitoring = False
    
    def start_monitoring(self) -> None:
        """Start the connection health monitoring."""
        if not self.is_monitoring:
            self.is_monitoring = True
            self.monitor_task = asyncio.create_task(self._monitor_loop())
            logger.info("Started voice connection monitoring")
    
    def stop_monitoring(self) -> None:
        """Stop the connection health monitoring."""
        self.is_monitoring = False
        if self.monitor_task:
            self.monitor_task.cancel()
            self.monitor_task = None
            logger.info("Stopped voice connection monitoring")
    
    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        try:
            while self.is_monitoring:
                try:
                    await self.voice_manager.validate_all_connections()
                    await asyncio.sleep(self.monitor_interval)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in connection monitoring loop: {e}")
                    await asyncio.sleep(self.monitor_interval)
        except asyncio.CancelledError:
            pass
        finally:
            logger.debug("Connection monitoring loop ended")
