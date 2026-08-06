"""Seed a shared demo workspace.

A public demo whose dashboard reads "0 executions" sells nothing, so this
populates enough history for every screen to have something to show: a user, a
project, two agents, a small knowledge base, and a spread of executions with
realistic pipelines, latencies, token counts, and costs.

Idempotent — it keys off the demo email and updates in place, so it is safe to
run on every deploy.

    cd backend
    python scripts/seed_demo.py
    python scripts/seed_demo.py --email demo@example.com --password 'strong-pass'
    python scripts/seed_demo.py --reset          # rebuild the workspace contents
    python scripts/seed_demo.py --skip-embeddings

``--skip-embeddings`` avoids downloading the embedding model (a few hundred MB
on first use). The knowledge base is still created; its chunks simply carry no
vectors, so retrieval will not return them.
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Allow `python scripts/seed_demo.py` from the backend directory: Python puts
# this file's directory on sys.path, not the working directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.evaluation.cost import calculate_cost_usd  # noqa: E402
from app.models import (  # noqa: E402
    Agent,
    Conversation,
    Document,
    DocumentChunk,
    Execution,
    ExecutionStep,
    KnowledgeBase,
    Message,
    Project,
    User,
)

DEFAULT_EMAIL = "demo@orchestra.dev"
DEFAULT_PASSWORD = "orchestra-demo"
DEFAULT_MODEL = "llama-3.1-8b-instant"

PROJECT_NAME = "Support Copilot"
PROJECT_DESCRIPTION = (
    "A customer-support assistant grounded in the product handbook. "
    "Demonstrates multi-agent routing, retrieval, and full execution tracing."
)

AGENTS = [
    {
        "name": "Support Specialist",
        "description": "Answers product questions using the handbook knowledge base.",
        "system_prompt": (
            "You are a customer support specialist. Answer using the provided "
            "handbook excerpts. If the handbook does not cover something, say so "
            "plainly instead of guessing, and suggest what the customer should ask next."
        ),
        "attach_knowledge_base": True,
    },
    {
        "name": "Release Notes Writer",
        "description": "Turns terse changelog entries into customer-facing notes.",
        "system_prompt": (
            "You turn engineering changelog entries into clear release notes for "
            "non-technical readers. Lead with the user-visible benefit, keep each "
            "entry to two sentences, and never invent features that are not listed."
        ),
        "attach_knowledge_base": False,
    },
]

KNOWLEDGE_BASE_NAME = "Product Handbook"

# Short, self-contained passages so retrieval has something meaningful to match
# without shipping a large fixture document.
HANDBOOK_CHUNKS = [
    "Refund policy: customers may request a full refund within 30 days of purchase. "
    "Refunds are issued to the original payment method and settle in 5 to 10 business "
    "days. Annual plans cancelled after 30 days are prorated to the end of the term.",
    "Supported plans: Starter includes one project and 5,000 monthly requests. Team "
    "adds unlimited projects, shared workspaces, and 100,000 monthly requests. "
    "Enterprise adds SSO, audit logs, and a dedicated support channel.",
    "Data retention: execution traces are retained for 90 days on Starter and Team, "
    "and 365 days on Enterprise. Uploaded documents are retained until deleted. "
    "Deleting a project permanently removes its traces and documents within 24 hours.",
    "Escalation path: contact support first through the in-app channel. If an issue "
    "is unresolved after two business days, it escalates to a support engineer. "
    "Production outages on Enterprise escalate immediately and are acknowledged "
    "within one hour.",
]

# Prompts paired with the pipeline each one exercises, so the seeded history
# mirrors what the router would actually choose.
DEMO_TURNS = [
    ("What is the refund window for an annual plan?", "orchestra_simple"),
    ("Compare the Team and Enterprise plans for a 40-person company.", "orchestra_full"),
    ("How long are execution traces retained?", "orchestra_simple"),
    ("What is 847 * 23?", "tools"),
    ("Draft release notes for: added SSO, fixed trace pagination.", "orchestra_full"),
    ("Who do I contact about a production outage?", "orchestra_simple"),
    ("Summarize the data retention policy for a customer email.", "orchestra_full"),
    ("What's the weather in Chennai?", "tools"),
    ("Does the Starter plan include shared workspaces?", "orchestra_simple"),
    ("Write a support macro for refund requests outside 30 days.", "orchestra_full"),
    ("How many monthly requests does Team include?", "orchestra_simple"),
    ("Explain our escalation path to a new support hire.", "orchestra_full"),
    ("What is 15% of 2400?", "tools"),
    ("Is audit logging available on Team?", "orchestra_simple"),
    ("Compare our retention policy against a 1-year requirement.", "orchestra_full"),
    ("When are refunds settled?", "orchestra_simple"),
    ("Rewrite the refund policy in plainer language.", "orchestra_full"),
    ("Do annual plans get prorated?", "orchestra_simple"),
    ("Draft a note explaining the 90-day trace retention.", "orchestra_full"),
    ("What happens 24 hours after deleting a project?", "direct"),
]

PIPELINE_STEPS = {
    "orchestra_simple": ["planner", "research", "fast_answer"],
    "orchestra_full": ["planner", "research", "writer", "reviewer"],
    "tools": ["planner", "tool", "reviewer", "answer"],
    "direct": ["retrieve", "generate"],
}

DEMO_RESPONSE = (
    "Based on the product handbook, here is the answer along with the section it "
    "came from. Open this execution in Observability to see the retrieved chunks, "
    "the agents that ran, and the token and cost breakdown for each step."
)


def _get_or_create_user(db: Session, *, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(
            email=email,
            hashed_password=hash_password(password),
            full_name="Demo User",
        )
        db.add(user)
        db.flush()
        print(f"  created user {email}")
        return user

    # Keep the password in sync so a rotated demo credential takes effect.
    user.hashed_password = hash_password(password)
    print(f"  reusing user {email}")
    return user


def _reset_workspace(db: Session, project: Project) -> None:
    """Delete seeded content for this project so the run rebuilds it cleanly."""
    for execution in db.scalars(
        select(Execution).where(Execution.project_id == project.id)
    ).all():
        db.delete(execution)
    for conversation in db.scalars(
        select(Conversation).where(Conversation.project_id == project.id)
    ).all():
        db.delete(conversation)
    for agent in db.scalars(select(Agent).where(Agent.project_id == project.id)).all():
        db.delete(agent)
    for kb in db.scalars(
        select(KnowledgeBase).where(KnowledgeBase.project_id == project.id)
    ).all():
        db.delete(kb)
    db.flush()
    print("  reset existing workspace contents")


def _get_or_create_project(db: Session, *, user: User, reset: bool) -> Project:
    project = db.scalar(
        select(Project).where(Project.owner_id == user.id, Project.name == PROJECT_NAME)
    )
    if project is None:
        project = Project(
            name=PROJECT_NAME,
            description=PROJECT_DESCRIPTION,
            owner_id=user.id,
        )
        db.add(project)
        db.flush()
        print(f"  created project '{PROJECT_NAME}'")
        return project

    print(f"  reusing project '{PROJECT_NAME}'")
    if reset:
        _reset_workspace(db, project)
    return project


def _seed_knowledge_base(
    db: Session,
    *,
    project: Project,
    skip_embeddings: bool,
) -> KnowledgeBase:
    kb = db.scalar(
        select(KnowledgeBase).where(
            KnowledgeBase.project_id == project.id,
            KnowledgeBase.name == KNOWLEDGE_BASE_NAME,
        )
    )
    if kb is not None:
        print(f"  reusing knowledge base '{KNOWLEDGE_BASE_NAME}'")
        return kb

    kb = KnowledgeBase(
        project_id=project.id,
        name=KNOWLEDGE_BASE_NAME,
        description="Policies and plan details used to ground support answers.",
    )
    db.add(kb)
    db.flush()

    document = Document(
        knowledge_base_id=kb.id,
        filename="product-handbook.txt",
        content_type="text/plain",
        file_path=None,
        status="processed",
        chunk_count=len(HANDBOOK_CHUNKS),
        embedding_status="skipped" if skip_embeddings else "generated",
    )
    db.add(document)
    db.flush()

    embeddings: list[list[float] | None] = [None] * len(HANDBOOK_CHUNKS)
    if not skip_embeddings:
        print("  generating embeddings (first run downloads the model)...")
        from app.knowledge.embedding import embed_texts

        embeddings = list(embed_texts(HANDBOOK_CHUNKS))

    for index, (content, embedding) in enumerate(zip(HANDBOOK_CHUNKS, embeddings, strict=True)):
        db.add(
            DocumentChunk(
                document_id=document.id,
                chunk_index=index,
                content=content,
                chunk_metadata={"source": "product-handbook.txt", "seeded": True},
                embedding=embedding,
            )
        )

    db.flush()
    state = "without embeddings" if skip_embeddings else "with embeddings"
    print(f"  created knowledge base with {len(HANDBOOK_CHUNKS)} chunks ({state})")
    return kb


def _seed_agents(db: Session, *, project: Project, kb: KnowledgeBase) -> list[Agent]:
    agents: list[Agent] = []
    for spec in AGENTS:
        agent = db.scalar(
            select(Agent).where(Agent.project_id == project.id, Agent.name == spec["name"])
        )
        if agent is None:
            agent = Agent(
                project_id=project.id,
                name=spec["name"],
                description=spec["description"],
                system_prompt=spec["system_prompt"],
                model_name=DEFAULT_MODEL,
            )
            db.add(agent)
            db.flush()
            print(f"  created agent '{spec['name']}'")
        if spec["attach_knowledge_base"] and kb not in agent.knowledge_bases:
            agent.knowledge_bases.append(kb)
        agents.append(agent)
    db.flush()
    return agents


def _seed_executions(
    db: Session,
    *,
    user: User,
    project: Project,
    agent: Agent,
    rng: random.Random,
) -> int:
    existing = db.scalar(
        select(Execution).where(Execution.project_id == project.id).limit(1)
    )
    if existing is not None:
        print("  executions already present, skipping")
        return 0

    conversation = Conversation(
        project_id=project.id,
        agent_id=agent.id,
        title="Demo support questions",
        model_name=DEFAULT_MODEL,
    )
    db.add(conversation)
    db.flush()

    now = datetime.now(UTC)
    created = 0

    for index, (prompt, pipeline) in enumerate(DEMO_TURNS):
        # Spread across ~20 hours so the 24h dashboard window is populated and
        # the history reads as steady use rather than one burst.
        started_at = now - timedelta(minutes=(len(DEMO_TURNS) - index) * 61)

        # Two deliberate failures: a success rate of exactly 100% looks seeded,
        # and it leaves the error state in the UI untested.
        failed = index in {6, 15}

        step_names = PIPELINE_STEPS[pipeline]
        step_latencies = [rng.randint(120, 1400) for _ in step_names]
        latency_ms = sum(step_latencies)

        input_tokens = rng.randint(320, 1800)
        output_tokens = 0 if failed else rng.randint(120, 900)
        total_tokens = input_tokens + output_tokens
        cost = calculate_cost_usd(
            model=DEFAULT_MODEL,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        user_message = Message(
            conversation_id=conversation.id,
            role="user",
            content=prompt,
            created_at=started_at,
        )
        db.add(user_message)
        db.flush()

        assistant_message = None
        if not failed:
            assistant_message = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=DEMO_RESPONSE,
                created_at=started_at + timedelta(milliseconds=latency_ms),
            )
            db.add(assistant_message)
            db.flush()

        execution = Execution(
            user_id=user.id,
            project_id=project.id,
            conversation_id=conversation.id,
            agent_id=agent.id,
            message_id=assistant_message.id if assistant_message else None,
            status="error" if failed else "completed",
            pipeline=pipeline,
            model_name=DEFAULT_MODEL,
            prompt=prompt,
            final_response=None if failed else DEMO_RESPONSE,
            error_detail="Upstream provider timed out after 30s" if failed else None,
            started_at=started_at,
            completed_at=started_at + timedelta(milliseconds=latency_ms),
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            api_calls=len(step_names),
            total_cost_usd=cost,
            success=not failed,
            user_rating=rng.choice([None, 4, 5, 5]) if not failed else None,
            snapshot={
                "system_prompt": agent.system_prompt,
                "route": pipeline.removeprefix("orchestra_") if "_" in pipeline else None,
                "seeded": True,
            },
            scores=None
            if failed
            else {
                "correctness": round(rng.uniform(0.62, 0.94), 3),
                "relevance": round(rng.uniform(0.58, 0.95), 3),
                "groundedness": round(rng.uniform(0.45, 0.9), 3),
                "hallucination_risk": round(rng.uniform(0.05, 0.35), 3),
                "latency_ok": latency_ms < 15000,
                "notes": "Heuristic scores (no LLM judge)",
            },
        )
        db.add(execution)
        db.flush()

        offset_ms = 0
        for sequence, (step_name, step_latency) in enumerate(
            zip(step_names, step_latencies, strict=True)
        ):
            step_failed = failed and sequence == len(step_names) - 1
            step_input = input_tokens // len(step_names)
            step_output = 0 if step_failed else output_tokens // len(step_names)
            db.add(
                ExecutionStep(
                    execution_id=execution.id,
                    sequence=sequence,
                    step_name=step_name,
                    status="error" if step_failed else "done",
                    latency_ms=step_latency,
                    input_tokens=step_input,
                    output_tokens=step_output,
                    tokens=step_input + step_output,
                    cost_usd=calculate_cost_usd(
                        model=DEFAULT_MODEL,
                        input_tokens=step_input,
                        output_tokens=step_output,
                    ),
                    detail={"seeded": True},
                    started_at=started_at + timedelta(milliseconds=offset_ms),
                    completed_at=started_at + timedelta(milliseconds=offset_ms + step_latency),
                )
            )
            offset_ms += step_latency

        created += 1

    db.flush()
    print(f"  created {created} executions across {len(PIPELINE_STEPS)} pipelines")
    return created


def seed(*, email: str, password: str, reset: bool, skip_embeddings: bool) -> None:
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        print("Seeding demo workspace...")
        user = _get_or_create_user(db, email=email, password=password)
        project = _get_or_create_project(db, user=user, reset=reset)
        kb = _seed_knowledge_base(db, project=project, skip_embeddings=skip_embeddings)
        agents = _seed_agents(db, project=project, kb=kb)
        # Fixed seed keeps the demo numbers stable across reseeds.
        _seed_executions(
            db,
            user=user,
            project=project,
            agent=agents[0],
            rng=random.Random(20260806),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print("\nDemo workspace ready.")
    print(f"  email:    {email}")
    print(f"  password: {password}")
    print("\nSet DEMO_EMAIL on the backend and NEXT_PUBLIC_DEMO_EMAIL /")
    print("NEXT_PUBLIC_DEMO_PASSWORD on the frontend to surface the demo button.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the Orchestra demo workspace.")
    parser.add_argument("--email", default=DEFAULT_EMAIL, help="Demo account email.")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Demo account password.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete the demo project's agents, knowledge bases, and executions first.",
    )
    parser.add_argument(
        "--skip-embeddings",
        action="store_true",
        help="Create knowledge base chunks without vectors (avoids the model download).",
    )
    args = parser.parse_args()

    seed(
        email=args.email.strip().lower(),
        password=args.password,
        reset=args.reset,
        skip_embeddings=args.skip_embeddings,
    )


if __name__ == "__main__":
    main()
