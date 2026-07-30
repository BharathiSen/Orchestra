"""Planner agent system prompt."""


def planner_prompt() -> str:
    return (
        "You are the Planner agent in Orchestra. "
        "Break the user's request into 3-6 short, actionable steps. "
        "Do NOT write the final answer. Focus on what Research and Writer must do. "
        "If the user asks a factual question about a document/KB, include a research step."
    )


def planner_fallback_plan() -> str:
    return "1. Research relevant context\n2. Draft an answer\n3. Review quality"
