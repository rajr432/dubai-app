"""
DubAI — Real AI Video Dubbing Server
Free APIs: Whisper (local) + deep-translator + edge-tts + ffmpeg
"""

import os, uuid, asyncio, json, subprocess, shutil, time
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import aiofiles

app = FastAPI(title="DubAI Server")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Language code mapping for edge-tts voices
VOICE_MAP = {
    "en": "en-US-AriaNeural",
    "hi": "hi-IN-SwaraNeural",
    "es": "es-ES-ElviraNeural",
    "fr": "fr-FR-DeniseNeural",
    "de": "de-DE-KatjaNeural",
    "ja": "ja-JP-NanamiNeural",
    "zh": "zh-CN-XiaoxiaoNeural",
    "ko": "ko-KR-SunHiNeural",
    "ar": "ar-SA-ZariyahNeural",
    "pt": "pt-BR-FranciscaNeural",
    "ru": "ru-RU-SvetlanaNeural",
    "tr": "tr-TR-EmelNeural",
    "ur": "ur-PK-UzmaNeural",
    "bn": "bn-BD-NabanitaNeural",
    "it": "it-IT-ElsaNeural",
}

VOICE_STYLE_MAP = {
    "en": {"male": "en-US-GuyNeural", "female": "en-US-AriaNeural", "young": "en-US-AnaNeural"},
    "hi": {"male": "hi-IN-MadhurNeural", "female": "hi-IN-SwaraNeural", "young": "hi-IN-SwaraNeural"},
    "es": {"male": "es-ES-AlvaroNeural", "female": "es-ES-ElviraNeural", "young": "es-MX-DaliaNeural"},
    "fr": {"male": "fr-FR-HenriNeural", "female": "fr-FR-DeniseNeural", "young": "fr-FR-EloiseNeural"},
    "de": {"male": "de-DE-ConradNeural", "female": "de-DE-KatjaNeural", "young": "de-DE-AmalaNeural"},
    "ja": {"male": "ja-JP-KeitaNeural", "female": "ja-JP-NanamiNeural", "young": "ja-JP-AoiNeural"},
    "zh": {"male": "zh-CN-YunyangNeural", "female": "zh-CN-XiaoxiaoNeural", "young": "zh-CN-XiaoyiNeural"},
    "ko": {"male": "ko-KR-InJoonNeural", "female": "ko-KR-SunHiNeural", "young": "ko-KR-SoonBokNeural"},
    "ar": {"male": "ar-SA-HamedNeural", "female": "ar-SA-ZariyahNeural", "young": "ar-EG-SalmaNeural"},
    "pt": {"male": "pt-BR-AntonioNeural", "female": "pt-BR-FranciscaNeural", "young": "pt-BR-BrendaNeural"},
    "ru": {"male": "ru-RU-DmitryNeural", "female": "ru-RU-SvetlanaNeural", "young": "ru-RU-DariyaNeural"},
    "tr": {"male": "tr-TR-AhmetNeural", "female": "tr-TR-EmelNeural", "young": "tr-TR-EmelNeural"},
}

# Progress store (in-memory)
progress_store = {}
cancel_flags = {}
job_settings = {}
MAX_UPLOAD_BYTES = 500 * 1024 * 1024


def run_cmd(cmd: list, cwd=None) -> tuple[int, str, str]:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.returncode, result.stdout, result.stderr


def update_progress(job_id: str, step: str, pct: int, msg: str, status: str = "running"):
    progress_store[job_id] = {
        "step": step,
        "percent": pct,
        "message": msg,
        "status": status,
    }
    print(f"[{job_id[:8]}] {step}: {pct}% — {msg}")


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/favicon.ico")
async def favicon():
    return Response(
        content="""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
        <defs><linearGradient id="g" x1="0" x2="1"><stop stop-color="#8b5cf6"/><stop offset="1" stop-color="#e0454a"/></linearGradient></defs>
        <rect width="64" height="64" rx="16" fill="#111827"/>
        <path d="M17 20h30v8H25v8h18v8H25v8h22v8H17z" fill="url(#g)"/>
        </svg>""",
        media_type="image/svg+xml",
    )


