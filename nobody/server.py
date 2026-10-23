"""FastAPI server for Nobody Took Notes."""

import asyncio
import json
import threading
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from nobody.pipeline import LivePipeline, TranscriptResult
from nobody.store import TranscriptStore
from nobody.stt import DEFAULT_MODEL
from nobody.summarise import Summariser, MeetingSummary

UI_DIR = Path(__file__).parent / "ui"
DEFAULT_DB = Path.home() / ".nobody-took-notes" / "transcripts.db"
AUDIO_DIR = Path.home() / ".nobody-took-notes" / "audio"

app = FastAPI(title="Nobody Took Notes")


class AppState:
    """Global application state."""

    def __init__(self) -> None:
        self.recording = False
        self.session_id: str | None = None
        self.pipeline: LivePipeline | None = None
        self.store: TranscriptStore | None = None
        self.mic = None
        self.loopback = None
        self._subscribers: list[asyncio.Queue[TranscriptResult | None]] = []
        self._lock = threading.Lock()
        self.mic_audio: list[bytes] = []
        self.loopback_audio: list[bytes] = []

    def subscribe(self) -> asyncio.Queue[TranscriptResult | None]:
        q: asyncio.Queue[TranscriptResult | None] = asyncio.Queue()
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def broadcast(self, result: TranscriptResult) -> None:
        with self._lock:
            for q in self._subscribers:
                try:
                    q.put_nowait(result)
                except asyncio.QueueFull:
                    pass


state = AppState()

# Singleton summariser - loads model once, reuses for all requests
_summariser: Summariser | None = None

def get_summariser() -> Summariser:
    global _summariser
    if _summariser is None:
        _summariser = Summariser()
    return _summariser


def ensure_db_dir() -> None:
    DEFAULT_DB.parent.mkdir(parents=True, exist_ok=True)


class StatusResponse(BaseModel):
    recording: bool
    session_id: str | None


class SessionInfo(BaseModel):
    id: str
    created_at: str
    duration_ms: int | None
    segment_count: int


class TranscriptSegment(BaseModel):
    source: str
    start_ms: int
    end_ms: int
    text: str


class ActionItem(BaseModel):
    owner: str = ""
    task: str
    due: str = ""


class SummaryResponse(BaseModel):
    title: str
    tldr: str
    key_points: list[str]
    decisions: list[str]
    action_items: list[ActionItem]
    open_questions: list[str]
    created_at: str | None = None


class TitleUpdate(BaseModel):
    title: str


class AudioResponse(BaseModel):
    url: str | None
    status: str


@app.get("/")
async def index() -> HTMLResponse:
    html_path = UI_DIR / "index.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text())
    return HTMLResponse(content="<h1>Nobody Took Notes</h1><p>UI not found</p>")


@app.get("/api/status")
async def get_status() -> StatusResponse:
    return StatusResponse(recording=state.recording, session_id=state.session_id)


@app.post("/api/start")
async def start_recording() -> StatusResponse:
    if state.recording:
        return StatusResponse(recording=True, session_id=state.session_id)

    ensure_db_dir()
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    from nobody.capture import get_sources

    state.store = TranscriptStore(DEFAULT_DB)
    state.session_id = state.store.create_session()
    state.mic_audio = []
    state.loopback_audio = []

    def on_transcript(result: TranscriptResult) -> None:
        state.broadcast(result)

    state.pipeline = LivePipeline(
        store=state.store,
        session_id=state.session_id,
        model=DEFAULT_MODEL,
        language="en",
        on_transcript=on_transcript,
    )

    mic_seg = state.pipeline.create_segmenter("me", sample_rate=48000)
    them_seg = state.pipeline.create_segmenter("them", sample_rate=48000)

    state.mic, state.loopback = get_sources()

    def on_mic(pcm: bytes, ts: int) -> None:
        mic_seg.push(pcm, ts)
        state.mic_audio.append(pcm)

    def on_loopback(pcm: bytes, ts: int) -> None:
        them_seg.push(pcm, ts)
        state.loopback_audio.append(pcm)

    state.pipeline.start()
    state.mic.start(on_mic)
    state.loopback.start(on_loopback)

    state.recording = True
    return StatusResponse(recording=True, session_id=state.session_id)


