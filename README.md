# AI Video Translator (Real-Time)

A full-stack web application that translates YouTube videos and local video/audio files in real-time. 

Unlike traditional tools that wait for the entire video to process before showing results, this project utilizes a Streaming Architecture via WebSockets to start playing subtitles almost immediately.

## Key Features

* **Real-Time Streaming:** Starts translating instantly using a linear audio processing pipeline.
* **Smart Caching:** The frontend intelligently caches subtitles. Seeking back and forward allows for instant replay without re-fetching data from the server.
* **Dockerized Execution:** Runs fully containerized on your machine, with GPU auto-detection (Nvidia CUDA) and fallbacks for CPU-only systems.
* **Pre-Baked Model:** The large-v3 model is baked directly into the Docker image, enabling instant load-times without downloading multi-gigabyte models on startup.
* **Dual-Language Transcript Export:** Compiles a side-by-side aligned CSV of both the original language and the English translation, downloadable via the interface after processing finishes.
* **Accuracy Presets:** Choose between Maximum Accuracy (default, high beam size and fallbacks) and Interactive Sweet Spot (balanced, faster, optimized for weaker systems).

## Tech Stack

### Backend
* **Python 3.12+ (Docker base image PyTorch)**
* **FastAPI:** High-performance web framework for handling API requests.
* **WebSockets:** For full-duplex communication between client and server.
* **Faster-Whisper:** Optimized implementation of OpenAI's Whisper model (using CTranslate2).
* **yt-dlp:** Media downloader for extracting audio from YouTube.
* **FFmpeg:** High-speed audio conversion and processing.

### Frontend
* **Vanilla JavaScript:** Event-driven logic for state management, socket handling, and client-side CSV downloads.
* **HTML5 & CSS3:** Responsive sci-fi layout and custom player configurations.
* **YouTube IFrame Player API:** For video control.

## Project Structure

```text
Youtube-Video-Translator/
├── backend/
│   ├── main.py             # FastAPI server & WebSocket handlers
│   └── utils.py            # Audio download (yt-dlp) & conversion (ffmpeg)
├── frontend/
│   ├── index.html          # Main application interface
│   ├── style.css           # Styling, animations, and responsive layout
│   └── newjs.js            # WebSocket client, caching logic, & player control
├── models/                 # Host directory volume-mounted for model caching
├── requirements.txt        # Python dependencies
├── dockerfile              # Backend container recipe
├── .dockerignore           # Excludes heavy folders from Docker context
├── run.bat                 # One-click startup script (Windows)
├── run.sh                  # One-click startup script (Unix/macOS)
└── README.md
```

## Setup and Running

The system uses Docker to manage the backend, ensuring dependencies (like PyTorch, CUDA, and FFmpeg) are pre-configured out-of-the-box.

### Prerequisites

* **Docker Desktop:** Installed and running on your system.
* **Nvidia Container Toolkit (Optional):** Required if you want GPU/CUDA acceleration on Windows/Linux.

### Startup Guide

Simply run the startup script for your operating system in the root directory:

#### On Windows (PowerShell/CMD):
```cmd
.\run.bat
```

#### On Linux / macOS / Git Bash:
```bash
./run.sh
```

### What the startup scripts do:
1. Automatically build the Docker backend image if it does not exist.
2. Auto-detect if an Nvidia GPU is available (runs with `--gpus all` if present, falls back to CPU safely if not).
3. Start the backend container and mount the local `models` directory to cache any runtime model downloads.
4. Launch the local HTTP server for the frontend on port 5500.
5. Poll the backend until it is responsive and automatically open the application in your browser at `http://localhost:5500`.

---

## How to Use

1. **Paste URL or Upload File:** Copy a YouTube link and paste it into the input field under the "YouTube URL" tab, or drop a video file in the "Local File" tab.
2. **Configure Settings:** Configure your Whisper model size, accuracy mode, and semantic context before initializing. These settings will lock during playback to maintain synchronization.
3. **Initialize Playback:** Click the initialize button. The UI locks briefly while the audio downloads/buffers, then unlocks to play the video with real-time subtitles.
4. **Extract Transcript:** Once the video has finished transcribing, the "Extract Transcript" button becomes active. Click it to download a dual-column CSV containing the original text and the translated English text, perfectly aligned.

## Disclaimer

This project is for educational and research purposes only. It utilizes yt-dlp to process audio streams. Users must respect YouTube's Terms of Service and copyright regulations. The authors do not condone downloading or distributing copyrighted content without permission.

## License

[MIT License](LICENSE)
