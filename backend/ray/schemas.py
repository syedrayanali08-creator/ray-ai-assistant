"""API-facing shapes.

These are the boundary between the database and everything else: services return
them, the API serialises them, and the frontend's types are generated from them.
Keeping them free of SQLAlchemy is what lets ``ray.api`` avoid importing
``ray.db.models`` (ADR-0012).
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ray.domain.enums import (
    EventSource,
    MemoryCategory,
    Modality,
    ProjectStatus,
    TaskPriority,
    TaskStatus,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    llm_provider: str
    voice: "VoiceCapabilities"


class VoiceCapabilities(BaseModel):
    """What the client may offer right now.

    The frontend renders its voice controls from this rather than hardcoding a
    phase, so upgrading the backend from browser to local speech needs no frontend
    change (ADR-0009).
    """

    stt_backend: str
    tts_backend: str
    wake_word_enabled: bool
    wake_word_phrase: str = "Ray"


class UserRead(ORMModel):
    id: uuid.UUID
    name: str
    email: str | None
    preferences: dict[str, object]
    settings: dict[str, object]
    created_at: datetime


class ProjectRead(ORMModel):
    id: uuid.UUID
    name: str
    description: str
    status: ProjectStatus
    technology_stack: list[str]
    progress: int | None
    repo_url: str | None
    created_at: datetime
    updated_at: datetime


class TaskRead(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID | None
    title: str
    description: str
    status: TaskStatus
    priority: TaskPriority
    category: str | None
    deadline: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = ""
    project_id: uuid.UUID | None = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    category: str | None = None
    deadline: datetime | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    project_id: uuid.UUID | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    category: str | None = None
    deadline: datetime | None = None


class CalendarEventRead(ORMModel):
    id: uuid.UUID
    title: str
    description: str
    start_time: datetime
    end_time: datetime
    location: str | None
    source: EventSource
    task_id: uuid.UUID | None


class MemoryRead(ORMModel):
    id: uuid.UUID
    category: MemoryCategory
    content: str
    importance: int
    why: str
    hit_count: int
    project_id: uuid.UUID | None
    created_at: datetime


class MessageRead(ORMModel):
    id: uuid.UUID
    role: str
    content: str
    speech_text: str | None
    agent_name: str | None
    trace: dict[str, object] | None
    input_modality: Modality
    created_at: datetime


class AgentRead(BaseModel):
    """An entry in the code-side agent registry, plus its runtime state."""

    name: str
    display_name: str
    description: str
    enabled: bool
    tools: list[str]


HealthResponse.model_rebuild()
