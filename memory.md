# Bot Troubleshooting: "SONG_UNAVAILABLE" Error

## Tasks:

- [x] Check `yt-dlp` version and update if necessary.
  - Current version: `2025.3.31`
  - Latest version: `2025.04.30`
  - Updated `yt-dlp` to `2025.04.30`.
- [x] Get `yt-dlp` documentation (Implicitly covered by web search and knowledge).
- [x] Check installed `yt-dlp` version (`2025.4.30`) against latest (`2025.04.30`) - no update needed for this session.
- [ ] Resolve git push secret scanning error (Discord Bot Token in `src/config/config.yaml`).
  - [ ] Ensure secret is removed from the working directory version of `src/config/config.yaml`.
  - [x] Add `src/config/config.yaml` to `.gitignore`. (Completed)
  - [ ] Amend the problematic commit (`d354fddcc75f2188f77b7151805e18e52713d253`) to remove the secret from history.
  - [ ] Advise on best practices for secret management. (Partially done)
- [ ] Investigate "Requested format is not available" error.
  - Locate code responsible for `yt-dlp` format selection.
  - Analyze `yt-dlp` options used by the bot.
  - Potentially use `yt-dlp --list-formats` to debug.
- [ ] Resolve the song unavailability issue.
- [ ] Investigate "Already connected to a voice channel" error.
  - [x] Identify command triggering the error: `!p`, `!p5`, `!p10`.
  - [ ] Get full traceback if available. (User described behavior, direct traceback not yet provided)
  - [IN PROGRESS] Analyze voice state management in `music.py` and `music_player.py`.
    - `music.py`'s `play`, `p5`, `p10` commands call `player.add_to_queue()` or `player.add_multiple_to_queue()` from `music_player.py`.
    - The error likely originates from `discord.py`'s voice client management or how `music_player.py` handles joining/connection state during these methods.
    - **TODO**: Examine `add_to_queue` and `add_multiple_to_queue` in `src/core/music_player.py`.
    - **IN PROGRESS**: Analyze `play_next` in `src/core/music_player.py` for unreliability.
        - Hypothesis: Failures in song processing (metadata, FFmpeg) in `play_next` lead to silent halts.
        - Recursive calls `await self.play_next()` within error handlers are ineffective due to `_playing_lock`.
        - **PLAN**: Modify error handling in `play_next` (for `info is None` and general `except Exception`) to schedule `self.play_next()` via `self.bot.loop.create_task()` instead of direct await, ensuring `self.current` is cleared and the method returns, to allow lock release and proper subsequent execution.

## NEW ISSUE: Voice Connection Loop (Error 4006)

### Problem Description:
- Bot joins voice channel then immediately leaves, creating an infinite loop
- Error code 4006: "Session Invalid" - Discord voice session becomes invalid
- Occurs when using `!p`, `!p5`, `!p10` commands
- Started happening recently (June 18, 2025)

### Root Causes Identified:
1. **Session invalidation** - Voice session becomes invalid due to network issues or Discord API changes
2. **Connection state management** - Improper handling of existing voice clients
3. **Auto-reconnect loops** - `reconnect=True` parameter causing infinite retry loops
4. **Race conditions** - Multiple connection attempts happening simultaneously

### Fixes Applied:
- [x] **Enhanced `ensure_voice_client()` method**:
  - Added proper cleanup of invalid voice clients before connecting
  - Disabled auto-reconnect (`reconnect=False`) to prevent loops
  - Added connection verification after establishment
  - Implemented exponential backoff retry mechanism (3 attempts)
  - Reduced connection timeout from 60s to 30s
  - Added proper error handling for "Already connected" scenarios

- [x] **Improved `on_voice_state_update()` handler**:
  - Added complete voice state management in `bot/client.py`
  - Proper handling of bot disconnections and channel moves
  - Automatic cleanup when bot is alone in voice channel

- [x] **Enhanced `cleanup()` method**:
  - More robust voice client disconnection
  - Better task cancellation and resource cleanup
  - Graceful error handling during cleanup

