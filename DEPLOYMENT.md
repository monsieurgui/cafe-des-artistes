# Containerized Deployment Guide

This guide covers deploying the Café des Artistes Discord bot using the new two-service architecture.

## Architecture Overview

The bot is now split into two containerized services:

- **bot-client**: Lightweight Discord interface that handles user interactions and streams audio to Discord
- **player-service**: Headless audio processing service that manages the queue and extracts audio URLs with FFmpeg (no Discord voice client)

Both services communicate via ZeroMQ IPC over a custom Docker network.

## Prerequisites

- Docker and Docker Compose installed
- Discord bot token

## Quick Start

1. **Configure Environment**:
   ```bash
   cp env.example .env
   # Edit .env and add your Discord bot token
   ```

2. **Deploy Services**:
   ```bash
   docker-compose up -d
   ```

3. **Check Logs**:
   ```bash
   # Bot client logs
   docker-compose logs -f bot-client
   
   # Player service logs
   docker-compose logs -f player-service
   ```

## Service Configuration

### Bot Client Service
- **Image**: Built from `bot-client.Dockerfile`
- **Purpose**: Discord gateway connection, user interaction, and streaming audio to Discord
- **Dependencies**: No FFmpeg (lightweight)
- **Network**: Connects to `player-service` via hostname

### Player Service
- **Image**: Built from `player-service.Dockerfile`
- **Purpose**: Audio processing, queue management, and audio URL extraction (no Discord gateway/voice)
- **Dependencies**: Includes FFmpeg for audio processing
- **Ports**: Exposes 5555 (commands) and 5556 (events) for IPC

## Network Architecture

```
┌─────────────────┐    ZeroMQ IPC    ┌─────────────────┐
│   bot-client    │◄────────────────►│ player-service  │
│                 │  tcp://player-   │                 │
│ - Discord API   │  service:5555/56 │ - Audio Engine  │
│ - Streams Audio │                  │ - FFmpeg URL    │
│ - UI Updates    │                  │   Extraction    │
└─────────────────┘                  └─────────────────┘
         │                                    │
         └──────────────┬─────────────────────┘
                        │
                ┌───────▼───────┐
                │ cafebot-net   │
                │ Docker Bridge │
                └───────────────┘
```

## Environment Variables

### Bot Client
- `PLAYER_SERVICE_HOST`: Hostname of player service (default: player-service)
- `PLAYER_SERVICE_COMMAND_PORT`: Command port (default: 5555)
- `PLAYER_SERVICE_EVENT_PORT`: Event port (default: 5556)
- `BOT_TOKEN`: Discord bot token (required)

### Player Service
- `BIND_HOST`: IP to bind sockets (default: 0.0.0.0 for containers)
- `COMMAND_PORT`: Port for receiving commands (default: 5555)
- `EVENT_PORT`: Port for sending events (default: 5556)

## Development Commands

```bash
# Build only
docker-compose build

# Build without cache
docker-compose build --no-cache

# Start in foreground
docker-compose up

# Stop services
docker-compose down

# View service status
docker-compose ps

# Execute shell in container
docker-compose exec bot-client /bin/bash
docker-compose exec player-service /bin/bash
```

## Troubleshooting

### Service Communication Issues
1. Check if both services are on the same network:
   ```bash
   docker network ls
   docker network inspect cafebot-network
   ```

2. Verify hostname resolution:
   ```bash
   docker-compose exec bot-client ping player-service
   ```

3. Check IPC port connectivity:
   ```bash
   docker-compose exec bot-client telnet player-service 5555
   ```

### Audio Issues
1. Verify FFmpeg in player service:
   ```bash
   docker-compose exec player-service ffmpeg -version
   ```

2. Check voice connection logs:
   ```bash
   docker-compose logs player-service | grep -i voice
   ```

## Success Criteria

The deployment is successful when:

✅ Both services start without errors
✅ Bot appears online in Discord
✅ `/play` triggers audio processing in player-service
✅ All music commands (`/skip`, `/leave`, `/reset`, `/queue`, `/p5`, `/support`) work correctly
✅ Start-of-song beacon message is created on song start and deleted on end/skip/reset/error (no persistent control panel)
✅ Restarting player-service doesn't crash bot-client

## Monitoring

Monitor service health:

```bash
# Service status
docker-compose ps

# Resource usage
docker stats cafe-bot-client cafe-player-service

# Real-time logs
docker-compose logs -f
```

## UX Notes

- The bot no longer uses a persistent control panel. Instead, a start-of-song beacon embed is posted at the beginning of each track and deleted automatically when the track ends, is skipped, the player is reset, or an error occurs.
- Use `/queue` to post a one-off public snapshot of up to the next 20 tracks.