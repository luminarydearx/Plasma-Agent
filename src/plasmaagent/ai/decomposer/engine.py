from __future__ import annotations
import re
import time
from typing import List, Optional
from plasmaagent.ai.decomposer.models import DecomposedTask, SubTask, ExecutionMode

MAX_INPUT_LENGTH = 10000
MAX_SUB_TASKS = 50
MAX_SUB_TASK_LENGTH = 2000
MIN_SEGMENT_LENGTH = 2

SEQUENTIAL_MARKERS = re.compile(
    r"\b(then|after that|next|followed by|and then|subsequently|later|kemudian|lalu|setelah itu)\b",
    re.IGNORECASE,
)

PARALLEL_MARKERS = re.compile(
    r"\b(also|simultaneously|while|at the same time|meanwhile|in parallel|serta|bersamaan)\b",
    re.IGNORECASE,
)

BOUNDARY_SPLITTER = re.compile(r"(?:\.|;|\n+)\s*(?=[A-Z0-9\"\'\(\[]|[\u4e00-\u9fff\u3040-\u30ff])")

LIST_ITEM_PATTERN = re.compile(
    r"^[\s]*[-*•\d][\.\)]?\s+(.+?)[\s]*$",
    re.MULTILINE,
)


class TaskDecomposer:
    def decompose(self, natural_language: str) -> DecomposedTask:
        start = time.perf_counter()
        self._validate_input(natural_language)

        if self._is_single_task(natural_language):
            return self._wrap_as_single(natural_language, time.perf_counter() - start)

        segments = self._split_into_segments(natural_language)
        if len(segments) <= 1:
            return self._wrap_as_single(natural_language, time.perf_counter() - start)

        sub_tasks = self._build_sub_tasks(segments)
        if len(sub_tasks) > MAX_SUB_TASKS:
            sub_tasks = sub_tasks[:MAX_SUB_TASKS]

        execution_mode = self._determine_mode(sub_tasks)
        total_groups = (max((t.parallel_group for t in sub_tasks), default=0) + 1) if sub_tasks else 0
        confidence = self._calculate_confidence(natural_language, sub_tasks, execution_mode)

        return DecomposedTask(
            original_input=natural_language.strip(),
            sub_tasks=sub_tasks,
            execution_mode=execution_mode,
            confidence=round(confidence, 2),
            decomposition_time_ms=round((time.perf_counter() - start) * 1000, 2),
            total_parallel_groups=total_groups,
        )

    def _validate_input(self, text: str) -> None:
        if not isinstance(text, str):
            raise TypeError("natural_language must be a string")
        if not text or not text.strip():
            raise ValueError("natural_language cannot be empty")
        if len(text) > MAX_INPUT_LENGTH:
            raise ValueError(f"natural_language exceeds {MAX_INPUT_LENGTH} characters")
        if "\x00" in text:
            raise ValueError("natural_language contains null bytes")

    def _is_single_task(self, text: str) -> bool:
        stripped = text.strip()
        if len(stripped) < 5:
            return True
        if not SEQUENTIAL_MARKERS.search(stripped) and not PARALLEL_MARKERS.search(stripped):
            if not BOUNDARY_SPLITTER.search(stripped):
                if not LIST_ITEM_PATTERN.search(stripped):
                    return True
        return False

    def _split_into_segments(self, text: str) -> List[str]:
        candidates: List[str] = []

        list_items = LIST_ITEM_PATTERN.findall(text)
        if len(list_items) >= 2:
            candidates = [item.strip() for item in list_items if item.strip()]
        else:
            parts = BOUNDARY_SPLITTER.split(text)
            candidates = [p.strip() for p in parts if p and p.strip()]

        if len(candidates) < 2:
            candidates = self._split_by_markers(text)

        return [c[:MAX_SUB_TASK_LENGTH] for c in candidates if len(c) >= MIN_SEGMENT_LENGTH]

    def _split_by_markers(self, text: str) -> List[str]:
        segments: List[str] = []
        current = text
        while True:
            match = SEQUENTIAL_MARKERS.search(current)
            if not match:
                if current.strip():
                    segments.append(current.strip())
                break
            before = current[:match.start()].strip()
            if before:
                segments.append(before)
            current = current[match.end():]
        return segments

    def _build_sub_tasks(self, segments: List[str]) -> List[SubTask]:
        sub_tasks: List[SubTask] = []
        group = 0
        for idx, segment in enumerate(segments):
            task_id = f"t{idx}"
            depends_on: List[str] = []

            is_parallel = bool(PARALLEL_MARKERS.search(segment)) and idx > 0
            if is_parallel and sub_tasks:
                group = sub_tasks[-1].parallel_group
                depends_on = []
            else:
                if idx > 0:
                    group = sub_tasks[-1].parallel_group + 1
                    depends_on = [sub_tasks[-1].task_id]

            sub_tasks.append(
                SubTask(
                    task_id=task_id,
                    natural_language=segment[:MAX_SUB_TASK_LENGTH],
                    depends_on=depends_on,
                    parallel_group=group,
                    priority=min(idx, 10),
                )
            )
        return sub_tasks

    def _determine_mode(self, sub_tasks: List[SubTask]) -> ExecutionMode:
        if not sub_tasks:
            return ExecutionMode.SEQUENTIAL
        groups = {t.parallel_group for t in sub_tasks}
        max_group_size = max(len([t for t in sub_tasks if t.parallel_group == g]) for g in groups)
        has_deps = any(len(t.depends_on) > 0 for t in sub_tasks)

        if max_group_size == 1 and has_deps:
            return ExecutionMode.SEQUENTIAL
        if max_group_size > 1 and not has_deps:
            return ExecutionMode.PARALLEL
        if max_group_size > 1 or has_deps:
            return ExecutionMode.MIXED
        return ExecutionMode.SEQUENTIAL

    def _calculate_confidence(
        self, text: str, sub_tasks: List[SubTask], mode: ExecutionMode
    ) -> float:
        if not sub_tasks:
            return 0.0
        if len(sub_tasks) == 1 and not SEQUENTIAL_MARKERS.search(text):
            return 1.0
        base = 0.5
        if len(sub_tasks) >= 2:
            base += 0.2
        if SEQUENTIAL_MARKERS.search(text):
            base += 0.1
        if PARALLEL_MARKERS.search(text):
            base += 0.1
        if mode in (ExecutionMode.SEQUENTIAL, ExecutionMode.MIXED):
            base += 0.05
        return min(base, 1.0)

    def _wrap_as_single(self, text: str, elapsed: float) -> DecomposedTask:
        return DecomposedTask(
            original_input=text.strip(),
            sub_tasks=[
                SubTask(
                    task_id="t0",
                    natural_language=text.strip()[:MAX_SUB_TASK_LENGTH],
                    depends_on=[],
                    parallel_group=0,
                    priority=0,
                )
            ],
            execution_mode=ExecutionMode.SEQUENTIAL,
            confidence=1.0,
            decomposition_time_ms=round(elapsed * 1000, 2),
            total_parallel_groups=1,
        )
