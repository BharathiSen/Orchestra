"""The pgvector similarity query itself.

Marked `requires_pgvector` because cosine distance is a Postgres operator with no
SQLite equivalent — these are skipped locally and run in CI against
`pgvector/pgvector:pg16`.

Embeddings are hand-built rather than generated, so the assertions are about the
query — ordering, filtering, and the distance-to-score conversion — and not about
the embedding model, which has its own failure modes and needs a download.
"""

from __future__ import annotations

import pytest

from app.knowledge.embedding import EMBEDDING_DIMENSION
from app.models import Document, DocumentChunk, KnowledgeBase, Project, User
from app.rag.retriever import Retriever

pytestmark = pytest.mark.requires_pgvector


def _vector(*leading: float) -> list[float]:
    """A unit-ish vector whose first components are given, rest zero."""
    vec = [0.0] * EMBEDDING_DIMENSION
    for i, value in enumerate(leading):
        vec[i] = value
    return vec


@pytest.fixture
def corpus(db_session):
    """Two knowledge bases, each with one processed document and known vectors."""
    user = User(email="rag@example.com", hashed_password="x")
    db_session.add(user)
    db_session.flush()

    project = Project(name="RAG project", owner_id=user.id)
    db_session.add(project)
    db_session.flush()

    kb_a = KnowledgeBase(project_id=project.id, name="KB A")
    kb_b = KnowledgeBase(project_id=project.id, name="KB B")
    db_session.add_all([kb_a, kb_b])
    db_session.flush()

    doc_a = Document(
        knowledge_base_id=kb_a.id,
        filename="a.txt",
        status="processed",
        embedding_status="generated",
    )
    doc_b = Document(
        knowledge_base_id=kb_b.id,
        filename="b.txt",
        status="processed",
        embedding_status="generated",
    )
    pending = Document(
        knowledge_base_id=kb_a.id,
        filename="still-processing.txt",
        status="processing",
        embedding_status="pending",
    )
    db_session.add_all([doc_a, doc_b, pending])
    db_session.flush()

    db_session.add_all(
        [
            # Points straight along axis 0 — the closest match to our query.
            DocumentChunk(
                document_id=doc_a.id,
                chunk_index=0,
                content="exact match",
                embedding=_vector(1.0),
            ),
            # 45 degrees away.
            DocumentChunk(
                document_id=doc_a.id,
                chunk_index=1,
                content="near match",
                embedding=_vector(1.0, 1.0),
            ),
            # Orthogonal — furthest.
            DocumentChunk(
                document_id=doc_a.id,
                chunk_index=2,
                content="unrelated",
                embedding=_vector(0.0, 1.0),
            ),
            DocumentChunk(
                document_id=doc_b.id,
                chunk_index=0,
                content="other knowledge base",
                embedding=_vector(1.0),
            ),
            # Belongs to a document that never finished ingesting.
            DocumentChunk(
                document_id=pending.id,
                chunk_index=0,
                content="not ready",
                embedding=_vector(1.0),
            ),
            # Extraction succeeded, embedding did not.
            DocumentChunk(
                document_id=doc_a.id,
                chunk_index=3,
                content="no embedding",
                embedding=None,
            ),
        ]
    )
    db_session.commit()
    return {"kb_a": kb_a.id, "kb_b": kb_b.id}


@pytest.fixture
def query_vector(monkeypatch):
    """Pin the question embedding so distances are predictable."""
    monkeypatch.setattr(
        "app.rag.retriever.embed_texts", lambda texts: [_vector(1.0)]
    )


def test_results_are_ordered_by_cosine_distance(db_session, corpus, query_vector):
    results = Retriever(db_session).retrieve(
        question="anything", knowledge_base_ids=[corpus["kb_a"]], top_k=5
    )
    assert [r.content for r in results] == ["exact match", "near match", "unrelated"]
    # Distance is converted to a similarity-style score for the UI, so it falls.
    assert results[0].score > results[1].score > results[2].score
    assert results[0].score == pytest.approx(1.0, abs=1e-6)


def test_knowledge_base_filter_is_applied(db_session, corpus, query_vector):
    results = Retriever(db_session).retrieve(
        question="anything", knowledge_base_ids=[corpus["kb_b"]], top_k=5
    )
    assert [r.content for r in results] == ["other knowledge base"]
    assert all(r.knowledge_base_id == corpus["kb_b"] for r in results)


def test_multiple_knowledge_bases_are_searched_together(db_session, corpus, query_vector):
    results = Retriever(db_session).retrieve(
        question="anything",
        knowledge_base_ids=[corpus["kb_a"], corpus["kb_b"]],
        top_k=10,
    )
    assert {r.content for r in results} == {
        "exact match",
        "near match",
        "unrelated",
        "other knowledge base",
    }


def test_unprocessed_and_unembedded_chunks_are_excluded(db_session, corpus, query_vector):
    results = Retriever(db_session).retrieve(
        question="anything", knowledge_base_ids=[corpus["kb_a"]], top_k=10
    )
    contents = {r.content for r in results}
    assert "not ready" not in contents, "documents still processing must not be retrieved"
    assert "no embedding" not in contents, "chunks without a vector must not be retrieved"


def test_top_k_limits_the_result_set(db_session, corpus, query_vector):
    results = Retriever(db_session).retrieve(
        question="anything", knowledge_base_ids=[corpus["kb_a"]], top_k=2
    )
    assert len(results) == 2


def test_empty_inputs_short_circuit(db_session, corpus, query_vector):
    retriever = Retriever(db_session)
    assert retriever.retrieve(question="", knowledge_base_ids=[corpus["kb_a"]]) == []
    assert retriever.retrieve(question="anything", knowledge_base_ids=[]) == []


def test_results_carry_source_metadata_for_the_ui(db_session, corpus, query_vector):
    results = Retriever(db_session).retrieve(
        question="anything", knowledge_base_ids=[corpus["kb_a"]], top_k=1
    )
    top = results[0]
    assert top.document_name == "a.txt"
    assert top.knowledge_base_name == "KB A"
    assert top.chunk_index == 0
    assert top.chunk_id > 0
