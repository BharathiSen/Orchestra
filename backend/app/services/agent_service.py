from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Agent, KnowledgeBase, Project, User
from app.repositories.agent_repository import AgentRepository
from app.schemas import AgentCreate, AgentUpdate


class AgentService:
    """Business rules for agents — ownership and project validation."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = AgentRepository(db)

    def _get_owned_project(self, *, project_id: int, user: User) -> Project:
        project = self.db.get(Project, project_id)
        if project is None or project.owner_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found",
            )
        return project

    def _get_owned_agent(self, *, agent_id: int, user: User) -> Agent:
        agent = self.repo.get_agent(agent_id)
        if agent is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
        if agent.project.owner_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
        return agent

    def create_agent(self, *, user: User, payload: AgentCreate) -> Agent:
        project = self._get_owned_project(project_id=payload.project_id, user=user)
        knowledge_bases = self._owned_knowledge_bases(
            user=user,
            project_id=project.id,
            knowledge_base_ids=payload.knowledge_base_ids,
        )
        agent = Agent(
            name=payload.name,
            description=payload.description,
            system_prompt=payload.system_prompt,
            model_name=payload.model_name,
            project_id=payload.project_id,
        )
        agent.knowledge_bases = knowledge_bases
        return self.repo.create_agent(agent)

    def list_agents(self, *, user: User, project_id: int | None = None) -> list[Agent]:
        if project_id is not None:
            self._get_owned_project(project_id=project_id, user=user)
        return self.repo.list_agents(owner_id=user.id, project_id=project_id)

    def get_agent(self, *, user: User, agent_id: int) -> Agent:
        return self._get_owned_agent(agent_id=agent_id, user=user)

    def update_agent(self, *, user: User, agent_id: int, payload: AgentUpdate) -> Agent:
        agent = self._get_owned_agent(agent_id=agent_id, user=user)
        data = payload.model_dump(exclude_unset=True)

        if "project_id" in data:
            self._get_owned_project(project_id=data["project_id"], user=user)

        knowledge_base_ids = data.pop("knowledge_base_ids", None)
        if knowledge_base_ids is not None:
            target_project_id = int(data.get("project_id", agent.project_id))
            agent.knowledge_bases = self._owned_knowledge_bases(
                user=user,
                project_id=target_project_id,
                knowledge_base_ids=knowledge_base_ids,
            )

        return self.repo.update_agent(agent, data)

    def delete_agent(self, *, user: User, agent_id: int) -> None:
        agent = self._get_owned_agent(agent_id=agent_id, user=user)
        self.repo.delete_agent(agent)

    def _owned_knowledge_bases(
        self,
        *,
        user: User,
        project_id: int,
        knowledge_base_ids: list[int],
    ) -> list[KnowledgeBase]:
        if not knowledge_base_ids:
            return []
        unique_ids = list(dict.fromkeys(knowledge_base_ids))
        rows = (
            self.db.query(KnowledgeBase)
            .filter(
                KnowledgeBase.id.in_(unique_ids),  # type: ignore[attr-defined]
                KnowledgeBase.project_id == project_id,
            )
            .all()
        )
        if len(rows) != len(unique_ids):
            # Also ensure project ownership for consistency with agent ownership rules.
            self._get_owned_project(project_id=project_id, user=user)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or more knowledge bases not found",
            )
        return rows
