import yt_dlp
import ffmpeg
import numpy as np
import os

def download_audio(url: str, session_id: str, allow_playlist: bool = False):
    print(f"Downloading Audio: {url}")
    base_filename = f"temp_{session_id}"
    
    ydl_ops = {
        'format': 'bestaudio[ext=m4a]/best', 
        'outtmpl': base_filename,
        'quiet': True,
        'noplaylist': not allow_playlist,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a',
        }],
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios']
            }
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_ops) as ydl:
            ydl.download([url])
        
        final_filename = f"{base_filename}.m4a"
        print("Download & Processing Completed")
        return final_filename
    except Exception as e:
        print(f"DL Error: {e}")
        return None

def load_audio_to_numpy(file_path):
    if not file_path or not os.path.exists(file_path): return None
    try:
        print("Converting Audio To Array")
        out, _ = (
            ffmpeg.input(file_path, threads=0)
            .output("-", format="s16le", acodec="pcm_s16le", ac=1, ar=16000)
            .run(cmd="ffmpeg", capture_stdout=True, capture_stderr=True)
        )
        return np.frombuffer(out, np.int16).flatten().astype(np.float32) / 32768.0
    except Exception as e:
        print(f"FFmpeg Error: {e}")
        return None