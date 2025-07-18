# User-Facing Messages Catalog

This document catalogs all existing user-facing messages in the Cafe des Artistes Bot for Epic 5 implementation.

## Command Response Messages

### `/play` Command
**Current Messages:**
- Success: `MESSAGES['SONG_ADDED']` - "✅ {title} ajoutée à la queue ({queue_size} dans la queue)"
- Success (now playing): `"Now playing: {song_title}"`
- Error: Generic error embed with `MESSAGES['ERROR_TITLE']` - "❌ Erreur"
- Error: Voice channel required: `MESSAGES['VOICE_CHANNEL_REQUIRED']` - "Ça prend un channel"

**Proposed Ephemeral Messages:**
- Initial: `⏳ Searching for your song...`
- Success: `✅ Added [Song Title] to the queue.`
- Error: `❌ You must be in a voice channel to use this command.`
- Error: `❌ Song not found or unavailable.`

### `/skip` Command
**Current Messages:**
- Success: `MESSAGES['SKIPPED']` - "Skippé"
- Error: `MESSAGES['NOTHING_PLAYING']` - "Rian joue mon'homme"

**Proposed Ephemeral Messages:**
- Success: `✅ The current song has been skipped.`
- Error: `⚠️ The queue is already empty, there is nothing to skip.`

### `/leave` Command
**Current Messages:**
- Success: `MESSAGES['GOODBYE']` - "On s'revoit bein tôt mon t'cham! 👋"
- Error: Generic error embed

**Proposed Ephemeral Messages:**
- Success: `✅ Disconnected from the voice channel.`
- Error: `❌ Bot is not connected to a voice channel.`

### `/p5` Command
**Current Messages:**
- Success: Same as `/play` but for 5 repetitions
- Error: Same as `/play`

**Proposed Ephemeral Messages:**
- Initial: `⏳ Searching for your song...`
- Success: `✅ Added [Song Title] to the queue (5 times).`
- Error: Same as `/play`

### `/reset` Command
**Current Messages:**
- Success: `MESSAGES['QUEUE_PURGED']` - "Purge complete de la queue"
- Error: Generic error embed

**Proposed Ephemeral Messages:**
- Success: `✅ The player has been reset. The queue is now empty.`
- Error: `❌ Failed to reset the player.`

### `/setup` Command
**Current Messages:**
- Permission Error: "You need Administrator permissions to use this command."
- Already Setup: "This server is already set up! The control panel is active."
- DM Success: "📨 I've sent you a DM with setup instructions. Please check your direct messages!"
- DM Error: "I couldn't send you a DM. Please enable DMs from server members and try again."

**Proposed Ephemeral Messages:**
- Permission Error: `❌ You do not have the required permissions to use this command.`
- Already Setup: `ℹ️ This server has already been set up. The control panel is in #[channel_name].`
- DM Success: `✅ Setup instructions sent to your DMs.`
- DM Error: `❌ Cannot send DM. Please enable direct messages and try again.`

### `/queue` Command
**Current Messages:**
- Empty Queue: `MESSAGES['QUEUE_EMPTY_SAD']` - "La queue est dead 😢"
- Success: Shows queue embed (public)

**Proposed Ephemeral Messages:**
- Success: `ℹ️ Current queue displayed above.`
- Empty: `ℹ️ The queue is currently empty.`

### `/support` Command
**Current Messages:**
- Success: `MESSAGES['SUPPORT_SENT']` - "✅ Votre message a été envoyé au god du bot!"
- Error: `MESSAGES['SUPPORT_ERROR']` - "Impossible d'envoyer le message de support. Veuillez réessayer plus tard."

**Proposed Ephemeral Messages:**
- Success: `✅ Your support message has been sent to the bot owner.`
- Error: `❌ Failed to send support message. Please try again later.`

## DM Messages (Setup Flow)

### Setup DM Messages
**Current Messages:**
- Initial Setup DM: Complex embed with instructions
- Channel Not Found: "I couldn't find a text channel named `#{channel_name}`..."
- Invalid Channel Type: "`#{channel_name}` is not a text channel..."
- Success: "✅ Setup Complete!" with detailed embed

**Proposed Ephemeral Messages:**
- Keep current DM format but standardize colors
- Use blue embeds for instructions
- Use green embeds for success
- Use red embeds for errors

## Error Messages

### Generic Errors
**Current Messages:**
- Generic: `MESSAGES['ERROR_TITLE']` - "❌ Erreur"
- Voice Channel Required: `MESSAGES['VOICE_CHANNEL_REQUIRED']` - "Ça prend un channel"
- Nothing Playing: `MESSAGES['NOTHING_PLAYING']` - "Rian joue mon'homme"

**Proposed Ephemeral Messages:**
- Generic: `❌ An error occurred. Please try again.`
- Voice Channel Required: `❌ You must be in a voice channel to use this command.`
- Nothing Playing: `⚠️ No song is currently playing.`

### Setup Errors
**Current Messages:**
- Session Not Found: "❓ Setup Session Not Found" with detailed explanation
- Session Expired: "⏰ Setup Timeout" 
- Invalid Channel: "❌ Invalid Channel Name"
- Channel Not Found: "❌ Channel Not Found"

**Proposed Ephemeral Messages:**
- Session Not Found: `❌ Setup session not found. Please run /setup again.`
- Session Expired: `⏰ Setup session expired. Please run /setup again.`
- Invalid Channel: `❌ The channel you provided does not exist or is not a text channel. Please try again.`

## Messages to Keep Public

### Control Panel Embeds (NO CHANGES)
- Queue embed (pinned message)
- Now Playing embed (pinned message)
- Welcome message in control channel

### Background Updates (NO CHANGES)
- Queue updates from Player Service events
- Now Playing updates from Player Service events
- Any `message.edit()` operations on pinned embeds

## Implementation Notes

1. All command responses should use `ephemeral=True`
2. All command responses should use standardized embed templates
3. DM messages should use standardized embed templates but remain as DMs
4. Public control panel embeds should remain unchanged
5. Error messages should be consistent and helpful