@app.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    """Save uploaded video, return job_id"""
    allowed_extensions = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
    extension = Path(file.filename or "").suffix.lower()
    if not file.content_type or not file.content_type.startswith("video/") or extension not in allowed_extensions:
        raise HTTPException(400, "Sirf video files allowed hain")

    job_id = str(uuid.uuid4())
    job_dir = UPLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    ext = extension or ".mp4"
    video_path = job_dir / f"input{ext}"

    async with aiofiles.open(video_path, "wb") as f:
        total_bytes = 0
        while chunk := await file.read(1024 * 1024):
            total_bytes += len(chunk)
            if total_bytes > MAX_UPLOAD_BYTES:
                shutil.rmtree(job_dir, ignore_errors=True)
                raise HTTPException(413, "Video 500MB se chhoti honi chahiye")
            await f.write(chunk)

    # Get video duration & info via ffprobe
    rc, out, _ = run_cmd([
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", str(video_path)
    ])
    info = {}
    if rc == 0:
        data = json.loads(out)
        fmt = data.get("format", {})
        streams = data.get("streams", [])
        video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
        info = {
            "duration": float(fmt.get("duration", 0)),
            "size": int(fmt.get("size", 0)),
            "width": video_stream.get("width", 0),
            "height": video_stream.get("height", 0),
        }

    return {"job_id": job_id, "filename": file.filename, "info": info}


@app.post("/process")
async def process_video(
    job_id: str = Form(...),
    source_lang: str = Form("hi"),
    target_lang: str = Form("en"),
    voice_type: str = Form("female"),
    speed: float = Form(1.0),
    add_subtitles: bool = Form(True),
    noise_remove: bool = Form(True),
    keep_music: bool = Form(False),
    music_volume: float = Form(0.18),
    voice_volume: float = Form(1.0),
    subtitle_style: str = Form("classic"),
    subtitle_position: str = Form("bottom"),
    output_quality: str = Form("standard"),
):
    """Start full AI pipeline in background"""
    job_dir = UPLOAD_DIR / job_id
    if not job_dir.exists():
        raise HTTPException(404, "Job nahi mila")

    # Find input video
    input_files = list(job_dir.glob("input.*"))
    if not input_files:
        raise HTTPException(404, "Video file nahi mili")
    input_video = input_files[0]

    if progress_store.get(job_id, {}).get("status") == "running":
        raise HTTPException(409, "Ye job already process ho rahi hai")
    cancel_flags[job_id] = False
    job_settings[job_id] = {
        "source_lang": source_lang, "target_lang": target_lang,
        "voice_type": voice_type, "speed": speed, "add_subtitles": add_subtitles,
        "noise_remove": noise_remove, "keep_music": keep_music,
        "music_volume": max(0, min(1, music_volume)), "voice_volume": max(0.2, min(2, voice_volume)),
        "subtitle_style": subtitle_style, "subtitle_position": subtitle_position,
        "output_quality": output_quality,
    }
    update_progress(job_id, "queued", 0, "Pipeline shuru ho rahi hai...")

    # Run pipeline in background
    asyncio.create_task(run_pipeline(
        job_id, input_video, source_lang, target_lang,
        voice_type, speed, add_subtitles, noise_remove, keep_music,
        music_volume, voice_volume, subtitle_style, subtitle_position, output_quality
    ))

    return {"status": "started", "job_id": job_id}


