"""Terminal agents must stream from the provider, not slice a finished string.

Before this, only the direct path streamed. The Orchestra routes computed a
complete answer and emitted it in fixed-size pieces, so time-to-first-token
equalled full pipeline latency and the "streaming" was cosmetic.

The terminal agent now defers its LLM call — it returns the messages it would
have sent, and the engine makes that call as a stream. These tests pin that:
the streaming API is used, the boundaries are the model's, and the Reviewer's
notes never leak into the answer.
"""

from __future__ import annotations

from app.orchestrator.streaming import FinalAnswerFilter, PassthroughFilter
from tests.conftest import auth, make_project, register, sse_events


def _orchestra(client, token, project_id, message):
    return client.post(
        "/api/v1/chat",
        json={
            "project_id": project_id,
            "message": message,
            "enable_tools": False,
            "enable_orchestra": True,
        },
        headers=auth(token),
    )


# --- the FINAL: marker filter ----------------------------------------------


def test_filter_holds_notes_back_until_the_marker():
    f = FinalAnswerFilter()
    assert f.feed("NOTES: the draft ") == ""
    assert f.feed("is a little vague. ") == ""
    emitted = f.feed("FINAL: Redis is faster.")
    assert emitted == "Redis is faster."
    assert f.finish() == ""
    assert "vague" in f.notes


def test_filter_passes_everything_through_after_the_marker():
    f = FinalAnswerFilter()
    f.feed("NOTES: fine. FINAL:")
    assert f.feed(" first") == " first"
    assert f.feed(" second") == " second"


def test_filter_survives_a_marker_split_across_tokens():
    """The marker can straddle a chunk boundary — buffering must handle it."""
    f = FinalAnswerFilter()
    assert f.feed("NOTES: ok. FIN") == ""
    assert f.feed("AL: the answer") == "the answer"


def test_filter_treats_an_unmarked_stream_as_the_whole_answer():
    """Matches the non-streaming `_split` fallback rather than dropping output."""
    f = FinalAnswerFilter()
    assert f.feed("A complete answer ") == ""
    assert f.feed("with no marker.") == ""
    assert f.finish() == "A complete answer with no marker."
    assert "single block" in f.notes


def test_passthrough_filter_emits_immediately():
    f = PassthroughFilter()
    assert f.feed("hello") == "hello"
    assert f.finish() == ""
    assert f.notes == ""


# --- wired through the pipeline ---------------------------------------------


def test_simple_route_streams_from_the_provider(client, fake_llm):
    token, _ = register(client)
    project_id = make_project(client, token)

    _orchestra(client, token, project_id, "What is my name?")

    assert fake_llm.stream_calls, "fast_answer should be streamed, not buffered"
    # Planner and research still use the non-streaming API — correct, because
    # their output is not user-facing.
    assert fake_llm.calls


def test_full_route_streams_from_the_provider(client, fake_llm):
    token, _ = register(client)
    project_id = make_project(client, token)

    _orchestra(client, token, project_id, "Compare Redis and Postgres in detail")

    assert fake_llm.stream_calls, "reviewer should be streamed, not buffered"


def test_streamed_tokens_follow_provider_boundaries(client, fake_llm):
    """Not fixed-size slices: the chunk sizes must come from the model."""
    fake_llm.default = "Alpha beta gamma delta epsilon zeta eta theta iota kappa"
    token, _ = register(client)
    project_id = make_project(client, token)

    response = _orchestra(client, token, project_id, "What is my name?")
    tokens = [e["content"] for e in sse_events(response.text) if e["type"] == "token"]

    assert len(tokens) > 1
    # `_chunk_text` produced uniform 24-character pieces. The stub splits into
    # thirds, so a uniform-24 result would mean the old path ran.
    assert not all(len(t) == 24 for t in tokens[:-1])
    assert "".join(tokens) == fake_llm.default


def test_reviewer_notes_never_reach_the_user(client, fake_llm):
    fake_llm.default = (
        "NOTES: the draft buries the conclusion and cites nothing.\n"
        "FINAL: Redis suits ephemeral session data; Postgres suits durable state."
    )
    token, _ = register(client)
    project_id = make_project(client, token)

    response = _orchestra(
        client, token, project_id, "Compare Redis and Postgres in detail"
    )
    events = sse_events(response.text)
    answer = "".join(e["content"] for e in events if e["type"] == "token")

    assert "buries the conclusion" not in answer
    assert "NOTES:" not in answer
    assert "FINAL:" not in answer
    assert answer.strip().startswith("Redis suits ephemeral session data")


def test_reviewer_notes_are_still_reported_as_a_step(client, fake_llm):
    fake_llm.default = "NOTES: tighten the opening.\nFINAL: The answer."
    token, _ = register(client)
    project_id = make_project(client, token)

    response = _orchestra(
        client, token, project_id, "Compare Redis and Postgres in detail"
    )
    notes = [
        e.get("review_notes")
        for e in sse_events(response.text)
        if e.get("type") == "orchestra_step" and e.get("review_notes")
    ]
    assert notes and "tighten the opening" in notes[0]


def test_streamed_answer_is_what_gets_persisted(client, fake_llm):
    fake_llm.default = "NOTES: fine.\nFINAL: The persisted answer."
    token, _ = register(client)
    project_id = make_project(client, token)

    response = _orchestra(
        client, token, project_id, "Compare Redis and Postgres in detail"
    )
    done = sse_events(response.text)[-1]

    messages = client.get(
        f"/api/v1/conversations/{done['conversation_id']}/messages", headers=auth(token)
    ).json()
    assert messages[-1]["content"] == "The persisted answer."

    execution = client.get(
        f"/api/v1/executions/{done['execution_id']}", headers=auth(token)
    ).json()
    assert execution["final_response"] == "The persisted answer."


def test_terminal_stream_failure_falls_back_to_the_draft(client, fake_llm, monkeypatch):
    """Losing the polish step must not lose the whole turn."""
    token, _ = register(client)
    project_id = make_project(client, token)

    def explode(**kwargs):
        raise RuntimeError("provider dropped the stream")
        yield  # pragma: no cover — makes this a generator

    monkeypatch.setattr(fake_llm, "stream_chat_completion", explode)

    response = _orchestra(
        client, token, project_id, "Compare Redis and Postgres in detail"
    )
    assert response.status_code == 200
    events = sse_events(response.text)
    types = [e["type"] for e in events]

    assert "error" not in types
    assert types[-1] == "done"
    answer = "".join(e["content"] for e in events if e["type"] == "token")
    assert answer.strip(), "the writer's draft should still reach the user"


def test_direct_path_records_measured_tokens_when_the_provider_reports_them(client):
    """`stream_options.include_usage` keeps streamed turns off the estimator."""
    token, _ = register(client)
    project_id = make_project(client, token)

    response = client.post(
        "/api/v1/chat",
        json={
            "project_id": project_id,
            "message": "hello",
            "enable_tools": False,
            "enable_orchestra": False,
        },
        headers=auth(token),
    )
    done = sse_events(response.text)[-1]
    execution = client.get(
        f"/api/v1/executions/{done['execution_id']}", headers=auth(token)
    ).json()

    stream_steps = [
        s for s in execution["steps"] if "llm_details" in (s.get("detail") or {})
    ]
    details = [d for s in stream_steps for d in s["detail"]["llm_details"]]
    streamed = [d for d in details if d.get("stream")]
    assert streamed, "the direct path should record a streamed LLM call"
    # The fake fills the usage sink, so this must not be flagged as an estimate.
    assert streamed[0]["estimated"] is False
