import re
import uuid
from datetime import datetime, timezone
from typing import Any
from .models import ExecutionContext, SessionContext


class ContextManager:
    VARIABLE_PATTERN = re.compile(r"\$\{([a-zA-Z0-9_\-]+)\.([a-zA-Z_]+)\}")
    MAX_VARIABLE_LENGTH = 10000
    MAX_SESSIONS = 100
    
    def __init__(self) -> None:
        self._sessions: dict[str, SessionContext] = {}
    
    def create_session(self, session_id: str | None = None) -> SessionContext:
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        if len(self._sessions) >= self.MAX_SESSIONS:
            oldest_session_id = min(
                self._sessions.keys(),
                key=lambda sid: self._sessions[sid].created_at
            )
            self.delete_session(oldest_session_id)
        
        session = SessionContext(
            session_id=session_id,
            created_at=datetime.now(timezone.utc),
            executions=[],
            variables={}
        )
        self._sessions[session_id] = session
        return session
    
    def get_session(self, session_id: str) -> SessionContext | None:
        return self._sessions.get(session_id)
    
    def delete_session(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False
    
    def clear_all_sessions(self) -> int:
        count = len(self._sessions)
        self._sessions.clear()
        return count
    
    def add_execution(
        self,
        session_id: str,
        task_id: str,
        output: str = "",
        exit_code: int = 0,
        duration_ms: int = 0,
        metadata: dict[str, Any] | None = None
    ) -> ExecutionContext:
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found")
        
        execution = ExecutionContext(
            task_id=task_id,
            output=output[:100000],
            exit_code=exit_code,
            duration_ms=duration_ms,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            metadata=metadata or {}
        )
        
        new_executions = list(session.executions) + [execution]
        updated_session = SessionContext(
            session_id=session.session_id,
            created_at=session.created_at,
            executions=new_executions,
            variables=session.variables
        )
        self._sessions[session_id] = updated_session
        
        return execution
    
    def set_variable(self, session_id: str, name: str, value: str) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found")
        
        new_variables = dict(session.variables)
        new_variables[name] = value[:self.MAX_VARIABLE_LENGTH]
        
        updated_session = SessionContext(
            session_id=session.session_id,
            created_at=session.created_at,
            executions=session.executions,
            variables=new_variables
        )
        self._sessions[session_id] = updated_session
    
    def get_variable(self, session_id: str, name: str) -> str | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        return session.variables.get(name)
    
    def substitute_variables(self, session_id: str, text: str) -> str:
        session = self._sessions.get(session_id)
        if session is None:
            return text
        
        def replace_match(match: re.Match) -> str:
            task_id = match.group(1)
            field_name = match.group(2)
            
            if task_id == "var":
                return session.variables.get(field_name, match.group(0))
            
            execution = session.get_execution(task_id)
            if execution is None:
                return match.group(0)
            
            if field_name == "output":
                return execution.output
            elif field_name == "exit_code":
                return str(execution.exit_code)
            elif field_name == "duration":
                return str(execution.duration_ms)
            elif field_name == "success":
                return str(execution.success).lower()
            elif field_name == "failed":
                return str(execution.failed).lower()
            else:
                return match.group(0)
        
        return self.VARIABLE_PATTERN.sub(replace_match, text)
    
    def get_execution_history(self, session_id: str) -> list[ExecutionContext]:
        session = self._sessions.get(session_id)
        if session is None:
            return []
        return list(session.executions)
    
    def get_last_execution(self, session_id: str) -> ExecutionContext | None:
        session = self._sessions.get(session_id)
        if session is None or session.execution_count == 0:
            return None
        return session.executions[-1]
    
    def get_session_stats(self, session_id: str) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if session is None:
            return {
                "execution_count": 0,
                "success_count": 0,
                "failure_count": 0,
                "success_rate": 0.0,
                "total_duration_ms": 0,
                "avg_duration_ms": 0.0
            }
        
        total_duration = sum(e.duration_ms for e in session.executions)
        avg_duration = total_duration / session.execution_count if session.execution_count > 0 else 0.0
        
        return {
            "execution_count": session.execution_count,
            "success_count": session.success_count,
            "failure_count": session.failure_count,
            "success_rate": session.success_rate,
            "total_duration_ms": total_duration,
            "avg_duration_ms": avg_duration
        }
    
    @property
    def session_count(self) -> int:
        return len(self._sessions)
    
    def list_sessions(self) -> list[str]:
        return list(self._sessions.keys())
