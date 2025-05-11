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

## Completions:

- Successfully updated `pip`.
- Successfully updated `yt-dlp` from `2025.3.31` to `2025.04.30`.
- Added `src/config/config.yaml` to `.gitignore`.
