# 🎥 AI Video Translator (Real-Time)

A full-stack web application that translates YouTube videos in real-time using OpenAI's Whisper model. 

Unlike traditional tools that wait for the entire video to process before showing results, this project utilizes a **Streaming Architecture** via WebSockets to start playing subtitles almost immediately.

![Project Screenshot](https://via.placeholder.com/800x400?text=AI+Video+Translator+Demo)

## 🚀 Key Features

* **⚡ Real-Time Streaming:** Starts translating instantly using a linear audio processing pipeline—no long wait times.
* **🧠 Smart Caching:** The frontend intelligently caches subtitles. Seeking back and forward allows for instant replay without re-fetching data from the server.
* **💾 Local Execution:** Runs 100% locally on your machine (Privacy-focused, no API costs).
* **🤖 Multi-Model Support:** Switch between Whisper model sizes (`tiny`, `small`, `medium`, `large-v3`) on the fly.
* **🎨 Dynamic UI:** 
    * "Smart Wait" buffering system that handles model warm-up times gracefully.
    * **Custom Fullscreen Player:** Bypasses YouTube's iframe limitations to keep subtitles visible in fullscreen mode.
* **🌍 Multi-Language Support:** Translates from any supported language into English (or other target languages supported by the backend configuration).

## 🛠️ Tech Stack

### Backend
* **Python 3.10+**
* **FastAPI:** High-performance web framework for handling API requests.
* **WebSockets:** For full-duplex communication between client and server.
* **Faster-Whisper:** Optimized implementation of OpenAI's Whisper model (using CTranslate2).
* **yt-dlp:** Robust media downloader for extracting audio from YouTube.
* **FFmpeg:** High-speed audio conversion and processing.

### Frontend
* **Vanilla JavaScript:** Lightweight, event-driven logic for state management and socket handling.
* **HTML5 & CSS3:** Custom animations and responsive layout.
* **YouTube Iframe API:** For embedding and controlling the video player.

## 📂 Project Structure
```

Youtube-Video-Translator/
├── backend/
│   ├── main.py             # FastAPI server & WebSocket endpoint
│   └── utils.py            # Audio download (yt-dlp) & processing (ffmpeg) logic
├── frontend/
│   ├── index.html          # Main application interface
│   ├── style.css           # Sci-fi theming, animations, and responsive design
│   └── script.js           # WebSocket client, caching logic, & player controls
├── models/                 # Directory where Whisper models are downloaded
├── requirements.txt        # Python dependencies
├── run.bat                 # One-click startup script (Windows)
└── README.md

```

## 📦 Installation & Setup

### Prerequisites
1.  **Python 3.10+**: Ensure Python is added to your system PATH.
2.  **FFmpeg**: Must be installed and added to your system PATH.
    * [Download FFmpeg](https://ffmpeg.org/download.html)
3.  **CUDA Toolkit (Optional)**: Recommended for GPU acceleration if you have an NVIDIA card.

### Step-by-Step Guide

1.  **Clone the Repository**
    ```bash
    git clone [https://github.com/abcdef54/Youtube-Video-Translator.git](https://github.com/abcdef54/Youtube-Video-Translator.git)
    cd AI-Video-Translator
    ```

2.  **Create a Virtual Environment**
    ```bash
    python -m venv .venv
    # Activate on Windows:
    .venv\Scripts\activate
    # Activate on Mac/Linux:
    source .venv/bin/activate
    ```

3.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run the Application**
    Simply double-click the **`run.bat`** file.
    
    *Or run manually:*
    ```bash
    # Terminal 1 (Backend)
    python backend/main.py
    
    # Terminal 2 (Frontend)
    cd frontend
    python -m http.server 5500
    ```

5.  **Access the App**
    Open your browser and navigate to `http://localhost:5500` (or the URL provided by your terminal).

## 🎮 How to Use

1.  **Paste URL:** Copy a YouTube link and paste it into the input field.
2.  **Configure:** Select your desired **Whisper Model** size (larger models = better accuracy but slower).
3.  **Initialize:** Click the **INITIALIZE VIDEO** button.
4.  **Watch:** The system will lock the UI briefly to buffer the AI stream, then automatically start playing with subtitles.
5.  **Context:** You can provide a "Context" hint (e.g., "Medical Lecture", "Coding Tutorial") to improve transcription accuracy for specific jargon.

## ⚠️ Disclaimer

This project is for **educational and research purposes only**. It utilizes `yt-dlp` to process audio streams. Users must respect YouTube's Terms of Service and copyright regulations. The authors do not condone downloading or distributing copyrighted content without permission.

## 📄 License

[MIT License](LICENSE)