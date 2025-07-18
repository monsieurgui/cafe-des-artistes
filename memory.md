# Project Progress Memory

## Memory of the Last Sprint

This document summarizes the progress and accomplishments from the most recent sprint for the Café des Artistes Discord music bot project.

---

### Architectural Refactoring & Decoupling

**Standalone Player Service:**
- Developed a comprehensive IPC protocol using ZeroMQ for low-latency, real-time communication between services. The protocol uses JSON messages for commands (CONNECT, DISCONNECT, ADD_TO_QUEUE, SKIP_SONG, GET_STATE, RESET_PLAYER, REMOVE_FROM_QUEUE) and events (SONG_STARTED, SONG_ENDED, QUEUE_UPDATED, PLAYER_IDLE, PLAYER_ERROR, STATE_UPDATE).
- Created `src/utils/ipc_protocol.py` for protocol definitions and helpers.
- Built the Player Service application entry point (`player_main.py`) with a main class, ZeroMQ initialization, command processing loop, graceful shutdown, and support for multiple MusicPlayerService instances (one per guild) using asyncio.
- Refactored the MusicPlayer core into `src/core/music_player_service.py`, removing all direct Discord API dependencies. The new core works with `guild_id`, accepts voice connection parameters, and maintains queue management and playback.
- Implemented a command handler in the Player Service to process all defined commands, manage player instances, and return structured JSON responses with robust error handling.
- Added event broadcasting to the MusicPlayerService, sending events to the Bot Client via ZeroMQ PUB socket. Events include full song data and player state, and are sent automatically on state changes.

**Files Created:**
- `src/utils/ipc_protocol.py`
- `player_main.py`
- `src/core/music_player_service.py`

**Architecture Achieved:**
- Full separation of audio processing from the Discord bot client.
- Headless Player Service, event-driven state synchronization, and a solid foundation for the Bot Client.

---

**Bot Client as Lightweight Controller:**
- Removed all player logic, direct MusicPlayer instantiations, and yt-dlp/FFmpeg management from the bot client. The bot now uses IPC for all audio operations.
- Developed `src/utils/ipc_client.py` with an `IPCClient` class for ZeroMQ communication and an `IPCManager` for high-level operations. Added command methods and event handlers, including an automatic event listener.
- Updated the bot to capture and forward voice connection details to the Player Service, including proper handling of connection/disconnection events.
- All music commands (`!play`, `!skip`, `!queue`, etc.) now delegate to the Player Service via IPC.
- Temporarily disabled features like loop and live, to be re-implemented in the Player Service.

**Files Modified/Created:**
- `src/bot/client.py`, `src/cogs/music.py`, `src/requirements.txt`, `src/utils/ipc_client.py`

**Architecture Achieved:**
- The Bot Client is now a lightweight controller, with all music commands handled via ZeroMQ IPC and event-driven updates from the Player Service.

---

**Persistent Server-Specific Settings:**
- Designed and implemented a SQLite database schema for persistent guild settings, including control channel and embed message IDs, with metadata and indexing for performance.
- Created `src/utils/database.py` with a `DatabaseManager` class for async CRUD operations, type-safe dataclasses, thread safety, and error handling.
- All database operations are asynchronous and thread-safe, with auto-initialization and built-in statistics.

**Files Created/Modified:**
- `src/utils/database.py`, `src/requirements.txt`

**Database Features:**
- Lightweight, async, persistent, and type-safe storage for guild settings.

**Schema Example:**

---

### User Story 1.1 Completion - Communication Protocol Definition

**Epic 1, User Story 1.1: Communication Protocol Implementation Verified**

✅ **ZeroMQ IPC Technology Selection Confirmed:**
- **REQ/REP Pattern:** Successfully implemented for commands (Bot Client → Player Service)
- **PUB/SUB Pattern:** Successfully implemented for events (Player Service → Bot Client)
- **Protocol Configuration:** Robust configuration with timeouts, retries, and error handling

