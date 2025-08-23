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

### `/setup` Command (Removed)
This command has been removed. The bot no longer uses a persistent control panel. A transient start-of-song beacon is posted on each track start, and `/queue` provides a public snapshot.

### `/queue` Command
Public snapshot, no components.
- Empty: `The queue is currently empty.` (public)
- Success: One embed listing up to 20 items: position, hyperlinked title, duration, requester. Footer shows remaining count if any.

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

## Public Messages
- Start-of-song beacon message (created on song start, deleted on end/skip/reset/error)
- `/queue` snapshot embed (one-off message)

## Implementation Notes

1. All command responses should use `ephemeral=True`
2. All command responses should use standardized embed templates
3. DM messages should use standardized embed templates but remain as DMs
4. Public control panel embeds should remain unchanged
5. Error messages should be consistent and helpful