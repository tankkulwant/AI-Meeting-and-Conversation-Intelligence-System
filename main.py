import os
import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from config import (
    TEMP_DIR,
    OUTPUT_DIR,
    STATIC_DIR,
    DEFAULT_WHISPER_MODEL,
    DEFAULT_DEVICE,
    GEMINI_API_KEY,
    DEFAULT_GEMINI_MODEL,
    HOST,
    PORT
)
from core.models import FullTranscript, MeetingAnalysis, ChatQueryResponse, ChatQueryRequest
from core.extractor import extract_audio
from core.transcriber import transcribe_audio, transcribe_audio_generator
from core.intelligence.analyzer import IntelligenceAnalyzer
from core.intelligence.gemini_provider import GeminiProvider
from core.exporter import export_to_srt, export_to_vtt, export_to_markdown, export_to_pdf

import json

# Session store with disk persistence for stability across reloads
sessions = {}

def get_session(session_id: str) -> dict:
    if session_id in sessions:
        return sessions[session_id]
    meta_path = TEMP_DIR / f"{session_id}_meta.json"
    if meta_path.exists():
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("transcript"):
                    data["transcript"] = FullTranscript(**data["transcript"])
                if data.get("analysis"):
                    data["analysis"] = MeetingAnalysis(**data["analysis"])
                sessions[session_id] = data
                return data
        except Exception:
            pass
    return None

def save_session(session_id: str, data: dict):
    sessions[session_id] = data
    meta_path = TEMP_DIR / f"{session_id}_meta.json"
    try:
        serializable = {}
        for k, v in data.items():
            if hasattr(v, "model_dump"):
                serializable[k] = v.model_dump()
            elif hasattr(v, "dict"):
                serializable[k] = v.dict()
            else:
                serializable[k] = v
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2)
    except Exception as e:
        print(f"Warning: Failed to persist session metadata: {e}")


app = FastAPI(
    title="AI-Powered Meeting & Conversation Intelligence System",
    description="Full-stack AI system for audio/video transcription, synced media playback, executive summaries, action item extraction, and conversational Q&A.",
    version="1.0.0"
)

# Enable CORS for local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure folders exist
for d in [TEMP_DIR, OUTPUT_DIR, STATIC_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Mount static files and media
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/media", StaticFiles(directory=str(TEMP_DIR)), name="media")


@app.get("/")
async def root():
    """Serves the Single-Page Application dashboard."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "AI Meeting Intelligence API is running. Access /docs for API documentation."}


@app.get("/favicon.ico")
async def favicon():
    """Serves the website favicon."""
    fav_file = STATIC_DIR / "favicon.ico"
    if fav_file.exists():
        return FileResponse(fav_file, media_type="image/x-icon")
    return FileResponse(STATIC_DIR / "favicon.svg", media_type="image/svg+xml")


class SettingsUpdate(BaseModel):
    gemini_api_key: Optional[str] = None
    whisper_model: Optional[str] = None
    gemini_model: Optional[str] = None


@app.get("/api/settings")
async def get_settings():
    """Returns current configuration status."""
    key = os.getenv("GEMINI_API_KEY", "") or GEMINI_API_KEY
    has_key = bool(key and key != "your_gemini_api_key_here")
    return {
        "has_gemini_key": has_key,
        "whisper_model": DEFAULT_WHISPER_MODEL,
        "gemini_model": DEFAULT_GEMINI_MODEL,
        "device": DEFAULT_DEVICE,
    }


@app.post("/api/settings")
async def update_settings(settings: SettingsUpdate):
    """Updates settings dynamically in memory."""
    if settings.gemini_api_key:
        os.environ["GEMINI_API_KEY"] = settings.gemini_api_key
    if settings.gemini_model:
        os.environ["GEMINI_MODEL"] = settings.gemini_model
    return {"status": "success", "message": "Settings updated"}


@app.get("/api/test-gemini")
async def test_gemini():
    """Diagnostic endpoint to inspect available models for current API key."""
    from google import genai
    key = os.getenv("GEMINI_API_KEY", "") or GEMINI_API_KEY
    if not key:
        return {"error": "No API key found"}
    try:
        client = genai.Client(api_key=key)
        models = [m.name for m in client.models.list()]
        return {"status": "connected", "models": models}
    except Exception as e:
        return {"status": "error", "message": str(e)}



@app.get("/api/sessions")
async def list_recent_sessions():
    """Returns a list of all saved meeting sessions on disk sorted by newest first."""
    sessions_list = []
    if not TEMP_DIR.exists():
        return []

    for meta_file in TEMP_DIR.glob("*_meta.json"):
        session_id = meta_file.name.replace("_meta.json", "")
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Compute disk size
            total_bytes = meta_file.stat().st_size
            media_path = TEMP_DIR / data.get("media_file", "")
            if media_path.exists():
                total_bytes += media_path.stat().st_size
            audio_path = Path(data.get("audio_path", ""))
            if audio_path.exists():
                total_bytes += audio_path.stat().st_size

            size_mb = round(total_bytes / (1024 * 1024), 1)

            # Extract title & duration
            transcript_data = data.get("transcript") or {}
            analysis_data = data.get("analysis") or {}
            title = analysis_data.get("meeting_title") or data.get("original_filename") or f"Meeting {session_id}"
            duration = transcript_data.get("duration", 0)
            language = transcript_data.get("language", "en")
            created_at = meta_file.stat().st_mtime

            sessions_list.append({
                "session_id": session_id,
                "title": title,
                "filename": data.get("original_filename", "recording"),
                "duration": duration,
                "language": language,
                "size_mb": size_mb,
                "created_at": created_at,
                "has_analysis": bool(analysis_data.get("executive_summary")),
            })
        except Exception as e:
            print(f"Error reading session {meta_file}: {e}")

    sessions_list.sort(key=lambda s: s["created_at"], reverse=True)
    return sessions_list


@app.get("/api/session/{session_id}")
async def get_session_detail(session_id: str):
    """Retrieves full session data from disk for auto-restoring after refresh."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Meeting session not found")

    serializable = {}
    for k, v in session.items():
        if hasattr(v, "model_dump"):
            serializable[k] = v.model_dump()
        elif hasattr(v, "dict"):
            serializable[k] = v.dict()
        else:
            serializable[k] = v

    media_file = session.get("media_file", "")
    return {
        "session_id": session_id,
        "media_url": f"/media/{media_file}",
        "is_video": session.get("is_video", True),
        "filename": session.get("original_filename", "meeting"),
        "transcript": serializable.get("transcript"),
        "analysis": serializable.get("analysis"),
    }


