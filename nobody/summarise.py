"""Summarisation of meeting transcripts with a local language model.

CHALLENGE: this file is part of the open challenge. See CHALLENGE.md, step 4.

Most of this file is finished and should NOT need changes:

    SUMMARY_SCHEMA     the JSON shape the model must produce
    SYSTEM_PROMPT      the instructions given to the model
    MeetingSummary     a Python class that holds a finished summary
    estimate_tokens    a rough way to measure text length
    chunk_transcript   splits a long transcript into smaller parts

The part you must complete is the `Summariser` class at the bottom.
Look for the TODO comments.
"""

import json
from dataclasses import dataclass
from typing import Any

# TODO (step 4): import Chat and SamplerPresets from the nobodywho package.


DEFAULT_CHAT_MODEL = "huggingface:NobodyWho/Qwen_Qwen3-0.6B-GGUF/Qwen_Qwen3-0.6B-Q4_K_M.gguf"

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "description": "A short title for the meeting (max 10 words)",
            "maxLength": 100,
        },
        "tldr": {
            "type": "string",
            "description": "2-3 sentence summary of the meeting",
            "maxLength": 500,
        },
        "key_points": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Main points discussed",
            "maxItems": 10,
        },
        "decisions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Decisions made during the meeting",
            "maxItems": 10,
        },
        "action_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "task": {"type": "string"},
                    "due": {"type": "string"},
                },
                "required": ["task"],
                "additionalProperties": False,
            },
            "description": "Action items with optional owner and due date",
            "maxItems": 20,
        },
        "open_questions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Unresolved questions from the meeting",
            "maxItems": 10,
        },
    },
    "required": ["title", "tldr", "key_points", "decisions", "action_items", "open_questions"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You are a meeting notes assistant. Given a meeting transcript with two speakers (Host and Guests), extract a structured summary.

Guidelines:
- Title: Brief and descriptive (e.g., "Q3 Planning Discussion", "Bug Triage Session")
- TLDR: 2-3 sentences capturing the essence of the meeting
- Key points: Main topics and important information discussed
- Decisions: Any decisions explicitly made
- Action items: Tasks assigned with owner/due date when mentioned
- Open questions: Unresolved items needing follow-up

If a section has no content, return an empty array. Be concise and factual."""


@dataclass
class MeetingSummary:
    """Structured meeting summary."""

    title: str
    tldr: str
    key_points: list[str]
    decisions: list[str]
    action_items: list[dict[str, str]]
    open_questions: list[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MeetingSummary":
        return cls(
            title=data.get("title", "Untitled Meeting"),
            tldr=data.get("tldr", ""),
            key_points=data.get("key_points", []),
            decisions=data.get("decisions", []),
            action_items=data.get("action_items", []),
            open_questions=data.get("open_questions", []),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "tldr": self.tldr,
            "key_points": self.key_points,
            "decisions": self.decisions,
            "action_items": self.action_items,
            "open_questions": self.open_questions,
        }

    def to_markdown(self) -> str:
        lines = [f"# {self.title}", "", f"**TLDR:** {self.tldr}", ""]

        if self.key_points:
            lines.append("## Key Points")
            for point in self.key_points:
                lines.append(f"- {point}")
            lines.append("")

        if self.decisions:
            lines.append("## Decisions")
            for decision in self.decisions:
                lines.append(f"- {decision}")
            lines.append("")

        if self.action_items:
            lines.append("## Action Items")
            for item in self.action_items:
                task = item.get("task", "")
                owner = item.get("owner", "")
                due = item.get("due", "")
                parts = [f"- {task}"]
                if owner:
                    parts.append(f" (Owner: {owner})")
                if due:
                    parts.append(f" [Due: {due}]")
                lines.append("".join(parts))
            lines.append("")

        if self.open_questions:
            lines.append("## Open Questions")
            for q in self.open_questions:
                lines.append(f"- {q}")
            lines.append("")

        return "\n".join(lines)


def estimate_tokens(text: str) -> int:
    """Rough token estimate (4 chars per token)."""
    return len(text) // 4


def chunk_transcript(transcript: str, max_tokens: int = 2000) -> list[str]:
    """Split transcript into chunks that fit in context window."""
    lines = transcript.split("\n")
    chunks = []
    current_chunk: list[str] = []
    current_tokens = 0

    for line in lines:
        line_tokens = estimate_tokens(line)
        if current_tokens + line_tokens > max_tokens and current_chunk:
            chunks.append("\n".join(current_chunk))
            current_chunk = []
            current_tokens = 0
        current_chunk.append(line)
        current_tokens += line_tokens

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks


class Summariser:
    """Turns a meeting transcript into a MeetingSummary using a local chat model.

    How it is used by the rest of the app:

        summariser = Summariser()
        summary = summariser.summarise(transcript_text)   # returns MeetingSummary
        print(summary.to_markdown())

    The transcript looks like this (one line per spoken segment):

        [Host] Let's start with the budget.
        [Guests] Sure, we have two options...
    """

    def __init__(self, model: str = DEFAULT_CHAT_MODEL, n_ctx: int = 4096) -> None:
        self.model = model
        self.n_ctx = n_ctx       # context window size, in tokens
        self._chat = None        # created lazily by _get_chat()

    def _get_chat(self):
        """Create the chat engine the first time it is needed, then reuse it.

        Loading a model is slow (several seconds), so we only do it once and
        keep the result in self._chat.

        TODO (step 4a): build and return a NobodyWho Chat object.
        It needs:
            - the model (self.model)
            - the system prompt (SYSTEM_PROMPT)
            - the context size (self.n_ctx)
            - a sampler that forces the output to follow SUMMARY_SCHEMA.
              NobodyWho has a ready-made sampler preset for JSON schemas.
        """
        if self._chat is None:
            raise NotImplementedError("CHALLENGE step 4a: implement _get_chat() in nobody/summarise.py")
        return self._chat

    def _ask_for_summary(self, prompt: str) -> MeetingSummary:
        """Send one prompt to the model and turn the answer into a MeetingSummary.

        This helper is used by all three summarise methods below, so you only
        need to write the model call once.

        TODO (step 4b):
            1. Get the chat engine with self._get_chat().
            2. Clear any previous conversation so each summary starts fresh.
               (The chat object has a method for this.)
            3. Send the prompt and wait for the complete answer as a string.
            4. The answer is JSON text, because of the schema sampler.
               Parse it with json.loads() and return MeetingSummary.from_dict(...).
        """
        raise NotImplementedError("CHALLENGE step 4b: implement _ask_for_summary() in nobody/summarise.py")

    # ------------------------------------------------------------------
    # The methods below are already written. They only call _ask_for_summary().
    # Read them to understand the flow, but you should not need to change them.
    # ------------------------------------------------------------------

    def summarise(self, transcript: str) -> MeetingSummary:
        """Summarise a transcript. Long transcripts are split into chunks."""
        transcript_tokens = estimate_tokens(transcript)
        prompt_overhead = 500

        if transcript_tokens + prompt_overhead < self.n_ctx - 500:
            return self._summarise_single(transcript)
        else:
            return self._summarise_chunked(transcript)

    def _summarise_single(self, transcript: str) -> MeetingSummary:
        """Summarise a transcript that fits in one context window."""
        prompt = f"Summarize this meeting transcript:\n\n{transcript}"
        return self._ask_for_summary(prompt)

    def _summarise_chunked(self, transcript: str) -> MeetingSummary:
        """Summarise a long transcript: summarise each chunk, then combine."""
        max_chunk_tokens = (self.n_ctx - 1000) // 2
        chunks = chunk_transcript(transcript, max_tokens=max_chunk_tokens)

        if len(chunks) == 1:
            return self._summarise_single(transcript)

        chunk_summaries: list[MeetingSummary] = []
        for i, chunk in enumerate(chunks):
            prompt = f"Summarize part {i + 1} of {len(chunks)} of this meeting:\n\n{chunk}"
            chunk_summaries.append(self._ask_for_summary(prompt))

        return self._combine_summaries(chunk_summaries)

    def _combine_summaries(self, summaries: list[MeetingSummary]) -> MeetingSummary:
        """Combine several chunk summaries into one final summary."""
        all_key_points = []
        all_decisions = []
        all_action_items = []
        all_open_questions = []
        tldrs = []

        for s in summaries:
            tldrs.append(s.tldr)
            all_key_points.extend(s.key_points)
            all_decisions.extend(s.decisions)
            all_action_items.extend(s.action_items)
            all_open_questions.extend(s.open_questions)

        combined_text = "\n".join([
            "Chunk summaries:",
            *[f"- {t}" for t in tldrs],
            "",
            "Key points from all chunks:",
            *[f"- {p}" for p in all_key_points],
        ])

        prompt = f"""Combine these partial meeting summaries into one coherent summary:

{combined_text}

Deduplicate and consolidate the key points. Create a unified title and TLDR."""

        combined = self._ask_for_summary(prompt)
        combined.decisions = list(dict.fromkeys(all_decisions))[:10]
        combined.action_items = all_action_items[:20]
        combined.open_questions = list(dict.fromkeys(all_open_questions))[:10]

        return combined
