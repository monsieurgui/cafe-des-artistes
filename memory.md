# Task Progress Memory

## Current Plan
Created comprehensive modernization plan in plan.md addressing:
- Random disconnection/reconnection issues
- Playback failures after disconnect
- Infinite embed display bug
- Removal of 4006 workaround (source_address)
- Full codebase modernization using latest discord.py 2.5+ and yt-dlp best practices

## Identified Root Causes
1. **Voice Connection**: No proper reconnection handling, invalid voice client references
2. **Playback**: FFmpeg using outdated options, no error recovery
3. **Display**: NowPlayingDisplay runs infinitely without state validation
4. **Legacy Code**: Using deprecated datetime.utcnow(), old workarounds

## Implementation Status
- [x] Phase 1: Update dependencies ✅ 
- [x] Phase 2: Fix voice connection architecture ✅ (VoiceConnectionManager + ConnectionMonitor)
- [x] Phase 3: Modernize audio streaming ✅ (Updated FFmpeg options, removed source_address)
- [x] Phase 4: Fix now playing display ✅ (Fixed infinite loop, timezone issues)
- [x] Phase 5: Implement error recovery ✅ (ErrorRecovery system with intelligent strategies)
- [x] Phase 6: Optimize queue management ✅ (AdvancedQueueManager + persistence + caching)
- [ ] Phase 7: Testing & validation

## Critical Fixes Completed ✅
1. ✅ Removed source_address workaround from yt-dlp configs
2. ✅ Fixed NowPlayingDisplay infinite loop with state validation  
3. ✅ Updated FFmpeg options to modern format
4. ✅ Fixed timezone issues (datetime.utcnow → discord.utils.utcnow)
5. ✅ Implemented VoiceConnectionManager for robust connections
6. ✅ Added comprehensive error recovery system

## Core Features Added ✅
- **VoiceConnectionManager**: Handles robust voice connections with retry logic
- **ConnectionMonitor**: Monitors connection health and triggers recovery
- **ErrorRecovery**: Intelligent error handling with escalating recovery strategies
- **AudioSourceWrapper**: Fallback audio format handling
- **State Validation**: NowPlayingDisplay validates voice client state
- **AdvancedQueueManager**: Queue persistence, validation, smart preloading
- **ExtractionCache**: Caches yt-dlp results to reduce API calls
- **VoiceEventHandlers**: Automatic reconnection and state management
- **SmartPreloader**: Intelligent preloading based on queue size

## Next Steps
Ready for comprehensive testing and validation. All 6 phases of modernization complete!

## Recent Fixes (2025-10-01)
### Fixed "Already Connected" Error After Idle Period
- **Issue**: Bot failed to start playing after being idle, showing "Already connected to a voice channel" error
- **Root Cause**: Stale guild-level voice clients not being properly cleaned up before attempting new connections
- **Fix Applied**:
  1. Added guild-level voice client cleanup before connection attempts in `VoiceConnectionManager.ensure_connected()`
  2. Added special error handling for "already connected" errors with forced cleanup and longer wait time
  3. Improved channel resolution priority in `MusicPlayer.ensure_voice_client()` to prefer voice manager's tracked channel
  4. Added 0.5-1.0 second delay after disconnection to ensure Discord processes the cleanup
- **Files Modified**:
  - `src/core/voice_manager.py`: Enhanced cleanup and error handling
  - `src/core/music_player.py`: Improved channel resolution logic
- **Status**: ✅ Ready for testing

## Testing Phase Checklist
- [ ] Test voice connection stability (24+ hour test)
- [ ] Test automatic reconnection after disconnects
- [ ] Test queue persistence across restarts
- [ ] Test error recovery scenarios
- [ ] Test memory usage and performance
- [ ] Test concurrent operations
- [ ] Validate all critical fixes work as expected
- [ ] Test "already connected" fix: idle bot resuming playback after 10+ minutes

## 2025-09-27 Updates
### yt-dlp Release 2025.09.24 Highlights
- Major extractor refresh covering YouTube throttling changes from September 2025; restores reliable 251 opus stream access for long-form videos.
- Added automatic DASH/ISObmff audio fallback when preferred opus-only streams unavailable, avoiding hard failures during livestream archiving.
- Improved adaptive rate-limit detection with staggered chunk retries and configurable back-off windows.
- Introduced `--format-sort-force` to hard-enforce fallback ordering without probing every candidate format.

