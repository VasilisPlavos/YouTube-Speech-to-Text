# Use an up-to-date slim Ubuntu base image
FROM ubuntu:jammy-20240227

# Update the package list and install prerequisites
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    python3 \
    python3-pip \
    ffmpeg \
    && apt-get clean

# Set working directory
WORKDIR /app
COPY /app /app

# if this is not working, use the requirements.txt file
RUN pip install --upgrade pip && \
pip install yt-dlp fastapi[standard] --ignore-installed

# if this is not working, use the requirements.txt file
RUN pip install --upgrade pip && \
pip install openai-whisper

# RUN pip install --upgrade -r requirements.txt

CMD ["fastapi", "run", "main.py", "--port", "80"]

# docker build -t youtube-to-text:latest .
# docker run -d --name youtube-to-text -p 3300:80 youtube-to-text:latest
# go to http://localhost:3300/yt/swXWUfufu2w