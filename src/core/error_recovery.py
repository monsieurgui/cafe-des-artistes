"""
Error Recovery System for Discord Music Bot
Handles playback errors with recovery strategies and fallback mechanisms
"""

import asyncio
import logging
import discord
from typing import Optional, Dict, Any, Callable
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Classification of different error types for targeted recovery strategies."""
    VOICE_CONNECTION = "voice_connection"
    AUDIO_SOURCE = "audio_source"
    NETWORK = "network"
    RATE_LIMIT = "rate_limit"
    PERMISSION = "permission"
    STREAM_UNAVAILABLE = "stream_unavailable"
    UNKNOWN = "unknown"


class RecoveryStrategy(Enum):
    """Different recovery strategies available."""
    RETRY = "retry"
    SKIP = "skip"
    RECONNECT = "reconnect"
    FALLBACK_FORMAT = "fallback_format"
    NOTIFY_ONLY = "notify_only"


class ErrorRecovery:
    """
    Handles playback errors with intelligent recovery strategies.
    Implements escalating recovery mechanisms based on error types.
    """
    
    def __init__(self, music_player):
        self.music_player = music_player
        self.error_counts: Dict[ErrorType, int] = {}
        self.max_retry_attempts = 3
        self.recovery_strategies = self._initialize_strategies()
        
    def _initialize_strategies(self) -> Dict[ErrorType, list]:
        """Initialize recovery strategies for each error type."""
        return {
            ErrorType.VOICE_CONNECTION: [
                RecoveryStrategy.RECONNECT,
                RecoveryStrategy.RETRY,
                RecoveryStrategy.SKIP
            ],
            ErrorType.AUDIO_SOURCE: [
                RecoveryStrategy.FALLBACK_FORMAT,
                RecoveryStrategy.RETRY,
                RecoveryStrategy.SKIP
            ],
            ErrorType.NETWORK: [
                RecoveryStrategy.RETRY,
                RecoveryStrategy.SKIP
            ],
            ErrorType.RATE_LIMIT: [
                RecoveryStrategy.RETRY,
                RecoveryStrategy.SKIP
            ],
            ErrorType.PERMISSION: [
                RecoveryStrategy.NOTIFY_ONLY,
                RecoveryStrategy.SKIP
            ],
            ErrorType.STREAM_UNAVAILABLE: [
                RecoveryStrategy.FALLBACK_FORMAT,
                RecoveryStrategy.SKIP
            ],
            ErrorType.UNKNOWN: [
                RecoveryStrategy.RETRY,
                RecoveryStrategy.SKIP
            ]
        }
    
    async def handle_playback_error(self, error: Exception, context: Dict[str, Any] = None) -> bool:
        """
        Handles playback errors with recovery strategies.
        
        Args:
            error: The exception that occurred
            context: Additional context about the error
            
        Returns:
            bool: True if recovery was successful, False if should skip
        """
        error_type = self._classify_error(error)
        
        logger.warning(f"Handling {error_type.value} error: {error}")
        
        # Increment error count for this type
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
        
        # Get appropriate recovery strategies
        strategies = self.recovery_strategies.get(error_type, [RecoveryStrategy.SKIP])
        
        # Try each strategy in order
        for strategy in strategies:
            try:
                recovery_successful = await self._execute_recovery_strategy(
                    strategy, error, error_type, context
                )
                
                if recovery_successful:
                    logger.info(f"Recovery successful using strategy: {strategy.value}")
                    # Reset error count on successful recovery
                    self.error_counts[error_type] = 0
                    return True
                    
            except Exception as recovery_error:
                logger.error(f"Recovery strategy {strategy.value} failed: {recovery_error}")
                continue
        
        # All recovery strategies failed
        logger.error(f"All recovery strategies failed for {error_type.value} error")
        await self._notify_error(error, error_type)
        return False
    
    def _classify_error(self, error: Exception) -> ErrorType:
        """
        Classify the error to determine appropriate recovery strategy.
        
        Args:
            error: The exception to classify
            
        Returns:
            ErrorType: The classified error type
        """
        error_str = str(error).lower()
        error_type_name = type(error).__name__.lower()
        
        # Voice connection errors
        if any(keyword in error_str for keyword in ['voice', 'connection', 'websocket', '4006']):
            return ErrorType.VOICE_CONNECTION
        if any(keyword in error_type_name for keyword in ['voice', 'connection']):
            return ErrorType.VOICE_CONNECTION
            
        # Audio source errors
        if any(keyword in error_str for keyword in ['ffmpeg', 'audio', 'stream', 'format']):
            return ErrorType.AUDIO_SOURCE
        if 'unavailable' in error_str:
            return ErrorType.STREAM_UNAVAILABLE
            
        # Network errors
        if any(keyword in error_str for keyword in ['network', 'timeout', 'dns', 'connection']):
            return ErrorType.NETWORK
        if any(keyword in error_type_name for keyword in ['timeout', 'connection']):
            return ErrorType.NETWORK
            
        # Rate limiting
        if any(keyword in error_str for keyword in ['rate', 'limit', '429', 'too many']):
            return ErrorType.RATE_LIMIT
            
        # Permission errors
        if any(keyword in error_str for keyword in ['permission', 'forbidden', '403', 'unauthorized']):
            return ErrorType.PERMISSION
            
        return ErrorType.UNKNOWN
    
    async def _execute_recovery_strategy(
        self, 
        strategy: RecoveryStrategy, 
        error: Exception, 
        error_type: ErrorType,
        context: Dict[str, Any] = None
    ) -> bool:
        """
        Execute a specific recovery strategy.
        
        Args:
            strategy: The recovery strategy to execute
            error: The original error
            error_type: The classified error type
            context: Additional context
            
        Returns:
            bool: True if recovery was successful
        """
        context = context or {}
        
        if strategy == RecoveryStrategy.RETRY:
            return await self._retry_operation(error_type)
            
        elif strategy == RecoveryStrategy.RECONNECT:
            return await self._reconnect_voice()
            
        elif strategy == RecoveryStrategy.FALLBACK_FORMAT:
            return await self._try_fallback_format(context)
            
        elif strategy == RecoveryStrategy.SKIP:
            await self._skip_current_song()
            return True  # Skipping is always "successful"
            
        elif strategy == RecoveryStrategy.NOTIFY_ONLY:
            await self._notify_error(error, error_type)
            return False
            
        return False
    
    async def _retry_operation(self, error_type: ErrorType) -> bool:
        """
        Retry the current operation with exponential backoff.
        
        Args:
            error_type: The type of error being retried
            
        Returns:
            bool: True if retry should be attempted
        """
        retry_count = self.error_counts.get(error_type, 0)
        
        if retry_count >= self.max_retry_attempts:
            logger.warning(f"Max retry attempts reached for {error_type.value}")
            return False
            
        # Exponential backoff
        delay = 2 ** retry_count
        logger.info(f"Retrying in {delay} seconds (attempt {retry_count + 1})")
        await asyncio.sleep(delay)
        
        # Retry the current song
        try:
            await self.music_player.play_next()
            return True
        except Exception as e:
            logger.error(f"Retry failed: {e}")
            return False
    
    async def _reconnect_voice(self) -> bool:
        """
        Attempt to reconnect to voice channel.
        
        Returns:
            bool: True if reconnection was successful
        """
        try:
            logger.info("Attempting voice reconnection")
            
            # Use the voice manager to handle reconnection
            if hasattr(self.music_player.bot, 'voice_manager'):
                guild_id = self.music_player.ctx.guild.id
                await self.music_player.bot.voice_manager._cleanup_connection(guild_id)
                
            # Re-establish voice connection
            await self.music_player.ensure_voice_client()
            
            logger.info("Voice reconnection successful")
            return True
            
        except Exception as e:
            logger.error(f"Voice reconnection failed: {e}")
            return False
    
    async def _try_fallback_format(self, context: Dict[str, Any]) -> bool:
        """
        Try alternative audio formats for the current song.
        
        Args:
            context: Context containing song information
            
        Returns:
            bool: True if fallback format worked
        """
        try:
            logger.info("Attempting fallback audio format")
            
            # This would involve re-extracting the audio with different options
            # For now, we'll just try to replay with different yt-dlp options
            if hasattr(self.music_player, 'current') and self.music_player.current:
                # Try with lower quality format
                fallback_options = {
                    'format': 'worst/bestaudio/best',
                    'quiet': True,
                    'no_warnings': True
                }
                
                # Re-extract with fallback options
                # This is a simplified implementation - in practice you'd want
                # to modify the extraction process in music_player
                await self.music_player.play_next()
                return True
                
        except Exception as e:
            logger.error(f"Fallback format failed: {e}")
            return False
    
    async def _skip_current_song(self) -> None:
        """Skip the current song and move to the next one."""
        try:
            logger.info("Skipping current song due to error")
            await self.music_player.skip()
        except Exception as e:
            logger.error(f"Error skipping song: {e}")
    
    async def _notify_error(self, error: Exception, error_type: ErrorType) -> None:
        """
        Notify users about the error.
        
        Args:
            error: The original error
            error_type: The classified error type
        """
        try:
            embed = discord.Embed(
                title="⚠️ Playback Error",
                description=f"An error occurred: {error_type.value.replace('_', ' ').title()}",
                color=0xff6b6b
            )
            
            if error_type == ErrorType.PERMISSION:
                embed.add_field(
                    name="Solution",
                    value="Please check bot permissions for voice channels",
                    inline=False
                )
            elif error_type == ErrorType.STREAM_UNAVAILABLE:
                embed.add_field(
                    name="Solution", 
                    value="This video may be unavailable or restricted",
                    inline=False
                )
            
            await self.music_player.ctx.send(embed=embed, delete_after=30)
            
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
    
    def reset_error_counts(self) -> None:
        """Reset all error counts. Useful after successful operations."""
        self.error_counts.clear()
        logger.debug("Error counts reset")
    
    def get_error_stats(self) -> Dict[str, int]:
        """
        Get error statistics for monitoring.
        
        Returns:
            Dict: Error counts by type
        """
        return {error_type.value: count for error_type, count in self.error_counts.items()}


class AudioSourceWrapper:
    """
    Wrapper for FFmpegPCMAudio with built-in error recovery and fallback options.
    """
    
    def __init__(self, url: str, ffmpeg_options: dict, executable: str = 'ffmpeg'):
        self.url = url
        self.ffmpeg_options = ffmpeg_options
        self.executable = executable
        self.fallback_formats = [
            {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'},
            {'before_options': '-reconnect 1'},
            {'before_options': ''}  # Minimal options as last resort
        ]
    
    def create_source(self, attempt: int = 0):
        """
        Create audio source with progressive fallback options.
        
        Args:
            attempt: Current attempt number (affects which options to use)
            
        Returns:
            discord.FFmpegPCMAudio: Audio source
        """
        try:
            # Use increasingly simplified options for each attempt
            if attempt < len(self.fallback_formats):
                options = {**self.ffmpeg_options, **self.fallback_formats[attempt]}
            else:
                # Last resort - minimal options
                options = {'options': '-vn'}
            
            return discord.FFmpegPCMAudio(
                self.url,
                **options,
                executable=self.executable
            )
            
        except Exception as e:
            logger.error(f"Failed to create audio source (attempt {attempt}): {e}")
            raise
