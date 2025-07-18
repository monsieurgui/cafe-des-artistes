"""
Database Utility Module for Cafe des Artistes Bot
=================================================

This module provides async database operations for persisting guild-specific settings
using SQLite. It manages the guild_settings table that stores configuration for
the persistent control panel feature.

Schema:
- guild_settings table:
  - guild_id (INTEGER, PRIMARY KEY): Discord guild ID
  - control_channel_id (INTEGER, NOT NULL): Channel ID for control panel
  - queue_message_id (INTEGER, NOT NULL): Message ID for queue embed
  - now_playing_message_id (INTEGER, NOT NULL): Message ID for now playing embed
"""

import aiosqlite
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path
from dataclasses import dataclass


@dataclass
class GuildSettings:
    """Data class for guild settings"""
    guild_id: int
    control_channel_id: int
    queue_message_id: int
    now_playing_message_id: int


class DatabaseManager:
    """
    Async database manager for guild settings
    
    This class handles all database operations for the guild_settings table,
    including initialization, CRUD operations, and connection management.
    """
    
    def __init__(self, db_path: str = "data/guild_settings.db", logger: Optional[logging.Logger] = None):
        """
        Initialize the database manager
        
        Args:
            db_path: Path to the SQLite database file
            logger: Logger instance for debugging
        """
        self.db_path = Path(db_path)
        self.logger = logger or logging.getLogger(__name__)
        self._lock = asyncio.Lock()
        
        # Create data directory if it doesn't exist
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    async def initialize(self):
        """
        Initialize the database and create tables if they don't exist
        """
        async with self._lock:
            try:
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute('''
                        CREATE TABLE IF NOT EXISTS guild_settings (
                            guild_id INTEGER PRIMARY KEY,
                            control_channel_id INTEGER NOT NULL,
                            queue_message_id INTEGER NOT NULL,
                            now_playing_message_id INTEGER NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    ''')
                    
                    # Create setup_sessions table for persistent setup sessions
                    await db.execute('''
                        CREATE TABLE IF NOT EXISTS setup_sessions (
                            user_id INTEGER PRIMARY KEY,
                            guild_id INTEGER NOT NULL,
                            guild_name TEXT NOT NULL,
                            started_at TIMESTAMP NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    ''')
                    
                    # Create index for faster lookups
                    await db.execute('''
                        CREATE INDEX IF NOT EXISTS idx_guild_settings_guild_id 
                        ON guild_settings(guild_id)
                    ''')
                    
                    await db.execute('''
                        CREATE INDEX IF NOT EXISTS idx_setup_sessions_user_id
                        ON setup_sessions(user_id)
                    ''')
                    
                    await db.commit()
                    
                self.logger.info("Database initialized successfully")
                
            except Exception as e:
                self.logger.error(f"Failed to initialize database: {e}")
                raise
    
    async def set_guild_setup(self, guild_id: int, control_channel_id: int, 
                             queue_message_id: int, now_playing_message_id: int) -> bool:
        """
        Create or update guild settings
        
        Args:
            guild_id: Discord guild ID
            control_channel_id: Channel ID for control panel
            queue_message_id: Message ID for queue embed  
            now_playing_message_id: Message ID for now playing embed
            
        Returns:
            True if successful, False otherwise
        """
        async with self._lock:
            try:
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute('''
                        INSERT OR REPLACE INTO guild_settings 
                        (guild_id, control_channel_id, queue_message_id, now_playing_message_id, updated_at)
                        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ''', (guild_id, control_channel_id, queue_message_id, now_playing_message_id))
                    
                    await db.commit()
                    
                self.logger.info(f"Guild settings saved for guild {guild_id}")
                return True
                
            except Exception as e:
                self.logger.error(f"Failed to save guild settings for {guild_id}: {e}")
                return False
    
    async def get_guild_setup(self, guild_id: int) -> Optional[GuildSettings]:
        """
        Get guild settings by guild ID
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            GuildSettings object if found, None otherwise
        """
        async with self._lock:
            try:
                async with aiosqlite.connect(self.db_path) as db:
                    db.row_factory = aiosqlite.Row
                    
                    async with db.execute('''
                        SELECT guild_id, control_channel_id, queue_message_id, now_playing_message_id
                        FROM guild_settings 
                        WHERE guild_id = ?
                    ''', (guild_id,)) as cursor:
                        
                        row = await cursor.fetchone()
                        
                        if row:
                            return GuildSettings(
                                guild_id=row['guild_id'],
                                control_channel_id=row['control_channel_id'],
                                queue_message_id=row['queue_message_id'],
                                now_playing_message_id=row['now_playing_message_id']
                            )
                        else:
                            return None
                            
            except Exception as e:
                self.logger.error(f"Failed to get guild settings for {guild_id}: {e}")
                return None
    
    async def get_all_guild_settings(self) -> List[GuildSettings]:
        """
        Get all guild settings from the database
        
        Returns:
            List of GuildSettings objects
        """
        async with self._lock:
            try:
                async with aiosqlite.connect(self.db_path) as db:
                    db.row_factory = aiosqlite.Row
                    
                    async with db.execute('''
                        SELECT guild_id, control_channel_id, queue_message_id, now_playing_message_id
                        FROM guild_settings 
                        ORDER BY guild_id
                    ''') as cursor:
                        
                        rows = await cursor.fetchall()
                        
                        return [
                            GuildSettings(
                                guild_id=row['guild_id'],
                                control_channel_id=row['control_channel_id'],
                                queue_message_id=row['queue_message_id'],
                                now_playing_message_id=row['now_playing_message_id']
                            )
                            for row in rows
                        ]
                            
            except Exception as e:
                self.logger.error(f"Failed to get all guild settings: {e}")
                return []
    
    async def delete_guild_setup(self, guild_id: int) -> bool:
        """
        Delete guild settings
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            True if successful, False otherwise
        """
        async with self._lock:
            try:
                async with aiosqlite.connect(self.db_path) as db:
                    cursor = await db.execute('''
                        DELETE FROM guild_settings WHERE guild_id = ?
                    ''', (guild_id,))
                    
                    await db.commit()
                    
                    if cursor.rowcount > 0:
                        self.logger.info(f"Guild settings deleted for guild {guild_id}")
                        return True
                    else:
                        self.logger.warning(f"No guild settings found to delete for guild {guild_id}")
                        return False
                        
            except Exception as e:
                self.logger.error(f"Failed to delete guild settings for {guild_id}: {e}")
                return False
    
    async def update_control_channel(self, guild_id: int, control_channel_id: int) -> bool:
        """
        Update only the control channel ID for a guild
        
        Args:
            guild_id: Discord guild ID
            control_channel_id: New control channel ID
            
        Returns:
            True if successful, False otherwise
        """
        async with self._lock:
            try:
                async with aiosqlite.connect(self.db_path) as db:
                    cursor = await db.execute('''
                        UPDATE guild_settings 
                        SET control_channel_id = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE guild_id = ?
                    ''', (control_channel_id, guild_id))
                    
                    await db.commit()
                    
                    if cursor.rowcount > 0:
                        self.logger.info(f"Control channel updated for guild {guild_id}")
                        return True
                    else:
                        self.logger.warning(f"No guild settings found to update for guild {guild_id}")
                        return False
                        
            except Exception as e:
                self.logger.error(f"Failed to update control channel for {guild_id}: {e}")
                return False
    
    async def update_message_ids(self, guild_id: int, queue_message_id: Optional[int] = None, 
                                now_playing_message_id: Optional[int] = None) -> bool:
        """
        Update message IDs for a guild
        
        Args:
            guild_id: Discord guild ID
            queue_message_id: New queue message ID (optional)
            now_playing_message_id: New now playing message ID (optional)
            
        Returns:
            True if successful, False otherwise
        """
        if queue_message_id is None and now_playing_message_id is None:
            return False
            
        async with self._lock:
            try:
                async with aiosqlite.connect(self.db_path) as db:
                    updates = []
                    params = []
                    
                    if queue_message_id is not None:
                        updates.append("queue_message_id = ?")
                        params.append(queue_message_id)
                    
                    if now_playing_message_id is not None:
                        updates.append("now_playing_message_id = ?")
                        params.append(now_playing_message_id)
                    
                    updates.append("updated_at = CURRENT_TIMESTAMP")
                    params.append(guild_id)
                    
                    cursor = await db.execute(f'''
                        UPDATE guild_settings 
                        SET {", ".join(updates)}
                        WHERE guild_id = ?
                    ''', params)
                    
                    await db.commit()
                    
                    if cursor.rowcount > 0:
                        self.logger.info(f"Message IDs updated for guild {guild_id}")
                        return True
                    else:
                        self.logger.warning(f"No guild settings found to update for guild {guild_id}")
                        return False
                        
            except Exception as e:
                self.logger.error(f"Failed to update message IDs for {guild_id}: {e}")
                return False
    
    async def get_all_guild_settings(self) -> Dict[int, GuildSettings]:
        """
        Get all guild settings
        
        Returns:
            Dictionary mapping guild_id to GuildSettings
        """
        async with self._lock:
            try:
                async with aiosqlite.connect(self.db_path) as db:
                    db.row_factory = aiosqlite.Row
                    
                    async with db.execute('''
                        SELECT guild_id, control_channel_id, queue_message_id, now_playing_message_id
                        FROM guild_settings
                    ''') as cursor:
                        
                        rows = await cursor.fetchall()
                        
                        return {
                            row['guild_id']: GuildSettings(
                                guild_id=row['guild_id'],
                                control_channel_id=row['control_channel_id'],
                                queue_message_id=row['queue_message_id'],
                                now_playing_message_id=row['now_playing_message_id']
                            )
                            for row in rows
                        }
                        
            except Exception as e:
                self.logger.error(f"Failed to get all guild settings: {e}")
                return {}
    
    async def guild_exists(self, guild_id: int) -> bool:
        """
        Check if guild settings exist
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            True if settings exist, False otherwise
        """
        async with self._lock:
            try:
                async with aiosqlite.connect(self.db_path) as db:
                    async with db.execute('''
                        SELECT 1 FROM guild_settings WHERE guild_id = ? LIMIT 1
                    ''', (guild_id,)) as cursor:
                        
                        row = await cursor.fetchone()
                        return row is not None
                        
            except Exception as e:
                self.logger.error(f"Failed to check if guild exists {guild_id}: {e}")
                return False
    
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics
        
        Returns:
            Dictionary with database statistics
        """
        async with self._lock:
            try:
                async with aiosqlite.connect(self.db_path) as db:
                    # Get total guild count
                    async with db.execute('SELECT COUNT(*) as count FROM guild_settings') as cursor:
                        total_guilds = (await cursor.fetchone())[0]
                    
                    # Get database file size
                    db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
                    
                    return {
                        'total_guilds': total_guilds,
                        'database_size_bytes': db_size,
                        'database_path': str(self.db_path)
                    }
                    
            except Exception as e:
                self.logger.error(f"Failed to get database statistics: {e}")
                return {}
    
    # Setup Session Management Methods
    
    async def create_setup_session(self, user_id: int, guild_id: int, guild_name: str, started_at: str) -> bool:
        """
        Create a new setup session
        
        Args:
            user_id: Discord user ID starting the setup
            guild_id: Discord guild ID being set up  
            guild_name: Guild name for user reference
            started_at: ISO timestamp when session started
            
        Returns:
            bool: True if successful, False otherwise
        """
        async with self._lock:
            try:
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute('''
                        INSERT OR REPLACE INTO setup_sessions 
                        (user_id, guild_id, guild_name, started_at)
                        VALUES (?, ?, ?, ?)
                    ''', (user_id, guild_id, guild_name, started_at))
                    
                    await db.commit()
                    self.logger.debug(f"Created setup session for user {user_id} in guild {guild_id}")
                    return True
                    
            except Exception as e:
                self.logger.error(f"Failed to create setup session: {e}")
                return False
    
    async def get_setup_session(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get setup session for a user
        
        Args:
            user_id: Discord user ID
            
        Returns:
            dict: Session data or None if not found
        """
        async with self._lock:
            try:
                async with aiosqlite.connect(self.db_path) as db:
                    async with db.execute('''
                        SELECT user_id, guild_id, guild_name, started_at
                        FROM setup_sessions 
                        WHERE user_id = ?
                    ''', (user_id,)) as cursor:
                        row = await cursor.fetchone()
                        
                        if row:
                            return {
                                'user_id': row[0],
                                'guild_id': row[1], 
                                'guild_name': row[2],
                                'started_at': row[3]
                            }
                        return None
                        
            except Exception as e:
                self.logger.error(f"Failed to get setup session: {e}")
                return None
    
    async def delete_setup_session(self, user_id: int) -> bool:
        """
        Delete a setup session
        
        Args:
            user_id: Discord user ID
            
        Returns:
            bool: True if successful, False otherwise
        """
        async with self._lock:
            try:
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute('''
                        DELETE FROM setup_sessions WHERE user_id = ?
                    ''', (user_id,))
                    
                    await db.commit()
                    self.logger.debug(f"Deleted setup session for user {user_id}")
                    return True
                    
            except Exception as e:
                self.logger.error(f"Failed to delete setup session: {e}")
                return False
                
    async def cleanup_expired_setup_sessions(self, expiry_minutes: int = 5) -> int:
        """
        Clean up expired setup sessions
        
        Args:
            expiry_minutes: Sessions older than this many minutes will be deleted
            
        Returns:
            int: Number of sessions cleaned up
        """
        async with self._lock:
            try:
                async with aiosqlite.connect(self.db_path) as db:
                    # Calculate cutoff time (expiry_minutes ago)
                    # Use timezone-aware datetime to match stored timestamps
                    import discord.utils
                    cutoff_time = (
                        discord.utils.utcnow() - timedelta(minutes=expiry_minutes)
                    ).isoformat()
                    
                    # Count sessions to be deleted
                    async with db.execute('''
                        SELECT COUNT(*) FROM setup_sessions 
                        WHERE started_at < ?
                    ''', (cutoff_time,)) as cursor:
                        count_row = await cursor.fetchone()
                        count = count_row[0] if count_row else 0
                    
                    # Delete expired sessions
                    await db.execute('''
                        DELETE FROM setup_sessions WHERE started_at < ?
                    ''', (cutoff_time,))
                    
                    await db.commit()
                    
                    if count > 0:
                        self.logger.info(f"Cleaned up {count} expired setup sessions")
                    
                    return count
                    
            except Exception as e:
                self.logger.error(f"Failed to cleanup expired setup sessions: {e}")
                return 0
    
    async def close(self):
        """
        Close database connections (cleanup method)
        """
        # aiosqlite automatically handles connection cleanup
        # This method is here for consistency and future extensions
        self.logger.info("Database manager closed")


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


