@echo off
echo.
echo ╔═══════════════════════════════════════════╗
echo ║        DubAI Setup Script (Windows)      ║
echo ╚═══════════════════════════════════════════╝
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo Python nahi mila! Install karo: https://python.org
    pause
    exit /b
)

if not exist venv (
    echo Virtual environment bana raha hai...
    python -m venv venv
)

call venv\Scripts\activate.bat

echo.
echo Dependencies install ho rahi hain...
echo.

pip install fastapi uvicorn python-multipart aiofiles openai-whisper edge-tts deep-translator -q

echo.
echo ╔═══════════════════════════════════════════╗
echo ║  Server shuru ho raha hai...             ║
echo ║  http://localhost:8000 browser mein kholo ║
echo ║  Band karne ke liye Ctrl+C dabaao        ║
echo ╚═══════════════════════════════════════════╝
echo.

python server.py
pause
