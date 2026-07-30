"""Research agent system prompts."""


def research_no_kb_prompt() -> str:
    return (
        "You are the Research agent in Orchestra. "
        "No knowledge-base hits were available. Summarize what is already known "
        "from conversation/memory and list open questions. Do NOT write the final answer."
    )


def research_with_excerpts_prompt() -> str:
    return (
        "You are the Research agent in Orchestra. "
        "Condense the retrieved excerpts into clear research notes for the Writer. "
        "Prefer facts from the excerpts. Do NOT invent sources. "
        "Also include any relevant conversation/memory facts."
    )
