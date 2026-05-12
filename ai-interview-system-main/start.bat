@echo off
echo Starting AI Interview System...
echo.

echo [1/4] Starting Flask Backend...
start "Flask Backend" cmd /k "cd /d %~dp0 && C:\Users\User\AppData\Local\Programs\Python\Python310\python.exe app.py"

echo [2/4] Starting FastAPI Backend...
start "FastAPI Backend" cmd /k "cd /d %~dp0\backend && C:\Users\User\AppData\Local\Programs\Python\Python310\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

echo [3/4] Starting Speech Service...
start "Speech Service" cmd /k "cd /d %~dp0\speech_service && C:\Users\User\AppData\Local\Programs\Python\Python310\python.exe app.py"

echo [4/4] Waiting for services to start...
timeout /t 8 /nobreak >nul

echo.
echo ========================================
echo AI Interview System Started!
echo ========================================
echo Flask Frontend: http://127.0.0.1:5000
echo FastAPI Backend: http://127.0.0.1:8000
echo Speech Service: http://127.0.0.1:9000
echo.
echo Open http://127.0.0.1:5000 in your browser
echo ========================================
echo.
pause
