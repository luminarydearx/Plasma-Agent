from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from plasmaagent.ai.context.models import (
    ContextEntry,
    ContextSnapshot,
    ContextVariableType,
    TaskExecutionResult,
)

MAX_VARIABLES_PER_SESSION = 1000
MAX_VARIABLE_NAME_LENGTH = 100
MAX_VARIABLE_VALUE_LENGTH = 50000
MAX_SESSION_ID_LENGTH = 100
VARIABLE_PATTERN = re.compile(r"\$\{([a-zA-Z_][a-zA-Z0-9_.]*)\}")


class ContextManager:
    def __init__(self, session_id: str | None = None) -> None:
        self._validate_session_id(session_id)
        self._session_id = session_id or f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self._entries: dict[str, ContextEntry] = {}
        self._task_results: list[TaskExecutionResult] = []
        self._created_at = datetime.now()

    def _validate_session_id(self, session_id: str | None) -> None:
        if session_id is not None:
            if not isinstance(session_id, str):
                raise TypeError("session_id must be a string")
            if not session_id.strip():
                raise ValueError("session_id cannot be empty")
            if len(session_id) > MAX_SESSION_ID_LENGTH:
                raise ValueError(f"session_id too long (max {MAX_SESSION_ID_LENGTH} chars)")
            if "\x00" in session_id:
                raise ValueError("session_id cannot contain null bytes")

    def _validate_variable_name(self, name: str) -> None:
        if not isinstance(name, str):
            raise TypeError("variable_name must be a string")
        if not name.strip():
            raise ValueError("variable_name cannot be empty")
        if len(name) > MAX_VARIABLE_NAME_LENGTH:
            raise ValueError(f"variable_name too long (max {MAX_VARIABLE_NAME_LENGTH} chars)")
        if "\x00" in name:
            raise ValueError("variable_name cannot contain null bytes")
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_.]*$", name):
            raise ValueError("variable_name must start with letter/underscore and contain only alphanumeric/underscore/dot")

    def _validate_value(self, value: Any) -> None:
        if isinstance(value, str):
            if "\x00" in value:
                raise ValueError("value cannot contain null bytes")
            if len(value) > MAX_VARIABLE_VALUE_LENGTH:
                raise ValueError(f"value too long (max {MAX_VARIABLE_VALUE_LENGTH} chars)")

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    @property
    def result_count(self) -> int:
        return len(self._task_results)

    def record_task_result(self, result: TaskExecutionResult) -> None:
        if not isinstance(result, TaskExecutionResult):
            raise TypeError("result must be a TaskExecutionResult instance")

        self._task_results.append(result)

        self._auto_set_variable(result.task_id, "status", ContextVariableType.CUSTOM, result.status)
        if result.output is not None:
            self._auto_set_variable(result.task_id, "output", ContextVariableType.OUTPUT, result.output)
        if result.stdout is not None:
            self._auto_set_variable(result.task_id, "stdout", ContextVariableType.STDOUT, result.stdout)
        if result.stderr is not None:
            self._auto_set_variable(result.task_id, "stderr", ContextVariableType.STDERR, result.stderr)
        if result.error is not None:
            self._auto_set_variable(result.task_id, "error", ContextVariableType.ERROR, result.error)
        if result.exit_code is not None:
            self._auto_set_variable(result.task_id, "exit_code", ContextVariableType.EXIT_CODE, result.exit_code)
        if result.duration_ms is not None:
            self._auto_set_variable(result.task_id, "duration_ms", ContextVariableType.DURATION_MS, result.duration_ms)

    def _auto_set_variable(
        self,
        task_id: str,
        variable_name: str,
        variable_type: ContextVariableType,
        value: Any,
    ) -> None:
        full_name = f"{task_id}.{variable_name}"
        try:
            self.set_variable(full_name, value, variable_type, task_id)
        except ValueError:
            pass

    def set_variable(
        self,
        name: str,
        value: Any,
        variable_type: ContextVariableType = ContextVariableType.CUSTOM,
        task_id: str | None = None,
    ) -> None:
        self._validate_variable_name(name)
        self._validate_value(value)

        if len(self._entries) >= MAX_VARIABLES_PER_SESSION and name not in self._entries:
            raise ValueError(f"Maximum variables per session reached ({MAX_VARIABLES_PER_SESSION})")

        entry = ContextEntry(
            task_id=task_id or "global",
            variable_name=name,
            variable_type=variable_type,
            value=value,
            timestamp=datetime.now(),
        )
        self._entries[name] = entry

    def get_variable(self, name: str, default: Any = None) -> Any:
        if not isinstance(name, str):
            raise TypeError("variable_name must be a string")
        entry = self._entries.get(name)
        return entry.value if entry is not None else default

    def has_variable(self, name: str) -> bool:
        return name in self._entries

    def delete_variable(self, name: str) -> bool:
        if name in self._entries:
            del self._entries[name]
            return True
        return False

    def get_previous_result(self) -> TaskExecutionResult | None:
        return self._task_results[-1] if self._task_results else None

    def get_task_result(self, task_id: str) -> TaskExecutionResult | None:
        for result in reversed(self._task_results):
            if result.task_id == task_id:
                return result
        return None

    def substitute(self, text: str, default: str = "") -> str:
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        if "\x00" in text:
            raise ValueError("text cannot contain null bytes")

        def replacer(match: re.Match[str]) -> str:
            var_name = match.group(1)
            value = self.get_variable(var_name)
            if value is None:
                return default
            return str(value)

        return VARIABLE_PATTERN.sub(replacer, text)

    def find_variables(self, text: str) -> list[str]:
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        return VARIABLE_PATTERN.findall(text)

    def list_variables(self, prefix: str | None = None) -> list[str]:
        if prefix is None:
            return sorted(self._entries.keys())
        return sorted(name for name in self._entries.keys() if name.startswith(prefix))

    def clear(self) -> None:
        self._entries.clear()
        self._task_results.clear()

    def snapshot(self) -> ContextSnapshot:
        return ContextSnapshot(
            session_id=self._session_id,
            entries=tuple(self._entries.values()),
            task_results=tuple(self._task_results),
            created_at=self._created_at,
        )

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, name: str) -> bool:
        return name in self._entries

    def __repr__(self) -> str:
        return f"ContextManager(session_id='{self._session_id}', entries={len(self._entries)}, results={len(self._task_results)})"
