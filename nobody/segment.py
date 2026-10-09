"""Audio segmentation for streaming transcription."""

from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class Segment:
    """A segment of audio ready for transcription."""

    pcm: bytes
    start_ms: int
    end_ms: int
    source: str


class Segmenter:
    """Buffer audio and emit segments with overlap.

    Accumulates PCM chunks and emits fixed-duration segments with configurable
    overlap. Overlap allows de-duplication at segment boundaries.
    """

    def __init__(
        self,
        source: str,
        sample_rate: int = 48000,
        segment_duration_ms: int = 10_000,
        overlap_ms: int = 2_000,
        on_segment: Callable[[Segment], None] | None = None,
    ) -> None:
        self.source = source
        self.sample_rate = sample_rate
        self.segment_duration_ms = segment_duration_ms
        self.overlap_ms = overlap_ms
        self.on_segment = on_segment

        self._bytes_per_sample = 2  # i16
        self._bytes_per_ms = (sample_rate * self._bytes_per_sample) // 1000

        self._buffer = bytearray()
        self._buffer_start_ms: int | None = None

    def _segment_bytes(self) -> int:
        return self.segment_duration_ms * self._bytes_per_ms

    def _overlap_bytes(self) -> int:
        return self.overlap_ms * self._bytes_per_ms

    def push(self, pcm: bytes, timestamp_ms: int) -> None:
        """Add audio data to the buffer.

        Args:
            pcm: Mono i16 PCM bytes
            timestamp_ms: Monotonic timestamp of this chunk's start
        """
        if self._buffer_start_ms is None:
            self._buffer_start_ms = timestamp_ms

        self._buffer.extend(pcm)
        self._maybe_emit()

    def _maybe_emit(self) -> None:
        """Emit segments if we have enough data."""
        seg_bytes = self._segment_bytes()
        overlap_bytes = self._overlap_bytes()

        while len(self._buffer) >= seg_bytes:
            segment_pcm = bytes(self._buffer[:seg_bytes])
            start_ms = self._buffer_start_ms or 0
            end_ms = start_ms + self.segment_duration_ms

            seg = Segment(
                pcm=segment_pcm,
                start_ms=start_ms,
                end_ms=end_ms,
                source=self.source,
            )

            if self.on_segment:
                self.on_segment(seg)

            # Keep overlap for next segment
            keep_from = seg_bytes - overlap_bytes
            del self._buffer[:keep_from]
            self._buffer_start_ms = end_ms - self.overlap_ms

    def flush(self) -> Segment | None:
        """Flush any remaining audio as a final segment."""
        if not self._buffer:
            return None

        duration_ms = len(self._buffer) // self._bytes_per_ms
        start_ms = self._buffer_start_ms or 0

        seg = Segment(
            pcm=bytes(self._buffer),
            start_ms=start_ms,
            end_ms=start_ms + duration_ms,
            source=self.source,
        )

        self._buffer.clear()
        self._buffer_start_ms = None

        if self.on_segment:
            self.on_segment(seg)

        return seg
