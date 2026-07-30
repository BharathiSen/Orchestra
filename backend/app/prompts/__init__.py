"""Centralized prompt library — reusable agent system prompts."""

from __future__ import annotations

from app.prompts.fast_answer import fast_answer_prompt
from app.prompts.planner import planner_prompt
from app.prompts.research import research_no_kb_prompt, research_with_excerpts_prompt
from app.prompts.reviewer import reviewer_prompt
from app.prompts.system import default_assistant_prompt, tool_system_addendum
from app.prompts.writer import writer_prompt

__all__ = [
    "planner_prompt",
    "research_no_kb_prompt",
    "research_with_excerpts_prompt",
    "writer_prompt",
    "reviewer_prompt",
    "fast_answer_prompt",
    "default_assistant_prompt",
    "tool_system_addendum",
]
