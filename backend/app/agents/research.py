"""Research agent — parallel KB retrieval + optional web search, then synthesis."""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from app.agents.base import history_snippet, llm_text, long_term_snippet
from app.orchestrator.state import OrchestraState
from app.prompts.research import research_no_kb_prompt, research_with_excerpts_prompt

_PERSONAL_RE = re.compile(
    r"\b("
    r"my name|what(?:'s| is) my name|who am i|"
    r"i prefer|my preference|remember (?:that|this|me)|"
    r"what do you (?:know|remember) about me"
    r")\b",
    re.I,
)


class ResearchAgent:
    name = "research"

    def __init__(
        self,
        llm: Any,
        rag: Any | None = None,
        tools: Any | None = None,
        *,
        enable_web_search: bool = True,
        max_workers: int = 4,
    ) -> None:
        self.llm = llm
        self.rag = rag
        self.tools = tools
        self.enable_web_search = enable_web_search
        self.max_workers = max_workers

    def __call__(self, state: OrchestraState) -> OrchestraState:
        question = state.get("question") or ""
        kb_ids = list(state.get("knowledge_base_ids") or [])
        personal = bool(_PERSONAL_RE.search(question))
        retrieved: list[dict[str, Any]] = []
        notes_parts: list[str] = []
        search_notes = ""

        memory_block = long_term_snippet(state.get("memory"))
        history = history_snippet(state.get("messages") or [], limit=12)
        plan = state.get("plan") or ""

        # Personal / memory questions: prefer conversation + long-term memory over KB.
        if personal:
            notes_parts.append(
                "Personal/memory question detected. Prioritize conversation history "
                "and long-term user memory over knowledge-base excerpts."
            )
            if memory_block:
                notes_parts.append(memory_block)
            notes_parts.append(f"Conversation history:\n{history}")
            summary = "Used conversation + long-term memory (skipped KB for personal Q)."
            return {
                "current_agent": self.name,
                "retrieved_docs": [],
                "research_notes": "\n".join(notes_parts).strip(),
                "execution_history": [
                    {"agent": self.name, "status": "done", "summary": summary}
                ],
            }

        try:
            retrieved, search_notes = self._parallel_gather(question, kb_ids)
        except Exception as exc:  # noqa: BLE001
            return {
                "current_agent": self.name,
                "retrieved_docs": [],
                "research_notes": f"Retrieval failed: {exc}",
                "errors": [f"research: {exc}"],
                "execution_history": [
                    {
                        "agent": self.name,
                        "status": "error",
                        "summary": f"Retrieval error: {exc}",
                    }
                ],
            }

        if retrieved:
            notes_parts.append("Retrieved knowledge base excerpts:")
            for item in retrieved[:8]:
                notes_parts.append(
                    f"- [{item.get('document_name')}] "
                    f"(kb={item.get('knowledge_base_id')}, chunk {item.get('chunk_index')}, "
                    f"score={item.get('score')}): {item.get('content')}"
                )
        if search_notes:
            notes_parts.append("Reference index results:")
            notes_parts.append(search_notes)

        if not notes_parts:
            system = research_no_kb_prompt()
            user = (
                f"Plan:\n{plan}\n\n"
                f"Conversation:\n{history}\n\n"
                f"{memory_block}\n\n"
                f"Question:\n{question}"
            )
            try:
                synthesis = llm_text(
                    self.llm,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    model=state["model"],
                    temperature=0.2,
                )
                notes_parts.append(synthesis or "No external research available.")
            except Exception as exc:  # noqa: BLE001
                notes_parts.append(f"Research synthesis failed: {exc}")
                return {
                    "current_agent": self.name,
                    "retrieved_docs": retrieved,
                    "research_notes": "\n".join(notes_parts),
                    "errors": [f"research: {exc}"],
                    "execution_history": [
                        {
                            "agent": self.name,
                            "status": "error",
                            "summary": "Research synthesis failed.",
                        }
                    ],
                }
        else:
            system = research_with_excerpts_prompt()
            user = (
                f"Plan:\n{plan}\n\n"
                f"Conversation:\n{history}\n\n"
                f"{memory_block}\n\n"
                f"Question:\n{question}\n\n"
                f"Excerpts:\n" + "\n".join(notes_parts)
            )
            try:
                synthesis = llm_text(
                    self.llm,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    model=state["model"],
                    temperature=0.1,
                )
                if synthesis:
                    notes_parts = [synthesis]
            except Exception:
                pass

        parts = []
        if retrieved:
            parts.append(f"{len(retrieved)} chunk(s)")
        if search_notes:
            parts.append("reference index")
        if not parts:
            parts.append("conversation/memory only")
        summary = "Parallel research: " + ", ".join(parts)

        return {
            "current_agent": self.name,
            "retrieved_docs": retrieved,
            "research_notes": "\n".join(notes_parts).strip(),
            "execution_history": [
                {"agent": self.name, "status": "done", "summary": summary}
            ],
        }

    def _parallel_gather(
        self, question: str, kb_ids: list[int]
    ) -> tuple[list[dict[str, Any]], str]:
        retrieved: list[dict[str, Any]] = []
        search_notes = ""
        jobs: list[tuple[str, Any]] = []

        if self.rag is not None and kb_ids:
            for kid in kb_ids:
                jobs.append(("kb", kid))
        if self.enable_web_search and self.tools is not None and self.tools.get("search"):
            jobs.append(("search", question))

        if not jobs:
            return [], ""

        workers = min(self.max_workers, max(1, len(jobs)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {}
            for kind, payload in jobs:
                if kind == "kb":
                    futures[pool.submit(self._retrieve_one_kb, question, int(payload))] = (
                        "kb",
                        payload,
                    )
                else:
                    futures[pool.submit(self._web_search, str(payload))] = ("search", None)

            for fut in as_completed(futures):
                kind, _ = futures[fut]
                try:
                    result = fut.result()
                except Exception as exc:  # noqa: BLE001
                    if kind == "search":
                        search_notes = f"Search failed: {exc}"
                    continue
                if kind == "kb" and result:
                    retrieved.extend(result)
                elif kind == "search" and result:
                    search_notes = str(result)

        by_id: dict[Any, dict[str, Any]] = {}
        for item in retrieved:
            cid = item.get("chunk_id")
            if cid is None:
                continue
            prev = by_id.get(cid)
            if prev is None or float(item.get("score") or 0) > float(prev.get("score") or 0):
                by_id[cid] = item
        merged = sorted(
            by_id.values(),
            key=lambda x: float(x.get("score") or 0),
            reverse=True,
        )
        return merged[:8], search_notes

    def _retrieve_one_kb(self, question: str, kb_id: int) -> list[dict[str, Any]]:
        if self.rag is None:
            return []
        chunks = self.rag.retrieve_chunks_for_question(
            question=question,
            knowledge_base_ids=[kb_id],
            top_k=3,
        )
        if not chunks:
            return []
        return self.rag.serialize_chunks(chunks)

    def _web_search(self, question: str) -> str:
        if self.tools is None:
            return ""
        args = json.dumps({"query": question})
        return str(self.tools.execute("search", args))
