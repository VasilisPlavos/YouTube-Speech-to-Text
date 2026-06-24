import json
import os
import re
from typing import Any
import speech_recognition as sr
import subprocess

AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".opus", ".wma"}
VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv"}
SUPPORTED_EXTS = AUDIO_EXTS | VIDEO_EXTS


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


def check_status(channel, id):
    folderPath = f"./{channel}/{id}/"
    fileName = "index.json"
    filePath = os.path.join(folderPath, fileName)
    file_context = ''
    if os.path.exists(filePath):
        with open(filePath) as json_data:
            file_context = json.load(json_data)
    else:
        file_context = { "channel": channel, "id": id, "status": "start" }
        save_file(folderPath, fileName, json.dumps(file_context))
    return file_context

def get_audio(folderPath, youtubeUrl):
    audioFile = f"{folderPath}audio.wav"
    cmd = f"yt-dlp --extract-audio --audio-format wav -o {audioFile} {youtubeUrl}"
    subprocess.run(f"{cmd}", shell=True)
    return audioFile

def get_text(audioFile, language : Any | None = None):
    r = sr.Recognizer()
    with sr.AudioFile(audioFile) as source:
        data = r.record(source)
        text = r.recognize_whisper(audio_data=data, language=language)
        return text

def get_video_lang(video_lang):
    if (video_lang == 'None'): return None
    if (video_lang == ''): return None
    return video_lang

def get_youtube_id(url):
    try:
        match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
        return match.group(1) if match else ""
    except:
        return ""

def run_process_in_background(channel, id, video_lang : Any | None = None):
    folderPath = f"./{channel}/{id}/"
    fileName = "index.json"
    if (channel != "yt"):
        save_file(folderPath, fileName, json.dumps({ "id": id, "status": f'{channel} is not supported' }))
    
    save_file(folderPath, fileName, json.dumps({ "channel": channel, "id": id, "status": "generating audio file" }))
    youtubeUrl = f'https://youtu.be/{id}'
    audioFile = get_audio(folderPath, youtubeUrl)
    save_file(folderPath, fileName, json.dumps({ "channel": channel, "id": id, "status": "generating text" }))
    text = get_text(audioFile, video_lang)
    save_file(folderPath, fileName, json.dumps({ "channel": channel, "id": id, "status": "done", "text": text }))
    os.remove(audioFile)


def save_file(folderPath, fileName, jsonFile):
    if not os.path.isdir(folderPath):
        os.makedirs(folderPath)
    filePath = os.path.join(folderPath, fileName)
    file = open(filePath, 'w')
    file.write(jsonFile)
    file.close()

def save_file_by_channel(channel, id, jsonFile):
    folderPath = f"./{channel}/{id}/"
    fileName = "index.json"
    save_file(folderPath, fileName, jsonFile)