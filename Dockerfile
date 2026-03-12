# ── Stage 1: install Python deps in a full image ─────────────────────────────
# python:3.11-slim is missing libsndfile, ffmpeg, and other audio libs
# needed by librosa, soundfile, demucs, and faster-whisper.
FROM python:3.11-slim AS builder

# System packages needed to build/run the audio stack
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    libsndfile1-dev \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer-cache friendly)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# ── Stage 2: lean runtime image ───────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Runtime system libs only (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code (see .dockerignore for exclusions)
COPY . .

# Create the songs cache directory so StaticFiles mount doesn't crash on cold start
RUN mkdir -p songs

EXPOSE 8000

# Use multiple uvicorn workers — adjust based on EC2 instance size.
# t2.micro (1 vCPU, 1 GB RAM): 1 worker to avoid OOM
# t2.medium (2 vCPU, 4 GB RAM): 2 workers
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