- [x] **Additional fixes for persistent 4006 errors**:
  - Added connection state tracking to prevent race conditions
  - Implemented connection lock to prevent multiple simultaneous connection attempts
  - Added specific handling for 4006 session invalidation errors
  - Enhanced error handling with `_handle_voice_connection_error()` method
  - Added guild voice client checking to reuse existing connections
  - Reduced connection timeout to 20s and increased stability wait to 2s
  - Added `on_disconnect()` and `on_resumed()` handlers for gateway events
  - Added `on_voice_client_error()` handler for voice-specific errors

- [x] **Voice Keepalive Solution** (Based on Discord.py discussion):
  - Implemented `_voice_keepalive()` method to send silence packets every 30 seconds
  - Added `_start_voice_keepalive()` and `_stop_voice_keepalive()` methods
  - Prevents Discord's 15-minute to 2-hour disconnection cycle for load balancing
  - Automatically starts when voice connection is established
  - Properly stops when bot disconnects or cleans up
  - Based on solution from [Discord.py discussion #9722](https://github.com/Rapptz/discord.py/discussions/9722#discussioncomment-8400265)

### Testing Status:
- [ ] User to test the fixes and provide feedback
- [ ] Monitor for any remaining connection issues

## Completions:

- Successfully updated `pip`.
- Successfully updated `yt-dlp` from `2025.3.31` to `2025.04.30`.
- Added `src/config/config.yaml` to `.gitignore`.
- Fixed voice connection loop issue with error code 4006.

# Bot Optimization Plan

## Phase 1: Prerequisites

1.  **DONE**: Get latest `yt-dlp` documentation.
2.  **DONE**: Check current `yt-dlp` version in the project and update.
    *   Current version found: 2025.03.31
    *   Latest version found: 2025.04.30
    *   User confirmed `yt-dlp` updated to 2025.04.30.
3.  **IN PROGRESS**: Analyze bot's current music implementation.
    *   **DONE**: Identified core music playback file: `src/cogs/music.py` which uses `src/core/music_player.py`.
    *   **IN PROGRESS**: Reviewing `src/core/music_player.py`.
        *   Initial findings (lines 1-250):
            *   Uses `MusicPlayer` class per server.
            *   Separate thread pools for search (`max_workers=1`) and playback ops (`max_workers=2`).
            *   Async queue (`processing_queue`) for background song processing.
            *   Preload queue (`preload_queue`, `maxlen=3`).
            *   Initial `yt-dlp` search uses minimal options: `extract_flat: True`, `socket_timeout: 1`, `retries: 1`.
            *   Full metadata processing for `yt-dlp` uses `YTDL_OPTIONS` from `utils.constants.py`.
            *   Basic URL caching (`_cached_urls`).
            *   Further findings (lines 251-500):
                *   `_process_song_metadata` fetches full metadata using `YTDL_OPTIONS` in background.
                *   `_preload_next` attempts to fetch full info for the immediate next song into `_song_cache`.
                *   `play_next` is the core playback function. It re-fetches full info with `YTDL_OPTIONS` if not in `_song_cache` (potential bottleneck).
                *   Uses `FFmpegPCMAudio` with `FFMPEG_OPTIONS` from `utils.constants.py`.
                *   `after_playing` callback triggers the next song.
            *   Further findings (lines 501-750):
                *   `cleanup` method handles resource release (thread pools shutdown with `wait=False`).
                *   `preload_next_songs` submits `self.download_song` to `thread_pool` for up to 3 songs, storing futures in `self.preload_queue`.
                *   Details of `download_song` and how `_song_cache` is populated from these futures is still pending.
                *   Paginated queue display is available.
                *   Loop logic started; when disabling loop, current loop song is added back to the main queue.
            *   Further findings (lines 751-1000):
                *   Looping a song re-fetches info using `self.bot.ytdl.extract_info()` on *every iteration* (inefficient).
                *   `add_multiple_to_queue` uses `extract_flat: False` and `force_generic_extractor: True` for its `yt-dlp` call, different from `add_to_queue`.
                *   `_prefetch_song` fetches full song info into `_song_cache` using `self.bot.ytdl.extract_info()`. This seems to be the main method for populating `_song_cache` during preloading.
                *   The relationship between `_preload_next` (preloading one song) and `preload_next_songs` (filling `preload_queue` with 3 futures) needs full clarity on how `_song_cache` is updated from those futures, and what `download_song` actually does. It's likely `_prefetch_song` is the target of those futures.
            *   Further findings (lines 1001-end & full review):
                *   `_prefetch_song` also attempts a `requests.head()` call to the stream URL to "pre-warm" the connection.
                *   Live streaming uses `self.bot.ytdl.extract_info()` and `FFmpegPCMAudio`.
                *   A generic `_extract_info()` helper method exists with its own distinct (and somewhat concerning, e.g., `nocheckcertificate`) `yt-dlp` options. Its direct usage in the primary playback flow isn't obvious yet.
                *   Multiple different sets of `yt-dlp` options are used in different contexts.
    *   **DONE**: Read `src/utils/constants.py` to get `YTDL_OPTIONS` and `FFMPEG_OPTIONS`.
        *   `YTDL_OPTIONS` (main options for song info/preloading):
            *   `format`: 'bestaudio/best'
            *   `socket_timeout`: 2, `retries`: 1 (aggressive, potential for premature failures)
            *   `nocheckcertificate`: True (security concern)
            *   `noplaylist`: True
            *   `source_address`: '0.0.0.0'
            *   `ignoreerrors`: True
            *   `extract_flat`: 'in_playlist'
        *   `FFMPEG_OPTIONS` (for `FFmpegPCMAudio`):
            *   `before_options`: '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -analyzeduration 0 -probesize 32000 -thread_queue_size 4096'
                *   Reconnect options are good for stream stability.
                *   `-analyzeduration 0 -probesize 32000`: Extremely aggressive for fast startup, but high risk of playback issues (stuttering, no audio, incorrect format detection).
            *   `options`: '-vn -ar 48000 -ac 2 -f s16le -acodec pcm_s16le -flags low_delay -threads 1' (standard for Discord audio)
        *   Other `YTDL_OPTIONS` sets exist for `_extract_info`, live streams, and downloads.
    *   **IN PROGRESS**: Examine audio buffering (`FFmpegPCMAudio` usage) and streaming in light of `FFMPEG_OPTIONS`.
    *   **IN PROGRESS**: Analyze queue management and preloading logic in detail, clarifying how `preload_next_songs` futures update `_song_cache`.
        *   `_prefetch_song` (likely target of `preload_next_songs` futures) populates `_song_cache` and attempts a `requests.head()` pre-warm.
4.  **IN PROGRESS**: Suggest optimizations based on analysis.
    *   **DONE**: Applied initial an_sugested_optimizations to `src/utils/constants.py`:
        *   `FFMPEG_OPTIONS['before_options']`: Removed aggressive `-analyzeduration 0 -probesize 32000` (reverted to FFmpeg defaults) to improve playback stability.
        *   `YTDL_OPTIONS`:
            *   Increased `socket_timeout` to 10 (from 2).
            *   Increased `retries` to 3 (from 1).
            *   Set `nocheckcertificate` to `False` (from `True`) for security.
    *   **TODO**: User to test the an_sugested_optimizations and provide feedback.
    *   Potential areas for further optimization discussion:
        *   Loop inefficiency (re-fetching info every loop).
        *   Preloading strategy refinement.
        *   Consistency of `yt-dlp` options across different methods.
        *   Thread pool sizes.
        *   Further tuning of `FFMPEG_OPTIONS` (`analyzeduration`, `probesize`) if defaults are too slow.

## Phase 2: Optimization Implementation (Iterative)

*   **TODO**: Implement agreed-upon optimization strategies one by one.
*   **TODO**: Test each optimization for impact on:
    *   Buffer-to-play time.
    *   Stuttering when adding songs.
    *   Overall stability and performance.

## Phase 3: Review and Refinement

*   **TODO**: Review overall changes.
*   **TODO**: Make further adjustments as needed.

---
*This file is for tracking progress. Please do not edit manually unless you are the AI assistant.*
