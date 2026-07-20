import json
import os
import re
from typing import Any
import speech_recognition as sr
import subprocess

AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".opus", ".wma"}
VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv"}
SUPPORTED_EXTS = AUDIO_EXTS | VIDEO_EXTS

INDEX_FILE = "index.json"


def is_supported_media(filename):
    return os.path.splitext(filename)[1].lower() in SUPPORTED_EXTS


def build_markdown(stem, text):
    return f"---\nchannel: local folder\nid: {stem}\n---\n{text}\n"


def free_base(target_dir, base, companion_exts):
    candidate = base
    n = 0
    while any(os.path.exists(os.path.join(target_dir, candidate + e)) for e in companion_exts):
        n += 1
        candidate = f"{base}-{n}"
    return candidate


def job_dir(channel, id):
    return f"./{channel}/{id}/"


def write_status(channel, id, **fields):
    payload = {"channel": channel, "id": id, **fields}
    save_file(job_dir(channel, id), INDEX_FILE, json.dumps(payload))


def check_status(channel, id):
    folder_path = job_dir(channel, id)
    file_path = os.path.join(folder_path, INDEX_FILE)
    if os.path.exists(file_path):
        with open(file_path) as json_data:
            return json.load(json_data)
    file_context = {"channel": channel, "id": id, "status": "start"}
    save_file(folder_path, INDEX_FILE, json.dumps(file_context))
    return file_context


def get_audio(folder_path, youtube_url):
    audio_file = f"{folder_path}audio.wav"
    cmd = ["yt-dlp", "--extract-audio", "--audio-format", "wav", "-o", audio_file, youtube_url]
    result = subprocess.run(cmd)
    if result.returncode != 0 or not os.path.exists(audio_file):
        raise RuntimeError(
            f"yt-dlp failed for {youtube_url} (exit code {result.returncode}); "
            f"no audio produced at {audio_file}. See container logs for yt-dlp output."
        )
    return audio_file


def get_text(audio_file, language: Any | None = None):
    r = sr.Recognizer()
    with sr.AudioFile(audio_file) as source:
        data = r.record(source)
        return r.recognize_whisper(audio_data=data, language=language)


def get_video_lang(video_lang):
    if video_lang in ('None', ''):
        return None
    return video_lang


def get_youtube_id(url):
    if not isinstance(url, str):
        return ""
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
    return match.group(1) if match else ""


def run_process_in_background(channel, id, video_lang: Any | None = None):
    if channel != "yt":
        write_status(channel, id, status=f"{channel} is not supported")
        return

    folder_path = job_dir(channel, id)
    try:
        write_status(channel, id, status="generating audio file")
        youtube_url = f'https://youtu.be/{id}'
        audio_file = get_audio(folder_path, youtube_url)
        write_status(channel, id, status="generating text")
        text = get_text(audio_file, video_lang)
        write_status(channel, id, status="done", text=text)
        os.remove(audio_file)
    except Exception as e:
        write_status(channel, id, status="error", error=str(e))
        raise


def save_file(folder_path, file_name, json_file):
    if not os.path.isdir(folder_path):
        os.makedirs(folder_path)
    file_path = os.path.join(folder_path, file_name)
    with open(file_path, 'w') as file:
        file.write(json_file)


def save_file_by_channel(channel, id, json_file):
    save_file(job_dir(channel, id), INDEX_FILE, json_file)


def extract_audio_to_wav(input_path, workdir):
    wav_path = os.path.join(workdir, "audio.wav")
    cmd = ["ffmpeg", "-y", "-i", input_path, "-ar", "16000", "-ac", "1", wav_path]
    subprocess.run(cmd, check=True)
    return wav_path


def transcribe_local_file(input_path, workdir, language=None):
    wav_path = extract_audio_to_wav(input_path, workdir)
    return get_text(wav_path, language)