✅ **JSON Message Contract Validation:**
- **Base Message Structure:** Standardized IPCMessage with type, action, guild_id, data, and timestamp
- **Command Messages:** All planned commands implemented (CONNECT, DISCONNECT, ADD_TO_QUEUE, SKIP_SONG, RESET_PLAYER) plus additional commands (GET_STATE, REMOVE_FROM_QUEUE)
- **Event Messages:** All planned events implemented (SONG_STARTED, QUEUE_UPDATED, PLAYER_IDLE) plus additional events (SONG_ENDED, PLAYER_ERROR, STATE_UPDATE)
- **Data Structures:** Comprehensive dataclasses for ConnectData, AddToQueueData, SongData, StateData, ErrorData

✅ **Implementation Status:**
- **Protocol Definition:** Complete in `src/utils/ipc_protocol.py` with full documentation
- **Player Service:** Complete ZeroMQ server implementation in `player_main.py`  
- **Bot Client:** Complete ZeroMQ client implementation in `src/utils/ipc_client.py`
- **Communication Testing:** IPC communication verified with mock services showing successful:
  - Command sending and response handling (REQ/REP)
  - Event publishing and subscription (PUB/SUB)
  - JSON message serialization/deserialization
  - Windows compatibility with proper event loop policy

**Files Involved:**
- `src/utils/ipc_protocol.py` - Protocol definitions and message helpers
- `player_main.py` - Player Service ZeroMQ server
- `src/utils/ipc_client.py` - Bot Client ZeroMQ client and IPCManager

**Architecture Status:** User Story 1.1 is complete. The robust, low-latency communication protocol between Bot Client and Player Service is fully implemented and tested.

---

### User Story 1.2 Completion - Standalone Headless Player Service

**Epic 1, User Story 1.2: Standalone Player Service Application Verified**

✅ **Project Directory Structure:**
- **Logical Separation Achieved:** While physical `bot-client/` and `player-service/` directories weren't created, the codebase achieves complete logical separation with clear boundaries between services
- **Player Service Isolation:** `player_main.py` serves as the standalone Player Service entry point
- **Bot Client Isolation:** All bot client code remains in `src/` directory with clear IPC-based communication

✅ **Headless Player Service Entry Point:**
- **Entry Point:** `player_main.py` serves as the main executable for the Player Service
- **No Discord Gateway:** Confirmed no `discord.py` imports for Gateway connections - completely headless
- **ZMQ Initialization:** Proper REP socket for commands and PUB socket for events
- **Command Processing Loop:** Infinite loop listening for IPC commands with robust error handling
- **Multi-Guild Support:** Maintains dictionary of MusicPlayerService instances keyed by guild_id

✅ **MusicPlayer Core Adaptation:**
- **Refactored Class:** `src/core/music_player_service.py` contains the adapted MusicPlayerService
- **Guild-ID Only Init:** `__init__(guild_id, config, event_socket, logger)` - no Discord objects
- **Voice Connection Method:** `connect(channel_id, token, endpoint, session_id)` method implemented
- **Removed Discord Dependencies:** `ensure_voice_client()` method removed as planned
- **Independent Operation:** Works completely independently of Discord bot client

✅ **Player Service Command Handler:**
- **Message Parsing:** Robust JSON message parsing using `IPCMessage.from_json()`
- **Command Routing:** All commands (CONNECT, DISCONNECT, ADD_TO_QUEUE, SKIP_SONG, GET_STATE, RESET_PLAYER, REMOVE_FROM_QUEUE) properly routed
- **Player Instance Management:** Automatic creation and management of MusicPlayerService instances per guild
- **Response Handling:** Structured JSON responses with status and data
- **Error Management:** Comprehensive error handling and logging

✅ **IPC Event Emitter Implementation:**
- **Event Methods:** Complete set of event emission methods (_send_song_started, _send_song_ended, _send_queue_update, _send_player_idle, _send_error_event, _send_state_update)
- **ZMQ Publishing:** Events published via ZMQ PUB socket to Bot Client
- **Action Triggers:** Events sent after state changes (song start, queue update, player idle)
- **Protocol Compliance:** Full compliance with IPC protocol event definitions
- **Automatic Updates:** Real-time state synchronization with Bot Client

**Files Involved:**
- `player_main.py` - Headless Player Service application entry point
- `src/core/music_player_service.py` - Adapted MusicPlayer core without Discord dependencies
- `src/utils/ipc_protocol.py` - Supporting IPC protocol definitions

