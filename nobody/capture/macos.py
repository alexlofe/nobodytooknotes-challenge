"""macOS audio capture using catap (loopback) and sounddevice (mic)."""

from typing import Callable

import numpy as np

import catap

from nobody.capture.mic import MicSource, get_timestamp_ms

__all__ = ["LoopbackSource", "MicSource"]


def _float32_to_pcm16(data: bytes, channels: int) -> bytes:
    """Convert float32 PCM to signed 16-bit mono PCM."""
    arr = np.frombuffer(data, dtype=np.float32)
    if channels > 1:
        arr = arr.reshape(-1, channels).mean(axis=1)
    arr = np.clip(arr * 32767, -32768, 32767).astype(np.int16)
    return arr.tobytes()


class LoopbackSource:
    """Capture system audio output (what you hear) via catap."""

    def __init__(self) -> None:
        self._session: catap.RecordingSession | None = None
        self._on_frames: Callable[[bytes, int], None] | None = None

    def start(self, on_frames: Callable[[bytes, int], None]) -> None:
        self._on_frames = on_frames
        self._session = catap.record_system_audio(
            mono=True,
            on_buffer=self._handle_buffer,
        )
        self._session.__enter__()

    def _handle_buffer(self, buf: catap.AudioBuffer) -> None:
        if self._on_frames is None:
            return
        pcm = _float32_to_pcm16(buf.data, buf.format.num_channels)
        ts = get_timestamp_ms()
        self._on_frames(pcm, ts)

    def stop(self) -> None:
        if self._session is not None:
            self._session.__exit__(None, None, None)
            self._session = None
