"""CLI entry point for Nobody Took Notes."""

import argparse
import sys
import time
import wave
from pathlib import Path


def cmd_live(args):
    """Live transcription of mic + system audio."""
    from nobody.capture import get_sources
    from nobody.pipeline import LivePipeline, TranscriptResult
    from nobody.store import TranscriptStore
    from nobody.stt import DEFAULT_MODEL

    model = args.model or DEFAULT_MODEL
    db_path = Path(args.db)
    duration = args.duration

    store = TranscriptStore(db_path)
    session_id = store.create_session()

    print(f"Session: {session_id[:8]}...")
    print(f"Model: {model}")
    print(f"Database: {db_path}")
    print("-" * 50)
    print()

    def on_transcript(result: TranscriptResult) -> None:
        speaker = "Me" if result.source == "me" else "Them"
        mins = result.start_ms // 60000
        secs = (result.start_ms % 60000) // 1000
        print(f"[{mins:02d}:{secs:02d}] {speaker}: {result.text.strip()}")

    pipeline = LivePipeline(
        store=store,
        session_id=session_id,
        model=model,
        language=args.language,
        on_transcript=on_transcript,
    )

    mic_seg = pipeline.create_segmenter("me", sample_rate=48000)
    them_seg = pipeline.create_segmenter("them", sample_rate=48000)

    mic, loopback = get_sources()

    pipeline.start()
    mic.start(lambda pcm, ts: mic_seg.push(pcm, ts))
    loopback.start(lambda pcm, ts: them_seg.push(pcm, ts))

    print("Recording... (Ctrl+C to stop)")
    print()

    try:
        if duration:
            for i in range(duration):
                time.sleep(1)
            print()
        else:
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        print()
        print("Stopping...")

    mic.stop()
    loopback.stop()
    pipeline.stop()

    print()
    print("-" * 50)
    print(f"Session saved: {session_id[:8]}...")
    print(f"View transcript: python -m nobody show {session_id[:8]}")
    store.close()


def cmd_show(args):
    """Show a saved transcript."""
    from nobody.store import TranscriptStore

    store = TranscriptStore(args.db)

    # Find session by prefix
    cur = store._conn.execute(
        "SELECT id FROM sessions WHERE id LIKE ? ORDER BY created_at DESC LIMIT 1",
        (f"{args.session}%",),
    )
    row = cur.fetchone()
    if not row:
        print(f"No session found matching: {args.session}")
        sys.exit(1)

    session_id = row[0]
    print(f"Session: {session_id}")
    print("-" * 50)
    print()
    print(store.get_merged_transcript(session_id))
    store.close()


def cmd_summarize(args):
    """Generate a summary for a session."""
    from nobody.store import TranscriptStore
    from nobody.summarise import Summariser

    store = TranscriptStore(args.db)

    # Find session by prefix
    cur = store._conn.execute(
        "SELECT id FROM sessions WHERE id LIKE ? ORDER BY created_at DESC LIMIT 1",
        (f"{args.session}%",),
    )
    row = cur.fetchone()
    if not row:
        print(f"No session found matching: {args.session}")
        sys.exit(1)

    session_id = row[0]
    transcript = store.get_merged_transcript(session_id)

    if not transcript.strip():
        print("No transcript content to summarize")
        sys.exit(1)

    from nobody.summarise import DEFAULT_CHAT_MODEL

    model = args.model or DEFAULT_CHAT_MODEL
    print(f"Session: {session_id[:8]}...")
    print(f"Model: {model.split('/')[-1] if '/' in model else model}")
    print("-" * 50)
    print()
    print("Generating summary...")
    print()

    summariser = Summariser(model=model)
    summary = summariser.summarise(transcript)

    if args.save:
        store.save_summary(session_id, summary.to_dict())
        print("Summary saved to database")
        print()

    if args.markdown:
        print(summary.to_markdown())
    else:
        print(f"Title: {summary.title}")
        print()
        print(f"TLDR: {summary.tldr}")
        print()

        if summary.key_points:
            print("Key Points:")
            for point in summary.key_points:
                print(f"  - {point}")
            print()

        if summary.decisions:
            print("Decisions:")
            for decision in summary.decisions:
                print(f"  - {decision}")
            print()

        if summary.action_items:
            print("Action Items:")
            for item in summary.action_items:
                owner = f" ({item.get('owner', '')})" if item.get('owner') else ""
                due = f" [Due: {item.get('due', '')}]" if item.get('due') else ""
                print(f"  - {item['task']}{owner}{due}")
            print()

        if summary.open_questions:
            print("Open Questions:")
            for q in summary.open_questions:
                print(f"  - {q}")

    store.close()


