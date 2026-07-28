from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeBaseCreate(BaseModel):
    project_id: int
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None


class KnowledgeBaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    document_count: int = 0


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    knowledge_base_id: int
    filename: str
    content_type: str | None
    status: str
    chunk_count: int
    embedding_status: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class ChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    chunk_index: int
    content: str
    metadata: dict | None = None
    created_at: datetime