async def run_pipeline(
    job_id, input_video, source_lang, target_lang,
    voice_type, speed, add_subtitles, noise_remove, keep_music,
    music_volume, voice_volume, subtitle_style, subtitle_position, output_quality
):
    job_dir = UPLOAD_DIR / job_id
    out_dir = OUTPUT_DIR / job_id
    out_dir.mkdir(exist_ok=True)

    try:
        def ensure_not_cancelled():
            if cancel_flags.get(job_id):
                raise asyncio.CancelledError()

        # ── STEP 1: Extract Audio ────────────────────────────────────────────
        update_progress(job_id, "extract", 5, "Video se audio nikal raha hai...")
        audio_path = job_dir / "audio.wav"
        extract_cmd = [
            "ffmpeg", "-y", "-i", str(input_video),
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        ]
        if noise_remove:
            extract_cmd += ["-af", "highpass=f=80,lowpass=f=12000,afftdn=nr=12:nf=-25"]
        extract_cmd += [str(audio_path)]
        rc, _, err = run_cmd(extract_cmd)
        if rc != 0:
            raise Exception(f"Audio extraction failed: {err}")
        update_progress(job_id, "extract", 15, "Audio extract ho gaya ✓")

        # ── STEP 2: Speech to Text (Whisper) ────────────────────────────────
        update_progress(job_id, "transcribe", 20, "Whisper AI speech samajh raha hai...")
        import whisper
        model = whisper.load_model("base")  # base = fast & free
        result = model.transcribe(str(audio_path), language=source_lang if source_lang != "auto" else None)

        segments = result["segments"]
        full_text = result["text"].strip()
        detected_lang = result.get("language") or source_lang
        if source_lang == "auto":
            source_lang = detected_lang
        update_progress(job_id, "transcribe", 35, f"Text ready: {len(segments)} segments ✓")

        # Save original transcript
        transcript_path = out_dir / "original_transcript.txt"
        transcript_path.write_text(full_text, encoding="utf-8")

        # ── STEP 3: Translate ────────────────────────────────────────────────
        update_progress(job_id, "translate", 40, "AI translate kar raha hai...")
        from deep_translator import GoogleTranslator

        translator = GoogleTranslator(source=source_lang, target=target_lang)

        translated_segments = []
        for seg in segments:
            try:
                translated = translator.translate(seg["text"].strip())
            except Exception:
                translated = seg["text"]  # fallback
            translated_segments.append({
                "start": seg["start"],
                "end": seg["end"],
                "original": seg["text"].strip(),
                "translated": translated,
            })

        full_translated = " ".join(s["translated"] for s in translated_segments)
        translated_path = out_dir / "translated.txt"
        translated_path.write_text(full_translated, encoding="utf-8")
        update_progress(job_id, "translate", 55, "Translation complete ✓")

        # ── STEP 4: Generate SRT Subtitles ──────────────────────────────────
        update_progress(job_id, "subtitles", 58, "Subtitles bana raha hai...")
        srt_orig = out_dir / "original.srt"
        srt_trans = out_dir / "translated.srt"

        def to_srt_time(seconds):
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = int(seconds % 60)
            ms = int((seconds - int(seconds)) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

        orig_srt_content = ""
        trans_srt_content = ""
        for i, seg in enumerate(translated_segments, 1):
            t_start = to_srt_time(seg["start"])
            t_end = to_srt_time(seg["end"])
            orig_srt_content += f"{i}\n{t_start} --> {t_end}\n{seg['original']}\n\n"
            trans_srt_content += f"{i}\n{t_start} --> {t_end}\n{seg['translated']}\n\n"

        srt_orig.write_text(orig_srt_content, encoding="utf-8")
        srt_trans.write_text(trans_srt_content, encoding="utf-8")
        update_progress(job_id, "subtitles", 62, "Subtitles ready ✓")

        # ── STEP 5: Text-to-Speech (Edge TTS) ──────────────────────────────
        update_progress(job_id, "tts", 65, "AI voice se dubbing ban rahi hai...")
        voice = VOICE_STYLE_MAP.get(target_lang, {}).get(voice_type) or VOICE_MAP.get(target_lang, "en-US-AriaNeural")

        # Generate TTS for each segment separately for better timing
        segment_audios = []
        dubbed_chunks_dir = job_dir / "chunks"
        dubbed_chunks_dir.mkdir(exist_ok=True)

        import edge_tts

        for i, seg in enumerate(translated_segments):
            ensure_not_cancelled()
            chunk_path = dubbed_chunks_dir / f"chunk_{i:04d}.mp3"
            text = seg["translated"]
            if not text.strip():
                text = "..."

            communicate = edge_tts.Communicate(text, voice, rate=f"+{int((speed-1)*100)}%")
            await communicate.save(str(chunk_path))
            segment_audios.append({
                "path": str(chunk_path),
                "start": seg["start"],
                "end": seg["end"],
            })

            pct = 65 + int((i / max(1, len(translated_segments))) * 15)
            update_progress(job_id, "tts", pct, f"Segment {i+1}/{len(translated_segments)} voiced...")

        update_progress(job_id, "tts", 80, "Voice synthesis complete ✓")

        # ── STEP 6: Assemble dubbed audio with ffmpeg ───────────────────────
        update_progress(job_id, "assemble", 82, "Audio assemble kar raha hai...")

        # Get total video duration
        rc, out, _ = run_cmd([
            "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
            "-of", "csv=p=0", str(input_video)
        ])
        total_duration = float(out.strip()) if rc == 0 else 60.0

        # Build complex filter: silence base + each segment at correct timestamp
        filter_parts = []
        inputs = ["-i", str(input_video)]

        ensure_not_cancelled()
        # Add silence as base track
        filter_str = f"aevalsrc=0:duration={total_duration}[base];"

        for i, seg in enumerate(segment_audios):
            inputs += ["-i", seg["path"]]
            filter_str += f"[{i+1}:a]adelay={int(seg['start']*1000)}|{int(seg['start']*1000)}[a{i}];"

        # Mix all segments with base
        mix_inputs = "[base]" + "".join(f"[a{i}]" for i in range(len(segment_audios)))
        filter_str += f"{mix_inputs}amix=inputs={len(segment_audios)+1}:normalize=0,volume={voice_volume}[dubbed]"
        has_original_audio = any(s.get("codec_type") == "audio" for s in json.loads(run_cmd([
            "ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", str(input_video)
        ])[1]).get("streams", []))
        if keep_music and has_original_audio:
            filter_str += f";[0:a]volume={music_volume}[music];[dubbed][music]amix=inputs=2:duration=longest:normalize=0[final]"
            audio_label = "[final]"
        else:
            audio_label = "[dubbed]"

        dubbed_audio_path = job_dir / "dubbed_audio.aac"
        cmd = ["ffmpeg", "-y"] + inputs + [
            "-filter_complex", filter_str,
            "-map", audio_label,
            "-c:a", "aac", "-b:a", "192k",
            str(dubbed_audio_path)
        ]
        rc, _, err = run_cmd(cmd)
        if rc != 0:
            # Fallback: simple concat
            update_progress(job_id, "assemble", 84, "Fallback audio method...")
            concat_list = job_dir / "concat.txt"
            with open(concat_list, "w") as f:
                for seg in segment_audios:
                    f.write(f"file '{seg['path']}'\n")
            run_cmd([
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(concat_list), str(dubbed_audio_path)
            ])

        update_progress(job_id, "assemble", 88, "Audio assembled ✓")

        # ── STEP 7: Merge video + dubbed audio + optional subtitles ────────
        update_progress(job_id, "render", 90, "Final video render ho raha hai...")
        output_video = out_dir / "dubbed_video.mp4"

        style_map = {
            "classic": "FontSize=20,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2",
            "yellow": "FontSize=20,PrimaryColour=&H0000FFFF,OutlineColour=&H00000000,Outline=2",
            "minimal": "FontSize=18,PrimaryColour=&H00FFFFFF,Outline=0,BorderStyle=0",
        }
        alignment = {"bottom": "2", "center": "5", "top": "8"}.get(subtitle_position, "2")
        subtitle_style_value = style_map.get(subtitle_style, style_map["classic"]) + f",Alignment={alignment}"
        quality_map = {"fast": ("23", "veryfast"), "standard": ("21", "fast"), "high": ("18", "medium")}
        crf, preset = quality_map.get(output_quality, quality_map["standard"])
        if add_subtitles:
            # Burn subtitles into video
            cmd = [
                "ffmpeg", "-y",
                "-i", str(input_video),
                "-i", str(dubbed_audio_path),
                 "-vf", f"subtitles={str(srt_trans)}:force_style='{subtitle_style_value}'",
                "-map", "0:v", "-map", "1:a",
                 "-c:v", "libx264", "-crf", crf, "-preset", preset,
                "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                str(output_video)
            ]
        else:
            cmd = [
                "ffmpeg", "-y",
                "-i", str(input_video),
                "-i", str(dubbed_audio_path),
                "-map", "0:v", "-map", "1:a",
                "-c:v", "copy", "-c:a", "aac",
                "-shortest",
                str(output_video)
            ]

        rc, _, err = run_cmd(cmd)
        if rc != 0:
            raise Exception(f"Video render failed: {err}")

        update_progress(job_id, "done", 100, "Video ready hai! 🎉", status="done")

        # Save results manifest
        manifest = {
            "job_id": job_id,
            "status": "done",
            "created_at": time.time(),
            "detected_language": detected_lang,
            "settings": job_settings.get(job_id, {}),
            "files": {
                "video": f"/download/{job_id}/dubbed_video.mp4",
                "srt_translated": f"/download/{job_id}/translated.srt",
                "srt_original": f"/download/{job_id}/original.srt",
                "transcript": f"/download/{job_id}/translated.txt",
                "original_transcript": f"/download/{job_id}/original_transcript.txt",
            },
            "segments": translated_segments,
        }
        (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))

    except asyncio.CancelledError:
        update_progress(job_id, "cancelled", 0, "Processing cancel kar diya gaya", status="cancelled")
    except Exception as e:
        update_progress(job_id, "error", 0, str(e), status="error")
        print(f"ERROR [{job_id[:8]}]: {e}")