def cmd_record(args):
    """Record audio from mic and system loopback."""
    from nobody.capture import get_sources

    duration = args.duration
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    mic_path = out_dir / "me.wav"
    them_path = out_dir / "them.wav"

    mic_chunks: list[bytes] = []
    them_chunks: list[bytes] = []

    def on_mic(pcm: bytes, ts: int) -> None:
        mic_chunks.append(pcm)

    def on_loopback(pcm: bytes, ts: int) -> None:
        them_chunks.append(pcm)

    mic, loopback = get_sources()

    print(f"Recording {duration}s...")
    print("  Mic → me.wav")
    print("  System audio → them.wav")
    print()

    mic.start(on_mic)
    loopback.start(on_loopback)

    try:
        for i in range(duration):
            print(f"\r  {duration - i}s remaining...", end="", flush=True)
            time.sleep(1)
        print("\r  Done!              ")
    except KeyboardInterrupt:
        print("\n  Stopped early.")
    finally:
        mic.stop()
        loopback.stop()

    for path, chunks, name in [
        (mic_path, mic_chunks, "me.wav"),
        (them_path, them_chunks, "them.wav"),
    ]:
        if not chunks:
            print(f"  {name}: no audio captured")
            continue
        data = b"".join(chunks)
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(48000)
            wf.writeframes(data)
        print(f"  {name}: {len(data) / 2 / 48000:.1f}s → {path}")


def cmd_transcribe(args):
    """Transcribe an audio file."""
    from nobody.stt import transcribe_file_streaming, DEFAULT_MODEL

    model = args.model or DEFAULT_MODEL
    start = time.perf_counter()

    print(f"Transcribing: {args.file}")
    print(f"Model: {model}")
    print("-" * 40)

    for piece in transcribe_file_streaming(args.file, model=model, language=args.language):
        print(piece, end="", flush=True)

    print()
    print("-" * 40)
    print(f"Done in {time.perf_counter() - start:.1f}s")


def cmd_setup(args):
    """Run first-time setup: check permissions and download models."""
    from nobody.setup import run_setup_cli
    success = run_setup_cli(verbose=True)
    sys.exit(0 if success else 1)


def cmd_serve(args):
    """Run the UI server with tray icon."""
    import threading
    import webbrowser
    from urllib.request import Request, urlopen

    from nobody.server import state, run_server
    from nobody.tray import TrayApp
    from nobody.setup import ensure_ready

    port = args.port
    hotkey = args.hotkey

    ensure_ready(silent=False)

    print(f"Nobody Took Notes")
    print(f"  Server: http://127.0.0.1:{port}")
    print(f"  Hotkey: {hotkey}")
    print()

    def do_start():
        try:
            req = Request(f"http://127.0.0.1:{port}/api/start", method="POST")
            urlopen(req, timeout=5)
        except Exception:
            pass

    def do_stop():
        try:
            req = Request(f"http://127.0.0.1:{port}/api/stop", method="POST")
            urlopen(req, timeout=5)
        except Exception:
            pass

    def on_quit():
        import os
        os._exit(0)

    tray = TrayApp(on_start=do_start, on_stop=do_stop, on_quit=on_quit, port=port)

    if hotkey:
        try:
            from pynput import keyboard

            def on_activate():
                if state.recording:
                    do_stop()
                    tray.set_recording(False)
                else:
                    do_start()
                    tray.set_recording(True)

            hotkey_listener = keyboard.GlobalHotKeys({hotkey: on_activate})
            hotkey_listener.start()
            print(f"  Global hotkey active: {hotkey}")
        except Exception as e:
            print(f"  Hotkey not available: {e}")

    # Start server in background thread (tray must run on main thread on macOS)
    server_thread = threading.Thread(target=lambda: run_server(port=port), daemon=True)
    server_thread.start()
    print("  Server started")

    if not args.no_browser:
        def open_browser():
            time.sleep(1.5)
            webbrowser.open(f"http://127.0.0.1:{port}")
        threading.Thread(target=open_browser, daemon=True).start()

    print("  Tray icon starting...")
    print()
    print("Running... (Quit from tray menu to stop)")

    try:
        tray.run()
    except KeyboardInterrupt:
        pass


