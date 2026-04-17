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
CMD exec uvicorn app.main:app --host 0.0.0.0 --port $PORT
