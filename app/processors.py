import json
import os
import re
import whisper
import subprocess
from typing import Any
from urllib.parse import urlparse

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

def get_channel(url):
    if (urlparse(url).netloc.endswith('instagram.com')):
        return "ig"
    if (get_youtube_id(url) != ""):
        return "yt"
    return ""

def get_text(audioFile, language : Any | None = None):
    model = whisper.load_model("turbo")

    # load audio and pad/trim it to fit 30 seconds
    audio = whisper.load_audio(audioFile)
    audio = whisper.pad_or_trim(audio)

    # make log-Mel spectrogram and move to the same device as the model
    mel = whisper.log_mel_spectrogram(audio).to(model.device)

    # detect the spoken language
    _, probs = model.detect_language(mel)
    print(f"Detected language: {max(probs, key=probs.get)}")

    # decode the audio
    options = whisper.DecodingOptions()
    result = whisper.decode(model, mel, options)

    # print the recognized text
    print(result.text)
    return result.text

def get_video_lang(video_lang):
    if (video_lang == 'None'): return None
    if (video_lang == ''): return None
    return video_lang

def get_instagram_id(url):
    return urlparse(url).path

def get_youtube_id(url):
    try:
        match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
        return match.group(1) if match else ""
    except:
        return ""

def channel_supported(channel):
    if (channel == "yt"):
        return True
    if (channel == "ig"):
        return True
    return False

def run_process_in_background(channel, id, video_lang : Any | None = None):
    folderPath = f"./{channel}/{id}/"
    fileName = "index.json"
    if (channel_supported(channel) == False):
        save_file(folderPath, fileName, json.dumps({ "id": id, "status": f'{channel} is not supported' }))
    
    save_file(folderPath, fileName, json.dumps({ "channel": channel, "id": id, "status": "generating audio file" }))

    source_url = ""
    if (channel == "yt"):
        source_url = f'https://youtu.be/{id}'
    if (channel == "ig"):
        source_url = f'https://instagram.com/{id}'
    
    audioFile = get_audio(folderPath, source_url)
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