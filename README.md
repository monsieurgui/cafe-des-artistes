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
   - Copy `.env.example` to `.env`
   - Edit `.env` and add your Discord token and other configuration
   ```bash
   cp .env.example .env
   ```

4. Run in development mode:
   - Windows: Double-click `run_dev.bat`
   - Linux/macOS: Use Docker Compose

### Production Environment (Docker)

1. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env with your production settings
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

## Configuration

The bot uses environment variables for configuration. Create a `.env` file in the project root with the following variables:

### Required Variables
- `DISCORD_TOKEN`: Your Discord bot token from the Discord Developer Portal
- `BOT_ENV`: Set to `development` for local development or `production` for Docker

### Optional Variables
- `BOT_PREFIX`: Command prefix (default: `!`)
- `OWNER_ID`: Your Discord user ID for bot management (if not set, uses guild owners automatically)
- `LOG_LEVEL`: Logging level (default: `INFO`)
- `DEBUG`: Enable debug mode (default: `false`)
- `MAX_QUEUE_SIZE`: Maximum songs in queue (default: `1000`)
- `TIMEOUT_DURATION`: Idle timeout in seconds (default: `1800`)
- `FFMPEG_PATH`: Path to FFmpeg executable (auto-detected if not specified)

See `.env.example` for a complete configuration template.

## Troubleshooting
- Ensure FFmpeg is properly installed and accessible in PATH
- Check Discord token permissions in the Developer Portal
- Verify Python version compatibility (3.8+)
- For development issues, check the virtual environment
- Make sure `.env` file is in the project root directory

## Contributing
Feel free to submit issues and pull requests!

## License
[Your License Here]