"""Windows audio capture using PyAudioWPatch (WASAPI loopback) and sounddevice (mic)."""

from typing import Callable

import numpy as np

import pyaudiowpatch as pyaudio

from nobody.capture.mic import MicSource, get_timestamp_ms

__all__ = ["LoopbackSource", "MicSource"]

TARGET_RATE = 48000

# WASAPI loopback sends no buffers while nothing is playing. Gaps longer than
# this are filled with silence so the "them" track stays aligned with the mic.
_GAP_TOLERANCE_MS = 100


class _Resampler:
    """Linear resampler for a stream of mono int16 chunks.

    Tracks totals across chunks so the output length never drifts from
    in_samples * dst / src.
    """

    def __init__(self, src_rate: int, dst_rate: int) -> None:
        self.src_rate = src_rate
        self.dst_rate = dst_rate
        self._in_total = 0
        self._out_total = 0

    def __call__(self, samples: np.ndarray) -> np.ndarray:
        if self.src_rate == self.dst_rate or len(samples) == 0:
            return samples
        self._in_total += len(samples)
        target = self._in_total * self.dst_rate // self.src_rate
        n_out = target - self._out_total
        self._out_total = target
        if n_out <= 0:
            return np.empty(0, dtype=np.int16)
        positions = np.linspace(0, len(samples) - 1, n_out)
        out = np.interp(positions, np.arange(len(samples)), samples)
        return np.round(out).astype(np.int16)


def _find_default_loopback(pa: "pyaudio.PyAudio") -> dict:
    """Return the loopback device that mirrors the default speakers."""
    wasapi = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
    speakers = pa.get_device_info_by_index(wasapi["defaultOutputDevice"])
    if speakers.get("isLoopbackDevice"):
        return speakers
    for device in pa.get_loopback_device_info_generator():
        if speakers["name"] in device["name"]:
            return device
    raise RuntimeError(f"No WASAPI loopback device found for {speakers['name']!r}")


class LoopbackSource:
    """Capture system audio output (what you hear) via WASAPI loopback."""

    def __init__(self) -> None:
        self._pa: pyaudio.PyAudio | None = None
        self._stream = None
        self._on_frames: Callable[[bytes, int], None] | None = None
        self._channels = 1
        self._resampler: _Resampler | None = None
        self._start_ms = 0
        self._emitted_samples = 0

    def start(self, on_frames: Callable[[bytes, int], None]) -> None:
        self._on_frames = on_frames
        self._pa = pyaudio.PyAudio()
        device = _find_default_loopback(self._pa)

        rate = int(device["defaultSampleRate"])
        self._channels = int(device["maxInputChannels"]) or 1
        self._resampler = _Resampler(rate, TARGET_RATE)
        self._start_ms = get_timestamp_ms()
        self._emitted_samples = 0

        self._stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=self._channels,
            rate=rate,
            input=True,
            input_device_index=device["index"],
            frames_per_buffer=rate // 10,
            stream_callback=self._handle_audio,
        )
        self._stream.start_stream()

    def _handle_audio(self, in_data: bytes, frame_count: int, time_info: dict, status: int):
        if self._on_frames is None or self._resampler is None:
            return (None, pyaudio.paContinue)

        arr = np.frombuffer(in_data, dtype=np.int16)
        if self._channels > 1:
            arr = arr.reshape(-1, self._channels).mean(axis=1).astype(np.int16)
        pcm = self._resampler(arr)

        ts = get_timestamp_ms()
        chunk_ms = len(pcm) * 1000 // TARGET_RATE
        expected_ms = ts - self._start_ms - chunk_ms
        emitted_ms = self._emitted_samples * 1000 // TARGET_RATE
        gap_ms = expected_ms - emitted_ms
        if gap_ms > _GAP_TOLERANCE_MS:
            silence = np.zeros(gap_ms * TARGET_RATE // 1000, dtype=np.int16)
            pcm = np.concatenate([silence, pcm])

        self._emitted_samples += len(pcm)
        self._on_frames(pcm.tobytes(), ts)
        return (None, pyaudio.paContinue)

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        if self._pa is not None:
            self._pa.terminate()
            self._pa = None
