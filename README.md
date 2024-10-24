<p align="center">
  <a href="https://www.linkedin.com/in/vasilisplavos/">
    <img src="https://img.shields.io/badge/LinkedIn-Vasilis_Plavos-blue" alt="Find me on LinkedIn!" />
  </a>
</p>

# YouTube-Speech-to-Text

YouTube Speech to Text: Convert Youtube URLs to text using Speech Recognition with Whisper AI (No API Required)

<p align="center">
  <a href="#video-example-here">
    <img alt="" src="https://github.com/VasilisPlavos/YouTube-Speech-to-Text/raw/refs/heads/main/assets/example.jpg" width="600" />
  </a>
</p>

## 🚀 Quick start
1. Download, Install and Run [Docker Desktop](https://www.docker.com/products/docker-desktop/)
1. Open a console to the folder that includes the **Dockerfile** and run the commands
    ```shell
    docker build -t youtube-to-text:latest . # be patient. it takes time to download the models
    docker run -d --name youtube-to-text -p 3300:80 youtube-to-text:latest # ready
    # go to http://localhost:3300/yt/swXWUfufu2w to try it! :)
    ```

## Features

1. Containerized solution:
    * You can easily run the application on your machine and the same time you keep it issolated from your local environment.
    * You can run the container easily to the cloud (eg. using Azure Container Registry & App Service)
1. API-based solution
1. Use of [FastAPI](https://fastapi.tiangolo.com/): A fast web framework for building APIs
1. Use of [Whisper AI](https://openai.com/index/whisper/): Open AI's automatic  speech recognition (ASR) system
1. Unlike solutions that rely on YouTube’s unreliable or missing transcripts, our Whisper AI-powered solution directly converts real voice, providing accurate multi-language support.

## How to use it

Once the container is running you can use 2 http requests (as simple as that):

1. `GET /?url=<youtube video url>&video_lang={video_lang}`  (ex. http://localhost:3300/?url=https://www.youtube.com/watch?v=swXWUfufu2w&video_lang=en)
1. `GET /yt/<youtube video id>?video_lang={video_lang}`     (ex. http://localhost:3300/yt/swXWUfufu2w?video_lang=en)

* `video_lang` parameter is not mandatory. you can just leave it blank!

Once the convertion will start you will get a response back. In order to get the text, you have to send a GET request again.

## VIDEO EXAMPLE HERE

<p align="center">
  <a href="https://github.com/VasilisPlavos/YouTube-Speech-to-Text/raw/refs/heads/main/assets/example.mp4">
    <img alt="" src="https://github.com/VasilisPlavos/YouTube-Speech-to-Text/raw/refs/heads/main/assets/example.jpg" width="600" />
  </a>
</p>

👉 Link to video: https://github.com/VasilisPlavos/YouTube-Speech-to-Text/raw/refs/heads/main/assets/example.mp4

## Files structure

    .
    ├── Dockerfile
    ├── app
    ├──── main.py
    ├──── processors.py
    ├──── test_processors.py
    ├──── requirements.txt*
    ├──── requirements.long.txt*

1.  **`Dockerfile`**: Contains the required commands to assemble the image 
1.  **`/app`**: This directory contains the Python application

*Files requirements.txt and requirements.long.txt are not used at the moment. Stored here as a backup