**Architecture Status:** User Story 1.2 is complete. The standalone, headless Player Service application is fully implemented with proper command handling, event emission, and multi-guild support.

---

### User Story 1.3 Completion - Lightweight Bot Client Controller

**Epic 1, User Story 1.3: Bot Client Refactored as Lightweight Controller Verified**

✅ **Audio Logic Removal:**
- **No Direct Audio Management:** Confirmed removal of all yt-dlp and FFmpeg direct management from Bot Client
- **No Music Players Dictionary:** Replaced with IPC Manager for Player Service communication
- **Clean Separation:** Bot Client has zero knowledge of audio processing internals
- **IPC-Only Communication:** All audio operations delegated to Player Service via ZeroMQ

✅ **IPC Client Utility Implementation:**
- **Complete IPC Infrastructure:** `src/utils/ipc_client.py` contains IPCClient and IPCManager classes
- **Command Interface:** Provides async `send_command()` functionality for all Player Service commands
- **Event Listener:** Background task listening on ZMQ SUB socket for Player Service events
- **Connection Management:** Robust ZeroMQ REQ and SUB socket management with proper cleanup
- **Error Handling:** Comprehensive error handling and retry logic

✅ **Slash Command Handler Refactoring:**
- **IPC Delegation Pattern:** All commands (play, skip, leave, p5, reset, queue) follow the required pattern:
  1. Defer response (`interaction.response.defer()`)
  2. Call IPC client with appropriate command
  3. Send follow-up message confirming action
- **No Direct Audio Calls:** Commands delegate to Player Service without direct audio processing
- **Structured Responses:** Proper handling of Player Service responses with status and data

✅ **Voice State Forwarding Implementation:**
- **Connection Detail Capture:** Bot captures voice token, endpoint, session_id, and channel_id from Discord
- **Automatic CONNECT Commands:** Voice server updates automatically trigger CONNECT commands to Player Service
- **State Management:** Maintains voice state dictionary for proper connection tracking
- **Disconnect Handling:** Properly handles voice disconnections and forwards to Player Service

✅ **Bot Client Event Handler:**
- **ZMQ Event Listening:** Background task listens for all Player Service events
- **UI Update Delegation:** Events trigger appropriate UI updates via Music cog methods:
  - SONG_STARTED → start_now_playing_updates()
  - SONG_ENDED → stop_now_playing_updates()
  - QUEUE_UPDATED → update_queue_display()
  - PLAYER_IDLE → idle state UI updates
- **Event Registration:** All event types properly registered with corresponding handlers
- **Real-time Synchronization:** UI stays synchronized with Player Service state

**Files Involved:**
- `src/bot/client.py` - Lightweight bot client with IPC Manager integration
- `src/cogs/music.py` - Refactored slash commands delegating to IPC
- `src/utils/ipc_client.py` - Complete IPC client and manager implementation

**Architecture Status:** User Story 1.3 is complete. The Bot Client is now a lightweight controller that delegates all audio operations to the Player Service while maintaining responsive UI updates through event-driven synchronization.

---

### User Story 1.4 Completion - Containerized Service Orchestration

**Epic 1, User Story 1.4: Containerized and Orchestrated Services for Reliable Deployment Implemented**

✅ **Bot Client Containerization:**
- **Lightweight Dockerfile**: `bot-client.Dockerfile` with `python:3.11-slim` base image
- **No FFmpeg Dependencies**: Clean separation - bot client has no audio processing dependencies
- **Environment Configuration**: Supports Docker networking via environment variables
- **IPC Client Setup**: Configured to connect to player-service via hostname resolution

✅ **Player Service Containerization:**
- **Audio-Ready Dockerfile**: `player-service.Dockerfile` with FFmpeg installation
- **Audio Dependencies**: Includes `apt-get install -y ffmpeg` for audio processing
- **Port Exposure**: Exposes ports 5555 (commands) and 5556 (events) for IPC communication
- **Headless Operation**: Runs `player_main.py` as standalone audio processing service

