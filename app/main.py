from typing import Optional
from fastapi import BackgroundTasks, FastAPI, Query
from fastapi.responses import RedirectResponse
from processors import *

# cmd: fastapi dev
# docker build -t youtube-to-text:dev .
# docker run -d --name youtube-to-text -v .\app:/app -p 3301:80 youtube-to-text:dev

app = FastAPI()

# example: http://localhost:3300/?url=https://www.youtube.com/watch?v=swXWUfufu2w?version=3&amp;hl=en_US&video_lang=en
@app.get('/')
async def read_root(url: str, video_lang: Optional[str] = Query(None)):
    response = "Try something like http://localhost:3300/?url=https://www.youtube.com/watch?v=swXWUfufu2w"

    channel = get_channel(url)
    if (channel == "yt"):
        youtubeId = get_youtube_id(url)
        if (youtubeId != ""):
            response = RedirectResponse(url=f'/yt/{youtubeId}?video_lang={video_lang}')

    if (channel == "ig"):
        instagramId = get_instagram_id(url)
        if (instagramId != ""):
            response = RedirectResponse(url=f'/ig{instagramId}?video_lang={video_lang}')

    return response


@app.get("/ig/{id}")
async def ig_id(id: str, background_tasks: BackgroundTasks, video_lang: Optional[str] = Query(None)):
    channel = 'ig'
    video_lang = get_video_lang(video_lang)
    response = check_status(channel, id)
    status = response["status"]
    if (status == "start"):
        background_tasks.add_task(run_process_in_background, "ig", id, video_lang)
        response = { "channel": channel, "id": id, "status": "work in progress, check later" }
        save_file_by_channel(channel, id, json.dumps(response))
    return response

@app.get("/yt/{id}")
async def yt_id(id: str, background_tasks: BackgroundTasks, video_lang: Optional[str] = Query(None)):
    channel = 'yt'
    video_lang = get_video_lang(video_lang)
    response = check_status(channel, id)
    status = response["status"]
    if (status == "start"):
        background_tasks.add_task(run_process_in_background, "yt", id, video_lang)
        response = { "channel": channel, "id": id, "status": "work in progress, check later" }
        save_file_by_channel(channel, id, json.dumps(response))
    return response