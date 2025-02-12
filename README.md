# Café des Artistes Discord Bot

A feature-rich Discord music bot with high-quality playback and performance optimizations.

## Setup

### Prerequisites
- Python 3.8 or higher
- FFmpeg
- Discord Bot Token

### Development Environment

1. Install FFmpeg:
   - Windows: Download from [FFmpeg official website](https://ffmpeg.org/download.html)
   - Linux: `sudo apt-get install ffmpeg`
   - macOS: `brew install ffmpeg`

2. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/cafe-des-artistes.git
   cd cafe-des-artistes
   ```

3. Set up environment:
   - Copy `src/.env.example` to `src/.env`
   - Edit `src/.env` and add your Discord token and FFmpeg path
   ```bash
   cp src/.env.example src/.env
   ```

4. Run in development mode:
   - Windows: Double-click `run_dev.bat`
   - Linux/macOS: Use Docker Compose

### Production Environment (Docker)

1. Configure environment:
   ```bash
   cp src/.env.example src/.env
   # Edit src/.env with your production settings
   ```

2. Run with Docker Compose:
   ```bash
   docker-compose up -d
   ```

## Features
- High-quality music playback
- Queue management
- Live streaming support
- Performance optimizations
- Playlist support
- Loop mode
- And more!

## Commands
- `!p` or `!play`: Play a song or add to queue
- `!s` or `!skip`: Skip current song
- `!q` or `!queue`: Show current queue
- `!l` or `!loop`: Toggle loop mode
- `!live`: Start a live stream
- Check `!help` for more commands

## Development vs Production
- Development: Uses local Python environment with hot-reloading
- Production: Uses Docker with optimized settings

## Troubleshooting
- Ensure FFmpeg is properly installed and path is set in .env
- Check Discord token permissions
- Verify Python version compatibility
- For development issues, check the virtual environment

## Contributing
Feel free to submit issues and pull requests!

## License
[Your License Here]