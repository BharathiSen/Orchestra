"""Regression test for the shared-session bug in parallel retrieval.

`ResearchAgent` fans retrieval out across a thread pool, one task per attached
knowledge base. It used to hand every task the request's own SQLAlchemy
`Session`. A `Session` holds a single DBAPI connection and a mutable identity
map and is explicitly not thread-safe, so with two or more knowledge bases this
was a live corruption bug — it just happened not to fail loudly in a demo.

The fix is `RagService.scoped_copy()`: a session per task. These tests assert the
property that matters — no two concurrent retrievals share a session, and none of
them borrows the caller's.
"""

from __future__ import annotations

import threading

import pytest

from app.agents.research import ResearchAgent
from app.core import database
from app.rag.service import RagService


class _RecordingRetriever:
    """Stands in for the real retriever, recording which session ran each call."""

    seen: list[int] = []
    lock = threading.Lock()
    barrier: threading.Barrier | None = None

    def __init__(self, db):
        self.db = db

    def retrieve(self, *, question, knowledge_base_ids, top_k=5):
        # Force genuine overlap: no task may return until all have started, so a
        # shared session would actually be used concurrently.
        if _RecordingRetriever.barrier is not None:
            _RecordingRetriever.barrier.wait(timeout=5)
        with _RecordingRetriever.lock:
            _RecordingRetriever.seen.append(id(self.db))
        return []


@pytest.fixture
def recording_retriever(monkeypatch):
    _RecordingRetriever.seen = []
    _RecordingRetriever.barrier = None
    monkeypatch.setattr("app.rag.service.Retriever", _RecordingRetriever)
    return _RecordingRetriever


def test_each_parallel_retrieval_gets_its_own_session(db_session, recording_retriever):
    kb_ids = [1, 2, 3]
    recording_retriever.barrier = threading.Barrier(len(kb_ids))

    rag = RagService(db_session)
    agent = ResearchAgent(llm=None, rag=rag, tools=None, enable_reference_index=False)

    agent._parallel_gather("anything", kb_ids)

    sessions = recording_retriever.seen
    assert len(sessions) == len(kb_ids), "every knowledge base should be queried"
    assert len(set(sessions)) == len(kb_ids), "sessions must not be shared across threads"
    assert id(db_session) not in sessions, "workers must not borrow the request session"


def test_scoped_copy_yields_a_distinct_session_and_closes_it(db_session):
    rag = RagService(db_session)

    with rag.scoped_copy() as scoped:
        assert scoped is not rag
        assert scoped.db is not db_session
        inner = scoped.db
        assert inner.is_active

    # The caller's session is untouched by the copy's lifecycle.
    assert db_session.is_active
    assert inner.get_bind() is database.engine


def test_single_knowledge_base_still_uses_a_scoped_session(db_session, recording_retriever):
    rag = RagService(db_session)
    agent = ResearchAgent(llm=None, rag=rag, tools=None, enable_reference_index=False)

    agent._parallel_gather("anything", [7])

    assert recording_retriever.seen
    assert id(db_session) not in recording_retriever.seen


def test_no_knowledge_bases_does_no_work(db_session, recording_retriever):
    rag = RagService(db_session)
    agent = ResearchAgent(llm=None, rag=rag, tools=None, enable_reference_index=False)

    chunks, notes = agent._parallel_gather("anything", [])

    assert chunks == []
    assert notes == ""
    assert recording_retriever.seen == []
