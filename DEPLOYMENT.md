# Containerized Deployment Guide

This guide covers deploying the Café des Artistes Discord bot using the new two-service architecture.

## Architecture Overview

The bot is now split into two containerized services:

- **bot-client**: Lightweight Discord interface that handles user interactions
- **player-service**: Headless audio processing service with FFmpeg

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
   docker-compose -f docker-compose-services.yml up -d
   ```

3. **Check Logs**:
   ```bash
   # Bot client logs
   docker-compose -f docker-compose-services.yml logs -f bot-client
   
   # Player service logs
   docker-compose -f docker-compose-services.yml logs -f player-service
   ```

## Service Configuration

### Bot Client Service
- **Image**: Built from `bot-client.Dockerfile`
- **Purpose**: Discord gateway connection and user interaction
- **Dependencies**: No FFmpeg (lightweight)
- **Network**: Connects to `player-service` via hostname

### Player Service
- **Image**: Built from `player-service.Dockerfile`
- **Purpose**: Audio processing and voice channel management
- **Dependencies**: Includes FFmpeg for audio processing
- **Ports**: Exposes 5555 (commands) and 5556 (events) for IPC

## Network Architecture

```
┌─────────────────┐    ZeroMQ IPC    ┌─────────────────┐
│   bot-client    │◄────────────────►│ player-service  │
│                 │  tcp://player-   │                 │
│ - Discord API   │  service:5555/56 │ - Audio Engine  │
│ - User Commands │                  │ - Voice Client  │
│ - UI Updates    │                  │ - FFmpeg        │
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
docker-compose -f docker-compose-services.yml build

# Build without cache
docker-compose -f docker-compose-services.yml build --no-cache

# Start in foreground
docker-compose -f docker-compose-services.yml up

# Stop services
docker-compose -f docker-compose-services.yml down

# View service status
docker-compose -f docker-compose-services.yml ps

# Execute shell in container
docker-compose -f docker-compose-services.yml exec bot-client /bin/bash
docker-compose -f docker-compose-services.yml exec player-service /bin/bash
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
   docker-compose -f docker-compose-services.yml exec bot-client ping player-service
   ```

3. Check IPC port connectivity:
   ```bash
   docker-compose -f docker-compose-services.yml exec bot-client telnet player-service 5555
   ```

### Audio Issues
1. Verify FFmpeg in player service:
   ```bash
   docker-compose -f docker-compose-services.yml exec player-service ffmpeg -version
   ```

2. Check voice connection logs:
   ```bash
   docker-compose -f docker-compose-services.yml logs player-service | grep -i voice
   ```

## Success Criteria

The deployment is successful when:

✅ Both services start without errors
✅ Bot appears online in Discord
✅ `/play` command triggers audio processing in player-service
✅ All music commands (`/skip`, `/leave`, `/reset`) work correctly
✅ Persistent embeds update based on player-service events
✅ Restarting player-service doesn't crash bot-client

## Monitoring

Monitor service health:

```bash
# Service status
docker-compose -f docker-compose-services.yml ps

# Resource usage
docker stats cafe-bot-client cafe-player-service

# Real-time logs
docker-compose -f docker-compose-services.yml logs -f
```