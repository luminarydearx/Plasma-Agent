import asyncio
import os
import subprocess
import sys
import threading
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Optional

from plasmaagent.core.exceptions import ExecutorTimeoutError
from plasmaagent.executor.result import ExecutionResult, OutputChunk, OutputSource

DEFAULT_TIMEOUT: int = 300
BUFFER_SIZE: int = 4096

OutputCallback = Callable[[OutputChunk], Awaitable[None]]


class ShellExecutor:
    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        cwd: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
    ) -> None:
        self._timeout = timeout
        self._cwd = cwd
        self._env = env

    async def execute(
        self,
        command: str,
        task_id: str,
        on_output: Optional[OutputCallback] = None,
    ) -> ExecutionResult:
        started_at = datetime.now()
        stdout_parts: list[str] = []
        stderr_parts: list[str] = []
        exit_code_holder: list[Optional[int]] = [None]
        timed_out_holder: list[bool] = [False]

        loop = asyncio.get_running_loop()
        output_queue: asyncio.Queue[Optional[OutputChunk]] = asyncio.Queue()

        def _run_subprocess() -> None:
            try:
                safe_env = {**_get_safe_env(), **(self._env or {})}
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=self._cwd,
                    env=safe_env,
                    bufsize=0,
                )

                def _reader_thread(
                    stream: object,
                    source: OutputSource,
                    accumulator: list[str],
                ) -> None:
                    while True:
                        data = stream.read(BUFFER_SIZE)
                        if not data:
                            break
                        text = data.decode("utf-8", errors="replace")
                        accumulator.append(text)
                        chunk = OutputChunk(source=source, data=text)
                        loop.call_soon_threadsafe(output_queue.put_nowait, chunk)
                    stream.close()

                stdout_thread = threading.Thread(
                    target=_reader_thread,
                    args=(process.stdout, OutputSource.STDOUT, stdout_parts),
                    daemon=True,
                )
                stderr_thread = threading.Thread(
                    target=_reader_thread,
                    args=(process.stderr, OutputSource.STDERR, stderr_parts),
                    daemon=True,
                )
                stdout_thread.start()
                stderr_thread.start()

                try:
                    process.wait(timeout=self._timeout)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    timed_out_holder[0] = True

                stdout_thread.join(timeout=5)
                stderr_thread.join(timeout=5)

                exit_code_holder[0] = process.returncode

            except Exception as e:
                stderr_parts.append(f"[EXECUTOR ERROR] {e}")
                exit_code_holder[0] = -1
            finally:
                loop.call_soon_threadsafe(output_queue.put_nowait, None)

        process_thread = threading.Thread(target=_run_subprocess, daemon=True)
        process_thread.start()

        while True:
            chunk = await output_queue.get()
            if chunk is None:
                break
            if on_output is not None:
                await on_output(chunk)

        process_thread.join(timeout=5)

        finished_at = datetime.now()
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)

        if timed_out_holder[0]:
            return ExecutionResult(
                exit_code=-1,
                stdout="".join(stdout_parts),
                stderr="".join(stderr_parts)
                + "\n[TIMEOUT] Command exceeded time limit",
                duration_ms=duration_ms,
                timed_out=True,
                started_at=started_at,
                finished_at=finished_at,
            )

        return ExecutionResult(
            exit_code=exit_code_holder[0] if exit_code_holder[0] is not None else -1,
            stdout="".join(stdout_parts),
            stderr="".join(stderr_parts),
            duration_ms=duration_ms,
            timed_out=False,
            started_at=started_at,
            finished_at=finished_at,
        )


def _get_safe_env() -> dict[str, str]:
    safe_keys = {
        "PATH",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "USERPROFILE",
        "COMSPEC",
        "PATHEXT",
        "WINDIR",
    }
    if sys.platform != "win32":
        safe_keys.update({"HOME", "SHELL", "LANG", "LC_ALL", "TERM"})
    return {k: v for k, v in os.environ.items() if k in safe_keys}
