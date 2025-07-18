"""
Inter-Process Communication Protocol for Cafe des Artistes Bot
=============================================================

This module defines the IPC protocol used for communication between the Bot Client
and the Player Service. The protocol uses ZeroMQ for low-latency message passing.

Message Format:
All messages are JSON-encoded with the following structure:
{
    "type": "command" | "event",
    "action": "ACTION_NAME",
    "guild_id": int,
    "data": {...},
    "timestamp": float
}

Commands (Bot -> Player):
- CONNECT: Connect to a voice channel
- DISCONNECT: Disconnect from voice channel  
- ADD_TO_QUEUE: Add song(s) to queue
- SKIP_SONG: Skip current song
- GET_STATE: Get current player state
- RESET_PLAYER: Clear queue and stop playback
- REMOVE_FROM_QUEUE: Remove specific song from queue

Events (Player -> Bot):
- SONG_STARTED: New song started playing
- SONG_ENDED: Song finished playing
- QUEUE_UPDATED: Queue state changed
- PLAYER_IDLE: Player has no songs and is idle
- PLAYER_ERROR: Error occurred in player
- STATE_UPDATE: Full state update
"""

import json
import time
from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict


class MessageType(Enum):
    COMMAND = "command"
    EVENT = "event"


class Command(Enum):
    CONNECT = "CONNECT"
    DISCONNECT = "DISCONNECT" 
    ADD_TO_QUEUE = "ADD_TO_QUEUE"
    SKIP_SONG = "SKIP_SONG"
    PLAY_NEXT = "PLAY_NEXT"
    GET_STATE = "GET_STATE"
    RESET_PLAYER = "RESET_PLAYER"
    REMOVE_FROM_QUEUE = "REMOVE_FROM_QUEUE"


class Event(Enum):
    SONG_STARTED = "SONG_STARTED"
    SONG_ENDED = "SONG_ENDED"
    QUEUE_UPDATED = "QUEUE_UPDATED"
    PLAYER_IDLE = "PLAYER_IDLE"
    PLAYER_ERROR = "PLAYER_ERROR"
    STATE_UPDATE = "STATE_UPDATE"


@dataclass
class IPCMessage:
    """Base IPC message structure"""
    type: str
    action: str
    guild_id: int
    data: Dict[str, Any]
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
    
    def to_json(self) -> str:
        """Convert message to JSON string"""
        return json.dumps(asdict(self))
    
    @classmethod
    def from_json(cls, json_str: str) -> 'IPCMessage':
        """Create message from JSON string"""
        data = json.loads(json_str)
        return cls(**data)


class CommandMessage(IPCMessage):
    """Command message from Bot to Player"""
    
    def __init__(self, action: Command, guild_id: int, data: Dict[str, Any] = None):
        super().__init__(
            type=MessageType.COMMAND.value,
            action=action.value,
            guild_id=guild_id,
            data=data or {}
        )


class EventMessage(IPCMessage):
    """Event message from Player to Bot"""
    
    def __init__(self, action: Event, guild_id: int, data: Dict[str, Any] = None):
        super().__init__(
            type=MessageType.EVENT.value,
            action=action.value,
            guild_id=guild_id,
            data=data or {}
        )


# Command Data Structures

@dataclass
class ConnectData:
    """Data for CONNECT command"""
    channel_id: int
    token: str
    endpoint: str
    session_id: str


@dataclass
class AddToQueueData:
    """Data for ADD_TO_QUEUE command"""
    query: str
    repeat_count: int = 1
    requester_name: str = "Unknown"


@dataclass
class RemoveFromQueueData:
    """Data for REMOVE_FROM_QUEUE command"""
    song_index: int


# Event Data Structures

@dataclass
class SongData:
    """Song information for events"""
    url: str
    title: str
    duration: int
    thumbnail: Optional[str] = None
    webpage_url: Optional[str] = None
    channel: Optional[str] = None
    view_count: Optional[int] = None
    requester_name: str = "Unknown"
    audio_url: Optional[str] = None


@dataclass
class StateData:
    """Full player state data"""
    current_song: Optional[SongData] = None
    queue: list = None
    is_playing: bool = False
    is_connected: bool = False
    channel_id: Optional[int] = None
    
    def __post_init__(self):
        if self.queue is None:
            self.queue = []


@dataclass
class ErrorData:
    """Error information for PLAYER_ERROR event"""
    error_type: str
    error_message: str
    song_data: Optional[SongData] = None


# Helper functions for creating common messages

def create_connect_command(guild_id: int, channel_id: int, token: str, 
                          endpoint: str, session_id: str) -> CommandMessage:
    """Create a CONNECT command message"""
    return CommandMessage(
        Command.CONNECT,
        guild_id,
        asdict(ConnectData(channel_id, token, endpoint, session_id))
    )


