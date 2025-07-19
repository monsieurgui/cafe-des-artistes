"""
Player Service Application Entry Point
=====================================

This is the headless Python application that manages audio playback for the 
Cafe des Artistes Discord bot. It runs independently of the Discord bot client
and communicates via ZeroMQ IPC.

The Player Service:
- Manages MusicPlayer instances for each guild
- Handles voice channel connections
- Processes audio queues and streaming
- Sends events back to the Bot Client

Usage: python player_main.py
"""

import asyncio
import logging
import signal
import sys
import zmq
import zmq.asyncio
from typing import Dict, Optional
import json
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.music_player_service import MusicPlayerService
from utils.ipc_protocol import (
    IPCMessage, Command, Event, MessageType,
    PLAYER_SERVICE_CONFIG, DEFAULT_COMMAND_PORT, DEFAULT_EVENT_PORT
)
from utils.config import load_config
import yaml
import os
from utils.logging_config import setup_logging


class PlayerServiceApp:
    """Main Player Service Application"""
    
    def __init__(self):
        self.config = None
        self.context = None
        self.command_socket = None
        self.event_socket = None
        self.music_players: Dict[int, MusicPlayerService] = {}
        self.running = False
        self.logger = None
        
    def load_player_config(self):
        """Load configuration for player service (no bot token required)"""
        default_config = {
            'command_prefix': '!',
            'ffmpeg_path': '/usr/bin/ffmpeg',
            'log_level': 'INFO'
        }
        
        # Try to load from yaml file
        try:
            config_path = os.path.join(os.path.dirname(__file__), 'src', 'config', 'config.yaml')
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    yaml_config = yaml.safe_load(f)
                    return {**default_config, **(yaml_config or {})}
        except Exception as e:
            print(f"Warning: Could not load config.yaml: {e}")
        
        return default_config
    
    async def initialize(self):
        """Initialize the Player Service"""
        try:
            # Load configuration (player service doesn't need bot token)
            self.config = self.load_player_config()
            
            # Setup logging
            setup_logging()
            self.logger = logging.getLogger("player_service")
            self.logger.info("Initializing Player Service...")
            
            # Initialize ZeroMQ context
            self.context = zmq.asyncio.Context()
            
            # Setup command socket (receives commands from Bot Client)
            self.command_socket = self.context.socket(zmq.REP)
            self.command_socket.bind(PLAYER_SERVICE_CONFIG["command_address"])
            self.logger.info(f"Command socket bound to {PLAYER_SERVICE_CONFIG['command_address']}")
            
            # Setup event socket (sends events to Bot Client)
            self.event_socket = self.context.socket(zmq.PUB)
            self.event_socket.bind(PLAYER_SERVICE_CONFIG["event_address"])
            self.logger.info(f"Event socket bound to {PLAYER_SERVICE_CONFIG['event_address']}")
            
            # Give the event socket time to establish connections
            await asyncio.sleep(0.1)
            
            self.logger.info("Player Service initialized successfully")
            
        except Exception as e:
            if hasattr(self, 'logger') and self.logger:
                self.logger.error(f"Failed to initialize Player Service: {e}")
            else:
                print(f"Failed to initialize Player Service: {e}")
            raise
    
    async def start(self):
        """Start the Player Service"""
        try:
            await self.initialize()
            self.running = True
            self.logger.info("Player Service started")
            
            # Start the command processing loop
            await self.command_loop()
            
        except Exception as e:
            self.logger.error(f"Error starting Player Service: {e}")
            raise
    
    async def command_loop(self):
        """Main command processing loop"""
        self.logger.info("Starting command processing loop...")
        
        while self.running:
            try:
                # Wait for command from Bot Client
                message_data = await self.command_socket.recv_string(zmq.NOBLOCK)
                
                # Process the command
                response = await self.process_command(message_data)
                
                # Send response back to Bot Client
                await self.command_socket.send_string(response)
                
            except zmq.Again:
                # No message available, wait a bit
                await asyncio.sleep(0.01)
            except Exception as e:
                self.logger.error(f"Error in command loop: {e}")
                # Send error response
                error_response = json.dumps({"status": "error", "message": str(e)})
                try:
                    await self.command_socket.send_string(error_response)
                except:
                    pass
    
    async def process_command(self, message_data: str) -> str:
        """Process a command message from the Bot Client"""
        try:
            message = IPCMessage.from_json(message_data)
            
            if message.type != MessageType.COMMAND.value:
                return json.dumps({"status": "error", "message": "Invalid message type"})
            
            guild_id = message.guild_id
            command = Command(message.action)
            data = message.data
            
            self.logger.debug(f"Processing command {command.value} for guild {guild_id}")
            
            # Get or create MusicPlayer for this guild
            if guild_id not in self.music_players:
                self.music_players[guild_id] = MusicPlayerService(
                    guild_id, self.config, self.event_socket, self.logger
                )
            
            player = self.music_players[guild_id]
            
            # Process the command
            if command == Command.CONNECT:
                result = await player.connect(
                    data["channel_id"],
                    data["token"], 
                    data["endpoint"],
                    data["session_id"]
                )
            elif command == Command.DISCONNECT:
                result = await player.disconnect()
            elif command == Command.ADD_TO_QUEUE:
                result = await player.add_to_queue(
                    data["query"],
                    data.get("repeat_count", 1),
                    data.get("requester_name", "Unknown")
                )
            elif command == Command.SKIP_SONG:
                result = await player.skip()
            elif command == Command.PLAY_NEXT:
                # Send SONG_ENDED event for current song before clearing it
                if player.current:
                    from utils.ipc_protocol import SongData, create_song_ended_event
                    current_song_data = SongData(
                        url=player.current['url'],
                        title=player.current['title'],
                        duration=player.current.get('duration', 0),
                        thumbnail=player.current.get('thumbnail'),
                        webpage_url=player.current.get('webpage_url'),
                        channel=player.current.get('channel'),
                        view_count=player.current.get('view_count'),
                        requester_name=player.current.get('requester_name', 'Unknown'),
                        audio_url=player.current.get('audio_url')
                    )
                    await player._send_song_ended(current_song_data)
                
                # Clear current song and play next from queue
                player.current = None
                await player.play_next()
                result = {"status": "play_next_triggered"}
            elif command == Command.GET_STATE:
                result = await player.get_state()
            elif command == Command.RESET_PLAYER:
                result = await player.reset()
            elif command == Command.REMOVE_FROM_QUEUE:
                result = await player.remove_from_queue(data["song_index"])
            else:
                return json.dumps({"status": "error", "message": f"Unknown command: {command.value}"})
            
            return json.dumps({"status": "success", "data": result})
            
        except Exception as e:
            self.logger.error(f"Error processing command: {e}")
            return json.dumps({"status": "error", "message": str(e)})
    
    async def send_event(self, event_message: str):
        """Send an event to the Bot Client"""
        try:
            await self.event_socket.send_string(event_message)
        except Exception as e:
            self.logger.error(f"Error sending event: {e}")
    
    async def cleanup_guild(self, guild_id: int):
        """Clean up resources for a specific guild"""
        if guild_id in self.music_players:
            try:
                await self.music_players[guild_id].cleanup()
                del self.music_players[guild_id]
                self.logger.info(f"Cleaned up player for guild {guild_id}")
            except Exception as e:
                self.logger.error(f"Error cleaning up guild {guild_id}: {e}")
    
    async def shutdown(self):
        """Shutdown the Player Service"""
        if hasattr(self, 'logger') and self.logger:
            self.logger.info("Shutting down Player Service...")
        else:
            print("Shutting down Player Service...")
        self.running = False
        
        # Cleanup all music players
        for guild_id in list(self.music_players.keys()):
            await self.cleanup_guild(guild_id)
        
        # Close sockets
        if self.command_socket:
            self.command_socket.close()
        if self.event_socket:
            self.event_socket.close()
        
        # Terminate context
        if self.context:
            self.context.term()
        
        if hasattr(self, 'logger') and self.logger:
            self.logger.info("Player Service shutdown complete")
        else:
            print("Player Service shutdown complete")


def signal_handler(app):
    """Handle shutdown signals"""
    def handler(signum, frame):
        print(f"\nReceived signal {signum}, shutting down...")
        asyncio.create_task(app.shutdown())
    return handler


async def main():
    """Main entry point"""
    app = PlayerServiceApp()
    
    # Setup signal handlers for graceful shutdown
    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, signal_handler(app))
    
    try:
        await app.start()
    except KeyboardInterrupt:
        print("\nReceived interrupt, shutting down...")
    except Exception as e:
        print(f"Fatal error: {e}")
        return 1
    finally:
        await app.shutdown()
    
    return 0


if __name__ == "__main__":
    # Run the Player Service
    exit_code = asyncio.run(main())
    sys.exit(exit_code)