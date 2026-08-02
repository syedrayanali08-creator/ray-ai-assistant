"""Domain enumerations (docs/06).

They live outside ``ray.db`` because the API and the agents need to speak about a
task status without importing the database layer (ADR-0012)."""

from enum import StrEnum


class MemoryCategory(StrEnum):
    USER = "user"
    PROJECT = "project"
    LEARNING = "learning"
    GOAL = "goal"
    CONVERSATION = "conversation"


class MemorySource(StrEnum):
    CONVERSATION = "conversation"
    USER = "user"
    TOOL = "tool"


class ProjectStatus(StrEnum):
    PLANNING = "planning"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETE = "complete"
    ARCHIVED = "archived"


class TaskStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"
    CANCELLED = "cancelled"


class TaskPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class EventSource(StrEnum):
    RAY = "ray"
    GOOGLE = "google"
    ICS = "ics"
    NOTION = "notion"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class Modality(StrEnum):
    TEXT = "text"
    VOICE = "voice"


class Proficiency(StrEnum):
    NONE = "none"
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class InvocationStatus(StrEnum):
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    FAILED = "failed"


class PermissionMode(StrEnum):
    ASK = "ask"
    ALWAYS_ALLOW = "always_allow"
    NEVER = "never"


class IntegrationType(StrEnum):
    GITHUB = "github"
    CALENDAR = "calendar"
    KNOWLEDGE = "knowledge"
    FILES = "files"


class IntegrationStatus(StrEnum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