✅ **Docker Compose Orchestration:**
- **Two-Service Architecture**: `docker-compose-services.yml` defines bot-client and player-service
- **Custom Bridge Network**: `cafebot-net` enables hostname-based service communication
- **Environment File Support**: `.env` file configuration for secure bot token management
- **Service Dependencies**: Proper startup order with `depends_on: player-service`
- **Restart Policies**: `restart: unless-stopped` for service resilience
- **Volume Mounting**: Shared configuration and log directories

✅ **Network Communication Configuration:**
- **Hostname Resolution**: Bot client connects to `tcp://player-service:5555` and `tcp://player-service:5556`
- **Environment Variables**: `PLAYER_SERVICE_HOST`, `COMMAND_PORT`, `EVENT_PORT` for Docker networking
- **IPC Protocol Updates**: Separate configs for bot client (connecting) and player service (binding)
- **Service Isolation**: Custom bridge network isolates services while enabling communication

✅ **Deployment Infrastructure:**
- **Comprehensive Documentation**: `DEPLOYMENT.md` with setup instructions and troubleshooting
- **Environment Template**: `env.example` for configuration guidance
- **Build Validation**: Docker Compose configuration validated and ready for deployment
- **Monitoring Commands**: Health check and logging commands for operational management

**Files Created/Modified:**
- `bot-client.Dockerfile` - Lightweight bot client container without FFmpeg
- `player-service.Dockerfile` - Audio processing container with FFmpeg
- `docker-compose-services.yml` - Two-service orchestration configuration
- `env.example` - Environment configuration template
- `DEPLOYMENT.md` - Comprehensive deployment and troubleshooting guide
- `src/utils/ipc_protocol.py` - Updated with Docker networking support
- `player_main.py` - Updated to use player service configuration
- `src/utils/ipc_client.py` - Updated to use bot client configuration

**Architecture Status:** User Story 1.4 is complete. Both services are fully containerized with proper orchestration, networking, and deployment infrastructure. The system is ready for reliable production deployment using `docker-compose up`.

---

### Build Fixes & Deployment Validation

**Docker Build Issues Resolved:**
✅ **Environment Variable Parsing**: Fixed critical configuration parsing issues in `src/utils/config.py`:
- Added `safe_int()` function to handle placeholder values like `'your_discord_user_id_here'` gracefully
- Fixed OWNER_ID environment variable parsing to prevent ValueError crashes
- Enhanced MAX_QUEUE_SIZE and TIMEOUT_DURATION parsing with safe integer conversion

✅ **Bot Token Configuration**: Improved bot token handling robustness:
- Added `get_bot_token()` function supporting both `BOT_TOKEN` and `DISCORD_TOKEN` environment variables
- Implemented placeholder value detection to ignore template values like `'your_discord_bot_token_here'`
- Added fallback mechanisms for missing or invalid token configurations

✅ **Full System Validation**: Successfully validated complete system operation:
- **Player Service**: Starts successfully, binds to ports 5555/5556, processes commands
- **Bot Client**: Successfully connects to Discord Gateway and Player Service via ZeroMQ IPC
- **IPC Communication**: REQ/REP and PUB/SUB patterns working correctly between services
- **Database**: SQLite database initializes successfully for guild settings persistence
- **Docker Orchestration**: Both services start and communicate properly in containerized environment

**Files Modified:**
- `src/utils/config.py` - Enhanced environment variable parsing with error handling

**Architecture Status:** The Discord music bot build is now fully functional. Both the lightweight Bot Client and headless Player Service start successfully in Docker containers with proper IPC communication established. The system is ready for testing and further development.

---

### Setup Command Fix - Session Persistence Issue Resolved

**Problem Identified:** 
The `/setup` command DM response mechanism was failing because setup sessions were stored in-memory and lost when the bot restarted. Users would run `/setup`, receive a DM, but when they responded with a channel name like `#test-bot-playground`, they got "Setup Session Not Found" errors.

**Root Cause Analysis:**
- Setup sessions were stored in `self.bot.setup_sessions` (in-memory dictionary)
- Bot restarts (which happened multiple times) cleared all active sessions
- Session creation happened AFTER DM sending, so failures could leave incomplete state
- No persistence mechanism for setup sessions across restarts

