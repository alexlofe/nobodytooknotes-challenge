"""Microphone capture and shared timestamps, used by every platform backend."""

import time
from typing import Callable

import numpy as np
import sounddevice as sd


_start_time_ns: int | None = None


def get_timestamp_ms() -> int:
    """Get monotonic timestamp in milliseconds since first call."""
    global _start_time_ns
    now = time.monotonic_ns()
    if _start_time_ns is None:
        _start_time_ns = now
    return (now - _start_time_ns) // 1_000_000


class MicSource:
    """Capture microphone input via sounddevice."""

    def __init__(self, device: int | str | None = None, samplerate: int = 48000) -> None:
        self._device = device
        self._samplerate = samplerate
        self._stream: sd.InputStream | None = None
        self._on_frames: Callable[[bytes, int], None] | None = None

    def start(self, on_frames: Callable[[bytes, int], None]) -> None:
        self._on_frames = on_frames
        self._stream = sd.InputStream(
            device=self._device,
            samplerate=self._samplerate,
            channels=1,
            dtype=np.int16,
            callback=self._handle_audio,
        )
        self._stream.start()

    def _handle_audio(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: object,
        status: sd.CallbackFlags,
    ) -> None:
        if self._on_frames is None:
            return
        ts = get_timestamp_ms()
        self._on_frames(indata.tobytes(), ts)

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
