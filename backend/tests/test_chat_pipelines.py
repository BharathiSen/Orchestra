"""End-to-end chat: SSE contract, pipeline selection, and execution recording.

These are the tests that exercise the thing the project is actually about — a
turn goes in, an SSE stream comes out, and a durable execution record is left
behind. The LLM is a stub, so nothing here asserts answer *quality*; it asserts
that the machinery around the model does what the README says it does.
"""

from __future__ import annotations

from tests.conftest import auth, event_types, make_project, register, sse_events


def _chat(client, token, project_id, message="Hello there", **overrides):
    payload = {
        "project_id": project_id,
        "message": message,
        "model": "llama-3.1-8b-instant",
        "enable_tools": False,
        "enable_orchestra": False,
    }
    payload.update(overrides)
    return client.post("/api/v1/chat", json=payload, headers=auth(token))


def test_direct_chat_emits_the_documented_event_sequence(client):
    token, _ = register(client)
    project_id = make_project(client, token)

    response = _chat(client, token, project_id)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    # SSE must never be compressed — a streaming compressor withholds bytes and
    # looks identical to a hung request.
    assert "content-encoding" not in response.headers

    types = event_types(response.text)
    assert types[0] == "meta"
    for expected in ("user_message", "execution_meta", "token", "done"):
        assert expected in types, f"missing {expected!r} in {types}"
    assert types[-1] == "done"
    # `meta` carries the conversation id before anything else can need it.
    assert sse_events(response.text)[0]["conversation_id"] > 0


def test_direct_path_streams_from_the_provider(client, fake_llm):
    """The direct path must use the streaming API, not build-then-slice."""
    token, _ = register(client)
    project_id = make_project(client, token)

    _chat(client, token, project_id)

    assert fake_llm.stream_calls, "direct path should call stream_chat_completion"
    assert not fake_llm.calls, "direct path should not use the non-streaming API"


def test_chat_persists_both_messages_and_completes_the_execution(client):
    token, _ = register(client)
    project_id = make_project(client, token)

    response = _chat(client, token, project_id, message="Remember this turn")
    done = sse_events(response.text)[-1]
    conversation_id = done["conversation_id"]

    messages = client.get(
        f"/api/v1/conversations/{conversation_id}/messages", headers=auth(token)
    ).json()
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "Remember this turn"
    assert messages[1]["content"].strip()

    execution = client.get(
        f"/api/v1/executions/{done['execution_id']}", headers=auth(token)
    ).json()
    assert execution["status"] == "completed"
    assert execution["success"] is True
    assert execution["pipeline"] == "direct"
    assert execution["total_tokens"] > 0
    assert execution["steps"], "an execution must record its steps"


def test_tools_pipeline_runs_the_graph_and_labels_the_execution(client):
    token, _ = register(client)
    project_id = make_project(client, token)

    response = _chat(
        client, token, project_id, message="What is 12 * 12?", enable_tools=True
    )
    types = event_types(response.text)
    assert "graph_step" in types

    nodes = {e.get("node") for e in sse_events(response.text) if e.get("type") == "graph_step"}
    assert {"planner", "tool", "reviewer", "answer"} <= nodes

    done = sse_events(response.text)[-1]
    execution = client.get(
        f"/api/v1/executions/{done['execution_id']}", headers=auth(token)
    ).json()
    assert execution["pipeline"] == "tools"


def test_orchestra_pipeline_emits_agent_steps_and_records_the_route(client):
    token, _ = register(client)
    project_id = make_project(client, token)

    response = _chat(
        client,
        token,
        project_id,
        message="Compare Redis and Postgres for session storage in detail",
        enable_orchestra=True,
    )
    events = sse_events(response.text)
    agents = {e.get("agent") for e in events if e.get("type") == "orchestra_step"}
    assert {"planner", "research", "writer", "reviewer"} <= agents

    done = events[-1]
    execution = client.get(
        f"/api/v1/executions/{done['execution_id']}", headers=auth(token)
    ).json()
    # A comparison prompt must take the full route.
    assert execution["pipeline"] == "orchestra_full"


def test_orchestra_simple_route_skips_writer_and_reviewer(client):
    token, _ = register(client)
    project_id = make_project(client, token)

    response = _chat(
        client, token, project_id, message="What is my name?", enable_orchestra=True
    )
    events = sse_events(response.text)
    done = events[-1]
    execution = client.get(
        f"/api/v1/executions/{done['execution_id']}", headers=auth(token)
    ).json()
    assert execution["pipeline"] == "orchestra_simple"

    step_names = {step["step_name"] for step in execution["steps"]}
    assert "fast_answer" in step_names
    assert "writer" not in step_names


