## Story Mode Plan: Replace Persistent UI with Start-of-Song Embed and Add /queue Snapshot

As the Café des Artistes bot, I will retire the persistent Now Playing and Queue embeds and instead post a single, elegant embed at the start of each song, then clean it up when the song ends. I will also provide a concise `/queue` snapshot of up to 20 upcoming tracks directly in the conversation.

### Acceptance Criteria
- [ ] No `/setup` command exists or is registered anywhere.
- [ ] No persistent Now Playing or Queue embed remains or is auto-restored on startup.
- [ ] On every song start, a new message is posted containing:
  - [ ] An embed whose title is the song name in bold
  - [ ] The current time rendered in ASCII art inside the embed (monospace block)
  - [ ] A timestamp (embed timestamp field)
- [ ] When the song ends (natural end, skip, stop/reset, disconnect, error), the start-of-song embed is deleted.
- [ ] `/queue` command returns a single embed in the channel with top 20 items (or fewer if less available), including position, title with link, duration, and requester.
- [ ] Docker build and run works; all tests pass.

---

### Act I — Retire the Old Boards (Remove Persistent UI)
- [x] Remove `/setup`:
  - [x] Delete slash registration and handler from `src/cogs/music.py`
  - [x] Remove setup-session logic (and DM flows) from bot client paths
  - [x] Stop any setup DM behaviors in `src/bot/client.py`
- [x] Remove persistent Now Playing and Queue embed logic:
  - [x] Remove restore-on-startup logic in `src/bot/client.py`
  - [x] Stop queue/now-playing updates from IPC side
- [x] Database and state cleanup:
  - [x] Ignore deprecated persistent message IDs at runtime
  - [x] No migrations required for functionality

---

### Act II — The Start-of-Song Beacon (Post, Track, Delete)
- [x] Dependency and utilities:
  - [x] Add `pyfiglet` to `src/requirements.txt` for ASCII time rendering
  - [x] Create `utils/ascii_time.py` with a function to render current time HH:MM:SS as ASCII using a compact font
- [x] Event handling on song start (Player → Bot event):
  - [x] On `SONG_STARTED`, compute current wall-clock time and render ASCII block
  - [x] Build a simple `discord.Embed` with bold title, ASCII time code block, and timestamp
  - [x] Post this embed in the most recent command channel for the guild; track `guild_id -> (channel_id, message_id)`
- [x] Event handling on song end (any termination):
  - [x] On `SONG_ENDED`, `PLAYER_STOP`, idle, or `PLAYER_ERROR` → attempt to delete the tracked message
  - [x] Handle `discord.NotFound` and permission errors gracefully, then clear tracking
- [x] Voice/connection edge cases:
  - [x] If a new song starts before the previous message is deleted, delete the previous first
  - [x] If the bot loses permissions mid-song, log and clear tracking safely

---

### Act III — The Queue Snapshot (Top 20)
- [x] Slash command `/queue`:
  - [x] Request current queue via IPC (`GET_STATE` or equivalent)
  - [x] Build one embed (no components) listing up to 20 items:
    - [x] Each item shows position, hyperlinked title, duration, requester
    - [x] If queue is empty, show a friendly empty-state message
  - [x] Send as a normal public message in the channel (not ephemeral)

---

### Act IV — Refactors, Tests, and Docs
- [x] Remove dead code paths, helpers, and imports related to persistent embeds/views
- [ ] Update tests:
  - [x] Add tests for `/queue` formatting (top 20 and fewer)
  - [x] Add unit test for ASCII time generator
  - [x] Adjust player/bot event integration tests to assert message create/delete sequence
- [ ] Update docs:
  - [ ] README.md: reflect new UX (no setup; per-song messages; `/queue` snapshot)
  - [x] DEPLOYMENT.md: confirm no persistent embed setup required
  - [ ] MESSAGE_CATALOG.md: remove old messages, add new ones

---

### Act V — Validation
- [ ] Local validation:
  - [ ] `docker-compose up --build` starts both services cleanly
  - [ ] Add a few songs: observe start-of-song embed creation and cleanup
  - [ ] Run `/queue`: shows up to first 20 items with correct details
  - [ ] Skip/stop/reset: start-of-song embed is deleted every time
- [ ] Done Definition:
  - [ ] Acceptance criteria satisfied
  - [ ] No regressions detected in logs
  - [ ] All tests green