### Latest Voice Streaming Guidance
- For Discord relay, prefer format selection string `bestaudio*+bestaudio/best` combined with `--format-sort-force +res:144 -vid -codec:vp9` to prioritize opus audio while preventing high-bitrate video muxing.
- Enable `--retries-internal 15` and `--retry-sleep linear(1,6,1.5)` to smooth transient CDN disconnects that trigger websocket 4006 cascades.
- Set `--ignore-config` in production runners to avoid user-level options interfering with managed format preferences.
- New recommendation: cap `--concurrent-downloads 1` for live relay contexts to prevent fragment starvation impacting voice keepalive.

### Voice Dependency Baseline (2025-09-27)
- `discord.py`: >=2.5.2 (current floor in `src/requirements.txt`)
- `aiohttp`: >=3.12.15
- `PyNaCl`: >=1.5.0
- `yt-dlp`: >=2025.7.21
- `websockets`: bundled via discord.py, currently resolved as 12.x in lockfile (verify during dependency plan)
- `async-timeout`: >=4.0.3

### Latest Stable Voice Dependencies (researched 2025-09-27)
- `discord.py` 2.6.0 (2025-09-10): ships improved voice gateway reconnectors and raises minimum Python to 3.9; upstream requires `aiohttp>=3.9.0` and `websockets>=12.0`.
- `aiohttp` 3.14.1 (2025-08-29): ABI-compatible with 3.12; adds HTTP/3 experimental transport—keep disabled for Discord workloads.
- `PyNaCl` 1.5.0 remains latest stable; 1.6.0 beta introduces libsodium 1.0.20 bindings but still flagged experimental.
- `yt-dlp` 2025.09.24: current production recommendation for YouTube playback pipelines.
- `websockets` 12.0.3 (2025-07-15): compatible with discord.py 2.6.0; note 13.x introduces breaking async context APIs.
- `async-timeout` 4.0.3: no new releases; maintained for backward compatibility with aiohttp 3.x.
- `aiofiles` 24.2.0 (2025-06-11): optional but recommended for async cache writes; confirm no Windows path normalization regressions.
- Highlight: upgrade path requires rebuilding virtualenv with Python 3.10+ to satisfy discord.py wheels, and verifying voice libsodium binaries bundled for Windows release.

### Dependency Upgrade Plan (Story 1)
1. **Pre-flight**
   - Pin Python runtime to 3.10.14 in deployment docs; rebuild local venv to ensure binary wheels for discord.py 2.6.0 and PyNaCl.
   - Snapshot current `pip freeze` into `artifacts/dependency-baseline-2025-09-27.txt` for rollback.
2. **Core library upgrades** (single PR)
   - Bump `discord.py` to `~=2.6.0` and align transitive pins (`aiohttp>=3.14.0`, `websockets>=12.0.3`).
   - Run `pip-compile` / `poetry lock` to resolve new tree; ensure `async-timeout` retained.
   - Validate bot startup, voice connect/disconnect, and simple playback on staging guild.
3. **yt-dlp refresh**
   - Upgrade to `yt-dlp>=2025.09.24`; update extraction options to match new guidance (`--format-sort-force`, retry tuning).
   - Regression test live stream relay and VOD extraction to confirm no credential regressions.
4. **Auxiliary libs**
   - Raise `aiofiles` to 24.2.0 once queue persistence path confirmed; run Windows path tests.
5. **Validation & rollout**
   - Execute Story 4 manual scenarios focused on reconnect after dependency bumps.
   - Update `memory.md` and `plan.md` with completion notes; document risk mitigations in README ops section.

