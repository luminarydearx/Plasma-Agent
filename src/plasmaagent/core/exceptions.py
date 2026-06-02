"""Custom exceptions for PlasmaAgent."""

from typing import Optional


class PlasmaAgentError(Exception):
    """Base exception for all PlasmaAgent errors."""

    pass


class ConfigurationError(PlasmaAgentError):
    """Raised when configuration is invalid or missing."""

    pass


class DatabaseError(PlasmaAgentError):
    """Raised when database operations fail."""

    pass


class ConnectionError(DatabaseError):
    """Raised when database connection fails."""

    pass


class InvalidStateTransitionError(PlasmaAgentError):
    """Raised when attempting an invalid state transition."""

    def __init__(self, current_state: str, target_state: str, task_id: str):
        self.current_state = current_state
        self.target_state = target_state
        self.task_id = task_id
        message = (
            f"Invalid state transition for task {task_id}: "
            f"{current_state} -> {target_state}"
        )
        super().__init__(message)


class TaskNotFoundError(PlasmaAgentError):
    """Raised when a task is not found."""

    def __init__(self, task_id: str):
        self.task_id = task_id
        message = f"Task not found: {task_id}"
        super().__init__(message)


class TaskLockedError(PlasmaAgentError):
    """Raised when a task is locked by another process."""

    def __init__(self, task_id: str):
        self.task_id = task_id
        message = f"Task is locked by another process: {task_id}"
        super().__init__(message)


class ExecutionError(PlasmaAgentError):
    """Raised when task execution fails."""

    def __init__(self, task_id: str, step_id: Optional[str] = None, message: str = ""):
        self.task_id = task_id
        self.step_id = step_id
        error_message = f"Execution failed for task {task_id}"
        if step_id:
            error_message += f", step {step_id}"
        if message:
            error_message += f": {message}"
        super().__init__(error_message)


class ValidationError(PlasmaAgentError):
    """Raised when validation fails."""

    pass
