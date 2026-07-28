from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Agent, Project


class AgentRepository:
    """Database operations for agents only — no business rules."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_agent(self, agent: Agent) -> Agent:
        self.db.add(agent)
        self.db.commit()
        self.db.refresh(agent)
        return agent

    def get_agent(self, agent_id: int) -> Agent | None:
        return (
            self.db.query(Agent)
            .options(joinedload(Agent.project), joinedload(Agent.knowledge_bases))
            .filter(Agent.id == agent_id)
            .first()
        )

    def list_agents(self, *, owner_id: int, project_id: int | None = None) -> list[Agent]:
        stmt = (
            select(Agent)
            .options(joinedload(Agent.knowledge_bases))
            .join(Project, Agent.project_id == Project.id)
            .where(Project.owner_id == owner_id)
            .order_by(Agent.created_at.desc())
        )
        if project_id is not None:
            stmt = stmt.where(Agent.project_id == project_id)
        return list(self.db.scalars(stmt).all())

    def update_agent(self, agent: Agent, data: dict) -> Agent:
        for key, value in data.items():
            setattr(agent, key, value)
        self.db.add(agent)
        self.db.commit()
        self.db.refresh(agent)
        return agent

    def delete_agent(self, agent: Agent) -> None:
        self.db.delete(agent)
        self.db.commit()
