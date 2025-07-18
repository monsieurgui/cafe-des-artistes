FROM python:3.11-slim

# Install system dependencies including FFmpeg for audio streaming
RUN apt-get update && \
    apt-get install -y git ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Create logs directory
RUN mkdir -p /app/logs

# Copy requirements and install dependencies
COPY src/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY src/ ./src/

# Set Python path
ENV PYTHONPATH=/app

# Set environment variables for IPC
ENV PLAYER_SERVICE_HOST=player-service
ENV PLAYER_SERVICE_COMMAND_PORT=5555
ENV PLAYER_SERVICE_EVENT_PORT=5556

# Run the bot client
CMD ["python", "src/main.py"]