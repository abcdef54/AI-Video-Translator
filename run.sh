#!/bin/bash

echo "==================================================="
echo "     STARTING AI VIDEO TRANSLATOR SYSTEM (DOCKER)  "
echo "==================================================="

IMAGE_NAME="ai-video-translator-backend"
CONTAINER_NAME="ai-video-translator-backend"

# 1. Build Docker image if it doesn't exist
if ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
    echo "[INFO] Docker image '$IMAGE_NAME' not found. Building it..."
    docker build -t "$IMAGE_NAME" -f dockerfile .
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to build Docker image."
        exit 1
    fi
else
    echo "[INFO] Docker image '$IMAGE_NAME' already exists."
fi

# 2. Stop and remove existing container if any
echo "[INFO] Cleaning up old container if it exists..."
docker stop "$CONTAINER_NAME" >/dev/null 2>&1
docker rm "$CONTAINER_NAME" >/dev/null 2>&1

# 3. Start container
echo "[INFO] Starting Backend Container..."
if command -v nvidia-smi >/dev/null 2>&1; then
    echo "[INFO] Nvidia GPU detected. Starting container with GPU support..."
    docker run -d --name "$CONTAINER_NAME" --gpus all -p 8000:8000 -v "$(pwd)/models:/app/models" "$IMAGE_NAME"
else
    echo "[INFO] No Nvidia GPU detected. Starting container on CPU..."
    docker run -d --name "$CONTAINER_NAME" -p 8000:8000 -v "$(pwd)/models:/app/models" "$IMAGE_NAME"
fi

if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to start Docker container."
    exit 1
fi

# 4. Start Frontend HTTP Server
echo "[INFO] Starting Frontend Server..."
cd frontend
python3 -m http.server 5500 &
FRONTEND_PID=$!
cd ..

# 5. Wait for backend to boot
echo "[INFO] Waiting for backend to boot..."
RETRY=0
MAX_RETRIES=30
until curl -s -o /dev/null http://localhost:8000/docs; do
    RETRY=$((RETRY+1))
    if [ $RETRY -gt $MAX_RETRIES ]; then
        echo "[ERROR] Backend failed to start in $MAX_RETRIES seconds. Docker logs:"
        docker logs "$CONTAINER_NAME"
        kill "$FRONTEND_PID" >/dev/null 2>&1
        exit 1
    fi
    sleep 1
done

echo "[INFO] Backend is up!"

# 6. Open browser
echo "[INFO] Opening Frontend..."
if command -v xdg-open >/dev/null 2>&1; then
    xdg-open http://localhost:5500
elif command -v open >/dev/null 2>&1; then
    open http://localhost:5500
else
    echo "[INFO] Please open http://localhost:5500 in your browser."
fi

# Setup cleanup on script exit
trap "echo '[INFO] Stopping frontend and container...'; kill $FRONTEND_PID; docker stop $CONTAINER_NAME; exit" INT TERM
echo "System is running! Press [Ctrl+C] to stop the frontend server and backend container."
wait
