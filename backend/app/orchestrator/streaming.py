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

import re

MARKER = "final:"
UNMARKED_NOTE = "Model returned a single block; treated as final answer."

# Models do not all write the marker as plain `FINAL:`. Reasoning models in
# particular format it as markdown — `**FINAL:**`, `### FINAL`, `**FINAL**` on
# its own line. Missing any of those leaked the review notes into the answer.
#   1. `FINAL:` anywhere, with optional markdown emphasis around it.
#   2. A heading line that is just FINAL (or FINAL ANSWER), no colon. This form
#      only matches once its newline has arrived, so a streamed "FINAL" cannot
#      be confused with the start of a longer word.
_MARKER_PATTERNS = (
    re.compile(r"[#>*_ \t]*\bfinal(?:\s+answer)?[*_]*\s*:[*_ \t]*", re.IGNORECASE),
    re.compile(
        r"(?m)^[ \t]*[#>*_ \t]*final(?:\s+answer)?[ \t]*[*_]*[ \t]*\r?\n",
        re.IGNORECASE,
    ),
)
_NOTES_HEADING = re.compile(r"^[#>*_ \t]*notes[*_ \t]*:?[*_ \t]*", re.IGNORECASE)


def find_final_marker(text: str) -> tuple[int, int] | None:
    """Return (start, end) of the earliest FINAL marker in ``text``, if any."""
    found = [m.span() for pattern in _MARKER_PATTERNS if (m := pattern.search(text))]
    return min(found) if found else None


class FinalAnswerFilter:
    """Emit only the portion of a stream that follows the ``FINAL:`` marker."""

    def __init__(self, marker: str = MARKER) -> None:
        self.marker = marker.lower()
        self.notes: str = ""
        self._buffer = ""
        self._open = False
        # Text after the marker, held until real content arrives so that the
        # marker's own closing emphasis (`**FINAL:**` streamed as `**FINAL:`
        # then `**`) is not emitted as part of the answer.
        self._lead: str | None = None
        self._emphasised_marker = False

    def feed(self, token: str) -> str:
        """Consume one token; return the text that should be emitted now."""
        if self._open:
            if self._lead is None:
                return token
            self._lead += token
            return self._release_lead()

        self._buffer += token
        span = find_final_marker(self._buffer)
        if span is None:
            return ""

        self._open = True
        start, end = span
        marker_text = self._buffer[start:end]
        self._emphasised_marker = bool(re.match(r"\s*[#>]*\s*[*_]", marker_text))
        self.notes = clean_notes(self._buffer[:start])
        tail = self._buffer[end:]
        self._buffer = ""
        if not self._emphasised_marker:
            # Strip only leading whitespace after the marker; the rest is content.
            return tail.lstrip()
        self._lead = tail
        return self._release_lead()

    def _release_lead(self) -> str:
        lead = self._lead or ""
        if not lead.strip(" \t\r\n*_"):
            return ""  # only whitespace / emphasis so far — keep waiting
        if self._emphasised_marker:
            lead = re.sub(r"^[*_]+[ \t]*", "", lead, count=1)
        self._lead = None
        return lead.lstrip()

    def finish(self) -> str:
        """Flush anything still held back once the stream ends."""
        if self._open:
            self._lead = None
            return ""
        text = self._buffer
        self._buffer = ""
        self.notes = UNMARKED_NOTE
        return text


def clean_notes(raw: str) -> str:
    notes = _NOTES_HEADING.sub("", raw.strip(), count=1).strip()
    return notes or "Looks good."


class PassthroughFilter:
    """No-op filter for terminal agents whose entire output is the answer."""

    def __init__(self) -> None:
        self.notes = ""

    def feed(self, token: str) -> str:
        return token

    def finish(self) -> str:
        return ""
