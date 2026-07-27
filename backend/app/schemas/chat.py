from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConversationCreate(BaseModel):
    project_id: int
    title: str = Field(default="New conversation", min_length=1, max_length=255)
    agent_id: int | None = None
    model_name: str = Field(default="gemini-2.0-flash", min_length=1, max_length=100)


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    model_name: str | None = Field(default=None, min_length=1, max_length=100)
    agent_id: int | None = None


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    agent_id: int | None
    title: str
    model_name: str
    created_at: datetime
    updated_at: datetime


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    role: str
    content: str
    created_at: datetime


class ChatRequest(BaseModel):
    project_id: int
    message: str = Field(min_length=1, max_length=50000)
    conversation_id: int | None = None
    agent_id: int | None = None
    model: str = Field(default="llama-3.1-8b-instant", min_length=1, max_length=100)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    system_prompt: str | None = Field(default=None, max_length=20000)


class ModelInfo(BaseModel):
    id: str
    label: str
    description: str


class ModelsResponse(BaseModel):
    models: list[ModelInfo]
    gemini_configured: bool = False  # legacy alias of llm_configured
    llm_configured: bool = False
    provider: str = "groq"
