# Use an up-to-date slim Ubuntu base image
FROM ubuntu:jammy-20240227

# Update the package list and install prerequisites
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    unzip \
    python3 \
    python3-pip \
    ffmpeg \
    && apt-get clean

# Install Deno — yt-dlp needs a JavaScript runtime for reliable YouTube extraction.
# Without it, yt-dlp falls back to a deprecated path that intermittently produces
# no audio file, which surfaced downstream as a confusing FileNotFoundError.
RUN curl -fsSL https://github.com/denoland/deno/releases/latest/download/deno-x86_64-unknown-linux-gnu.zip -o /tmp/deno.zip \
    && unzip -o /tmp/deno.zip -d /usr/local/bin \
    && rm /tmp/deno.zip \
    && chmod +x /usr/local/bin/deno

# Set working directory
WORKDIR /app
COPY /app /app

# if this is not working, use the requirements.txt file
RUN pip install --no-cache-dir --upgrade pip && \
pip install --no-cache-dir SpeechRecognition[whisper-local] yt-dlp fastapi[standard] --ignore-installed

# RUN pip install --no-cache-dir --upgrade -r requirements.txt

CMD ["fastapi", "run", "main.py", "--port", "80"]

# docker build -t youtube-to-text:latest .
# docker run -d --name youtube-to-text -p 3300:80 -v ${env:USERPROFILE}/docker/volumes/whisper_data/media:/data youtube-to-text:latest
# Drop audio/video files into /host/media/in ; transcripts appear in /host/media/out
# Optional env: -e POLL_INTERVAL=5 -e DEFAULT_LANG=en -e WATCH_DIR=/data
# YouTube endpoint still available at http://localhost:3300/yt/swXWUfufu2w