def mix_and_compress_audio(session_id: str, mic_audio: list[bytes], loopback_audio: list[bytes]) -> None:
    """Mix mic and loopback audio, compress to MP3 in background."""
    import subprocess
    import wave
    import struct

    if not mic_audio and not loopback_audio:
        return

    try:
        AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        wav_path = AUDIO_DIR / f"{session_id}.wav"
        mp3_path = AUDIO_DIR / f"{session_id}.mp3"

        mic_data = b"".join(mic_audio)
        loopback_data = b"".join(loopback_audio)

        max_len = max(len(mic_data), len(loopback_data))
        mic_data = mic_data.ljust(max_len, b'\x00')
        loopback_data = loopback_data.ljust(max_len, b'\x00')

        mixed = bytearray(max_len)
        for i in range(0, max_len, 2):
            if i + 1 < max_len:
                mic_sample = struct.unpack('<h', mic_data[i:i+2])[0]
                loop_sample = struct.unpack('<h', loopback_data[i:i+2])[0]
                mixed_sample = (mic_sample + loop_sample) // 2
                mixed_sample = max(-32768, min(32767, mixed_sample))
                mixed[i:i+2] = struct.pack('<h', mixed_sample)

        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(48000)
            wf.writeframes(bytes(mixed))

        result = subprocess.run(
            ["ffmpeg", "-y", "-i", str(wav_path), "-b:a", "128k", str(mp3_path)],
            capture_output=True,
            timeout=300,
        )

        if result.returncode == 0 and mp3_path.exists():
            wav_path.unlink(missing_ok=True)

    except Exception as e:
        print(f"Audio processing error: {e}")


@app.post("/api/stop")
async def stop_recording(background_tasks: BackgroundTasks) -> StatusResponse:
    if not state.recording:
        return StatusResponse(recording=False, session_id=None)

    if state.mic:
        state.mic.stop()
    if state.loopback:
        state.loopback.stop()
    if state.pipeline:
        state.pipeline.stop()
    if state.store:
        state.store.close()

    saved_session = state.session_id
    mic_audio = state.mic_audio.copy()
    loopback_audio = state.loopback_audio.copy()

    state.recording = False
    state.session_id = None
    state.pipeline = None
    state.mic = None
    state.loopback = None
    state.mic_audio = []
    state.loopback_audio = []

    if saved_session:
        background_tasks.add_task(mix_and_compress_audio, saved_session, mic_audio, loopback_audio)

    return StatusResponse(recording=False, session_id=saved_session)


@app.get("/api/sessions")
async def list_sessions() -> list[SessionInfo]:
    ensure_db_dir()
    store = TranscriptStore(DEFAULT_DB)
    cur = store._conn.execute("""
        SELECT s.id, s.created_at,
               MAX(t.end_ms) - MIN(t.start_ms) as duration_ms,
               COUNT(t.id) as segment_count
        FROM sessions s
        LEFT JOIN transcripts t ON t.session_id = s.id
        GROUP BY s.id
        ORDER BY s.created_at DESC
    """)
    sessions = []
    for row in cur.fetchall():
        sessions.append(SessionInfo(
            id=row[0],
            created_at=row[1],
            duration_ms=row[2],
            segment_count=row[3] or 0,
        ))
    store.close()
    return sessions


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str) -> list[TranscriptSegment]:
    ensure_db_dir()
    store = TranscriptStore(DEFAULT_DB)
    cur = store._conn.execute(
        "SELECT id FROM sessions WHERE id LIKE ? LIMIT 1",
        (f"{session_id}%",),
    )
    row = cur.fetchone()
    if not row:
        store.close()
        return []

    full_id = row[0]
    rows = store.get_session_transcripts(full_id)
    store.close()

    return [
        TranscriptSegment(
            source=r.source,
            start_ms=r.start_ms,
            end_ms=r.end_ms,
            text=r.text,
        )
        for r in rows
    ]


@app.get("/api/live")
async def live_transcript() -> StreamingResponse:
    """SSE endpoint for live transcript updates."""

    async def event_stream() -> AsyncIterator[str]:
        q = state.subscribe()
        try:
            while True:
                try:
                    result = await asyncio.wait_for(q.get(), timeout=30.0)
                    if result is None:
                        break
                    data = json.dumps({
                        "source": result.source,
                        "start_ms": result.start_ms,
                        "end_ms": result.end_ms,
                        "text": result.text,
                    })
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            state.unsubscribe(q)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.get("/api/sessions/{session_id}/summary")
async def get_summary(session_id: str) -> SummaryResponse | None:
    """Get existing summary for a session."""
    ensure_db_dir()
    store = TranscriptStore(DEFAULT_DB)

    cur = store._conn.execute(
        "SELECT id FROM sessions WHERE id LIKE ? LIMIT 1",
        (f"{session_id}%",),
    )
    row = cur.fetchone()
    if not row:
        store.close()
        return None

    full_id = row[0]
    summary_row = store.get_summary(full_id)
    store.close()

    if not summary_row:
        return None

    data = summary_row.to_dict()
    return SummaryResponse(
        title=data.get("title", ""),
        tldr=data.get("tldr", ""),
        key_points=data.get("key_points", []),
        decisions=data.get("decisions", []),
        action_items=[ActionItem(**a) for a in data.get("action_items", [])],
        open_questions=data.get("open_questions", []),
        created_at=summary_row.created_at,
    )


