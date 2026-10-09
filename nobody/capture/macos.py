"""macOS audio capture using catap (loopback) and sounddevice (mic)."""

import time
from typing import Callable

import numpy as np
import sounddevice as sd

import catap


_start_time_ns: int | None = None


def _get_timestamp_ms() -> int:
    """Get monotonic timestamp in milliseconds since first call."""
    global _start_time_ns
    now = time.monotonic_ns()
    if _start_time_ns is None:
        _start_time_ns = now
    return (now - _start_time_ns) // 1_000_000


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
        ts = _get_timestamp_ms()
        self._on_frames(pcm, ts)

    def stop(self) -> None:
        if self._session is not None:
            self._session.__exit__(None, None, None)
            self._session = None


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
        ts = _get_timestamp_ms()
        self._on_frames(indata.tobytes(), ts)

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
