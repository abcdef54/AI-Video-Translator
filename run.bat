@echo off
TITLE AI Video Translator

echo ===================================================
echo      STARTING AI VIDEO TRANSLATOR SYSTEM
echo ===================================================

:: Activate the virtual environment
call .venv\Scripts\activate

:: 1. Start Backend
echo [1/3] Launching Backend Server...
start "AI Backend Server" cmd /k "call .venv\Scripts\activate && python backend/main.py"

:: 2. Wait for backend
echo [INFO] Waiting for backend to boot...
timeout /t 3 /nobreak >nul

:: 3. Start Frontend HTTP Server
echo [2/3] Starting Frontend Server...
start "Frontend Server" cmd /k "cd frontend && python -m http.server 5500"

:: 4. Open browser
timeout /t 2 /nobreak >nul
echo [3/3] Opening Frontend...
start http://localhost:5500


echo.
echo    System is running! 
echo    - Backend is running in the other window.
echo    - Close that window to stop the server.
echo    - If you want faster startup next time, pre-download the models.
echo    - The next time you run this script with the same model size, it will start faster.
echo    Thank you for using AI Video Translator!
echo.
pause