# YouTube Video Translator

A web application that translates YouTube videos to English using speech recognition and translation.

## Project Structure

```
Youtube-Video-Translator/
├── frontend/
│   ├── index.html      # Main HTML page
│   ├── style.css       # Styling
│   └── script.js       # Frontend JavaScript logic
├── backend/
│   ├── main.py                # Main API server
│   ├── audio_downloader.py    # YouTube audio download
│   ├── speech_recognizer.py   # OpenAI Whisper speech recognition
│   └── translator.py          # Translation to English
├── requirements.txt    # Python dependencies
└── README.md
```

## Features

- **Frontend**: HTML/CSS/Vanilla JavaScript interface for:
  - YouTube video link input
  - Video player
  - Display of translated text

- **Backend**: Python server that handles:
  - Downloading audio from YouTube videos
  - Speech recognition using OpenAI Whisper model
  - Translation to English
  - Sending translated text back to frontend

## Setup

1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the backend server:
   ```bash
   python backend/main.py
   ```

3. Open `frontend/index.html` in a web browser

## Technologies

- **Frontend**: HTML, CSS, Vanilla JavaScript
- **Backend**: Python, OpenAI Whisper
- **Audio Processing**: YouTube audio extraction
- **Speech Recognition**: OpenAI Whisper model
- **Translation**: English translation