def create_disconnect_command(guild_id: int) -> CommandMessage:
    """Create a DISCONNECT command message"""
    return CommandMessage(Command.DISCONNECT, guild_id)


def create_add_to_queue_command(guild_id: int, query: str, repeat_count: int = 1, 
                               requester_name: str = "Unknown") -> CommandMessage:
    """Create an ADD_TO_QUEUE command message"""
    return CommandMessage(
        Command.ADD_TO_QUEUE,
        guild_id,
        asdict(AddToQueueData(query, repeat_count, requester_name))
    )


def create_skip_command(guild_id: int) -> CommandMessage:
    """Create a SKIP_SONG command message"""
    return CommandMessage(Command.SKIP_SONG, guild_id)


def create_get_state_command(guild_id: int) -> CommandMessage:
    """Create a GET_STATE command message"""
    return CommandMessage(Command.GET_STATE, guild_id)


def create_reset_command(guild_id: int) -> CommandMessage:
    """Create a RESET_PLAYER command message"""
    return CommandMessage(Command.RESET_PLAYER, guild_id)


def create_remove_from_queue_command(guild_id: int, song_index: int) -> CommandMessage:
    """Create a REMOVE_FROM_QUEUE command message"""
    return CommandMessage(
        Command.REMOVE_FROM_QUEUE,
        guild_id,
        asdict(RemoveFromQueueData(song_index))
    )


def create_play_next_command(guild_id: int) -> CommandMessage:
    """Create a PLAY_NEXT command message"""
    return CommandMessage(Command.PLAY_NEXT, guild_id, {})


def create_song_started_event(guild_id: int, song_data: SongData) -> EventMessage:
    """Create a SONG_STARTED event message"""
    return EventMessage(Event.SONG_STARTED, guild_id, asdict(song_data))


def create_song_ended_event(guild_id: int, song_data: SongData) -> EventMessage:
    """Create a SONG_ENDED event message"""
    return EventMessage(Event.SONG_ENDED, guild_id, asdict(song_data))


def create_queue_updated_event(guild_id: int, queue: list) -> EventMessage:
    """Create a QUEUE_UPDATED event message"""
    return EventMessage(Event.QUEUE_UPDATED, guild_id, {"queue": queue})


def create_player_idle_event(guild_id: int) -> EventMessage:
    """Create a PLAYER_IDLE event message"""
    return EventMessage(Event.PLAYER_IDLE, guild_id)


def create_player_error_event(guild_id: int, error_type: str, error_message: str, 
                             song_data: Optional[SongData] = None) -> EventMessage:
    """Create a PLAYER_ERROR event message"""
    error_data = ErrorData(error_type, error_message, song_data)
    return EventMessage(Event.PLAYER_ERROR, guild_id, asdict(error_data))


def create_state_update_event(guild_id: int, state_data: StateData) -> EventMessage:
    """Create a STATE_UPDATE event message"""
    return EventMessage(Event.STATE_UPDATE, guild_id, asdict(state_data))


# ZeroMQ Configuration
import os

DEFAULT_COMMAND_PORT = 5555  # Bot -> Player commands
DEFAULT_EVENT_PORT = 5556    # Player -> Bot events

# Support Docker networking via environment variables
PLAYER_SERVICE_HOST = os.getenv("PLAYER_SERVICE_HOST", "127.0.0.1")
BIND_HOST = os.getenv("BIND_HOST", "127.0.0.1")
COMMAND_PORT = int(os.getenv("COMMAND_PORT", DEFAULT_COMMAND_PORT))
EVENT_PORT = int(os.getenv("EVENT_PORT", DEFAULT_EVENT_PORT))

# For bot client (connecting to player service)
BOT_CLIENT_CONFIG = {
    "command_address": f"tcp://{PLAYER_SERVICE_HOST}:{COMMAND_PORT}",
    "event_address": f"tcp://{PLAYER_SERVICE_HOST}:{EVENT_PORT}",
    "socket_timeout": 5000,  # 5 seconds
    "max_retries": 3,
    "retry_delay": 1000,     # 1 second
}

# For player service (binding sockets)
PLAYER_SERVICE_CONFIG = {
    "command_address": f"tcp://{BIND_HOST}:{COMMAND_PORT}",
    "event_address": f"tcp://{BIND_HOST}:{EVENT_PORT}",
    "socket_timeout": 5000,  # 5 seconds
    "max_retries": 3,
    "retry_delay": 1000,     # 1 second
}

# Backward compatibility
ZEROMQ_CONFIG = BOT_CLIENT_CONFIG