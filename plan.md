# Discord Music Bot Modernization Plan

## Current Issues
1. **Random Disconnections**: Bot randomly disconnects and reconnects from voice channels
2. **Playback Failure**: Bot won't play songs after disconnection  
3. **Infinite Embed Display**: Now playing embed continues updating even when no song is playing
4. **Legacy Workaround**: Using `source_address: '0.0.0.0'` as a workaround for 4006 websocket errors
5. **Outdated Code**: Not using latest discord.py and yt-dlp best practices

## Root Cause Analysis

### Voice Connection Issues
- No proper reconnection handling when websocket closes (4006 error)
- Voice client state not properly validated before operations
- No recovery mechanism for failed connections
- Using `source_address: '0.0.0.0'` workaround instead of proper error handling

### Playback Issues  
- After disconnection, voice client reference becomes invalid
- No mechanism to recreate voice client after unexpected disconnect
- FFmpeg options using outdated format that may cause stream interruptions
- No proper error recovery in the playback pipeline

### Embed Display Issues
- `NowPlayingDisplay._update_display()` runs infinitely without checking playback state
- No validation if voice client is still playing
- Uses deprecated `datetime.utcnow()` instead of `discord.utils.utcnow()`
- Display task not properly cancelled when playback stops unexpectedly

## Modernization Strategy

### Phase 1: Update Dependencies & Core Libraries

#### 1.1 Update Requirements
```python
discord.py>=2.5.2  # Latest stable version
yt-dlp>=2025.7.21  # Latest version with improved streaming
PyNaCl>=1.5.0     # For voice support
```

#### 1.2 Documentation References
- **discord.py 2.5 Documentation**: https://discordpy.readthedocs.io/en/stable/
- **yt-dlp Documentation**: https://github.com/yt-dlp/yt-dlp#readme
- **discord.py Voice Reference**: https://discordpy.readthedocs.io/en/stable/api.html#voice-related

### Phase 2: Fix Voice Connection Architecture

#### 2.1 Remove 4006 Workaround
- Remove `source_address: '0.0.0.0'` from all yt-dlp configurations
- This workaround is no longer needed with proper connection handling

#### 2.2 Implement Robust Voice Connection Manager
```python
class VoiceConnectionManager:
    """Handles all voice connection operations with automatic recovery"""
    
    async def ensure_connected(self, channel):
        """Ensures bot is connected to voice with retry logic"""
        - Check existing connection validity
        - Implement exponential backoff for reconnection
        - Handle region changes gracefully
        - Validate connection before returning
    
    async def handle_disconnect(self):
        """Handles unexpected disconnections"""
        - Detect disconnection reason
        - Attempt automatic reconnection
        - Restore playback state if needed
```

#### 2.3 Voice State Recovery
- Monitor `on_voice_state_update` for bot disconnections
- Implement connection health checks before each operation
- Add reconnection queue to resume playback after disconnect

### Phase 3: Modernize Audio Streaming

#### 3.1 Update FFmpeg Options
```python
FFMPEG_OPTIONS = {
    'before_options': (
        '-reconnect 1 '
        '-reconnect_streamed 1 '
        '-reconnect_delay_max 5 '
        '-analyzeduration 0 '
        '-loglevel error '
        '-nostats '
    ),
    'options': '-vn -b:a 128k'
}
```

#### 3.2 Implement Stream Resilience
```python
class AudioSource:
    """Wrapper for FFmpegPCMAudio with error recovery"""
    
    def create_source(self, url):
        """Creates audio source with fallback options"""
        - Try primary format
        - Fallback to alternative formats on failure
        - Implement stream validation
        - Add automatic retry on stream failure
```

#### 3.3 Update yt-dlp Configuration
```python
YTDL_OPTIONS = {
    'format': 'bestaudio[acodec=opus]/bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'extract_flat': False,
    'skip_download': True,
    'no_check_certificates': False,
    'prefer_free_formats': True,
    'socket_timeout': 30,
    'retries': 5,
    # Remove source_address - no longer needed
}
```

