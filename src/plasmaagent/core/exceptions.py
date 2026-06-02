from typing import Optional


class PlasmaAgentError(Exception):
    pass


class ConfigurationError(PlasmaAgentError):
    pass


class DatabaseError(PlasmaAgentError):
    pass


class ConnectionError(DatabaseError):
    pass


class InvalidStateTransitionError(PlasmaAgentError):
    def __init__(self, current_state: str, target_state: str, task_id: str) -> None:
        self.current_state = current_state
        self.target_state = target_state
        self.task_id = task_id
        message = (
            f"Invalid state transition for task {task_id}: "
            f"{current_state} -> {target_state}"
        )
        super().__init__(message)


class TaskNotFoundError(PlasmaAgentError):
    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        message = f"Task not found: {task_id}"
        super().__init__(message)


class TaskLockedError(PlasmaAgentError):
    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        message = f"Task is locked by another process: {task_id}"
        super().__init__(message)


class ExecutionError(PlasmaAgentError):
    def __init__(
        self,
        task_id: str,
        step_id: Optional[str] = None,
        message: str = "",
    ) -> None:
        self.task_id = task_id
        self.step_id = step_id
        error_message = f"Execution failed for task {task_id}"
        if step_id:
            error_message += f", step {step_id}"
        if message:
            error_message += f": {message}"
        super().__init__(error_message)


class ValidationError(PlasmaAgentError):
    pass


class ExecutorTimeoutError(ExecutionError):
    pass


class ExecutorNotFoundError(ExecutionError):
    pass
