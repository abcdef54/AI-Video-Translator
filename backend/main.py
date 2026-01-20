import os
import asyncio
import gc
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from faster_whisper import WhisperModel
import json
import uuid
import numpy as np
import torch
from   utils import  download_audio, load_audio_to_numpy

GLOBAL_MODEL = None
CURRENT_MODEL_SIZE = "medium"
LOCAL_MODEL_DIR = "./models"

if torch.cuda.is_available():
    device = "cuda"
    compute_type = "float16"
else:
    device = "cpu"
    compute_type = "int8"

app = FastAPI()



def load_model(size_name):
    global GLOBAL_MODEL, CURRENT_MODEL_SIZE
    if GLOBAL_MODEL is not None:
        del GLOBAL_MODEL
        gc.collect()
        if torch.cuda.is_available(): torch.cuda.empty_cache()

    print(f"Loading {size_name}...")
    try:
        model_path = f"{LOCAL_MODEL_DIR}/{size_name}"
        if os.path.exists(model_path):
            GLOBAL_MODEL = WhisperModel(model_path, device=device, compute_type=compute_type)
        else:
            GLOBAL_MODEL = WhisperModel(size_name, device=device, compute_type=compute_type)
        CURRENT_MODEL_SIZE = size_name
        return True
    except Exception:
        return False

load_model("medium") 

@app.websocket("/ws/translate")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session_id = str(uuid.uuid4())
    audio_file = None
    audio_array = None
    transcription_task = None
    
    stream_state = { "last_processed_time": 0.0, "rolling_transcript": "", "static_context": "" }

    try:
        while True:
            data = await websocket.receive_text()
            command = json.loads(data)
            action = command.get("action")

            if action == "load_video":
                if transcription_task: transcription_task.cancel()
                
                url = command.get("url")
                await websocket.send_json({"status" : "Downloading Audio..."})
                audio_file = await asyncio.to_thread(download_audio, url, session_id)
                audio_array = await asyncio.to_thread(load_audio_to_numpy, audio_file)
                
                duration = len(audio_array) / 16000.0 if audio_array is not None else 0
                await websocket.send_json({"status" : "Ready to play", "duration": duration})

                # START the stream  immeadately
                start_time = float(command.get("timestamp", 0.0))
                language = command.get("language", "zh")
                if command.get("context"): stream_state["static_context"] = command.get("context")

                transcription_task = asyncio.create_task(
                    run_transcription(websocket, GLOBAL_MODEL, audio_array, start_time, language, stream_state["static_context"])
                )

            elif action == "change_model":
                new_size = command.get("model_size")
                if new_size != CURRENT_MODEL_SIZE:
                    if transcription_task: transcription_task.cancel()
                    await websocket.send_json({"status" : f"Switching to {new_size}..."})
                    await asyncio.to_thread(load_model, new_size)
                    await websocket.send_json({"status" : f"Model Ready ({new_size})"})

            elif action == "translate": 
                if transcription_task: 
                    transcription_task.cancel()
                    try: await transcription_task 
                    except: pass

                start_time = float(command.get("timestamp", 0.0))
                language = command.get("language", "zh")
                if command.get("context"): stream_state["static_context"] = command.get("context")

                transcription_task = asyncio.create_task(
                    run_transcription(websocket, GLOBAL_MODEL, audio_array, start_time, language, stream_state["static_context"])
                )

    except WebSocketDisconnect:
        print("Client disconnected")
    finally:
        if transcription_task: transcription_task.cancel()
        if audio_file and os.path.exists(audio_file): os.remove(audio_file)

async def run_transcription(websocket: WebSocket, model: WhisperModel, audio_array: np.ndarray, start_time: float, language: str, context: str):
    try:
        start_sample = int(start_time * 16000)
        if audio_array is None or start_sample >= len(audio_array):
            return
        
        audio_slice = audio_array[start_sample:]

        def get_segments():
            segments, _ = model.transcribe(
                audio_slice,
                task="translate",
                language=language,
                beam_size=5,
                initial_prompt=context,
                condition_on_previous_text=True 
            )
            return segments
        
        segment_generator = await asyncio.to_thread(get_segments)

        for segment in segment_generator:
            # Check if client closed connection, stop processing
            if websocket.client_state.name != "CONNECTED": break

            real_start = segment.start + start_time
            real_end = segment.end + start_time
            
            payload = {
                "type" : "subtitle",
                "start" : real_start,
                "end" : real_end,
                "text" : segment.text
            }
            await websocket.send_json(payload)
            await asyncio.sleep(0.01)

    except asyncio.CancelledError:
        pass 
    except Exception as e:
        print(f"Transcribe Error: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)