import os
import asyncio
import gc
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from faster_whisper import WhisperModel
import json
import uuid
import numpy as np
import torch
from  utils import  download_audio, load_audio_to_numpy
import shutil

GLOBAL_MODEL = None
CURRENT_MODEL_SIZE = "large-v3"
model_map = {
    "large-v3" : "large",
    "medium" : "medium",
    "small" : "small",
    "tiny" : "tiny"
}
LOCAL_MODEL_DIR = "./models"

if torch.cuda.is_available():
    device = "cuda"
    compute_type = "float16"
else:
    device = "cpu"
    compute_type = "int8"

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

def safe_next(iterator):
    try:
        return next(iterator)
    except StopIteration:
        return None

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
        CURRENT_MODEL_SIZE = model_map[size_name]
        return True
    except Exception:
        return False

load_model("large") 

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        file_id = str(uuid.uuid4())
        file_path = f"{file_id}_{file.filename}"

        with open(file_path, 'wb+') as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        return {"status" : "success", "file_path" : file_path}
    except Exception as e:
        return {"status" : "erorr", "message" : str(e)}

@app.websocket("/ws/translate")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session_id = None
    audio_file = None
    audio_array = None
    transcription_task = None
    
    stream_state = {
                    "last_processed_time": 0.0,
                    "rolling_transcript": "", 
                    "static_context": "",
                    "language" : "zh",
                    "model_size" : CURRENT_MODEL_SIZE,
                    "url" : "",
                    "session_id" : session_id
                    }

    try:
        while True:
            data = await websocket.receive_text()
            command = json.loads(data)
            action = command.get("action")

            # Cancel existing task before major changes
            if action in ["load_video", "change_model", "change_language", "change_context", "translate"]:
                if transcription_task and not transcription_task.done():
                    transcription_task.cancel()
                    try:
                        await transcription_task
                    except asyncio.CancelledError:
                        pass # Expected

            if action == "load_video":  
                model_size = command.get("model_size")
                if model_size and model_size != stream_state["model_size"]:
                    await websocket.send_json({"status" : f"Switching to {model_size}..."})
                    success = await asyncio.to_thread(load_model, model_size)
                    
                    if success:
                        stream_state["model_size"] = model_size
                        await websocket.send_json({"status" : "New Model Ready", "model_size" : stream_state["model_size"]})
                    else:
                        await websocket.send_json({"status" : "Failed to change Model size", "model_size" : stream_state["model_size"]})


                url = command.get("url")
                if url:
                    stream_state["url"] = url
                    await websocket.send_json({
                        "status" : "Downloading Audio...",
                        "url" : url
                    })
                else: 
                    await websocket.send_json({
                        "status" : "Invalid URL",
                        "url" : url
                    })
                    continue
                
                stream_state["session_id"] = str(uuid.uuid4())
                
                try:
                    audio_file = await asyncio.to_thread(download_audio, stream_state["url"], stream_state["session_id"])
                    audio_array = await asyncio.to_thread(load_audio_to_numpy, audio_file)
                except Exception as e:
                    await websocket.send_json({
                        "status" : "Error loading audio",
                        "message" : str(e)
                    })
                    continue
                
                duration = len(audio_array) / 16000.0 if audio_array is not None else 0
                start_time = float(command.get("timestamp", 0.0))

                if command.get("language", "zh"):
                    stream_state["language"] = command.get("language", "zh")
                if command.get("context"): 
                    stream_state["static_context"] = command.get("context")

                # START the stream  immeadately
                transcription_task = asyncio.create_task(
                    run_transcription(websocket, GLOBAL_MODEL, audio_array, start_time, stream_state["language"], stream_state["static_context"])
                )

                await websocket.send_json({
                    "status" : "Ready to play",
                    "duration" : duration,
                    "language" : stream_state["language"],
                    "context" : stream_state["static_context"],
                    "model_size" : stream_state["model_size"],
                })

            
            elif action == "load_file":
                file_path = command.get("file_path")
                if not file_path or not os.path.exists(file_path):
                    await websocket.send_json({"status": "Error: File not found on server"})
                    continue

                stream_state["url"] = "Local File"
                stream_state["session_id"] = str(uuid.uuid4())
                audio_file = file_path

                try:
                    audio_array = await asyncio.to_thread(load_audio_to_numpy, audio_file)
                except Exception as e:
                    await websocket.send_json({"status": "Error processing audio", "message": str(e)})
                    continue

                duration = len(audio_array) / 16000.0 if audio_array is not None else 0
                start_time = float(command.get("timestamp", 0.0))

                if command.get("language", "zh"): stream_state["language"] = command.get("language", "zh")
                if command.get("context"): stream_state["static_context"] = command.get("context")

                transcription_task = asyncio.create_task(
                    run_transcription(websocket, GLOBAL_MODEL, audio_array, start_time, stream_state["language"], stream_state["static_context"])
                )

                await websocket.send_json({
                    "status": "Ready to play",
                    "duration": duration,
                    "language": stream_state["language"],
                    "context": stream_state["static_context"],
                    "model_size": stream_state["model_size"],
                })


            elif action == "init_config":
                await websocket.send_json({
                    "type" : "config",
                    "model_size" : stream_state["model_size"]
                })


            elif action == "change_model":
                new_size = command.get("model_size")
                if new_size != stream_state["model_size"]:
                    await websocket.send_json({"status" : f"Switching to {new_size}..."})
                    success = await asyncio.to_thread(load_model, new_size)
                    
                    if success:
                        stream_state["model_size"] = new_size
                        await websocket.send_json({"status" : f"New Model Ready", "model_size" : stream_state["model_size"]})
                        transcription_task = asyncio.create_task(
                            run_transcription(websocket, GLOBAL_MODEL, audio_array, start_time, stream_state["language"], stream_state["static_context"])
                        )
                    else:
                        await websocket.send_json({"status" : "Failed to change Model size", "model_size" : stream_state["model_size"]})
                    


            elif action == "change_language":
                new_lang = command.get("language")
                start_time = float(command.get("timestamp", 0.0))
                
                if new_lang and new_lang != stream_state["language"]:
                    stream_state["language"] = new_lang
                    await websocket.send_json({"status": "Language Changed", "language": new_lang})
                    
                    # Restart Transcription
                    transcription_task = asyncio.create_task(
                        run_transcription(websocket, GLOBAL_MODEL, audio_array, start_time, stream_state["language"], stream_state["static_context"])
                    )

            elif action == "change_context":
                new_context = command.get("context")
                start_time = float(command.get("timestamp", 0.0)) # Ensure key matches frontend
                
                if new_context != stream_state["static_context"]:
                    stream_state["static_context"] = new_context
                    await websocket.send_json({"status": "Context Changed"})
                    
                    # Restart Transcription
                    transcription_task = asyncio.create_task(
                        run_transcription(websocket, GLOBAL_MODEL, audio_array, start_time, stream_state["language"], stream_state["static_context"])
                    )

            elif action == "translate": 
                start_time = float(command.get("timestamp", 0.0))

                transcription_task = asyncio.create_task(
                    run_transcription(websocket, GLOBAL_MODEL, audio_array, start_time, stream_state["language"], stream_state["static_context"])
                )

                await websocket.send_json({
                    "status" : "Started translation",
                    "start_time" : start_time,
                    "language" : stream_state["language"],
                    "context" : stream_state["static_context"],
                    "model_size" : stream_state["model_size"]
                })

    except WebSocketDisconnect:
        print("Client disconnected")
    finally:
        if transcription_task:
            transcription_task.cancel()
        if audio_file and os.path.exists(audio_file):
            try:
                os.remove(audio_file)
            except:
                pass