def test_orchestra_takes_precedence_over_tools(client):
    """Both flags set: Orchestra owns the multi-agent path."""
    token, _ = register(client)
    project_id = make_project(client, token)

    response = _chat(
        client,
        token,
        project_id,
        message="Write a detailed comparison of two databases",
        enable_tools=True,
        enable_orchestra=True,
    )
    types = event_types(response.text)
    assert "orchestra_step" in types
    assert "graph_step" not in types


def test_failed_turn_still_records_an_execution(client, fake_llm):
    """A trace that only exists on success is not observability."""
    token, _ = register(client)
    project_id = make_project(client, token)
    fake_llm.raise_on_call = RuntimeError("provider exploded")

    response = _chat(client, token, project_id)
    events = sse_events(response.text)
    assert events[-1]["type"] == "error"

    execution_id = next(e["execution_id"] for e in events if e.get("type") == "execution_meta")
    execution = client.get(
        f"/api/v1/executions/{execution_id}", headers=auth(token)
    ).json()
    assert execution["status"] == "error"
    assert execution["success"] is False
    assert "provider exploded" in (execution["error_detail"] or "")


def test_chat_rejects_conversation_from_another_project(client):
    token, _ = register(client)
    project_a = make_project(client, token, name="A")
    project_b = make_project(client, token, name="B")

    created = client.post(
        "/api/v1/conversations",
        json={"project_id": project_a, "title": "Thread in A"},
        headers=auth(token),
    )
    conversation_id = created.json()["id"]

    response = _chat(client, token, project_b, conversation_id=conversation_id)
    assert response.status_code == 400


def test_chat_rejects_foreign_project(client):
    owner_token, _ = register(client, email="owner@example.com")
    other_token, _ = register(client, email="other@example.com")
    project_id = make_project(client, owner_token)

    assert _chat(client, other_token, project_id).status_code == 404


def test_chat_requires_authentication(client):
    token, _ = register(client)
    project_id = make_project(client, token)
    response = client.post(
        "/api/v1/chat", json={"project_id": project_id, "message": "hi"}
    )
    assert response.status_code == 401


def test_agent_system_prompt_reaches_the_model(client, fake_llm):
    token, _ = register(client)
    project_id = make_project(client, token)
    agent = client.post(
        "/api/v1/agents",
        json={
            "project_id": project_id,
            "name": "Terse agent",
            "system_prompt": "ALWAYS-ANSWER-IN-HAIKU",
        },
        headers=auth(token),
    ).json()

    _chat(client, token, project_id, agent_id=agent["id"])

    system_messages = [
        m for m in fake_llm.all_messages() if m.get("role") == "system"
    ]
    assert any("ALWAYS-ANSWER-IN-HAIKU" in str(m["content"]) for m in system_messages)


def test_execution_appears_in_history_and_dashboard(client):
    token, _ = register(client)
    project_id = make_project(client, token)
    _chat(client, token, project_id, message="dashboard please")

    listing = client.get(
        f"/api/v1/executions?project_id={project_id}", headers=auth(token)
    ).json()
    assert len(listing) == 1

    filtered = client.get(
        f"/api/v1/executions?project_id={project_id}&q=dashboard", headers=auth(token)
    ).json()
    assert len(filtered) == 1

    missing = client.get(
        f"/api/v1/executions?project_id={project_id}&q=nothing-matches-this",
        headers=auth(token),
    ).json()
    assert missing == []

    summary = client.get(
        f"/api/v1/dashboard/summary?project_id={project_id}", headers=auth(token)
    ).json()
    assert summary["executions_today"] == 1
    assert summary["success_rate"] == 100.0  # reported as a percentage


def test_finished_chat_returns_its_database_connection(client):
    """Regression: streaming turns used to leak a connection per request.

    `Depends(get_db)` is torn down with the request/response cycle, but a
    `StreamingResponse` body is consumed *after* the handler returns — so the
    session outlived its teardown and was released only when Python happened to
    garbage-collect it. On PostgreSQL those connections sat `idle in transaction`
    holding locks. The route now owns the session and closes it in the stream's
    `finally`.
    """
    from app.core import database

    token, _ = register(client)
    project_id = make_project(client, token)

    pool = database.engine.pool
    _chat(client, token, project_id, message="warm the pool")
    baseline = pool.checkedout()

    for i in range(6):
        assert _chat(client, token, project_id, message=f"turn {i}").status_code == 200

    assert pool.checkedout() <= baseline, (
        f"connections leaked: {baseline} before, {pool.checkedout()} after six turns"
    )