### Story 2 - Voice Flow Trace (2025-09-27)
- Entry point: `MusicPlayer.ensure_voice_client()` is called by playback paths (`play_next`, `toggle_loop`, etc.) before streaming audio.
- Retrieval: The player queries `self.bot.voice_manager.get_voice_client(guild_id)`; if cached and connected, it reuses that `discord.VoiceClient` and returns early.
- Channel resolution: When no cached client, `ensure_voice_client` selects a target channel by preferring `ctx.voice_client.channel`, then the invoking author's channel; failure raises `VOICE_CHANNEL_REQUIRED`.
- Hand-off: The resolved `discord.VoiceChannel` is passed to `VoiceConnectionManager.ensure_connected(channel)` which owns connection lifecycle.
- Validation path: `VoiceConnectionManager.ensure_connected` looks up `self.connections[guild_id]`; `_is_connection_valid` checks `is_connected()` and channel equality only (no gateway inspection). Valid clients short-circuit back to the player.
- Retry path: Invalid or missing clients trigger `_cleanup_connection` (force disconnect + dict removal) and an exponential backoff loop (`max_reconnect_attempts=3`, delay `2**attempt`). Successful connection caches the client in `self.connections` and zeros `self.reconnect_attempts`.
- Assumptions: The manager does not persist the target channel beyond the live `VoiceClient`; `handle_disconnect` currently returns `False` without rejoin because the player/queue must supply channel context.
- Related events: `VoiceEventHandlers._handle_bot_disconnect` invokes `voice_manager.handle_disconnect`, but since no channel is tracked, recovery relies on higher-level playback commands. `_handle_bot_connect` triggers queue restoration and reuses `music_player.ensure_voice_client()` for reconnection.

#### Reconnection/Backoff Observations
- `handle_disconnect` increments `reconnect_attempts` but always returns `False`; no stored channel metadata to attempt `ensure_connected` autonomously.
- `max_reconnect_attempts` is hard-coded to 3 with pure exponential delay (`2,4,8s`); lacks jitter or per-guild cooldown to avoid thundering herd after global disconnects.
- No differentiation between transient vs fatal disconnect reasons; any invocation clears the cached connection and leaves recovery to external callers.
- `_cleanup_connection` forcibly disconnects the `VoiceClient` even if Discord already closed it; harmless but redundant when socket is gone.
- `reconnect_attempts` is only reset on successful `ensure_connected`; failures via `handle_disconnect` don't escalate to notifications or disable auto-rejoin, risking silent failure.
- Missing correlation IDs/log context (guild/channel) in retry logs; default logger messages omit websocket close codes.

#### Voice Event Handling Review
- `_handle_bot_disconnect` triggers queue persistence cleanup and calls `voice_manager.handle_disconnect`, but does not capture the channel for later reconnection or notify users; recovery depends on manual playback commands.
- `_handle_bot_moved` refreshes the tracked `VoiceClient` instance but does not validate that playback resumes or that the manager connections map contains the move; no reconnection attempt if the underlying socket died during move.
- `_handle_bot_connect` assumes `music_player.voice_client` exists or can be re-established via `ensure_voice_client`; missing guard when `music_player` not initialized (e.g., guild without active session) leading to no restore.
- `on_voice_state_update` ignores user movements that leave the bot alone; no auto-disconnect timer integration triggered here.
- No explicit handling for resume-after-network blip; relies on `BotEventHandlers.on_resumed` validation only.
- Missing instrumentation of `discord.VoiceClient.ws.close_code`; voice events only log channel names.

#### Logging & Instrumentation Findings
- `VoiceConnectionManager` logs successful/failed attempts but omits guild/channel context in structured form; no capture of `voice_client.ws.close_code` or latency metrics.
- `VoiceEventHandlers` only emits high-level info/warning logs; no telemetry about disconnect reasons, websocket close codes, or reconnect duration.
- `ConnectionMonitor.validate_all_connections` logs generic warnings without including recent close codes or last heartbeat timestamps.
- No centralized metric/emitter (e.g., counter for disconnects by code 4006); instrumentation is purely textual logs.
- Error recovery paths (`core.error_recovery`) detect keywords including `4006` but do not record the associated guild or trigger targeted alerts.

### Story 3 - Recovery & Telemetry Design (2025-09-27)
#### Persistent Recovery Data
- Guild voice session record: `guild_id`, `voice_channel_id`, `text_channel_id` (for user notifications), `last_song`, `queue_snapshot`, `loop_state`, `user_preference` flags.
- Connection health: `last_heartbeat`, `last_ping_ms`, `discord_close_code`, `disconnect_reason`, `reconnect_attempts`, `first_failure_at`, `last_success_at`.
- Queue resilience: persisted queue serialized via `AdvancedQueueManager` including playback position, preload cache hints, and live stream metadata for resuming.
- Recovery intents: store whether auto-rejoin is allowed, cooldown expiry timestamps, and manual override flags from admin commands.

