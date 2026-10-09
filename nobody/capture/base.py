"""Base protocol for audio capture backends."""

from typing import Callable, Protocol


class AudioSource(Protocol):
    """Protocol for platform-specific audio capture."""

    def start(self, on_frames: Callable[[bytes, int], None]) -> None:
        """Start capturing audio.

        Args:
            on_frames: Callback receiving (pcm_bytes, timestamp_ms).
                       PCM is signed 16-bit mono at the source's native rate.
                       timestamp_ms is monotonic, shared across all sources.
        """
        ...

    def stop(self) -> None:
        """Stop capturing audio."""
        ...
