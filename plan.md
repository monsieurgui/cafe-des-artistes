## Epic: Resolve Discord Voice 4006 Disconnect Loop

### Story 1: Establish Dependency & Documentation Baseline
- Capture latest `yt-dlp` release notes and voice-related guidance; summarize actionable changes in `memory.md`.
- Inventory current dependency versions from `src/requirements.txt` (discord.py, aiohttp, PyNaCl, websockets, yt-dlp) and record in `memory.md`. ✅ (2025-09-27)
- Research newest stable versions for each voice-critical dependency and note compatibility or migration flags. ✅ (2025-09-27)
- Plan the dependency update sequence (order of upgrades, required virtualenv rebuild, validation steps). ✅ (2025-09-27)

### Story 2: Audit Existing Voice Connection Lifecycle
- Trace the voice connection flow starting at `MusicPlayer.ensure_voice_client()` through `VoiceConnectionManager.ensure_connected()`; document hand-offs and assumptions. ✅ (2025-09-27)
- Review `VoiceConnectionManager` reconnection/backoff logic for gaps (e.g., missing jitter, stale channel tracking) and flag issues. ✅ (2025-09-27)
- Inspect `core/event_handlers.py` voice state handlers to confirm disconnect, move, and resume flows; identify missing websocket close code handling. ✅ (2025-09-27)
- Map out how current logging captures websocket close codes (4006) and list required instrumentation upgrades. ✅ (2025-09-27)

### Story 3: Design Robust Reconnection & Telemetry Improvements
- Define data the bot must persist (voice channel IDs, reconnect attempts, queue state) to recover after 4006 disconnects. ✅ (2025-09-27)
- Specify enhancements for exponential backoff with jitter, attempt resets, and guild-level cool-downs in `VoiceConnectionManager`. ✅ (2025-09-27)
- Outline logic to detect Discord close code 4006, differentiate fatal vs transient closures, and trigger targeted recovery actions. ✅ (2025-09-27)
- Plan detailed logging/metrics (guild ID, close code, latency) and alerting hooks to diagnose recurrent failures. ✅ (2025-09-27)

### Story 4: Prepare Testing & Rollout Strategy
- Enumerate manual scenarios to validate reconnection resilience (forced disconnects, channel moves, voice region changes, network blips).
- Determine automated test coverage or mocks needed to simulate websocket close codes and reconnection paths.
- Define success criteria and rollback plan for dependency upgrades and reconnection changes.
- Schedule documentation updates (README, operator runbooks) covering new recovery behaviors and monitoring expectations.
