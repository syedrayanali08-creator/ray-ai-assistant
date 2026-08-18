import uuid


class ServiceError(Exception):
    """A service refused an operation for a reason the caller can explain.

    Distinct from a bug: the Tool Manager converts these into a tool result the agent
    can reason about, rather than failing the turn (ADR-0010).
    """


class InvalidEventError(ServiceError):
    """A calendar event that cannot exist, e.g. one that ends before it starts."""


class UnknownProjectError(ServiceError):
    """A task referenced a project that does not exist or belongs to someone else.

    Raised instead of letting the foreign key fail, so the caller gets a 404 rather
    than a 500 — and so a project id from another user is indistinguishable from a
    nonexistent one.
    """

    def __init__(self, project_id: uuid.UUID) -> None:
        super().__init__(f"Project {project_id} not found")
        self.project_id = project_id