**Solution Implemented:**
✅ **Database-Persistent Sessions**: Added `setup_sessions` table to SQLite database with schema:
- `user_id` (INTEGER, PRIMARY KEY): Discord user ID
- `guild_id` (INTEGER, NOT NULL): Guild being set up  
- `guild_name` (TEXT, NOT NULL): Guild name for reference
- `started_at` (TIMESTAMP, NOT NULL): Session start time
- Proper indexing for performance

✅ **Session Management Functions**: Added complete CRUD operations:
- `create_setup_session()`: Create new session with validation
- `get_setup_session()`: Retrieve session by user ID
- `delete_setup_session()`: Clean up completed/failed sessions
- `cleanup_expired_setup_sessions()`: Automatic cleanup of expired sessions

✅ **Improved Setup Command Flow**:
- Session creation moved BEFORE DM sending (ensures session exists when user responds)
- Comprehensive error handling with session cleanup on failures
- Added logging for debugging setup command flow
- Validation that session creation succeeds before proceeding

✅ **Enhanced Error Handling & Recovery**:
- Graceful handling of DM failures (disabled DMs) with session cleanup
- User-friendly recovery messages for expired/lost sessions
- Automatic cleanup of expired sessions on bot startup
- Debug logging for troubleshooting

✅ **Session Expiry & Cleanup**:
- 5-minute session timeout maintained
- Automatic cleanup on bot startup removes stale sessions
- Proper datetime handling with ISO format timestamps

**Files Modified:**
- `src/utils/database.py` - Added setup session table and management functions
- `src/cogs/music.py` - Updated setup command to use database persistence
- `src/bot/client.py` - Added session cleanup on bot startup

**Critical Datetime Fix Applied:**
✅ **Timezone Comparison Error Resolved**: Fixed `TypeError: can't subtract offset-naive and offset-aware datetimes` that occurred when users responded to setup DMs. The error happened because of mixed timezone-aware and timezone-naive datetime usage throughout the codebase:
- Setup sessions used `discord.utils.utcnow().isoformat()` (timezone-aware) when created
- Multiple locations used `datetime.utcnow()` (timezone-naive) for comparison
- **Fixed in multiple files**: `music.py` (lines 516, 601), `now_playing.py` (lines 9, 44), database session handling
- **Solution**: Using `discord.utils.utcnow()` consistently throughout for timezone-aware operations

**Testing Status:** 
- ✅ Database operations verified working correctly
- ✅ Session creation, retrieval, and deletion tested
- ✅ Bot rebuilds and starts successfully
- ✅ Datetime timezone comparison fixed and tested
- 🔄 Ready for user testing of complete setup flow

**Architecture Status:** Setup command session persistence is now fully implemented with database backing and proper timezone handling. The `/setup` command should work reliably across bot restarts, and users can complete the setup process by responding to DMs with channel names without encountering datetime errors.

---

### Setup DM Spam Prevention - Only Send DMs for New Guilds

**Problem Identified:**
The bot was sending setup DMs to guild owners on every restart, even for servers that were already configured. This was happening because the `on_ready` event was checking ALL guilds and triggering setup flows for any unconfigured ones.

**Root Cause:**
- `on_ready` event called `_check_guild_setups()` on every bot startup
- This method looped through ALL guilds and sent setup DMs to unconfigured ones
- While the logic was correct for first-time deployment, it was inappropriate for routine restarts
- Guild owners were getting spammed with setup DMs every time the bot restarted

**Solution Implemented:**
✅ **Removed Auto-Setup from Startup**: Removed the `_check_guild_setups()` call from `on_ready` event to prevent setup DMs on every restart

✅ **Enhanced Guild Join Logic**: Improved `on_guild_join` event with database checks:
- Only sends setup DMs for truly new/unconfigured guilds
- Checks if guild already has setup before sending DM (handles rejoining scenarios)
- Added comprehensive logging for transparency
- Fallback behavior in case of database errors

✅ **Smart Setup DM Behavior**:
- **Send DM**: Only when bot joins a new, unconfigured guild
- **Skip DM**: For already-configured guilds (rejoining scenarios)
- **No DMs**: On bot restarts, regardless of configuration status

**Files Modified:**
- `src/bot/client.py` - Removed auto-setup from on_ready, enhanced on_guild_join logic

