import uuid


class RayError(Exception):
    """Base for every error Ray raises on purpose.

    A numeric code keeps the UI from parsing English messages, and a category keeps
    logs and diagnostics readable (docs/12, docs/13).
    """

    code = "ray_error"
    status_code = 500

    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ServiceError(RayError):
    """A service refused an operation for a reason the caller can explain.

    Distinct from a bug: the Tool Manager converts these into a tool result the agent
    can reason about, rather than failing the turn (ADR-0010).
    """

    code = "service_error"
    status_code = 400


class InvalidEventError(ServiceError):
    """A calendar event that cannot exist, e.g. one that ends before it starts."""

    code = "invalid_event"
    status_code = 422


class UnknownProjectError(ServiceError):
    """A task referenced a project that does not exist or belongs to someone else.

    Raised instead of letting the foreign key fail, so the caller gets a 404 rather
    than a 500 — and so a project id from another user is indistinguishable from a
    nonexistent one.
    """

    code = "unknown_project"
    status_code = 404

    def __init__(self, project_id: uuid.UUID) -> None:
        super().__init__(f"Project {project_id} not found")
        self.project_id = project_id


class ConfigError(RayError):
    """A setting is missing, malformed, or inconsistent."""

    code = "config_error"
    status_code = 500


class IntegrationError(RayError):
    """An external adapter failed or is misconfigured."""

    code = "integration_error"
    status_code = 502


class ModelError(RayError):
    """The LLM provider is unreachable, misconfigured, or returned something unusable."""

    code = "model_error"
    status_code = 503


class SecurityError(RayError):
    """A request or operation failed a security check."""

    code = "security_error"
    status_code = 403


class UserError(RayError):
    """The user asked for something impossible or malformed."""

    code = "user_error"
    status_code = 400
