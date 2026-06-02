from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class OutputSource(str, Enum):
    STDOUT = "stdout"
    STDERR = "stderr"


@dataclass(frozen=True)
class OutputChunk:
    source: OutputSource
    data: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True)
class ExecutionResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    @property
    def succeeded(self) -> bool:
        return self.exit_code == 0 and not self.timed_out

    @property
    def failed(self) -> bool:
        return not self.succeeded
