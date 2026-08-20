# 🎬 DubAI — Real AI Video Dubbing Tool

**100% Free | No API Keys | Fully Local**

Whisper + Edge-TTS + Google Translate + FFmpeg se real dubbing!

---

## ⚡ Quick Start (3 Steps)

### Step 1 — FFmpeg Install Karo (ek baar)
```
Ubuntu/Debian:  sudo apt install ffmpeg
Mac:            brew install ffmpeg
Windows:        https://ffmpeg.org/download.html  (PATH mein add karo)
```

### Step 2 — App Chalao

**Linux/Mac:**
```bash
chmod +x start.sh
./start.sh
```

**Windows:**
```
start_windows.bat  (double click)
```

### Step 3 — Browser mein kholo
```
http://localhost:8000
```

---

## 🤖 AI Pipeline (Sab Real Hai)

| Step | Technology | Kya Karta Hai |
|------|-----------|---------------|
| 1 | FFmpeg | Audio extract karta hai |
| 2 | OpenAI Whisper (local) | Speech ko text mein convert karta hai |
| 3 | Google Translate (free) | Target language mein translate karta hai |
| 4 | Microsoft Edge TTS (free) | AI voice se audio banata hai |
| 5 | FFmpeg | Audio ko sahi timing par assemble karta hai |
| 6 | FFmpeg | Video + dubbed audio + subtitles merge karta hai |

---

## 🌍 Supported Languages

**Input:** Hindi, English, Urdu, Bengali, Tamil, Arabic  
**Output:** English, Spanish, French, German, Japanese, Chinese, Korean, Portuguese, Russian, Hindi, Arabic, Turkish

---

## 📁 Output Files

- `dubbed_video.mp4` — Final dubbed video with subtitles
- `translated.srt` — Translated subtitle file
- `original.srt` — Original subtitle file  
- `translated.txt` — Full translated transcript

---

## 💡 Tips

- **Pehli baar** Whisper model download hoga (~140MB) — internet chahiye
- **Uske baad** sab offline kaam karta hai
- Short videos (< 5 min) fast process honge
- Clear audio = better results

---

## ❓ Troubleshooting

**Server nahi chala?**
```bash
pip install -r requirements.txt
python server.py
```

**Whisper slow hai?**
- `server.py` mein `whisper.load_model("base")` ko `"tiny"` kar do (faster)
- Ya `"small"` zyada accurate hoga

**FFmpeg error?**
```bash
ffmpeg -version   # check karo installed hai ya nahi
```
