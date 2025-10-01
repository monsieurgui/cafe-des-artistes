"""
Voice Connection Manager for handling robust Discord voice connections
Addresses random disconnections and implements automatic recovery
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


@dataclass
class GuildVoiceState:
    channel_id: Optional[int] = None
    text_channel_id: Optional[int] = None
    voice_client: Optional[discord.VoiceClient] = None
    reconnect_attempts: int = 0
    cooldown_until: float = 0.0
    last_success_at: float = 0.0
    last_failure_at: float = 0.0
    last_close_code: Optional[int] = None
    last_disconnect_reason: Optional[str] = None
    recovery_state: str = "IDLE"
    allow_auto_rejoin: bool = True
    lock: Optional[asyncio.Lock] = None
    recovery_task: Optional[asyncio.Task] = None
    unknown_close_count: int = 0


class VoiceConnectionManager:
    """
    Handles all voice connection operations with automatic recovery.
    Addresses the core issues with random disconnections and failed reconnections.
    """
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.voice_states: Dict[int, GuildVoiceState] = {}
        self.max_reconnect_attempts = 5
        self.reconnect_delay_base = 2  # Base delay in seconds for exponential backoff
        self.max_reconnect_delay = 300  # clamp at 5 minutes
        
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
        state = self.voice_states.setdefault(guild_id, GuildVoiceState(lock=asyncio.Lock()))

        # Respect cooldown before attempting new connection
        now = time.monotonic()
        if state.cooldown_until and now < state.cooldown_until:
            delay = state.cooldown_until - now
            logger.info(
                "Voice connection waiting for cooldown",
                extra={
                    "guild_id": guild_id,
                    "channel_id": channel.id,
                    "delay": round(delay, 2),
                },
            )
            await asyncio.sleep(delay)

        existing_voice_client = state.voice_client
        if existing_voice_client and self._is_connection_valid(existing_voice_client, channel):
            logger.debug(
                "Voice connection reused",
                extra={
                    "guild_id": guild_id,
                    "channel_id": channel.id,
                    "close_code": state.last_close_code,
                    "recovery_state": state.recovery_state,
                },
            )
            state.channel_id = channel.id
            state.recovery_state = "STABLE"
            return existing_voice_client
            
        # Clean up invalid connections
        if existing_voice_client:
            await self._cleanup_connection(guild_id)
            
        # Also check for any lingering guild-level voice clients
        guild = channel.guild
        if guild.voice_client:
            logger.warning(f"Found lingering guild voice client for guild {guild_id}, cleaning up")
            try:
                await guild.voice_client.disconnect(force=True)
            except Exception as e:
                logger.error(f"Error disconnecting lingering voice client: {e}")
            # Give Discord a moment to process the disconnection
            await asyncio.sleep(0.5)
            
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
                state.voice_client = voice_client
                state.reconnect_attempts = 0
                state.last_success_at = time.monotonic()
                state.cooldown_until = 0
                state.channel_id = channel.id
                state.recovery_state = "STABLE"
                state.last_close_code = None
                state.last_disconnect_reason = None
                
                logger.info(f"Successfully connected to voice channel {channel.name}")
                return voice_client
                
            except Exception as e:
                attempt += 1
                state.reconnect_attempts = attempt
                state.last_failure_at = time.monotonic()
                state.recovery_state = "RETRYING"
                
                # Special handling for "already connected" error
                error_str = str(e).lower()
                if "already connected" in error_str:
                    logger.warning(f"Already connected error detected, forcing cleanup for guild {guild_id}")
                    # Force disconnect any lingering connections
                    try:
                        if guild.voice_client:
                            await guild.voice_client.disconnect(force=True)
                            await asyncio.sleep(1.0)  # Give more time for cleanup
                    except Exception as cleanup_error:
                        logger.error(f"Error during forced cleanup: {cleanup_error}")
                
                logger.warning(
                    "Voice connection attempt failed",
                    extra={
                        "guild_id": guild_id,
                        "channel_id": channel.id,
                        "attempt": attempt,
                        "max_attempts": self.max_reconnect_attempts,
                        "error": str(e),
                    },
                )
                
                if attempt < self.max_reconnect_attempts:
                    # Exponential backoff delay
                    base_delay = min(self.reconnect_delay_base ** attempt, self.max_reconnect_delay)
                    jitter = random.uniform(0.7, 1.3)
                    delay = base_delay * jitter
                    state.cooldown_until = time.monotonic() + delay
                    logger.info(
                        "Retrying voice connection",
                        extra={
                            "guild_id": guild_id,
                            "channel_id": channel.id,
                            "delay": round(delay, 2),
                            "attempt": attempt,
                        },
                    )
                    await asyncio.sleep(delay)
                else:
                    # Final attempt failed
                    await self._cleanup_connection(guild_id)
                    raise discord.DiscordException(f"Failed to connect after {self.max_reconnect_attempts} attempts: {e}")
    
    async def handle_disconnect(self, guild_id: int, reason: str = "Unknown", *, close_code: Optional[int] = None) -> bool:
        """
        Handles unexpected disconnections with automatic recovery.
        
        Args:
            guild_id: Guild where disconnection occurred
            reason: Reason for disconnection
            
        Returns:
            bool: True if recovery was successful, False otherwise
        """
        logger.warning(
            "Voice disconnect detected",
            extra={
                "guild_id": guild_id,
                "reason": reason,
                "close_code": close_code,
            },
        )
        
        state = self.voice_states.setdefault(guild_id, GuildVoiceState(lock=asyncio.Lock()))
        state.last_disconnect_reason = reason
        state.last_close_code = close_code
        if close_code == 4006:
            state.unknown_close_count = 0
        elif close_code in (4014, 1000):
            state.unknown_close_count = 0
        else:
            state.unknown_close_count += 1
        state.recovery_state = "RETRYING"
        state.last_failure_at = time.monotonic()
        
        await self._cleanup_connection(guild_id)

        if not state.allow_auto_rejoin:
            logger.info(
                "Auto-rejoin suppressed for guild",
                extra={"guild_id": guild_id, "cooldown_until": state.cooldown_until},
            )
            return False

        state.reconnect_attempts += 1

        # escalate cooldown for unknown close codes
        if close_code and close_code not in (4006, 4014, 1000) and state.unknown_close_count >= 3:
            state.allow_auto_rejoin = False
            state.recovery_state = "MANUAL_REQUIRED"
            logger.error(
                "Repeated unknown voice close codes; disabling auto rejoin",
                extra={
                    "guild_id": guild_id,
                    "close_code": close_code,
                    "unknown_count": state.unknown_close_count,
                },
            )
            return False

        if state.reconnect_attempts >= self.max_reconnect_attempts:
            state.cooldown_until = time.monotonic() + self._long_cooldown(state.reconnect_attempts)
            state.recovery_state = "COOLDOWN"
            logger.error(
                "Max reconnection attempts reached",
                extra={
                    "guild_id": guild_id,
                    "close_code": close_code,
                    "reason": reason,
                    "cooldown_until": state.cooldown_until,
                },
            )
            return False

        if state.channel_id is None:
            logger.warning(
                "No channel stored for reconnect; manual intervention required",
                extra={"guild_id": guild_id},
            )
            return False

        delay = self._calculate_backoff(state.reconnect_attempts)
        state.cooldown_until = time.monotonic() + delay

        if not state.lock:
            state.lock = asyncio.Lock()

        if state.recovery_task and not state.recovery_task.done():
            state.recovery_task.cancel()

        async def delayed_reconnect():
            async with state.lock:
                await asyncio.sleep(delay)
                if time.monotonic() < state.cooldown_until - 0.01:
                    return
                channel = self._resolve_channel(guild_id, state.channel_id)
                if channel:
                    try:
                        await self.ensure_connected(channel)
                    except Exception as exc:
                        logger.error(
                            "Auto-reconnect attempt failed",
                            extra={
                                "guild_id": guild_id,
                                "channel_id": state.channel_id,
                                "error": str(exc),
                            },
                        )

        state.recovery_task = asyncio.create_task(delayed_reconnect())
        return True
    
    def _calculate_backoff(self, attempts: int) -> float:
        base_delay = min(self.reconnect_delay_base ** attempts, self.max_reconnect_delay)
        jitter = random.uniform(0.7, 1.3)
        return base_delay * jitter

    def _long_cooldown(self, attempts: int) -> float:
        # escalate cooldown after exhausting retries
        return min(self.max_reconnect_delay, 30 * (attempts ** 2))

    def _resolve_channel(self, guild_id: int, channel_id: Optional[int]) -> Optional[discord.VoiceChannel]:
        if channel_id is None:
            return None
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return None
        channel = guild.get_channel(channel_id)
        return channel if isinstance(channel, discord.VoiceChannel) else None

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
        state = self.voice_states.get(guild_id)
        voice_client = state.voice_client if state else None
        try:
            if voice_client:
                logger.debug(f"Cleaning up voice connection for guild {guild_id}")
                
                # Disconnect if still connected
                if voice_client.is_connected():
                    await voice_client.disconnect(force=True)
                
                # Remove from our tracking
                if state:
                    state.voice_client = None
                
        except Exception as e:
            logger.error(f"Error during voice connection cleanup for guild {guild_id}: {e}")
        finally:
            if state:
                state.voice_client = None
    
    async def disconnect_all(self) -> None:
        """
        Disconnect from all voice channels and cleanup.
        Useful for bot shutdown or reset.
        """
        logger.info("Disconnecting from all voice channels")

        for guild_id in list(self.voice_states.keys()):
            await self._cleanup_connection(guild_id)

        # Clear state data
        for state in self.voice_states.values():
            state.voice_client = None
            state.reconnect_attempts = 0
            state.recovery_state = "IDLE"
    
    def get_voice_client(self, guild_id: int) -> Optional[discord.VoiceClient]:
        """
        Get the voice client for a guild if it exists and is valid.
        
        Args:
            guild_id: Guild ID to get voice client for
            
        Returns:
            Optional[discord.VoiceClient]: Voice client if valid, None otherwise
        """
        state = self.voice_states.get(guild_id)
        if state and state.voice_client and state.voice_client.is_connected():
            return state.voice_client
        return None
    
    async def validate_all_connections(self) -> None:
        """
        Validate all stored connections and cleanup invalid ones.
        Should be called periodically by a connection monitor.
        """
        invalid_guilds = []
        
        for guild_id, state in self.voice_states.items():
            voice_client = state.voice_client
            if not voice_client:
                continue
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
