# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

FastAPI service that transcribes YouTube videos to text. It downloads a video's audio with `yt-dlp` and transcribes it locally with OpenAI Whisper (via the `SpeechRecognition[whisper-local]` wrapper) — no external transcription API is used. The whole app is two source files in `app/`.

## Commands

> **Always run this project via Docker — never run the app directly on the host.** The bare `fastapi`/`unittest` commands below are documented for reference, but to actually launch or exercise the app end-to-end, use the Docker workflow. If a task seems to require a non-Docker run, stop and confirm first.

All commands run from the `app/` directory (modules import each other by bare name, e.g. `from processors import *`, so the working directory must be `app/`).

```shell
fastapi dev                              # local dev server with reload
fastapi run main.py --port 80            # production-style run (this is the container CMD)
python -m unittest test_processors.py    # run the test suite
python -m unittest test_processors.TestGetYoutubeId.test_valid_url   # run a single test
```

Docker (from repo root, where the `Dockerfile` lives):

```shell
docker build -t youtube-to-text:latest .
docker run -d --name youtube-to-text -p 3300:80 youtube-to-text:latest
# then GET http://localhost:3300/yt/swXWUfufu2w
```

`ffmpeg` is a required system dependency (used by `yt-dlp` for audio extraction and by Whisper); the Dockerfile installs it.

## Architecture

The core design is an **async poll-and-persist pattern** — there is no database, no in-memory job queue, and no websockets. State lives entirely in JSON files on disk.

**Request flow** (`main.py`):
1. `GET /?url=<youtube url>` extracts the 11-char video id and 302-redirects to `/yt/{id}`.
2. `GET /yt/{id}` reads the job's status file. If status is `start`, it schedules transcription as a FastAPI `BackgroundTask`, immediately writes a "work in progress" file, and returns. Otherwise it returns the current file contents.
3. The client **polls the same `/yt/{id}` endpoint repeatedly** until status becomes `done`, at which point the response includes the `text` field.

**State machine** (status field in `index.json`): `start` → `work in progress, check later` → `generating audio file` → `generating text` → `done`. Each transition overwrites the file via `save_file`.

**Storage layout**: every job is `./{channel}/{id}/index.json`, relative to the working directory. The only `channel` currently supported is `yt`; the `channel` parameter threads through the code as an extension point for other sources (anything else gets a "not supported" status). Because the path is relative, files land in `app/yt/...` under `fastapi dev` and `/app/yt/...` in the container.

**Background pipeline** (`run_process_in_background` in `processors.py`): build `https://youtu.be/{id}` → `get_audio` shells out to `yt-dlp` to produce `audio.wav` → `get_text` runs Whisper via `SpeechRecognition` → write `done` + transcript → delete the `.wav`.

**Language handling**: `video_lang` is optional. It survives the `/` → `/yt/{id}` redirect as a query string, so an absent value arrives as the literal string `"None"` or `""`; `get_video_lang` normalizes both back to Python `None` (Whisper then auto-detects).

## Notes

- `processors.py` holds all logic and I/O; `main.py` is only routing. `test_processors.py` currently covers `get_youtube_id` only.
- `requirements.txt` (pinned top-level deps) and `requirements.long.txt` (full frozen tree) are kept as backups — the Dockerfile does **not** use them; it `pip install`s the packages directly. Keep these in sync if you change dependencies.
