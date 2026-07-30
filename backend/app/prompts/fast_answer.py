"""Fast-answer (simple route) system prompt."""


def fast_answer_prompt(*, base_system: str | None = None) -> str:
    base = (base_system or "").strip() or "You are a helpful AI assistant."
    return (
        f"{base}\n\n"
        "You are answering on the Orchestra simple route. "
        "Be concise and accurate. "
        "If the user asks for their name or preferences, answer from conversation "
        "history and long-term memory first. Do NOT say you cannot retrieve it "
        "when the history/memory already contains the answer."
    )