### Phase 4: Fix Now Playing Display

#### 4.1 Implement Playback State Tracking
```python
class NowPlayingDisplay:
    async def _update_display(self):
        """Update display with state validation"""
        while self.should_continue():
            if not self.is_playing():
                await self.stop()
                break
            await self.update_embed()
            await asyncio.sleep(5)
    
    def should_continue(self):
        """Check if display should continue updating"""
        - Validate voice client exists
        - Check if actually playing
        - Verify message still exists
```

#### 4.2 Fix Timezone Issues
- Replace all `datetime.utcnow()` with `discord.utils.utcnow()`
- Ensure timezone-aware datetime operations

#### 4.3 Add Cleanup Handlers
- Properly cancel update tasks on stop
- Remove orphaned embeds on bot restart
- Add timeout for stale displays

### Phase 5: Implement Error Recovery System

#### 5.1 Global Error Handler
```python
class ErrorRecovery:
    async def handle_playback_error(self, error):
        """Handles playback errors with recovery strategies"""
        - Log error details
        - Attempt recovery based on error type
        - Skip to next song if unrecoverable
        - Notify users of issues
```

#### 5.2 Connection Monitor
```python
class ConnectionMonitor:
    async def monitor_health(self):
        """Continuously monitors connection health"""
        - Regular ping checks
        - Detect stale connections
        - Trigger reconnection when needed
        - Track connection metrics
```

### Phase 6: Optimize Queue Management

#### 6.1 Implement Queue Persistence
- Save queue state on disconnect
- Restore queue on reconnect
- Add queue validation

#### 6.2 Preloading Optimization
- Validate URLs before playback
- Cache extraction results
- Implement smart preloading based on queue size

### Phase 7: Testing & Validation

#### 7.1 Test Scenarios
1. **Disconnection Recovery**: Force disconnect and verify auto-recovery
2. **Long Playback**: Test 1+ hour continuous playback
3. **Region Changes**: Test voice region changes during playback
4. **Network Interruptions**: Simulate network issues
5. **Concurrent Operations**: Test multiple commands simultaneously

#### 7.2 Performance Metrics
- Monitor memory usage over time
- Track reconnection frequency
- Measure playback reliability
- Log error rates

## Implementation Priority

### Critical (Fix Immediately)
1. Remove `source_address` workaround ✅
2. Fix NowPlayingDisplay infinite loop ✅
3. Implement voice connection validation ✅
4. Update FFmpeg options ✅

### High Priority (Core Functionality)
1. Implement VoiceConnectionManager
2. Add playback state tracking
3. Create error recovery system
4. Fix timezone issues

### Medium Priority (Stability)
1. Add connection monitoring
2. Implement queue persistence
3. Optimize preloading
4. Add comprehensive logging

### Low Priority (Enhancements)
1. Add metrics collection
2. Implement advanced caching
3. Add connection pooling
4. Create diagnostic commands

## Success Criteria
- ✅ Bot maintains stable connection for 24+ hours
- ✅ Automatic recovery from disconnections within 10 seconds
- ✅ Now playing embed stops when playback ends
- ✅ No 4006 errors or connection issues
- ✅ Smooth playback without interruptions
- ✅ Memory usage remains stable over time

## Code Quality Standards
- Type hints for all functions
- Comprehensive error handling
- Async/await best practices
- Proper resource cleanup
- Extensive logging for debugging
- Unit tests for critical components

## Migration Notes
- Backup current configuration before changes
- Test in development environment first
- Implement changes incrementally
- Monitor logs during initial deployment
- Have rollback plan ready

## Resources
- [discord.py Voice Guide](https://discordpy.readthedocs.io/en/stable/discord.html#voice-related)
- [yt-dlp Extractors](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)
- [FFmpeg Streaming Guide](https://trac.ffmpeg.org/wiki/StreamingGuide)
- [Discord Voice Gateway](https://discord.com/developers/docs/topics/voice-connections)
