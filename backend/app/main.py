from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1 import api_router
from app.core.config import settings
from app.core.database import Base, engine
from app.core.redis_client import get_redis
from app import models  # noqa: F401


@asynccontextmanager
async def lifespan(_: FastAPI):
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        # create_all does not add new columns to existing tables
        conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS trace JSON"))
    Base.metadata.create_all(bind=engine)
    redis = get_redis()
    try:
        redis.ping()
    except Exception:
        # Redis is provisioned for later memory/sessions; not required for Day 1–2 CRUD.
        pass
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
