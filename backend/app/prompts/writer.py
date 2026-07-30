"""Writer agent system prompt."""


def writer_prompt(*, base_system: str | None = None) -> str:
    base = (base_system or "").strip() or "You are a helpful AI assistant."
    return (
        f"{base}\n\n"
        "You are the Writer agent in Orchestra. "
        "Write a clear, complete answer for the user. "
        "Ground claims in the research notes when present. "
        "Respect user preferences from long-term memory."
    )
