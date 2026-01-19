import yt_dlp
import ffmpeg
import numpy as np

async def download_audio(url: list[str], session_id: str, allow_playlist: bool = False):
    assert isinstance(url, list)
    filename = f"temp_{session_id}.m4a"
    ydl_ops = {
        'format' : 'bestaudio/best',
        'outtmpl' : filename,
        'quiet' : False,
        'noplaylist' : not allow_playlist,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a',
        }],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_ops) as ydl:
            ydl.download(url)
        print("Download complete")
    except Exception as e:
        print(f"An error occurred: {e}")


def load_audio_to_numpy(file_path):
    try:
        # This uses ffmpeg to read the audio into a float32 buffer at 16k sample rate
        out, _ = (
            ffmpeg.input(file_path, threads=0)
            .output("-", format="s16le", acodec="pcm_s16le", ac=1, ar=16000)
            .run(cmd="ffmpeg", capture_stdout=True, capture_stderr=True)
        )
        return np.frombuffer(out, np.int16).flatten().astype(np.float32) / 32768.0
    except Exception as e:
        print(f"FFmpeg Error: {e}")
        return None