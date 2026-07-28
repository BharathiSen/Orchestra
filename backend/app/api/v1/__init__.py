from fastapi import APIRouter

from app.api.v1 import agents, auth, chat, projects
from app.knowledge.router import router as knowledge_router

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(projects.router)
api_router.include_router(agents.router)
api_router.include_router(chat.router)
api_router.include_router(knowledge_router)