def test_rejected_chat_returns_its_database_connection(client):
    """The early-exit paths must not leak either."""
    from app.core import database

    owner_token, _ = register(client, email="owner@example.com")
    other_token, _ = register(client, email="other@example.com")
    project_id = make_project(client, owner_token)

    pool = database.engine.pool
    _chat(client, other_token, project_id)
    baseline = pool.checkedout()

    for _ in range(6):
        assert _chat(client, other_token, project_id).status_code == 404

    assert pool.checkedout() <= baseline


def test_abandoned_stream_releases_slot_and_connection(client, fake_redis):
    """A client that disconnects mid-answer must not leak anything.

    Closing the response early makes Starlette close the generator, which raises
    `GeneratorExit` inside it. The `finally` in `_stream_with_cleanup` is what
    turns that into a released concurrency slot and a closed session — without
    it, a user who navigates away mid-answer would burn a slot until the 15
    minute TTL and strand a connection until garbage collection.
    """
    from app.core import database

    token, user_id = register(client)
    project_id = make_project(client, token)

    # One completed turn first, so the pool has warmed and the baseline is real.
    _chat(client, token, project_id, message="warm up")
    baseline = database.engine.pool.checkedout()

    for i in range(4):
        with client.stream(
            "POST",
            "/api/v1/chat",
            json={
                "project_id": project_id,
                "message": f"abandon {i}",
                "enable_tools": False,
                "enable_orchestra": False,
            },
            headers=auth(token),
        ) as response:
            assert response.status_code == 200
            # Consume a single event, then walk away.
            for _ in response.iter_lines():
                break

    assert database.engine.pool.checkedout() <= baseline, "abandoned stream leaked a connection"
    active = fake_redis.get(f"orchestra:rl:streams:{user_id}")
    assert active in (None, 0, "0"), f"abandoned stream leaked a concurrency slot: {active}"

    # And the account is still usable — the point of releasing the slot.
    assert _chat(client, token, project_id, message="after").status_code == 200


def test_agent_retrieves_only_from_its_own_knowledge_bases(client, monkeypatch):
    """Knowledge-base isolation at the wiring level, without needing pgvector.

    `test_retrieval.py` proves the SQL filters by knowledge base. This proves the
    chat path passes the *right* ids — an agent must never be able to retrieve
    from a knowledge base it is not attached to, even one in the same project.
    """
    token, _ = register(client)
    project_id = make_project(client, token)

    def make_kb(name: str) -> int:
        response = client.post(
            "/api/v1/knowledge-bases",
            json={"project_id": project_id, "name": name},
            headers=auth(token),
        )
        assert response.status_code == 201, response.text
        return response.json()["id"]

    attached, unattached = make_kb("Attached KB"), make_kb("Unattached KB")

    agent = client.post(
        "/api/v1/agents",
        json={
            "project_id": project_id,
            "name": "Scoped agent",
            "system_prompt": "You answer from your own documents.",
            "knowledge_base_ids": [attached],
        },
        headers=auth(token),
    ).json()

    seen: list[list[int]] = []

    def spy(self, *, question, knowledge_base_ids, top_k=5):
        seen.append(list(knowledge_base_ids))
        return []

    monkeypatch.setattr("app.rag.service.RagService.retrieve_chunks_for_question", spy)

    _chat(client, token, project_id, message="What do my docs say?", agent_id=agent["id"])

    assert seen, "an agent with a knowledge base should trigger retrieval"
    requested = {kb_id for call in seen for kb_id in call}
    assert requested == {attached}
    assert unattached not in requested


def test_agent_without_knowledge_bases_skips_retrieval(client, monkeypatch):
    token, _ = register(client)
    project_id = make_project(client, token)
    agent = client.post(
        "/api/v1/agents",
        json={"project_id": project_id, "name": "Bare agent", "system_prompt": "Hi."},
        headers=auth(token),
    ).json()

    called = []
    monkeypatch.setattr(
        "app.rag.service.RagService.retrieve_chunks_for_question",
        lambda self, **kw: called.append(kw) or [],
    )

    response = _chat(client, token, project_id, agent_id=agent["id"])
    assert response.status_code == 200
    assert called == [], "no knowledge base means no retrieval query at all"
    assert "retrieved_context" not in event_types(response.text)


def test_replay_returns_the_original_prompt_and_flags(client):
    token, _ = register(client)
    project_id = make_project(client, token)
    response = _chat(
        client, token, project_id, message="replay me", enable_orchestra=True
    )
    execution_id = sse_events(response.text)[-1]["execution_id"]

    replay = client.post(
        f"/api/v1/executions/{execution_id}/replay", headers=auth(token)
    ).json()
    assert replay["prompt"] == "replay me"
    assert replay["enable_orchestra"] is True
    assert replay["enable_tools"] is False
