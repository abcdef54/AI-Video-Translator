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
    "large-v3" : "large-v3",
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

load_model("large-v3") 

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
                    "accuracy_mode": "maximum",
                    "url" : "",
                    "session_id" : session_id
                    }

    try:
        while True:
            data = await websocket.receive_text()
            command = json.loads(data)
            action = command.get("action")

            # Cancel existing task before major changes
            if action in {"load_video", "change_language", "translate"}:
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
                if command.get("accuracy_mode"):
                    stream_state["accuracy_mode"] = command.get("accuracy_mode")

                # START the stream  immeadately
                transcription_task = asyncio.create_task(
                    run_transcription(websocket, GLOBAL_MODEL, audio_array, start_time, stream_state)
                )

                await websocket.send_json({
                    "status" : "Ready to play",
                    "duration" : duration,
                    "language" : stream_state["language"],
                    "context" : stream_state["static_context"],
                    "model_size" : stream_state["model_size"],
                    "accuracy_mode" : stream_state["accuracy_mode"],
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
                if command.get("accuracy_mode"): stream_state["accuracy_mode"] = command.get("accuracy_mode")

                transcription_task = asyncio.create_task(
                    run_transcription(websocket, GLOBAL_MODEL, audio_array, start_time, stream_state)
                )

                await websocket.send_json({
                    "status": "Ready to play",
                    "duration": duration,
                    "language": stream_state["language"],
                    "context": stream_state["static_context"],
                    "model_size": stream_state["model_size"],
                    "accuracy_mode": stream_state["accuracy_mode"],
                })


            elif action == "init_config":
                await websocket.send_json({
                    "type" : "config",
                    "model_size" : stream_state["model_size"],
                    "accuracy_mode": stream_state["accuracy_mode"]
                })


            elif action == "change_language":
                new_lang = command.get("language")
                start_time = float(command.get("timestamp", 0.0))
                
                if new_lang and new_lang != stream_state["language"]:
                    stream_state["language"] = new_lang
                    await websocket.send_json({"status": "Language Changed", "language": new_lang})
                    
                    # Restart Transcription
                    transcription_task = asyncio.create_task(
                        run_transcription(websocket, GLOBAL_MODEL, audio_array, start_time, stream_state)
                    )

            elif action == "translate": 
                start_time = float(command.get("timestamp", 0.0))

                transcription_task = asyncio.create_task(
                    run_transcription(websocket, GLOBAL_MODEL, audio_array, start_time, stream_state)
                )

                await websocket.send_json({
                    "status" : "Started translation",
                    "start_time" : start_time,
                    "language" : stream_state["language"],
                    "context" : stream_state["static_context"],
                    "model_size" : stream_state["model_size"],
                    "accuracy_mode" : stream_state["accuracy_mode"]
                })

            elif action == "extract_transcript":
                if stream_state.get("is_completed") and stream_state.get("aligned_transcript"):
                    import io
                    import csv
                    
                    output = io.StringIO()
                    writer = csv.writer(output)
                    writer.writerow(["Start Time (s)", "End Time (s)", f"Original ({stream_state['language']})", "Translated (English)"])
                    for seg in stream_state["aligned_transcript"]:
                        writer.writerow([
                            f"{seg['start']:.2f}",
                            f"{seg['end']:.2f}",
                            seg["original"].strip(),
                            seg["translated"].strip()
                        ])
                    
                    csv_data = output.getvalue()
                    await websocket.send_json({
                        "type": "transcript_csv",
                        "csv_data": csv_data
                    })
                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Transcription not completed yet"
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

async def run_transcription(websocket: WebSocket, model: WhisperModel, audio_array: np.ndarray, start_time: float, stream_state: dict):
    language = stream_state.get("language", "zh")
    context = stream_state.get("static_context", "")
    accuracy_mode = stream_state.get("accuracy_mode", "maximum")
    
    orig_task = None
    try:
        start_sample = int(start_time * 16000)
        if audio_array is None or start_sample >= len(audio_array):
            await websocket.send_json({"type": "silence", "start": start_time, "end": start_time + 1})
            return
        
        audio_slice = audio_array[start_sample:]
 
        if accuracy_mode == "balanced":
            transcribe_kwargs = {
                "beam_size": 5,
                "patience": 1.0,
                "best_of": 1,
                "temperature": [0.0, 0.2, 0.4],
                "vad_filter": True,
                "vad_parameters": dict(
                    threshold=0.6,
                ),
                "no_speech_threshold": 0.8,
                "initial_prompt": context,
                "condition_on_previous_text": False
            }
        else:
            # default to maximum accuracy
            transcribe_kwargs = {
                "beam_size": 10,
                "patience": 2.0,
                "best_of": 5,
                "temperature": [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
                "vad_filter": True,
                "vad_parameters": dict(
                    threshold=0.6,
                    min_speech_duration_ms=250,
                    speech_pad_ms=400
                ),
                "no_speech_threshold": 0.8,
                "initial_prompt": context,
                "condition_on_previous_text": False
            }

        # Start original language transcription in background thread
        def _run_transcribe():
            try:
                segments, _ = model.transcribe(
                    audio_slice,
                    task="transcribe",
                    language=language,
                    **transcribe_kwargs
                )
                return [{"start": s.start, "end": s.end, "text": s.text} for s in segments]
            except Exception as e:
                print(f"Transcribe background error: {e}")
                return []

        orig_task = asyncio.create_task(asyncio.to_thread(_run_transcribe))

        # Start translation generator
        def _init_generator():
            segments, _ = model.transcribe(
                audio_slice,
                task="translate",
                language=language,
                **transcribe_kwargs
            )
            return segments
        
        segment_generator = await asyncio.to_thread(_init_generator)
        translated_segments = []

        while True:
            if websocket.client_state.name != "CONNECTED" : break

            segment = await asyncio.to_thread(safe_next, segment_generator)
            if segment is None:
                # Wait for the background original language transcription to finish
                orig_segments = await orig_task
                
                # Align transcribed (original) and translated (English) segments
                aligned = []
                for orig in orig_segments:
                    best_trans = None
                    best_overlap = 0.0
                    orig_start_real = orig["start"] + start_time
                    orig_end_real = orig["end"] + start_time
                    
                    for trans in translated_segments:
                        overlap = max(0.0, min(orig_end_real, trans["end"]) - max(orig_start_real, trans["start"]))
                        if overlap > best_overlap:
                            best_overlap = overlap
                            best_trans = trans
                    
                    aligned.append({
                        "start": orig_start_real,
                        "end": orig_end_real,
                        "original": orig["text"],
                        "translated": best_trans["text"] if best_trans else ""
                    })
                
                stream_state["aligned_transcript"] = aligned
                stream_state["is_completed"] = True
                
                await websocket.send_json({
                    "type": "completed",
                    "duration": len(audio_array) / 16000.0
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
            translated_segments.append(payload)
            await websocket.send_json(payload)

    except asyncio.CancelledError:
        print("Transcription task cancelled")
        if orig_task and not orig_task.done():
            orig_task.cancel()
        raise # Re-raise to ensure proper task cleanup
    except Exception as e:
        print(f"Transcribe Error: {e}")
        if orig_task and not orig_task.done():
            orig_task.cancel()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)