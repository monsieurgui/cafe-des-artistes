# Café des Artistes - Discord Music Bot

A Discord music bot built with discord.py that plays music from YouTube with queue management and playlist support.

## Features

- Play music from YouTube URLs or search queries
- Queue management with pagination
- Playlist support
- Support ticket system
- Docker support for easy deployment
- Automatic cleanup of downloaded files
- Auto-disconnect when alone or inactive

## Commands

- `!p` or `!play` - Play a song or playlist from YouTube
- `!p5` - Play a song or playlist 5 times
- `!p10` - Play a song or playlist 10 times
- `!s` or `!skip` - Skip the current song
- `!purge` - Clear the music queue
- `!q` or `!queue` - Display current queue
- `!help` or `!h` - Display all available commands
- `!queue all` - Display full queue with pagination
- `!l` or `!loop` - Toggle loop mode for the current song
- `!support` - Send a support message to bot owner

## Installation

### Prerequisites

- Python 3.11+
- FFmpeg
- Discord Bot Token

### Local Setup

1. Clone the repository
2. Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate # Linux/Mac
venv\Scripts\activate # Windows
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Configure the bot:

```bash
cp src/config/config.template.yaml src/config/config.yaml
```
Edit `config.yaml` with your bot token and settings.

5. Run the bot:
```bash
python src/main.py
```

### Docker Setup

1. Configure the bot:

```bash
cp src/config/config.template.yaml config.yaml
```

2. Build and run with docker-compose:

```bash
docker-compose up -d
```

## Configuration

The bot requires a configuration file (`config.yaml`) with the following settings:

```yaml
bot_token: "<enter bot token here>"
command_prefix: "!"
ffmpeg_path: "/usr/bin/ffmpeg"
```

## Maintenance

### Logs
Logs are stored in `logs/` directory when running with Docker. Monitor these for issues.

### Memory Management
The bot automatically:
- Cleans up downloaded files after playing
- Disconnects after 30 minutes of inactivity
- Has memory limits when running in Docker

### Docker Resource Limits
Memory limits are configured in docker-compose.yml:

```yaml
deploy:
resources:
limits:
memory: 512M
reservations:
memory: 256M
```

## Troubleshooting

1. **Bot not playing audio**
   - Ensure FFmpeg is installed
   - Check bot has proper permissions
   - Verify voice channel connection

2. **High memory usage**
   - Check logs for memory leaks
   - Verify cleanup is working
   - Adjust Docker memory limits

3. **Connection issues**
   - Check network connectivity
   - Verify Discord API status
   - Review error logs

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit changes
4. Push to the branch
5. Create a Pull Request

## License

Apache License 2.0

Copyright 2024 Guillaume Lévesque

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.