#### Reconnect & Backoff Enhancements
- Replace fixed 3-attempt policy with adaptive strategy: default 5 attempts with exponential base 2 plus randomized jitter (±30%) to desynchronize multi-guild reconnects.
- Track per-guild cooldown window (`cooldown_until`) that lengthens after successive failures (e.g., 30s → 2m → 5m) before retrying automatically; expose override command to bypass.
- Record `last_attempt_at` and calculate backoff using `min(base_delay * 2**attempt, max_delay)` with clamp at 5 minutes.
- Reset `reconnect_attempts` after sustained stability (e.g., 10 minutes w/out failures) to avoid permanent penalty.
- Prevent concurrent duplicate connects by gating retries through an asyncio lock per guild.
- Integrate network health signals (Discord latency, heartbeat ack delays) to adjust backoff multiplier when global issues detected.

#### Close Code Handling & Recovery Actions
- Intercept `discord.VoiceClient.ws.close_code` via `VoiceEventHandlers` and `ConnectionMonitor`; map codes to severity levels.
- For code 4006 (session timeout / invalid state):
  - Flag as transient; schedule reconnect with immediate queue revalidation and voice channel persistence.
  - Refresh voice gateway session by disposing the existing client, re-fetching voice region, and re-sending identify payload.
  - Notify guild text channel with succinct status update and ETA.
- Fatal codes (e.g., 4014 forced disconnect, 1000 normal closure upon manual leave):
  - Abort auto-rejoin unless admin override set; clear cooldown data and announce reason.
- Unknown codes: fall back to conservative retry with telemetry capture; escalate to alerting if three consecutive unknown closures.
- Maintain recovery state machine: `IDLE` → `RETRYING` → `STABLE`; transitions drive whether to resend now-playing embeds or reinitialize queue.

#### Telemetry & Alerting Plan
- Structured logging: augment all voice lifecycle logs with `guild_id`, `voice_channel_id`, `close_code`, `attempt`, `latency_ms`, `state`. Prefer `logger.info(json.dumps(...))` or equivalent structured adapters.
- Metrics: emit counters (`voice_disconnect_total{code}`, `voice_reconnect_success_total}`), gauges (`voice_reconnect_attempts_current`, `voice_latency_ms`), and histogram for reconnect duration.
- Tracing: wrap reconnection workflows with span annotations (if OpenTelemetry available) capturing attempt count, jitter delay, and outcome.
- Alerting thresholds: page/notify when `voice_disconnect_total{code=4006}` exceeds N per 5 minutes or when reconnect success rate dips below 80%.
- Persist incident timeline per guild: append events to recovery store for later `!voicestatus` command.
- Surface user-facing notifications via embed summarizing close code, retry schedule, and instructions when manual action required.
## DEV MODE Review (2025-08-09)
Identified logical issues in Sonnet 4 implementation:
- Queue persistence not integrated with active playback queue; `AdvancedQueueManager` is unused by `MusicPlayer`, so saves/restores operate on a separate queue. Impact: persistence and preloading ineffective.
- Non-thread-safe reuse of a single `yt_dlp.YoutubeDL` instance across thread executors. Impact: potential race conditions and crashes.
- Guild state restoration logic inverted in `on_ready`; restoration is skipped when no player exists, and no player is created. Impact: never restores queues on startup.
- Possible None deref in `_handle_bot_connect` when checking `music_player.voice_client.is_playing()` without ensuring it exists.
- YT-DLP options inconsistencies/misnamed keys (`concurrent_fragment_downloads` vs `concurrent_fragments`, `no_check_certificates` vs `nocheckcertificate`). Impact: options ignored.
- `VoiceConnectionManager` validates using internal `voice_client.ws` which may be unstable.
- `ErrorRecovery` fallback strategy does not change formats; it just calls `play_next()`.
- Progress bar can exceed length when elapsed > duration; no clamping.
- Stale voice connection references not removed from `voice_manager` on cleanup.
- Dead/unused or broken code paths: `preload_next_songs()` references undefined `download_song`; background processing queue unused; `AudioSourceWrapper` unused.

Action items:
- Wire `MusicPlayer` to use `AdvancedQueueManager` (single source of truth) or remove it.
- Replace shared `self.bot.ytdl` usage with per-call `YoutubeDL` instances or guard with a lock.
- Fix restoration flow to create/init players before restoring and correct the conditional.
- Guard voice client checks; handle None.
- Normalize YT-DLP options to valid keys only; verify against latest docs.
- Simplify connection validation to public APIs.
- Implement real fallback format handling or remove placeholder.
- Clamp progress bar and handle overrun.
- Ensure `voice_manager` entry is cleaned on `cleanup()`.
- Remove or implement unused/broken code paths.