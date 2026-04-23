# Use the official lightweight Python image.
FROM python:3.12-slim

# Allow statements and log messages to immediately appear in the logs
ENV PYTHONUNBUFFERED True

# Set the working directory
WORKDIR /app

# Copy requirements file first (for Docker caching)
COPY requirements.txt .

# ffmpeg is required by yt-dlp to merge separate video+audio streams into mp4
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# Run Uvicorn when the container starts.
# Cloud Run automatically injects the PORT environment variable.
# 2 workers = 2 separate OS processes, each on its own CPU core.
# Each worker gets its own Redis connection pools (max_connections=6 each),
# so total Redis connections = 2 workers × 2 pools × 6 = 24, under Upstash free-tier limit of 30.
CMD exec uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2
