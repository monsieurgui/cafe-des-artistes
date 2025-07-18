FROM python:3.11-slim

# Install system dependencies including FFmpeg for audio processing
RUN apt-get update && \
    apt-get install -y ffmpeg git && \
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
COPY player_main.py .

# Set Python path
ENV PYTHONPATH=/app

# Set environment variables for IPC
ENV COMMAND_PORT=5555
ENV EVENT_PORT=5556
ENV BIND_HOST=0.0.0.0

# Expose ports for IPC communication
EXPOSE 5555 5556

# Run the player service
CMD ["python", "player_main.py"]