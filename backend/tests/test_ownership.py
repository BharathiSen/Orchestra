"""Ownership isolation.

Every project-scoped resource must be unreachable by anyone but its owner, and
the refusal must be **404, not 403** — a 403 confirms the resource exists, which
leaks the existence of other users' data.

Ownership checks currently live in three services rather than one dependency, so
these tests are the safety net for the class of bug where a new endpoint forgets
the check.
"""

from __future__ import annotations

import pytest

from tests.conftest import auth, make_project, register


@pytest.fixture
def two_users(client):
    owner_token, owner_id = register(client, email="owner@example.com")
    other_token, other_id = register(client, email="intruder@example.com")
    project_id = make_project(client, owner_token, name="Private project")
    return {
        "owner_token": owner_token,
        "owner_id": owner_id,
        "other_token": other_token,
        "other_id": other_id,
        "project_id": project_id,
    }


def test_owner_can_read_own_project(client, two_users):
    response = client.get(
        f"/api/v1/projects/{two_users['project_id']}",
        headers=auth(two_users["owner_token"]),
    )
    assert response.status_code == 200


def test_other_user_gets_404_not_403_for_project(client, two_users):
    response = client.get(
        f"/api/v1/projects/{two_users['project_id']}",
        headers=auth(two_users["other_token"]),
    )
    assert response.status_code == 404, "403 would confirm the project exists"


def test_other_user_cannot_list_projects_of_owner(client, two_users):
    response = client.get("/api/v1/projects", headers=auth(two_users["other_token"]))
    assert response.status_code == 200
    assert response.json() == []


def test_other_user_cannot_delete_project(client, two_users):
    response = client.delete(
        f"/api/v1/projects/{two_users['project_id']}",
        headers=auth(two_users["other_token"]),
    )
    assert response.status_code == 404
    # And the project is still there for its owner.
    assert (
        client.get(
            f"/api/v1/projects/{two_users['project_id']}",
            headers=auth(two_users["owner_token"]),
        ).status_code
        == 200
    )


def test_other_user_cannot_create_agent_in_foreign_project(client, two_users):
    response = client.post(
        "/api/v1/agents",
        json={
            "project_id": two_users["project_id"],
            "name": "Intruder agent",
            "system_prompt": "hello",
        },
        headers=auth(two_users["other_token"]),
    )
    assert response.status_code == 404


def test_other_user_cannot_list_conversations_of_foreign_project(client, two_users):
    response = client.get(
        f"/api/v1/conversations?project_id={two_users['project_id']}",
        headers=auth(two_users["other_token"]),
    )
    assert response.status_code == 404


def test_other_user_cannot_read_foreign_conversation(client, two_users):
    created = client.post(
        "/api/v1/conversations",
        json={"project_id": two_users["project_id"], "title": "Owner thread"},
        headers=auth(two_users["owner_token"]),
    )
    assert created.status_code == 201
    conversation_id = created.json()["id"]

    response = client.get(
        f"/api/v1/conversations/{conversation_id}",
        headers=auth(two_users["other_token"]),
    )
    assert response.status_code == 404


def test_other_user_cannot_create_knowledge_base_in_foreign_project(client, two_users):
    response = client.post(
        "/api/v1/knowledge-bases",
        json={"project_id": two_users["project_id"], "name": "Intruder KB"},
        headers=auth(two_users["other_token"]),
    )
    assert response.status_code == 404


def test_other_user_cannot_read_foreign_dashboard(client, two_users):
    response = client.get(
        f"/api/v1/dashboard/summary?project_id={two_users['project_id']}",
        headers=auth(two_users["other_token"]),
    )
    assert response.status_code == 404


def test_other_user_cannot_list_foreign_executions(client, two_users):
    response = client.get(
        f"/api/v1/executions?project_id={two_users['project_id']}",
        headers=auth(two_users["other_token"]),
    )
    assert response.status_code == 404
