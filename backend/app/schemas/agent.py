from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    project_id: int
    description: str | None = None
    system_prompt: str = Field(default="", max_length=20000)
    model_name: str = Field(default="gpt-4o-mini", min_length=1, max_length=100)


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    system_prompt: str | None = Field(default=None, max_length=20000)
    model_name: str | None = Field(default=None, min_length=1, max_length=100)
    project_id: int | None = None


class AgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    system_prompt: str
    model_name: str
    project_id: int
    created_at: datetime
    updated_at: datetime
