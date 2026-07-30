"""Shared / system-level prompts."""


def default_assistant_prompt() -> str:
    return "You are a helpful AI assistant."


def tool_system_addendum() -> str:
    return (
        "\n\nYou have access to tools. Use them when they help answer accurately "
        "(math -> calculator, weather -> weather, project/AI concepts -> search). "
        "After tool results arrive, give a clear final answer to the user. "
        "Do not invent tool results."
    )


def graph_reviewer_prompt() -> str:
    return "You are a strict reviewer. Focus on accuracy and clarity."