@app.get("/progress/{job_id}")
async def get_progress(job_id: str):
    return progress_store.get(job_id, {"step": "unknown", "percent": 0, "message": "...", "status": "waiting"})


@app.post("/cancel/{job_id}")
async def cancel_job(job_id: str):
    current = progress_store.get(job_id)
    if not current:
        raise HTTPException(404, "Job nahi mila")
    if current.get("status") not in {"running", "waiting"}:
        return {"status": current.get("status"), "job_id": job_id}
    cancel_flags[job_id] = True
    return {"status": "cancelling", "job_id": job_id}


@app.get("/jobs")
async def list_jobs():
    jobs = []
    for job_id, progress in progress_store.items():
        item = {"job_id": job_id, **progress}
        manifest = OUTPUT_DIR / job_id / "manifest.json"
        if manifest.exists():
            try:
                data = json.loads(manifest.read_text())
                item["files"] = data.get("files", {})
                item["detected_language"] = data.get("detected_language")
            except json.JSONDecodeError:
                pass
        jobs.append(item)
    return sorted(jobs, key=lambda job: job.get("job_id", ""), reverse=True)


@app.get("/settings")
async def get_settings():
    return {
        "max_upload_bytes": MAX_UPLOAD_BYTES,
        "languages": sorted(VOICE_MAP.keys()),
        "subtitle_styles": ["classic", "yellow", "minimal"],
        "subtitle_positions": ["bottom", "center", "top"],
        "output_qualities": ["fast", "standard", "high"],
    }


@app.get("/health")
async def health():
    return {"status": "ok", "service": "DubAI", "active_jobs": sum(
        1 for item in progress_store.values() if item.get("status") == "running"
    )}


@app.get("/result/{job_id}")
async def get_result(job_id: str):
    manifest_path = OUTPUT_DIR / job_id / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(404, "Result abhi ready nahi")
    return json.loads(manifest_path.read_text())


@app.get("/download/{job_id}/{filename}")
async def download_file(job_id: str, filename: str):
    job_output_dir = (OUTPUT_DIR / job_id).resolve()
    file_path = (job_output_dir / filename).resolve()
    if job_output_dir not in file_path.parents or not file_path.is_file():
        raise HTTPException(404, "File nahi mili")
    return FileResponse(str(file_path), filename=filename)


# Mount static files
app.mount("/", StaticFiles(directory=BASE_DIR / "static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "5000"))
    print(f"\n🚀 DubAI Server starting on port {port}\n")
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False)
