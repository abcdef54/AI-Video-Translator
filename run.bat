@echo off
setlocal enabledelayedexpansion
TITLE AI Video Translator

echo ===================================================
echo      STARTING AI VIDEO TRANSLATOR SYSTEM (DOCKER)
echo ===================================================

set IMAGE_NAME=ai-video-translator-backend
set CONTAINER_NAME=ai-video-translator-backend

:: 1. Build Docker image if it doesn't exist
docker image inspect %IMAGE_NAME% >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [INFO] Docker image '%IMAGE_NAME%' not found. Building it...
    docker build -t %IMAGE_NAME% -f dockerfile .
    if !ERRORLEVEL! neq 0 (
        echo [ERROR] Failed to build Docker image.
        pause
        exit /b 1
    )
) else (
    echo [INFO] Docker image '%IMAGE_NAME%' already exists.
)

:: 2. Stop and remove existing container if any
echo [INFO] Cleaning up old container if it exists...
docker stop %CONTAINER_NAME% >nul 2>nul
docker rm %CONTAINER_NAME% >nul 2>nul

:: 3. Start container
echo [INFO] Starting Backend Container...
where nvidia-smi >nul 2>nul
if %ERRORLEVEL% equ 0 (
    echo [INFO] Nvidia GPU detected. Starting container with GPU support...
    docker run -d --name %CONTAINER_NAME% --gpus all -p 8000:8000 -v "%CD%/models:/app/models" %IMAGE_NAME%
) else (
    echo [INFO] No Nvidia GPU detected. Starting container on CPU...
    docker run -d --name %CONTAINER_NAME% -p 8000:8000 -v "%CD%/models:/app/models" %IMAGE_NAME%
)

if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to start Docker container.
    pause
    exit /b 1
)

:: 4. Start Frontend HTTP Server
echo [INFO] Starting Frontend Server...
start "Frontend Server" cmd /k "cd frontend && python -m http.server 5500"

:: 5. Wait for backend to boot
echo [INFO] Waiting for backend to boot...
set /a retry=0
:loop
curl -s -o nul http://localhost:8000/docs
if %ERRORLEVEL% neq 0 (
    set /a retry+=1
    if !retry! gtr 30 (
        echo [ERROR] Backend failed to start in 30 seconds. Check docker logs:
        docker logs %CONTAINER_NAME%
        pause
        exit /b 1
    )
    timeout /t 1 /nobreak >nul
    goto loop
)

echo [INFO] Backend is up!

:: 6. Open browser
echo [INFO] Opening Frontend...
start http://localhost:5500

echo.
echo    System is running! 
echo    - Backend is running in Docker (container: %CONTAINER_NAME%).
echo    - Frontend server is running locally on port 5500.
echo.
pause