async def get_database_manager(db_path: str = "data/guild_settings.db", 
                              logger: Optional[logging.Logger] = None) -> DatabaseManager:
    """
    Get or create the global database manager instance
    
    Args:
        db_path: Path to the SQLite database file
        logger: Logger instance
        
    Returns:
        DatabaseManager instance
    """
    global _db_manager
    
    if _db_manager is None:
        _db_manager = DatabaseManager(db_path, logger)
        await _db_manager.initialize()
    
    return _db_manager


# Convenience functions for common operations

async def set_guild_setup(guild_id: int, control_channel_id: int, 
                         queue_message_id: int, now_playing_message_id: int,
                         db_manager: Optional[DatabaseManager] = None) -> bool:
    """Convenience function to set guild setup"""
    if db_manager is None:
        db_manager = await get_database_manager()
    
    return await db_manager.set_guild_setup(
        guild_id, control_channel_id, queue_message_id, now_playing_message_id
    )


async def get_guild_setup(guild_id: int, 
                         db_manager: Optional[DatabaseManager] = None) -> Optional[GuildSettings]:
    """Convenience function to get guild setup"""
    if db_manager is None:
        db_manager = await get_database_manager()
    
    return await db_manager.get_guild_setup(guild_id)


async def delete_guild_setup(guild_id: int, 
                            db_manager: Optional[DatabaseManager] = None) -> bool:
    """Convenience function to delete guild setup"""
    if db_manager is None:
        db_manager = await get_database_manager()
    
    return await db_manager.delete_guild_setup(guild_id)


async def guild_exists(guild_id: int, 
                      db_manager: Optional[DatabaseManager] = None) -> bool:
    """Convenience function to check if guild exists"""
    if db_manager is None:
        db_manager = await get_database_manager()
    
    return await db_manager.guild_exists(guild_id)