@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str):
    """Permanently deletes a meeting session and its raw media, extracted audio, transcript, and exports from disk."""
    deleted_files = []

    # Files in temp/
    for pattern in [f"{session_id}_original.*", f"{session_id}_extracted.wav", f"{session_id}_meta.json"]:
        for f in TEMP_DIR.glob(pattern):
            try:
                f.unlink(missing_ok=True)
                deleted_files.append(str(f.name))
            except Exception as e:
                print(f"Error removing {f}: {e}")

    # Files in output/
    for pattern in [f"{session_id}.*", f"{session_id}_MoM.*"]:
        for f in OUTPUT_DIR.glob(pattern):
            try:
                f.unlink(missing_ok=True)
                deleted_files.append(str(f.name))
            except Exception as e:
                print(f"Error removing {f}: {e}")

    # Remove from memory cache
    sessions.pop(session_id, None)

    return {
        "status": "success",
        "message": f"Session {session_id} deleted permanently",
        "deleted_files": deleted_files
    }


@app.post("/api/upload")
async def upload_media(file: UploadFile = File(...)):
    """
    Receives video/audio file upload, saves it, and extracts a normalized 16kHz mono audio WAV.
    """
    session_id = str(uuid.uuid4())[:8]
    ext = Path(file.filename).suffix.lower() or ".mp4"
    saved_filename = f"{session_id}_original{ext}"
    media_path = TEMP_DIR / saved_filename
    audio_path = TEMP_DIR / f"{session_id}_extracted.wav"

    # Save uploaded file
    with open(media_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Extract audio using FFmpeg
    try:
        extract_audio(str(media_path), str(audio_path))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audio extraction failed: {str(e)}")

    is_video = ext in [".mp4", ".mov", ".mkv", ".webm", ".avi"]

    session_data = {
        "media_file": saved_filename,
        "media_path": str(media_path),
        "audio_path": str(audio_path),
        "is_video": is_video,
        "original_filename": file.filename,
        "transcript": None,
        "analysis": None,
    }
    save_session(session_id, session_data)

    return {
        "session_id": session_id,
        "media_url": f"/media/{saved_filename}",
        "is_video": is_video,
        "filename": file.filename,
    }


class TranscribeRequest(BaseModel):
    session_id: str
    model_size: Optional[str] = DEFAULT_WHISPER_MODEL
    language: Optional[str] = None


@app.post("/api/transcribe")
async def transcribe(req: TranscribeRequest):
    """Transcribes extracted audio and generates WebVTT and SRT subtitles."""
    session = get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found. Please upload a file first.")

    audio_path = session["audio_path"]
    try:
        transcript = transcribe_audio(
            audio_path=audio_path,
            model_size=req.model_size or DEFAULT_WHISPER_MODEL,
            language=req.language if req.language and req.language != "auto" else None,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

    # Export SRT and VTT
    srt_path = OUTPUT_DIR / f"{req.session_id}.srt"
    vtt_path = OUTPUT_DIR / f"{req.session_id}.vtt"
    export_to_srt(transcript.segments, str(srt_path))
    export_to_vtt(transcript.segments, str(vtt_path))

    session["transcript"] = transcript
    session["srt_path"] = str(srt_path)
    session["vtt_path"] = str(vtt_path)
    save_session(req.session_id, session)

    return transcript


@app.get("/api/transcribe-stream/{session_id}")
def transcribe_stream(session_id: str, model_size: Optional[str] = DEFAULT_WHISPER_MODEL, language: Optional[str] = None):
    """
    Streams Server-Sent Events (SSE) reporting real-time Whisper transcription progress percentage (0-100%).
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found. Please upload a file first.")

    audio_path = session["audio_path"]
    lang = language if language and language != "auto" else None
    model_name = model_size or DEFAULT_WHISPER_MODEL

    def event_stream():
        try:
            for event in transcribe_audio_generator(
                audio_path=audio_path,
                model_size=model_name,
                language=lang
            ):
                if event.get("type") == "complete":
                    transcript_dict = event["transcript"]
                    transcript_obj = FullTranscript(**transcript_dict)
                    srt_path = OUTPUT_DIR / f"{session_id}.srt"
                    vtt_path = OUTPUT_DIR / f"{session_id}.vtt"
                    export_to_srt(transcript_obj.segments, str(srt_path))
                    export_to_vtt(transcript_obj.segments, str(vtt_path))

                    session["transcript"] = transcript_obj
                    session["srt_path"] = str(srt_path)
                    session["vtt_path"] = str(vtt_path)
                    save_session(session_id, session)

                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            err_data = {"type": "error", "message": str(e)}
            yield f"data: {json.dumps(err_data)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


class AnalyzeRequest(BaseModel):
    session_id: str
    gemini_api_key: Optional[str] = None


@app.post("/api/analyze")
async def analyze_meeting(req: AnalyzeRequest):
    """Runs AI analysis on the transcript to extract executive summary, action items, and decisions."""
    session = get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if not session.get("transcript"):
        raise HTTPException(status_code=400, detail="Transcript not ready. Transcribe the audio first.")

    api_key = req.gemini_api_key or os.getenv("GEMINI_API_KEY", "") or GEMINI_API_KEY
    if not api_key or api_key == "your_gemini_api_key_here":
        raise HTTPException(
            status_code=400,
            detail="Gemini API Key is missing. Please provide it in the Dashboard settings or .env file."
        )

    try:
        provider = GeminiProvider(api_key=api_key)
        analyzer = IntelligenceAnalyzer(provider=provider)
        analysis = analyzer.analyze(session["transcript"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Analysis failed: {str(e)}")

    session["analysis"] = analysis

    # Pre-generate export files
    md_path = OUTPUT_DIR / f"{req.session_id}_MoM.md"
    pdf_path = OUTPUT_DIR / f"{req.session_id}_MoM.pdf"
    export_to_markdown(analysis, session["transcript"], str(md_path))
    export_to_pdf(analysis, str(pdf_path))

    session["md_path"] = str(md_path)
    session["pdf_path"] = str(pdf_path)
    save_session(req.session_id, session)

    return analysis


@app.post("/api/ask")
async def ask_meeting(req: ChatQueryRequest):
    """Interactive conversational Q&A about the meeting."""
    session = get_session(req.session_id)
    if not session or not session.get("transcript"):
        raise HTTPException(status_code=400, detail="Active transcript not found for this session.")

    api_key = os.getenv("GEMINI_API_KEY", "") or GEMINI_API_KEY
    if not api_key or api_key == "your_gemini_api_key_here":
        raise HTTPException(status_code=400, detail="Gemini API key is required for Q&A.")

    try:
        provider = GeminiProvider(api_key=api_key)
        analyzer = IntelligenceAnalyzer(provider=provider)
        response = analyzer.ask(session["transcript"], req.query)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Q&A failed: {str(e)}")


@app.get("/api/export/{session_id}/{fmt}")
async def export_file(session_id: str, fmt: str):
    """Downloads Minutes of Meeting in requested format (pdf, md, srt, vtt)."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    fmt = fmt.lower()
    if fmt == "pdf":
        path = session.get("pdf_path") or (OUTPUT_DIR / f"{session_id}_MoM.pdf")
        if os.path.isfile(path):
            return FileResponse(path, filename=f"Minutes_of_Meeting_{session_id}.pdf", media_type="application/pdf")
    elif fmt in ["md", "markdown"]:
        path = session.get("md_path") or (OUTPUT_DIR / f"{session_id}_MoM.md")
        if os.path.isfile(path):
            return FileResponse(path, filename=f"Minutes_of_Meeting_{session_id}.md", media_type="text/markdown")
    elif fmt == "srt":
        path = session.get("srt_path") or (OUTPUT_DIR / f"{session_id}.srt")
        if os.path.isfile(path):
            return FileResponse(path, filename=f"Subtitles_{session_id}.srt", media_type="text/plain")
    elif fmt == "vtt":
        path = session.get("vtt_path") or (OUTPUT_DIR / f"{session_id}.vtt")
        if os.path.isfile(path):
            return FileResponse(path, filename=f"Subtitles_{session_id}.vtt", media_type="text/vtt")

    raise HTTPException(status_code=404, detail=f"Requested export file for format '{fmt}' not found.")


if __name__ == "__main__":
    print(f"Starting AI Meeting Intelligence Server on http://{HOST}:{PORT}")
    print(f"API Docs available at http://{HOST}:{PORT}/docs")
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
