import sys
import traceback
import discord
from discord.ext import commands
from utils.config import load_config
from utils.constants import MESSAGES, COLORS
from utils.ipc_client import IPCManager
import logging
import asyncio

class MusicBot(commands.Bot):
    """
    Bot Discord spécialisé dans la lecture de musique.
    
    Cette classe étend discord.ext.commands.Bot avec des fonctionnalités
    spécifiques pour la gestion de la musique via IPC avec le Player Service.
    
    Attributes:
        config (dict): Configuration du bot chargée depuis config.yaml
        ipc_manager (IPCManager): Gestionnaire IPC pour communiquer avec le Player Service
    """

    def __init__(self):
        """
        Initialize the bot with necessary configurations.
        
        Configures:
        - Required Discord intents
        - Command prefix
        - IPC Manager for Player Service communication
        """
        self.config = load_config()
        
        # Configure Discord intents
        intents = discord.Intents.default()
        intents.message_content = True  # MESSAGE CONTENT INTENT
        intents.members = True          # SERVER MEMBERS INTENT  
        intents.voice_states = True
        
        # Initialize the bot with configuration
        super().__init__(
            command_prefix=self.config['command_prefix'],
            intents=intents,
            help_command=None
        )
        
        # Configure logging - use a safer way to get log level
        try:
            log_level = self.config.get('log_level', 'INFO').upper()
            level = getattr(logging, log_level, logging.INFO)
        except (AttributeError, KeyError):
            level = logging.INFO
            
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Initialize IPC Manager for Player Service communication
        self.ipc_manager = IPCManager(self, logging.getLogger(__name__))

    def get_effective_owner(self, guild: discord.Guild = None) -> discord.User:
        """
        Get the effective owner for bot operations.
        
        Args:
            guild: The guild to get the owner for. If None, uses the configured owner.
            
        Returns:
            discord.User: The effective owner (configured owner or guild owner)
        """
        # If OWNER_ID is configured in environment, use that
        if self.config.get('owner_id'):
            return self.get_user(self.config['owner_id'])
        
        # Otherwise, use the guild owner if guild is provided
        if guild and guild.owner:
            return guild.owner
            
        # Fallback: no effective owner found
        return None

    async def get_effective_owner_async(self, guild: discord.Guild = None) -> discord.User:
        """
        Async version of get_effective_owner that can fetch users if needed.
        
        Args:
            guild: The guild to get the owner for. If None, uses the configured owner.
            
        Returns:
            discord.User: The effective owner (configured owner or guild owner)
        """
        # If OWNER_ID is configured in environment, fetch that user
        if self.config.get('owner_id'):
            try:
                return await self.fetch_user(self.config['owner_id'])
            except discord.NotFound:
                logger = logging.getLogger(__name__)
                logger.warning(f"Configured OWNER_ID {self.config['owner_id']} not found")
        
        # Otherwise, use the guild owner if guild is provided
        if guild and guild.owner:
            return guild.owner
            
        # Fallback: no effective owner found
        return None

    async def setup_hook(self):
        """Configure bot extensions on startup"""
        # Initialize IPC connection to Player Service
        await self.ipc_manager.initialize()
        
        # Load music cog
        await self.load_extension('cogs.music')

    async def on_ready(self):
        """Called when the bot is ready and connected"""
        logger = logging.getLogger(__name__)
        logger.info(f"Bot connected as {self.user}")
        logger.info(f"Bot ID: {self.user.id}")
        logger.info("Bot ready to receive commands!")
        
        # Set bot activity
        activity = discord.Activity(
            type=discord.ActivityType.listening,
            name="/play music"
        )
        await self.change_presence(activity=activity)
        
        # Persistent setup and UI logic has been retired

    async def on_guild_join(self, guild):
        """Called when the bot joins a new guild"""
        logger = logging.getLogger(__name__)
        logger.info(f"Joined new guild: {guild.name} (ID: {guild.id})")
        # No setup DM flow

    async def _check_guild_setups(self):
        """Deprecated: Persistent setup removed."""
        return

    async def _cleanup_expired_setup_sessions(self):
        """Deprecated: Setup sessions removed."""
        return

    async def _trigger_setup_flow(self, owner: discord.Member, guild: discord.Guild):
        """Deprecated: Setup flow removed."""
        return

    async def on_voice_state_update(self, member, before, after):
        """
        Handle voice state updates and forward to Player Service.
        
        This method captures voice connection details and forwards them
        to the Player Service via IPC.
        
        Args:
            member (Member): Member whose voice state changed
            before (VoiceState): Previous voice state
            after (VoiceState): New voice state
        """
        try:
            # Handle bot's own voice state changes
            if member.id == self.user.id:
                guild_id = member.guild.id
                
                if after.channel is None:
                    # Bot was disconnected from voice
                    await self.ipc_manager.handle_voice_state_update(guild_id, None, None)
                else:
                    # Bot was connected or moved to a voice channel
                    session_id = getattr(after, 'session_id', None)
                    if session_id:
                        await self.ipc_manager.handle_voice_state_update(
                            guild_id, session_id, after.channel.id
                        )
                        
            # Handle other members' voice state changes for auto-disconnect
            else:
                guild = member.guild
                voice_client = guild.voice_client
                
                if voice_client and voice_client.channel:
                    # Check if bot is alone in the voice channel
                    voice_members = [m for m in voice_client.channel.members if not m.bot]
                    
                    if len(voice_members) == 0:
                        # Bot is alone - the Player Service will handle auto-disconnect
                        pass
                        
        except Exception as e:
            print(f"Error in voice state update: {e}")

    async def on_disconnect(self):
        """
        Handle bot disconnection
        """
        logger = logging.getLogger(__name__)
        logger.info("Bot disconnected from Discord")
        
        # IPC shutdown is handled in the close() method to avoid duplicate cleanup

    async def on_resumed(self):
        """
        Handle bot reconnection
        """
        print("Bot reconnected to Discord")
        
        # Re-initialize IPC connection
        try:
            await self.ipc_manager.initialize()
        except Exception as e:
            print(f"Error re-initializing IPC manager: {e}")

    async def on_voice_server_update(self, data):
        """
        Handle voice server updates from Discord.
        
        This captures the voice connection details needed by the Player Service.
        """
        try:
            guild_id = int(data['guild_id'])
            token = data.get('token')
            endpoint = data.get('endpoint')
            
            if token and endpoint:
                await self.ipc_manager.handle_voice_server_update(guild_id, token, endpoint)
                
        except Exception as e:
            print(f"Error handling voice server update: {e}")

    async def on_command_error(self, ctx, error):
        """Global command error handler"""
        if isinstance(error, commands.CommandInvokeError):
            error = error.original
        
        if isinstance(error, ValueError):
            embed = discord.Embed(
                title=MESSAGES['ERROR_TITLE'],
                description=str(error),
                color=COLORS['ERROR']
            )
            await ctx.send(embed=embed, delete_after=10)
        elif self.config.get('debug', False):
            # In debug mode, show full error traceback
            traceback.print_exception(type(error), error, error.__traceback__)

    async def on_error(self, event_method: str, *args, **kwargs):
        """Global event error handler"""
        print(f'Error in {event_method}:', file=sys.stderr)
        traceback.print_exc()

    async def _restore_embed_views(self):
        """Restore interactive views for existing embed messages after bot restart"""
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)  # Temporarily enable debug logging
        logger.info("Restoring interactive views for existing embed messages...")
        
        try:
            from utils.database import get_database_manager
            db_manager = await get_database_manager()
            
            # Get all guild settings from database
            logger.info("Getting all guild settings from database...")
            guild_settings_list = await db_manager.get_all_guild_settings()
            logger.info(f"Retrieved {len(guild_settings_list)} guild settings: {guild_settings_list}")
            
            for guild_settings in guild_settings_list:
                try:
                    logger.debug(f"Processing guild_settings: {type(guild_settings)} - {guild_settings}")
                    guild = self.get_guild(guild_settings.guild_id)
                    if not guild:
                        logger.warning(f"Guild {guild_settings.guild_id} not found, skipping view restoration")
                        continue
                    
                    control_channel = guild.get_channel(guild_settings.control_channel_id)
                    if not control_channel:
                        logger.warning(f"Control channel {guild_settings.control_channel_id} not found for guild {guild.name}")
                        continue
                    
                    # Try to fetch the queue message and restore its view
                    try:
                        queue_message = await control_channel.fetch_message(guild_settings.queue_message_id)
                        
                        # Get current queue data from Player Service
                        queue_data = []
                        try:
                            if self.ipc_manager and self.ipc_manager.ipc_client:
                                response = await self.ipc_manager.ipc_client.get_player_state(guild_settings.guild_id)
                                if response and response.get('status') == 'success':
                                    queue_data = response.get('data', {}).get('state', {}).get('queue', [])
                            else:
                                logger.warning(f"IPC manager not ready during view restoration for guild {guild.name}")
                        except Exception as e:
                            logger.warning(f"Could not get queue data for guild {guild.name}: {e}")
                        
                        # Create and attach the QueueView to the message
                        from cogs.music import QueueView
                        queue_view = QueueView(queue_data, current_page=1, bot=self, guild_id=guild_settings.guild_id)
                        queue_embed = queue_view._generate_queue_embed()
                        
                        # Update the message with the restored view
                        await queue_message.edit(embed=queue_embed, view=queue_view)
                        logger.info(f"Restored queue view for guild {guild.name}")
                        
                    except discord.NotFound:
                        logger.warning(f"Queue message {guild_settings.queue_message_id} not found for guild {guild.name}")
                    except discord.Forbidden:
                        logger.warning(f"No permission to edit queue message for guild {guild.name}")
                    except Exception as e:
                        logger.error(f"Error restoring queue view for guild {guild.name}: {e}")
                        
                except Exception as e:
                    logger.error(f"Error processing guild {guild_settings.guild_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Error restoring embed views: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
        
        logger.info("Embed view restoration completed")

    async def close(self):
        """Clean shutdown of the bot"""
        logger = logging.getLogger(__name__)
        logger.info("Bot shutdown initiated...")
        
        # Shutdown IPC connection first
        try:
            await self.ipc_manager.shutdown()
            logger.info("IPC manager shutdown completed")
        except Exception as e:
            logger.error(f"Error shutting down IPC manager: {e}")
        
        # Call parent close method
        await super().close()
        logger.info("Bot shutdown completed")

    def run(self):
        """Run the bot with the configured token"""
        super().run(self.config['bot_token'], log_handler=None)