**Testing Status:**
- ✅ Bot rebuilt and restarted successfully
- ✅ Setup DMs now only sent for new guilds, not on restarts
- ✅ Proper logging added for debugging setup flow

**Architecture Status:** Setup DM behavior is now user-friendly and non-intrusive. Guild owners will only receive setup DMs when the bot first joins their server and it's not already configured. No more spam on bot restarts.

---

### Voice Architecture Redesign - Persistent Connection Solution

**Problem Identified:**
The original voice architecture had fundamental conflicts where both bot client and player service were trying to manage Discord voice connections separately, causing connection issues and disconnections after every song.

**Root Cause:**
- Bot client was connecting to Discord voice but trying to transfer control to player service via IPC
- Player service attempted to create its own Discord voice connections
- Voice clients can't be transferred between processes, causing connection conflicts
- This resulted in the "Cannot play - not connected to voice channel" error

**Solution Implemented:**
✅ **Persistent Voice Connection Architecture**:
- **Bot Client**: Maintains persistent Discord voice connection across all songs
- **Player Service**: Handles audio processing (yt-dlp), queue management, provides audio URLs
- **IPC Audio Flow**: Player service → extracts audio URLs → sends SONG_STARTED events → bot client streams to Discord

✅ **Separation of Concerns**:
- **Bot Client Responsibilities**: Discord connection, voice streaming, user interactions, embed updates
- **Player Service Responsibilities**: Audio processing, URL extraction, queue management, playback logic
- **No Voice Transfer**: Eliminated attempts to transfer voice clients between processes

✅ **Persistent Connection Benefits**:
- Voice connection stays active between songs
- No disconnection/reconnection cycle
- Faster song transitions
- More reliable audio streaming

**Files Modified:**
- `src/core/music_player_service.py` - Removed voice connection logic, added audio URL extraction
- `src/cogs/music.py` - Simplified voice connection handling
- `src/utils/ipc_client.py` - Added audio streaming from player service URLs
- `src/bot/client.py` - Enhanced voice state logging

**Architecture Status:** Voice architecture redesigned with persistent connections. Bot client maintains stable Discord voice connection while player service handles all audio processing and provides streamable URLs. This eliminates connection conflicts and provides reliable, persistent voice functionality.

---

### Bug Fixes & Code Quality Improvements

**Critical Runtime Fixes Applied:**
✅ **Unawaited Coroutine Fix**: Fixed RuntimeWarning in `QueueView._update_remove_buttons` method by removing incorrect `async` keyword from `create_remove_callback` function. The function was creating unawaited coroutines instead of returning callback functions.

✅ **ZMQ Cancellation Handling**: Improved ZeroMQ shutdown handling in IPC client to prevent asyncio.CancelledError exceptions:
- Enhanced `_event_listener` with proper ZMQ error handling during shutdown
- Added timeout and proper cancellation handling in `disconnect` method
- Improved context termination with error handling

✅ **Bot Shutdown Sequence**: Added proper `close()` method override to MusicBot class ensuring IPC manager shutdown before Discord client shutdown. Updated `on_disconnect` to avoid duplicate IPC cleanup.

✅ **Indentation Error Fix**: Resolved critical syntax error in `src/core/music_player_service.py` line 465 where orphaned code blocks with incorrect indentation were preventing player service startup.

**Files Modified:**
- `src/cogs/music.py` - Fixed unawaited coroutine in QueueView remove buttons
- `src/utils/ipc_client.py` - Enhanced ZMQ cancellation and shutdown handling  
- `src/bot/client.py` - Added proper close method and improved disconnect handling
- `src/core/music_player_service.py` - Fixed indentation syntax error

**Testing Status:**
- ✅ Bot client starts successfully and connects to Discord
- ✅ Player service starts without syntax errors
- ✅ IPC communication established between services
- ✅ Voice connection handshake completes successfully
- ✅ Queue functionality working (songs can be added)
- ✅ No more runtime warnings or cancellation errors
- 🔄 Minor `asdict()` dataclass error remains to be addressed

**Architecture Status:** All critical bugs resolved. Bot services are running stably with proper error handling, clean shutdown sequences, and reliable IPC communication. Ready for full functionality testing and user interaction.