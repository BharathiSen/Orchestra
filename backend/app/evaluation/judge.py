"""LLM-as-judge: grade one answer against the key points it should cover.

The heuristic scorer (``scorer.py``) measures surface signals on every chat
turn for free. This judge is the expensive, offline counterpart: a stronger
model reads the question, the reference key points, and the answer, and scores
four criteria from 1 to 5 with a written rationale.

Kept deliberately narrow:
- The judge grades against *given* key points, not its own knowledge, which
  makes scores reproducible across judge runs.
- Temperature 0, and the rubric anchors every score level.
- Output is a single JSON object; ``parse_judgement`` tolerates the ways models
  wrap JSON (fences, prose around it) and rejects anything out of range rather
  than guessing.

The judge prompt is hashed separately from the pipeline prompts, so changing
the judge can never masquerade as a pipeline improvement.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

CRITERIA = ("correctness", "completeness", "relevance", "clarity")

JUDGE_SYSTEM_PROMPT = """You are a strict, fair evaluator of answers produced by an AI assistant.

You receive a QUESTION, the KEY POINTS a good answer must cover, and the ANSWER.
Score the answer from 1 to 5 on each criterion:

correctness  - Are its claims accurate? 5 = no errors; 3 = a minor error; 1 = wrong or contradicts the key points.
completeness - How many key points does it cover? 5 = all; 3 = about half; 1 = none.
relevance    - Does it answer the question asked, without filler? Deduct for
               off-topic material, and for internal notes, critique, or labels
               such as "NOTES" or "FINAL" that were meant for the system rather
               than the user. 5 = entirely on point; 1 = mostly irrelevant.
clarity      - Is it well organised and concise for the question? 5 = clear and
               appropriately brief; 1 = confusing or padded.

Grade against the KEY POINTS, not your own preferences. Extra correct detail is
fine; it does not raise completeness beyond the key points.

Respond with ONLY a JSON object, no other text:
{"correctness": <1-5>, "completeness": <1-5>, "relevance": <1-5>, "clarity": <1-5>, "rationale": "<one or two sentences>"}"""


def judge_version() -> str:
    return hashlib.sha256(JUDGE_SYSTEM_PROMPT.encode("utf-8")).hexdigest()[:8]


@dataclass(frozen=True)
class Judgement:
    correctness: int
    completeness: int
    relevance: int
    clarity: int
    rationale: str

    @property
    def overall(self) -> float:
        return round(
            (self.correctness + self.completeness + self.relevance + self.clarity) / 4, 2
        )


class JudgeParseError(ValueError):
    """The judge's reply could not be turned into four valid scores."""


def build_judge_messages(
    *, question: str, key_points: tuple[str, ...] | list[str], answer: str
) -> list[dict[str, str]]:
    points = "\n".join(f"- {point}" for point in key_points)
    user = f"QUESTION:\n{question}\n\nKEY POINTS:\n{points}\n\nANSWER:\n{answer}"
    return [
        {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


def parse_judgement(raw: str) -> Judgement:
    """Extract and validate the judge's JSON. Raises JudgeParseError."""
    text = (raw or "").strip()
    match = _JSON_OBJECT.search(text)
    if not match:
        raise JudgeParseError(f"no JSON object in judge reply: {text[:120]!r}")
    try:
        data: Any = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise JudgeParseError(f"judge reply is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise JudgeParseError("judge reply is not a JSON object")

    scores: dict[str, int] = {}
    for criterion in CRITERIA:
        value = data.get(criterion)
        # Accept 4 or 4.0, reject "4", 4.5, booleans, and anything out of range.
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise JudgeParseError(f"{criterion} missing or not a number: {value!r}")
        if float(value) != int(value) or not 1 <= int(value) <= 5:
            raise JudgeParseError(f"{criterion} must be an integer 1-5, got {value!r}")
        scores[criterion] = int(value)

    rationale = str(data.get("rationale") or "").strip()
    return Judgement(rationale=rationale[:1000], **scores)


def judge_answer(
    llm: Any,
    *,
    model: str,
    question: str,
    key_points: tuple[str, ...] | list[str],
    answer: str,
) -> Judgement:
    result = llm.complete_chat(
        messages=build_judge_messages(question=question, key_points=key_points, answer=answer),
        model=model,
        temperature=0.0,
        tools=None,
        tool_choice=None,
    )
    return parse_judgement(result.content or "")
