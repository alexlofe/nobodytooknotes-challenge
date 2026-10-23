"""First-run setup: permissions, model downloads, dependency checks.

CHALLENGE: one function in this file is part of the open challenge.
See CHALLENGE.md, step 5. Look for `download_models_with_progress`.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

# TODO (step 5): import download_model from the nobodywho package.

from nobody.stt import DEFAULT_MODEL
from nobody.summarise import DEFAULT_CHAT_MODEL


def check_ffmpeg() -> bool:
    """Check if ffmpeg is available."""
    return shutil.which("ffmpeg") is not None


def ffmpeg_install_hint() -> str:
    """Return the command that installs ffmpeg on this platform."""
    if sys.platform == "darwin":
        return "brew install ffmpeg"
    if sys.platform == "win32":
        return "winget install ffmpeg"
    return "your package manager, e.g. sudo apt install ffmpeg"


def check_macos_permissions() -> dict[str, bool | None]:
    """Check macOS permissions. Returns dict with permission status."""
    if sys.platform != "darwin":
        return {}

    results = {}

    # Screen Recording permission (needed for system audio capture via catap)
    # We can't directly check this, but we can try to import catap
    try:
        import catap
        results["screen_recording"] = True
    except ImportError:
        results["screen_recording"] = None  # catap not installed
    except Exception:
        results["screen_recording"] = False

    # Accessibility permission (needed for global hotkeys via pynput)
    # Try a minimal check
    try:
        from pynput import keyboard
        results["accessibility"] = True
    except ImportError:
        results["accessibility"] = None  # pynput not installed
    except Exception:
        results["accessibility"] = False

    return results


def open_macos_privacy_settings(pane: str = "ScreenCapture") -> None:
    """Open macOS Privacy settings to a specific pane."""
    if sys.platform != "darwin":
        return

    panes = {
        "ScreenCapture": "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture",
        "Accessibility": "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
        "Microphone": "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone",
    }

    url = panes.get(pane, panes["ScreenCapture"])
    subprocess.run(["open", url], check=False)


def get_model_cache_dir() -> Path:
    """Get the NobodyWho model cache directory."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "nobodywho"
    elif sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "nobodywho" / "cache"
    else:
        return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "nobodywho"


def download_models_with_progress(
    on_progress: callable = None,
    on_status: callable = None,
) -> dict[str, bool]:
    """Download the two models the app needs, reporting progress as we go.

    This runs when the user types `python -m nobody setup`. It is also a
    good place to check that the models are already cached before a meeting.

    Args:
        on_progress: Called with (model_name, downloaded_bytes, total_bytes)
                     while a download is running. May be None.
        on_status:   Called with (model_name, status_text) where status_text
                     is "checking", "ready" or "error: <message>". May be None.

    Returns:
        A dict like {"chat": True, "whisper": False} saying which models are ready.

    The function below is partly written. The structure (status messages,
    try/except, the results dict) is done. You need to fill in the two
    places marked TODO.
    """
    results = {}

    # ---- 1. The chat model (a GGUF file used by the Summariser) ----
    if on_status:
        on_status("chat", "checking")

    def chat_progress(downloaded: int, total: int):
        # NobodyWho calls this with two numbers. We add the model name
        # and pass it on to the caller.
        if on_progress:
            on_progress("chat", downloaded, total)

    try:
        # TODO (step 5a): download DEFAULT_CHAT_MODEL with NobodyWho.
        # The download function accepts a progress callback. Pass chat_progress
        # so the progress bar in the terminal works.
        raise NotImplementedError("CHALLENGE step 5a: download the chat model in nobody/setup.py")
        results["chat"] = True
        if on_status:
            on_status("chat", "ready")
    except Exception as e:
        if on_status:
            on_status("chat", f"error: {e}")
        results["chat"] = False

    # ---- 2. The speech-to-text model (Whisper, ONNX format) ----
    if on_status:
        on_status("whisper", "checking")

    try:
        # TODO (step 5b): make sure the Whisper model is downloaded and cached.
        # Whisper models are not GGUF files, so download_model does not apply.
        # Instead, simply creating the speech-to-text engine downloads and
        # caches the model. You already wrote a function that does this in
        # nobody/stt.py. Call it with DEFAULT_MODEL and ignore the result.
        raise NotImplementedError("CHALLENGE step 5b: cache the Whisper model in nobody/setup.py")
        results["whisper"] = True
        if on_status:
            on_status("whisper", "ready")
    except Exception as e:
        if on_status:
            on_status("whisper", f"error: {e}")
        results["whisper"] = False

    return results


def format_bytes(n: int) -> str:
    """Format bytes as human-readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def run_setup_cli(verbose: bool = True) -> bool:
    """Run interactive setup from CLI. Returns True if all checks pass."""
    all_ok = True

    print("Nobody Took Notes — Setup")
    print("=" * 40)
    print()

    # Check ffmpeg
    print("Checking dependencies...")
    if check_ffmpeg():
        print("  ✓ ffmpeg found")
    else:
        print("  ✗ ffmpeg not found")
        print(f"    Install with: {ffmpeg_install_hint()}")
        all_ok = False
    print()

    # Check macOS permissions
    if sys.platform == "darwin":
        print("Checking macOS permissions...")
        perms = check_macos_permissions()

        if perms.get("screen_recording") is True:
            print("  ✓ Screen Recording (catap available)")
        elif perms.get("screen_recording") is None:
            print("  ? Screen Recording (catap not installed)")
        else:
            print("  ✗ Screen Recording permission needed")
            print("    Grant permission in System Settings > Privacy & Security > Screen Recording")
            all_ok = False

        if perms.get("accessibility") is True:
            print("  ✓ Accessibility (pynput available)")
        elif perms.get("accessibility") is None:
            print("  ? Accessibility (pynput not installed)")
        else:
            print("  ✗ Accessibility permission needed for global hotkey")
            print("    Grant permission in System Settings > Privacy & Security > Accessibility")

        print()

    # Download models
    print("Checking models...")

    current_model = None
    last_percent = -1

    def on_progress(name: str, downloaded: int, total: int):
        nonlocal last_percent
        if total > 0:
            percent = int(downloaded * 100 / total)
            if percent != last_percent:
                last_percent = percent
                bar_width = 30
                filled = int(bar_width * percent / 100)
                bar = "█" * filled + "░" * (bar_width - filled)
                print(f"\r  [{bar}] {percent:3d}% {format_bytes(downloaded)}/{format_bytes(total)}", end="", flush=True)

    def on_status(name: str, status: str):
        nonlocal current_model, last_percent
        if status == "checking":
            current_model = name
            last_percent = -1
            print(f"  {name}: checking...", end="", flush=True)
        elif status == "ready":
            print(f"\r  {name}: ✓ ready" + " " * 40)
        elif status.startswith("error"):
            print(f"\r  {name}: ✗ {status}" + " " * 40)

    results = download_models_with_progress(on_progress=on_progress, on_status=on_status)

    for name, success in results.items():
        if not success:
            all_ok = False

    print()

    if all_ok:
        print("Setup complete! Run with: python -m nobody serve")
    else:
        print("Setup incomplete. Please resolve the issues above.")

    return all_ok


def ensure_ready(silent: bool = False) -> bool:
    """Quick check that app is ready to run. Returns True if ready."""
    issues = []

    if not check_ffmpeg():
        issues.append("ffmpeg not found (needed for audio export)")

    if issues and not silent:
        print("Warning: " + "; ".join(issues))

    return len(issues) == 0