def main():
    parser = argparse.ArgumentParser(
        prog="nobody",
        description="Nobody Took Notes — a fully local meeting notetaker",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # live command
    p_live = subparsers.add_parser("live", help="Live transcription of mic + system audio")
    p_live.add_argument("--duration", "-d", type=int, help="Duration in seconds (default: until Ctrl+C)")
    p_live.add_argument("--model", "-m", help="STT model (default: whisper-base)")
    p_live.add_argument("--language", "-l", default="en", help="Language code (default: en)")
    p_live.add_argument("--db", default="transcripts.db", help="Database path (default: transcripts.db)")
    p_live.set_defaults(func=cmd_live)

    # show command
    p_show = subparsers.add_parser("show", help="Show a saved transcript")
    p_show.add_argument("session", help="Session ID (or prefix)")
    p_show.add_argument("--db", default="transcripts.db", help="Database path (default: transcripts.db)")
    p_show.set_defaults(func=cmd_show)

    # record command
    p_record = subparsers.add_parser("record", help="Record mic + system audio to wav files")
    p_record.add_argument("--duration", "-d", type=int, default=30, help="Duration in seconds (default: 30)")
    p_record.add_argument("--output", "-o", default=".", help="Output directory (default: current)")
    p_record.set_defaults(func=cmd_record)

    # transcribe command
    p_transcribe = subparsers.add_parser("transcribe", help="Transcribe an audio file")
    p_transcribe.add_argument("file", help="Path to audio file (wav, mp3, etc.)")
    p_transcribe.add_argument("--model", "-m", help="STT model (default: whisper-base)")
    p_transcribe.add_argument("--language", "-l", default="en", help="Language code (default: en)")
    p_transcribe.set_defaults(func=cmd_transcribe)

    # serve command
    p_serve = subparsers.add_parser("serve", help="Run the UI server with tray icon")
    p_serve.add_argument("--port", "-p", type=int, default=8765, help="Server port (default: 8765)")
    default_hotkey = "<cmd>+<shift>+r" if sys.platform == "darwin" else "<ctrl>+<shift>+r"
    p_serve.add_argument("--hotkey", default=default_hotkey, help="Global hotkey (default: Cmd+Shift+R on macOS, Ctrl+Shift+R elsewhere)")
    p_serve.add_argument("--no-browser", action="store_true", help="Don't open browser on start")
    p_serve.set_defaults(func=cmd_serve)

    # summarize command
    p_summarize = subparsers.add_parser("summarize", help="Generate a summary for a session")
    p_summarize.add_argument("session", help="Session ID (or prefix)")
    p_summarize.add_argument("--db", default="transcripts.db", help="Database path (default: transcripts.db)")
    p_summarize.add_argument("--model", "-m", help="Chat model (default: Qwen3-0.6B)")
    p_summarize.add_argument("--markdown", action="store_true", help="Output as Markdown")
    p_summarize.add_argument("--save", "-s", action="store_true", help="Save summary to database")
    p_summarize.set_defaults(func=cmd_summarize)

    # setup command
    p_setup = subparsers.add_parser("setup", help="First-time setup: check permissions and download models")
    p_setup.set_defaults(func=cmd_setup)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
