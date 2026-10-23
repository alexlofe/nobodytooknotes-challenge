"""Audio capture backends."""

import sys


def get_sources():
    """Return (MicSource(), LoopbackSource()) for the current platform."""
    if sys.platform == "darwin":
        from nobody.capture.macos import MicSource, LoopbackSource
    elif sys.platform == "win32":
        from nobody.capture.windows import MicSource, LoopbackSource
    else:
        raise RuntimeError(f"Audio capture is not supported on {sys.platform} yet")
    return MicSource(), LoopbackSource()
