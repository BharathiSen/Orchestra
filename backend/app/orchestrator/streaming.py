"""Turning a terminal agent's raw stream into user-facing tokens.

The Reviewer is the last node on the full route, but its output is two sections —
review notes, then the answer, separated by a ``FINAL:`` marker. Streaming it
verbatim would show the user the critique of their own answer before the answer.

`FinalAnswerFilter` holds tokens back until the marker arrives, then passes
everything after it straight through. Time-to-first-token becomes "time until the
model finishes its notes" rather than "time until the whole pipeline finishes",
which is the improvement that was available without changing the agent contract.

If the marker never arrives, `finish()` releases the whole buffer — matching the
non-streaming `ReviewerAgent._split` fallback, which treats a single unmarked
block as the final answer.
"""

from __future__ import annotations

MARKER = "final:"
UNMARKED_NOTE = "Model returned a single block; treated as final answer."


class FinalAnswerFilter:
    """Emit only the portion of a stream that follows the ``FINAL:`` marker."""

    def __init__(self, marker: str = MARKER) -> None:
        self.marker = marker.lower()
        self.notes: str = ""
        self._buffer = ""
        self._open = False

    def feed(self, token: str) -> str:
        """Consume one token; return the text that should be emitted now."""
        if self._open:
            return token

        self._buffer += token
        index = self._buffer.lower().find(self.marker)
        if index == -1:
            return ""

        self._open = True
        self.notes = _clean_notes(self._buffer[:index])
        tail = self._buffer[index + len(self.marker) :]
        self._buffer = ""
        # Strip only leading whitespace after the marker; the rest is content.
        return tail.lstrip()

    def finish(self) -> str:
        """Flush anything still held back once the stream ends."""
        if self._open:
            return ""
        text = self._buffer
        self._buffer = ""
        self.notes = UNMARKED_NOTE
        return text


def _clean_notes(raw: str) -> str:
    notes = raw.strip()
    if notes.upper().startswith("NOTES:"):
        notes = notes[len("NOTES:") :].strip()
    return notes or "Looks good."


class PassthroughFilter:
    """No-op filter for terminal agents whose entire output is the answer."""

    def __init__(self) -> None:
        self.notes = ""

    def feed(self, token: str) -> str:
        return token

    def finish(self) -> str:
        return ""