async def run_transcription(websocket: WebSocket, model: WhisperModel, audio_array: np.ndarray, start_time: float, language: str, context: str):
    try:
        start_sample = int(start_time * 16000)
        if audio_array is None or start_sample >= len(audio_array):
            await websocket.send_json({"type": "silence", "start": start_time, "end": start_time + 1})
            return
        
        audio_slice = audio_array[start_sample:]

        def _init_generator():
            segments, _ = model.transcribe(
                audio_slice,
                task="translate",
                language=language,
                beam_size=10,
                patience=2.0,
                vad_filter=True,
                initial_prompt=context,
                condition_on_previous_text=True 
            )
            return segments
        
        segment_generator = await asyncio.to_thread(_init_generator)

        while True:
            if websocket.client_state.name != "CONNECTED" : break

            segment = await asyncio.to_thread(safe_next, segment_generator)
            if segment is None:
                await websocket.send_json({
                    "type" : "silence",
                    "start" : start_time,
                    "end" : start_time + 5
                })
                return

            real_start = segment.start + start_time
            real_end = segment.end + start_time
            
            payload = {
                "type" : "subtitle",
                "start" : real_start,
                "end" : real_end,
                "text" : segment.text,
                "language" : language
            }
            await websocket.send_json(payload)

    except asyncio.CancelledError:
        print("Transcription task cancelled")
        raise # Re-raise to ensure proper task cleanup
    except Exception as e:
        print(f"Transcribe Error: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)