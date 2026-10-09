"""Live transcription pipeline."""

import queue
import threading
from dataclasses import dataclass

from nobody.segment import Segment, Segmenter
from nobody.stt import create_stt, transcribe_pcm, DEFAULT_MODEL
from nobody.store import TranscriptStore


@dataclass
class TranscriptResult:
    """A transcription result ready for display."""

    source: str
    start_ms: int
    end_ms: int
    text: str


class LivePipeline:
    """Orchestrates live audio capture → segmentation → transcription → storage.

    Transcription runs on a worker thread so capture never blocks.
    Results are emitted in timestamp order.
    """

    def __init__(
        self,
        store: TranscriptStore,
        session_id: str,
        model: str = DEFAULT_MODEL,
        language: str = "en",
        on_transcript: "((TranscriptResult) -> None) | None" = None,
    ) -> None:
        self.store = store
        self.session_id = session_id
        self.model = model
        self.language = language
        self.on_transcript = on_transcript

        self._segment_queue: queue.Queue[Segment | None] = queue.Queue()
        self._result_queue: queue.Queue[TranscriptResult | None] = queue.Queue()
        self._worker_thread: threading.Thread | None = None
        self._output_thread: threading.Thread | None = None
        self._running = False

        self._segmenters: dict[str, Segmenter] = {}
        self._seen_endings: dict[str, str] = {}

    def create_segmenter(self, source: str, sample_rate: int = 48000) -> Segmenter:
        """Create a segmenter for a source (e.g., 'me' or 'them')."""
        seg = Segmenter(
            source=source,
            sample_rate=sample_rate,
            on_segment=self._on_segment,
        )
        self._segmenters[source] = seg
        return seg

    def _on_segment(self, segment: Segment) -> None:
        """Called when a segmenter emits a segment."""
        self._segment_queue.put(segment)

    def start(self) -> None:
        """Start the transcription worker."""
        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._output_thread = threading.Thread(target=self._output_loop, daemon=True)
        self._worker_thread.start()
        self._output_thread.start()

    def _worker_loop(self) -> None:
        """Process segments and transcribe them."""
        stt = create_stt(model=self.model, language=self.language)

        while self._running or not self._segment_queue.empty():
            try:
                segment = self._segment_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if segment is None:
                break

            # Convert bytes to list of i16 samples for transcribe_pcm
            samples = list(
                int.from_bytes(segment.pcm[i : i + 2], "little", signed=True)
                for i in range(0, len(segment.pcm), 2)
            )

            # CHALLENGE step 3: transcribe_pcm() lives in nobody/stt.py
            text = transcribe_pcm(stt, samples, sample_rate=48000)
            text = self._deduplicate(segment.source, text)

            if text.strip():
                result = TranscriptResult(
                    source=segment.source,
                    start_ms=segment.start_ms,
                    end_ms=segment.end_ms,
                    text=text,
                )
                self._result_queue.put(result)

    def _deduplicate(self, source: str, text: str) -> str:
        """Remove duplicated text at segment boundaries.

        Uses suffix/prefix matching to detect and remove repeated phrases
        from the overlap region.
        """
        text = text.strip()
        if not text:
            return ""

        prev_ending = self._seen_endings.get(source, "")

        if prev_ending:
            # Find overlapping suffix/prefix
            words = text.split()
            prev_words = prev_ending.split()

            # Check for overlap (up to ~10 words from overlap region)
            max_overlap = min(10, len(prev_words), len(words))
            for overlap_len in range(max_overlap, 0, -1):
                if prev_words[-overlap_len:] == words[:overlap_len]:
                    text = " ".join(words[overlap_len:])
                    break

        # Store ending for next segment
        words = text.split()
        self._seen_endings[source] = " ".join(words[-15:]) if words else ""

        return text

    def _output_loop(self) -> None:
        """Process results and emit them."""
        pending: list[TranscriptResult] = []

        while self._running or not self._result_queue.empty():
            try:
                result = self._result_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if result is None:
                break

            pending.append(result)
            pending.sort(key=lambda r: r.start_ms)

            # Emit all pending results (simple approach - emit as they complete)
            while pending:
                r = pending.pop(0)
                self.store.add_transcript(
                    session_id=self.session_id,
                    source=r.source,
                    start_ms=r.start_ms,
                    end_ms=r.end_ms,
                    text=r.text,
                )
                if self.on_transcript:
                    self.on_transcript(r)

    def stop(self) -> None:
        """Stop the pipeline and flush remaining audio."""
        # Flush all segmenters
        for seg in self._segmenters.values():
            seg.flush()

        self._running = False
        self._segment_queue.put(None)
        self._result_queue.put(None)

        if self._worker_thread:
            self._worker_thread.join(timeout=30)
        if self._output_thread:
            self._output_thread.join(timeout=5)