@app.post("/api/sessions/{session_id}/summarize")
async def summarize_session(session_id: str, background_tasks: BackgroundTasks) -> SummaryResponse:
    """Generate a summary for a session."""
    ensure_db_dir()
    store = TranscriptStore(DEFAULT_DB)

    cur = store._conn.execute(
        "SELECT id FROM sessions WHERE id LIKE ? LIMIT 1",
        (f"{session_id}%",),
    )
    row = cur.fetchone()
    if not row:
        store.close()
        raise ValueError("Session not found")

    full_id = row[0]
    transcript = store.get_merged_transcript(full_id)

    if not transcript.strip():
        store.close()
        raise ValueError("No transcript content")

    summariser = get_summariser()
    summary = summariser.summarise(transcript)

    store.save_summary(full_id, summary.to_dict())
    store.close()

    return SummaryResponse(
        title=summary.title,
        tldr=summary.tldr,
        key_points=summary.key_points,
        decisions=summary.decisions,
        action_items=[ActionItem(**a) for a in summary.action_items],
        open_questions=summary.open_questions,
    )


@app.get("/api/sessions/{session_id}/export")
async def export_session(session_id: str) -> dict[str, str]:
    """Export session as Markdown."""
    ensure_db_dir()
    store = TranscriptStore(DEFAULT_DB)

    cur = store._conn.execute(
        "SELECT id FROM sessions WHERE id LIKE ? LIMIT 1",
        (f"{session_id}%",),
    )
    row = cur.fetchone()
    if not row:
        store.close()
        return {"markdown": "", "error": "Session not found"}

    full_id = row[0]
    summary_row = store.get_summary(full_id)
    transcript = store.get_merged_transcript(full_id)
    store.close()

    lines = []

    if summary_row:
        data = summary_row.to_dict()
        summary = MeetingSummary.from_dict(data)
        lines.append(summary.to_markdown())
        lines.append("---\n")
        lines.append("## Full Transcript\n")
    else:
        lines.append("# Meeting Transcript\n")

    lines.append(transcript)

    return {"markdown": "\n".join(lines)}


@app.put("/api/sessions/{session_id}/title")
async def update_title(session_id: str, title_update: TitleUpdate) -> dict[str, str]:
    """Update the title of a session's summary."""
    ensure_db_dir()
    store = TranscriptStore(DEFAULT_DB)

    cur = store._conn.execute(
        "SELECT id FROM sessions WHERE id LIKE ? LIMIT 1",
        (f"{session_id}%",),
    )
    row = cur.fetchone()
    if not row:
        store.close()
        return {"status": "error", "message": "Session not found"}

    full_id = row[0]
    summary_row = store.get_summary(full_id)

    if summary_row:
        data = summary_row.to_dict()
        data["title"] = title_update.title
        store.save_summary(full_id, data)

    store.close()
    return {"status": "ok"}


@app.get("/api/sessions/{session_id}/audio")
async def get_audio(session_id: str) -> AudioResponse:
    """Get audio file URL for a session."""
    ensure_db_dir()
    store = TranscriptStore(DEFAULT_DB)

    cur = store._conn.execute(
        "SELECT id FROM sessions WHERE id LIKE ? LIMIT 1",
        (f"{session_id}%",),
    )
    row = cur.fetchone()
    store.close()

    if not row:
        return AudioResponse(url=None, status="not_found")

    full_id = row[0]
    mp3_path = AUDIO_DIR / f"{full_id}.mp3"
    wav_path = AUDIO_DIR / f"{full_id}.wav"

    if mp3_path.exists():
        return AudioResponse(url=f"/api/sessions/{full_id}/audio/file", status="ready")
    elif wav_path.exists():
        return AudioResponse(url=None, status="processing")
    else:
        return AudioResponse(url=None, status="unavailable")


@app.get("/api/sessions/{session_id}/audio/file")
async def get_audio_file(session_id: str):
    """Serve the audio file."""
    ensure_db_dir()
    store = TranscriptStore(DEFAULT_DB)

    cur = store._conn.execute(
        "SELECT id FROM sessions WHERE id LIKE ? LIMIT 1",
        (f"{session_id}%",),
    )
    row = cur.fetchone()
    store.close()

    if not row:
        return {"error": "Session not found"}

    full_id = row[0]
    mp3_path = AUDIO_DIR / f"{full_id}.mp3"

    if mp3_path.exists():
        return FileResponse(mp3_path, media_type="audio/mpeg", filename=f"meeting-{full_id[:8]}.mp3")

    return {"error": "Audio not available"}


def preload_models() -> None:
    """Preload STT and LLM models in background so first request is fast."""
    import threading

    def _preload():
        try:
            print("  Preloading models...")
            get_summariser()
            print("  Models ready")
        except Exception as e:
            print(f"  Model preload failed: {e}")

    threading.Thread(target=_preload, daemon=True).start()


def run_server(host: str = "127.0.0.1", port: int = 8765, preload: bool = True) -> None:
    """Run the FastAPI server."""
    import uvicorn
    if preload:
        preload_models()
    uvicorn.run(app, host=host, port=port, log_level="warning")
