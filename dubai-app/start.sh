#!/bin/bash
# ================================================================
# DubAI — Real AI Video Dubbing Tool
# Setup & Run Script
# ================================================================

echo ""
echo "╔═══════════════════════════════════════════╗"
echo "║        🎬  DubAI Setup Script             ║"
echo "║   Real AI Dubbing — Free, No API Keys     ║"
echo "╚═══════════════════════════════════════════╝"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "❌ Python3 nahi mila. Install karo: https://python.org"
    exit 1
fi
echo "✅ Python3 mila: $(python3 --version)"

# Check ffmpeg
if ! command -v ffmpeg &>/dev/null; then
    echo ""
    echo "⚠️  FFmpeg nahi mila. Install karo:"
    echo "   Ubuntu/Debian: sudo apt install ffmpeg"
    echo "   Mac:           brew install ffmpeg"
    echo "   Windows:       https://ffmpeg.org/download.html"
    echo ""
    read -p "FFmpeg install karne ke baad Enter dabaao..."
fi
echo "✅ FFmpeg mila"

# Create venv if not exists
if [ ! -d "venv" ]; then
    echo ""
    echo "📦 Virtual environment bana raha hai..."
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate || source venv/Scripts/activate 2>/dev/null

echo ""
echo "📦 Dependencies install ho rahi hain (pehli baar thoda time lagega)..."
echo ""

pip install --upgrade pip -q

# Core dependencies
pip install \
    fastapi==0.104.1 \
    uvicorn[standard]==0.24.0 \
    python-multipart==0.0.6 \
    aiofiles==23.2.1 \
    -q && echo "  ✅ FastAPI installed"

pip install \
    openai-whisper==20231117 \
    -q && echo "  ✅ Whisper installed"

pip install \
    edge-tts==6.1.9 \
    -q && echo "  ✅ Edge-TTS installed"

pip install \
    deep-translator==1.11.4 \
    -q && echo "  ✅ Translator installed"

echo ""
echo "✅ Sab kuch install ho gaya!"
echo ""
echo "╔═══════════════════════════════════════════╗"
echo "║  🚀 Server shuru ho raha hai...           ║"
echo "║  Browser mein kholo: http://localhost:8000 ║"
echo "║  Band karne ke liye: Ctrl+C               ║"
echo "╚═══════════════════════════════════════════╝"
echo ""

# Run server
python3 server.py
