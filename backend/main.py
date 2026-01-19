import os
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from backend.utils import download_audio, load_audio_to_numpy
from faster_whisper import WhisperModel
import json
import uuid
from  typing import Dict
import numpy as np

app = FastAPI()

print("Loading Model...")
model = WhisperModel("small", device="cuda", compute_type="float16")
print("Model Loaded!")

@app.websocket("/ws/translate")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session_id = str(uuid.uuid4())
    audio_file = None
    audio_array = None
    transcription_task = None
    
    stream_state = {
        "last_processed_time": 0.0, # The exact second where the model stopped speaking
        "rolling_transcript": "",   # The last few sentences generated
        "static_context": ""        # The user-defined context ("Video about coding")
    }

    try:
        while True:
            data = await websocket.receive_text()
            command: Dict[str, str] = json.loads(data)

            action = command.get("action")

            if action == "load_video":
                # Cancel any running transcription
                if transcription_task:
                    transcription_task.cancel()

                # Reset context
                stream_state["last_processed_time"] = 0.0
                stream_state["rolling_transcript"] = ""
                
                url = command.get("url")
                await  websocket.send_json({"status" : "Downloading Audio"})
                audio_file = await asyncio.to_thread(download_audio, url, session_id)
                audio_array = await asyncio.to_thread(load_audio_to_numpy, audio_file)

                await websocket.send_json({"status" : "Ready to play"})

            elif action == "transcribe": # First time playing video or switching languages or skipping part of the video
                # Kill previous transcription (e.g. was playing in Chinese, now switching)
                if transcription_task:
                    transcription_task.cancel()
                    try:
                        await transcription_task
                    except Exception as e:
                        pass
                
                current_seek_time = float(command.get("timestamp", 0.0))
                language = command.get("language", "zh")

                # Update Static Context if provided (Persist it)
                if command.get("context"):
                    stream_state["static_context"] = command.get("context")

                # soft skip detection
                time_diff = abs(current_seek_time - stream_state["last_processed_time"])

                final_prompt = ""
                if time_diff <= 5.0 and stream_state["rolling_transcript"]:
                    final_prompt = (
                        stream_state["static_context"] + "\n\n" +
                        stream_state["rolling_transcript"]
                    )
                elif time_diff > 5:
                    final_prompt = stream_state["static_context"] + "\n"

                transcription_task = asyncio.create_task(
                    run_transcription(
                        websocket,
                        model,
                        audio_array,
                        current_seek_time,
                        language,
                        final_prompt,
                        stream_state
                    )
                )

    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"Error: {e}")
        await websocket.send_text(f"ERROR: {str(e)}")
    finally:
        # Cleanup unique file
        if transcription_task: transcription_task.cancel()
        if audio_file and os.path.exists(audio_file):
            os.remove(audio_file)

async def run_transcription(websocket: WebSocket, 
                            model: WhisperModel, 
                            audio_array: np.ndarray, 
                            start_time: float, 
                            language: str, 
                            context: str|None,
                            state: Dict ):
    try:
        # Sample rate is 16000. Index = Seconds * 16000
        start_sample = int(start_time * 16000)
        if start_sample > len(audio_array):
            await websocket.send_json({"status" : "End of video"})
            return
        
        audio_slice = audio_array[start_sample:]

        def get_segments():
            segments, info = model.transcribe(
                audio_slice,
                task="translate",
                language=language,
                beam_size=5,
                initial_prompt=context
            )
            return segments
        
        # Run generator in thread (so we don't block the main loop)
        segment_generator = await asyncio.to_thread(get_segments)

        for segment in segment_generator:
            real_start = segment.start + start_time
            real_end = segment.end + start_time
            text = segment.text

            # We track exactly where the model is currently looking
            state["last_processed_time"] = real_end
            
            # Append to rolling transcript (keep it limited to ~200 chars to avoid Prompt bloat)
            state["rolling_transcript"] += " " + text
            if len(state["rolling_transcript"]) > 200:
                state["rolling_transcript"] = state["rolling_transcript"][-200:]
        
            pay_load = {
                "type" : "subtitle",
                "start" : real_start,
                "end" : real_end,
                "text" : text
            }

            await websocket.send_json(pay_load)
            await asyncio.sleep(0.01)  # Yield to event loop
    except asyncio.CancelledError:
        print("Transcription stopped (Language change or seek).")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)