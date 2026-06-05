from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Awaitable
from uuid import UUID, uuid4


@dataclass(frozen=True)
class ToolResult:
    success: bool
    output: str
    data: Any = None


ToolHandler = Callable[..., Awaitable[ToolResult]]

DANGEROUS_DIRS = {
    Path("C:/Windows"),
    Path("C:/Program Files"),
    Path("C:/Program Files (x86)"),
    Path("/etc"),
    Path("/usr"),
    Path("/bin"),
    Path("/sbin"),
}


def _is_safe(path: Path) -> bool:
    resolved = path.expanduser().resolve()
    for dangerous in DANGEROUS_DIRS:
        try:
            resolved.relative_to(dangerous)
            return False
        except ValueError:
            continue
    return True


async def create_file(path: str, content: str = "", overwrite: bool = False) -> ToolResult:
    target = Path(path).expanduser().resolve()
    if not _is_safe(target):
        return ToolResult(False, f"Access denied: {target} is in system directory")
    if target.exists() and not overwrite:
        return ToolResult(False, f"File already exists: {target}. Use overwrite=True to replace.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return ToolResult(True, f"Created file: {target} ({len(content)} chars)", {"path": str(target)})


async def read_file(path: str, max_lines: int | None = None) -> ToolResult:
    target = Path(path).expanduser().resolve()
    if not _is_safe(target):
        return ToolResult(False, f"Access denied: {target}")
    if not target.exists():
        return ToolResult(False, f"File not found: {target}")
    if not target.is_file():
        return ToolResult(False, f"Not a file: {target}")
    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ToolResult(False, "Binary file, cannot read as text")
    if max_lines:
        content = "\n".join(content.split("\n")[:max_lines])
    return ToolResult(True, content, {"path": str(target), "chars": len(content)})


async def write_file(path: str, content: str, append: bool = False) -> ToolResult:
    target = Path(path).expanduser().resolve()
    if not _is_safe(target):
        return ToolResult(False, f"Access denied: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with open(target, mode, encoding="utf-8") as f:
        f.write(content)
    action = "Appended" if append else "Wrote"
    return ToolResult(True, f"{action} {len(content)} chars to {target}", {"path": str(target)})


async def list_directory(path: str = ".", recursive: bool = False) -> ToolResult:
    target = Path(path).expanduser().resolve()
    if not _is_safe(target):
        return ToolResult(False, f"Access denied: {target}")
    if not target.exists():
        return ToolResult(False, f"Directory not found: {target}")
    if not target.is_dir():
        return ToolResult(False, f"Not a directory: {target}")
    items = sorted(target.rglob("*") if recursive else target.iterdir())
    entries = []
    for item in items:
        if item.name.startswith("."):
            continue
        entry_type = "DIR" if item.is_dir() else "FILE"
        try:
            size = item.stat().st_size if item.is_file() else 0
        except OSError:
            size = 0
        entries.append({
            "type": entry_type,
            "name": str(item.relative_to(target)),
            "size": size,
        })
    return ToolResult(True, f"Listed {len(entries)} items in {target}", {"items": entries})


async def delete_file(path: str, recursive: bool = False) -> ToolResult:
    target = Path(path).expanduser().resolve()
    if not _is_safe(target):
        return ToolResult(False, f"Access denied: {target}")
    if not target.exists():
        return ToolResult(False, f"Not found: {target}")
    if target.is_dir():
        if not recursive:
            return ToolResult(False, "Use recursive=True to delete directories")
        import shutil
        shutil.rmtree(target)
    else:
        target.unlink()
    return ToolResult(True, f"Deleted: {target}", {"path": str(target)})


async def file_info(path: str) -> ToolResult:
    target = Path(path).expanduser().resolve()
    if not target.exists():
        return ToolResult(False, f"Not found: {target}")
    stat = target.stat()
    info = {
        "path": str(target),
        "type": "directory" if target.is_dir() else "file",
        "size_bytes": stat.st_size,
        "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "permissions": oct(stat.st_mode)[-3:],
    }
    return ToolResult(True, json.dumps(info, indent=2), info)


async def execute_shell(command: str, timeout: int = 300) -> ToolResult:
    dangerous = ["rm -rf /", "format c:", "del /s /q c:\\", "rmdir /s /q c:\\", "DROP DATABASE", "shutdown /s", "shutdown -s"]
    for pattern in dangerous:
        if pattern.lower() in command.lower():
            return ToolResult(False, f"Dangerous command blocked: {pattern}")
    shell_name = "powershell" if sys.platform == "win32" else "bash"
    shell_flag = "-Command" if sys.platform == "win32" else "-c"
    try:
        result = subprocess.run(
            [shell_name, shell_flag, command],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout or ""
        if result.stderr:
            output += f"\n[STDERR]\n{result.stderr}"
        if not output.strip():
            output = f"Exit code: {result.returncode}"
        return ToolResult(
            result.returncode == 0,
            output.strip(),
            {"exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr},
        )
    except subprocess.TimeoutExpired:
        return ToolResult(False, f"Command timed out after {timeout}s")
    except Exception as e:
        return ToolResult(False, f"Execution failed: {e}")


async def open_app(app_name: str, arguments: str = "") -> ToolResult:
    try:
        if sys.platform == "win32":
            cmd = f"Start-Process '{app_name}'"
            if arguments:
                cmd += f" -ArgumentList '{arguments}'"
            result = subprocess.run(
                ["powershell", "-Command", cmd],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return ToolResult(True, f"Opened: {app_name} {arguments}".strip())
            return ToolResult(False, f"Failed to open {app_name}: {result.stderr}")
        else:
            cmd = ["xdg-open", app_name] if "://" in app_name or "/" in app_name else [app_name]
            if arguments:
                cmd.extend(arguments.split())
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return ToolResult(True, f"Opened: {app_name} {arguments}".strip())
    except FileNotFoundError:
        return ToolResult(False, f"Application not found: {app_name}")
    except Exception as e:
        return ToolResult(False, f"Failed to open app: {e}")


async def cron_schedule(task_name: str, cron_expression: str, commands: list[str]) -> ToolResult:
    try:
        from plasmaagent.core.database import get_database
        from plasmaagent.scheduling.service import SchedulingService

        db = get_database()
        await db.connect()
        try:
            task_id = uuid4()
            payload = json.dumps({"commands": commands})
            async with db.transaction() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "INSERT INTO tasks (id, name, status, payload, created_at, updated_at) "
                        "VALUES (%s, %s, 'PENDING', %s, NOW(), NOW())",
                        (task_id, task_name, payload),
                    )
            service = SchedulingService(db)
            result = await service.enable_schedule(
                task_id=task_id,
                cron_expression=cron_expression,
            )
            if result is None:
                return ToolResult(False, f"Failed to schedule task '{task_name}'")
            next_run = result.next_run_at
            return ToolResult(
                True,
                f"Scheduled '{task_name}' with cron '{cron_expression}'. Next run: {next_run}",
                {"task_id": str(task_id), "next_run": str(next_run)},
            )
        finally:
            await db.disconnect()
    except Exception as e:
        return ToolResult(False, f"Failed to schedule: {e}")


async def schedule_once(task_name: str, run_at: str, commands: list[str]) -> ToolResult:
    try:
        from plasmaagent.core.database import get_database

        db = get_database()
        await db.connect()
        try:
            run_time = datetime.fromisoformat(run_at.replace("Z", "+00:00"))
            task_id = uuid4()
            payload = json.dumps({"commands": commands, "type": "one_time"})
            async with db.transaction() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "INSERT INTO tasks (id, name, status, payload, created_at, updated_at) "
                        "VALUES (%s, %s, 'PENDING', %s, NOW(), NOW())",
                        (task_id, task_name, payload),
                    )
                    await cur.execute(
                        "INSERT INTO schedules (id, task_id, schedule_type, run_at, status, created_at) "
                        "VALUES (%s, %s, 'ONETIME', %s, 'ACTIVE', NOW())",
                        (uuid4(), task_id, run_time),
                    )
            return ToolResult(
                True,
                f"One-time task '{task_name}' scheduled for {run_time.isoformat()}",
                {"task_id": str(task_id), "run_at": run_time.isoformat()},
            )
        finally:
            await db.disconnect()
    except ValueError as e:
        return ToolResult(False, f"Invalid datetime format: {e}. Use ISO format: YYYY-MM-DDTHH:MM:SS")
    except Exception as e:
        return ToolResult(False, f"Failed to schedule: {e}")


async def store_memory(content: str, memory_type: str = "fact", metadata: dict[str, Any] | None = None) -> ToolResult:
    try:
        from plasmaagent.core.database import get_database
        from plasmaagent.memory.service import MemoryService
        from plasmaagent.memory.models import MemoryType

        db = get_database()
        await db.connect()
        try:
            async with db.connection() as conn:
                service = MemoryService(conn)
                mt = MemoryType(memory_type)
                memory = await service.store_memory(content, mt, metadata=metadata or {})
                await conn.commit()
                return ToolResult(True, f"Stored memory: {memory.id}", {"id": str(memory.id)})
        finally:
            await db.disconnect()
    except Exception as e:
        return ToolResult(False, f"Failed to store memory: {e}")


async def search_memory(query: str, limit: int = 10) -> ToolResult:
    try:
        from plasmaagent.core.database import get_database
        from plasmaagent.memory.service import MemoryService

        db = get_database()
        await db.connect()
        try:
            async with db.connection() as conn:
                service = MemoryService(conn)
                memories = await service.search_memories(query, limit=limit)
                if not memories:
                    return ToolResult(True, "No memories found", {"results": []})
                results = [
                    {"id": str(m.id), "type": m.memory_type.value, "content": m.content}
                    for m in memories
                ]
                formatted = "\n".join(f"[{r['id']}] ({r['type']}) {r['content']}" for r in results)
                return ToolResult(True, formatted, {"results": results})
        finally:
            await db.disconnect()
    except Exception as e:
        return ToolResult(False, f"Search failed: {e}")


async def system_info() -> ToolResult:
    import platform
    info = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "hostname": platform.node(),
        "user": os.getlogin() if hasattr(os, "getlogin") else "unknown",
        "cwd": str(Path.cwd()),
        "home": str(Path.home()),
    }
    return ToolResult(True, json.dumps(info, indent=2), info)


async def current_time() -> ToolResult:
    now = datetime.now()
    return ToolResult(True, now.isoformat(), {"timestamp": now.isoformat()})


async def web_search(query: str, max_results: int = 5) -> ToolResult:
    try:
        import httpx
        encoded = query.replace(" ", "+")
        url = f"https://html.duckduckgo.com/html/?q={encoded}"
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            resp.raise_for_status()
        html = resp.text
        import re
        results = []
        pattern = re.compile(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
        for match in pattern.finditer(html):
            href = match.group(1)
            title = re.sub(r'<[^>]+>', '', match.group(2)).strip()
            if title and len(results) < max_results:
                results.append({"title": title, "url": href})
        if not results:
            alt_pattern = re.compile(r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
            for match in alt_pattern.finditer(html):
                href = match.group(1)
                title = re.sub(r'<[^>]+>', '', match.group(2)).strip()
                if title and len(results) < max_results:
                    results.append({"title": title, "url": href})
        if not results:
            return ToolResult(True, f"No results found for: {query}", {"results": []})
        formatted = "\n".join(f"{i+1}. {r['title']}\n   {r['url']}" for i, r in enumerate(results))
        return ToolResult(True, f"Search results for '{query}':\n{formatted}", {"results": results})
    except Exception as e:
        return ToolResult(False, f"Web search failed: {e}")


async def youtube_search(query: str, max_results: int = 5) -> ToolResult:
    try:
        import httpx
        encoded = query.replace(" ", "+")
        url = f"https://www.youtube.com/results?search_query={encoded}"
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            resp.raise_for_status()
        html = resp.text
        import re
        results = []
        pattern = re.compile(r'"videoId":"([^"]+)".*?"title":\{"runs":\[\{"text":"([^"]+)"\}', re.DOTALL)
        seen_ids: set[str] = set()
        for match in pattern.finditer(html):
            vid = match.group(1)
            title = match.group(2)
            if vid not in seen_ids and len(results) < max_results:
                seen_ids.add(vid)
                results.append({
                    "title": title,
                    "video_id": vid,
                    "url": f"https://www.youtube.com/watch?v={vid}",
                })
        if not results:
            alt = re.compile(r'/watch\?v=([a-zA-Z0-9_-]{11})[^"]*"[^>]*>\s*<span[^>]*>([^<]+)</span>', re.DOTALL)
            for match in alt.finditer(html):
                vid = match.group(1)
                title = match.group(2).strip()
                if vid not in seen_ids and len(results) < max_results:
                    seen_ids.add(vid)
                    results.append({
                        "title": title,
                        "video_id": vid,
                        "url": f"https://www.youtube.com/watch?v={vid}",
                    })
        if not results:
            return ToolResult(True, f"No YouTube results for: {query}. Opening search page instead.", {"results": [], "search_url": url})
        formatted = "\n".join(f"{i+1}. {r['title']}\n   {r['url']}" for i, r in enumerate(results))
        return ToolResult(True, f"YouTube results for '{query}':\n{formatted}\n\nTo watch: use open_app with the URL. To search in browser: open_app('msedge', '{url}')", {"results": results})
    except Exception as e:
        return ToolResult(False, f"YouTube search failed: {e}")


async def screenshot(save_path: str = "") -> ToolResult:
    try:
        if not save_path:
            save_path = str(Path.home() / "Desktop" / f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        if sys.platform == "win32":
            ps_script = f"""
Add-Type -AssemblyName System.Windows.Forms
$screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bitmap = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)
$bitmap.Save('{save_path}')
$graphics.Dispose()
$bitmap.Dispose()
Write-Output '{save_path}'
"""
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return ToolResult(True, f"Screenshot saved: {save_path}", {"path": save_path})
            return ToolResult(False, f"Screenshot failed: {result.stderr}")
        else:
            result = subprocess.run(
                ["scrot", save_path],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return ToolResult(True, f"Screenshot saved: {save_path}", {"path": save_path})
            return ToolResult(False, f"Screenshot failed: {result.stderr}")
    except Exception as e:
        return ToolResult(False, f"Screenshot failed: {e}")


async def clipboard_get() -> ToolResult:
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["powershell", "-Command", "Get-Clipboard"],
                capture_output=True, text=True, timeout=5,
            )
            return ToolResult(True, result.stdout.strip(), {"content": result.stdout.strip()})
        else:
            result = subprocess.run(["xclip", "-selection", "clipboard", "-o"], capture_output=True, text=True, timeout=5)
            return ToolResult(True, result.stdout.strip(), {"content": result.stdout.strip()})
    except Exception as e:
        return ToolResult(False, f"Clipboard read failed: {e}")


async def clipboard_set(content: str) -> ToolResult:
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["powershell", "-Command", f"Set-Clipboard -Value '{content}'"],
                capture_output=True, text=True, timeout=5,
            )
            return ToolResult(True, f"Copied to clipboard ({len(content)} chars)", {"chars": len(content)})
        else:
            proc = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
            proc.communicate(content.encode("utf-8"), timeout=5)
            return ToolResult(True, f"Copied to clipboard ({len(content)} chars)", {"chars": len(content)})
    except Exception as e:
        return ToolResult(False, f"Clipboard write failed: {e}")


async def process_list(filter_name: str = "", limit: int = 20) -> ToolResult:
    try:
        if sys.platform == "win32":
            cmd = "Get-Process | Sort-Object WorkingSet64 -Descending"
            if filter_name:
                cmd = f"Get-Process -Name '*{filter_name}*' -ErrorAction SilentlyContinue | Sort-Object WorkingSet64 -Descending"
            cmd += f" | Select-Object -First {limit} Name, Id, @{{N='MemMB';E={{[math]::Round($_.WorkingSet64/1MB,1)}}}}, CPU"
            result = subprocess.run(
                ["powershell", "-Command", cmd],
                capture_output=True, text=True, timeout=10,
            )
            return ToolResult(True, result.stdout.strip(), {"output": result.stdout})
        else:
            cmd = ["ps", "aux", "--sort=-%mem"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            lines = result.stdout.strip().split("\n")
            output = "\n".join(lines[:limit + 1])
            return ToolResult(True, output, {"output": output})
    except Exception as e:
        return ToolResult(False, f"Process list failed: {e}")


async def kill_process(name: str = "", pid: int = 0) -> ToolResult:
    try:
        if not name and not pid:
            return ToolResult(False, "Must specify either name or pid")
        if sys.platform == "win32":
            if pid:
                cmd = f"Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue"
            else:
                cmd = f"Stop-Process -Name '{name}' -Force -ErrorAction SilentlyContinue"
            result = subprocess.run(
                ["powershell", "-Command", cmd],
                capture_output=True, text=True, timeout=10,
            )
            target = f"PID {pid}" if pid else f"'{name}'"
            return ToolResult(True, f"Killed process: {target}", {"target": target})
        else:
            import signal
            if pid:
                os.kill(pid, signal.SIGTERM)
                return ToolResult(True, f"Killed PID {pid}", {"pid": pid})
            else:
                result = subprocess.run(["pkill", name], capture_output=True, text=True, timeout=10)
                return ToolResult(True, f"Killed process: {name}", {"name": name})
    except Exception as e:
        return ToolResult(False, f"Kill process failed: {e}")


async def send_notification(title: str, message: str, duration: int = 5) -> ToolResult:
    try:
        if sys.platform == "win32":
            ps_script = f"""
Add-Type -AssemblyName System.Windows.Forms
$notification = New-Object System.Windows.Forms.NotifyIcon
$notification.Icon = [System.Drawing.SystemIcons]::Information
$notification.BalloonTipTitle = '{title}'
$notification.BalloonTipText = '{message}'
$notification.Visible = $true
$notification.ShowBalloonTip({duration * 1000})
Start-Sleep -Milliseconds {(duration + 1) * 1000}
$notification.Dispose()
"""
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True, text=True, timeout=duration + 5,
            )
            if result.returncode == 0:
                return ToolResult(True, f"Notification sent: {title}", {"title": title, "message": message})
            return ToolResult(False, f"Notification failed: {result.stderr}")
        else:
            result = subprocess.run(
                ["notify-send", title, message, "-t", str(duration * 1000)],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                return ToolResult(True, f"Notification sent: {title}", {"title": title, "message": message})
            return ToolResult(False, f"Notification failed: {result.stderr}")
    except Exception as e:
        return ToolResult(False, f"Notification failed: {e}")


async def system_stats() -> ToolResult:
    try:
        import psutil
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        
        stats = {
            "cpu_percent": cpu_percent,
            "memory_total_gb": round(memory.total / (1024**3), 2),
            "memory_used_gb": round(memory.used / (1024**3), 2),
            "memory_percent": memory.percent,
            "disk_total_gb": round(disk.total / (1024**3), 2),
            "disk_used_gb": round(disk.used / (1024**3), 2),
            "disk_percent": disk.percent,
        }
        
        output = f"""System Stats:
CPU: {stats['cpu_percent']}%
Memory: {stats['memory_used_gb']}/{stats['memory_total_gb']} GB ({stats['memory_percent']}%)
Disk: {stats['disk_used_gb']}/{stats['disk_total_gb']} GB ({stats['disk_percent']}%)"""
        
        return ToolResult(True, output, stats)
    except ImportError:
        if sys.platform == "win32":
            cmd = """
$cpu = (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
$os = Get-CimInstance Win32_OperatingSystem
$mem_total = [math]::Round($os.TotalVisibleMemorySize / 1MB, 2)
$mem_free = [math]::Round($os.FreePhysicalMemory / 1MB, 2)
$mem_used = $mem_total - $mem_free
$mem_percent = [math]::Round(($mem_used / $mem_total) * 100, 1)
Write-Output "CPU: $cpu%"
Write-Output "Memory: $mem_used/$mem_total GB ($mem_percent%)"
"""
            result = subprocess.run(
                ["powershell", "-Command", cmd],
                capture_output=True, text=True, timeout=10,
            )
            return ToolResult(True, result.stdout.strip(), {"output": result.stdout})
        else:
            result = subprocess.run(
                ["top", "-bn1", "|", "head", "-n", "5"],
                capture_output=True, text=True, timeout=10, shell=True,
            )
            return ToolResult(True, result.stdout.strip(), {"output": result.stdout})
    except Exception as e:
        return ToolResult(False, f"System stats failed: {e}")


async def download_file(url: str, save_path: str = "") -> ToolResult:
    try:
        import httpx
        from urllib.parse import urlparse
        
        if not save_path:
            parsed = urlparse(url)
            filename = Path(parsed.path).name or "downloaded_file"
            save_path = str(Path.home() / "Downloads" / filename)
        
        target = Path(save_path).expanduser().resolve()
        if not _is_safe(target):
            return ToolResult(False, f"Access denied: {target} is in system directory")
        
        target.parent.mkdir(parents=True, exist_ok=True)
        
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                with open(target, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        f.write(chunk)
        
        size = target.stat().st_size
        return ToolResult(True, f"Downloaded: {target} ({size} bytes)", {"path": str(target), "size": size})
    except Exception as e:
        return ToolResult(False, f"Download failed: {e}")


async def find_file(pattern: str, directory: str = ".", max_results: int = 20) -> ToolResult:
    try:
        target_dir = Path(directory).expanduser().resolve()
        if not _is_safe(target_dir):
            return ToolResult(False, f"Access denied: {target_dir}")
        if not target_dir.exists():
            return ToolResult(False, f"Directory not found: {target_dir}")
        
        matches = list(target_dir.rglob(pattern))[:max_results]
        
        if not matches:
            return ToolResult(True, f"No files matching '{pattern}' in {target_dir}", {"matches": []})
        
        results = []
        for match in matches:
            try:
                stat = match.stat()
                results.append({
                    "path": str(match),
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })
            except OSError:
                continue
        
        formatted = "\n".join(f"{i+1}. {r['path']} ({r['size']} bytes)" for i, r in enumerate(results))
        return ToolResult(True, f"Found {len(results)} files matching '{pattern}':\n{formatted}", {"matches": results})
    except Exception as e:
        return ToolResult(False, f"Find file failed: {e}")


async def web_scrape(url: str, max_chars: int = 10000) -> ToolResult:
    try:
        import httpx
        import re
        
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            resp.raise_for_status()
        
        html = resp.text
        
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<[^>]+>', ' ', html)
        html = re.sub(r'\s+', ' ', html)
        text = html.strip()
        
        if len(text) > max_chars:
            text = text[:max_chars] + "..."
        
        return ToolResult(True, f"Content from {url}:\n{text}", {"url": url, "chars": len(text)})
    except Exception as e:
        return ToolResult(False, f"Web scrape failed: {e}")


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler
    requires_permission: bool = True


TOOL_REGISTRY: dict[str, ToolDefinition] = {
    "create_file": ToolDefinition(
        name="create_file",
        description="Create a new file at the specified path with optional content. Will not overwrite existing files unless overwrite=True.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute file path"},
                "content": {"type": "string", "description": "File content", "default": ""},
                "overwrite": {"type": "boolean", "description": "Overwrite if exists", "default": False},
            },
            "required": ["path"],
        },
        handler=create_file,
        requires_permission=True,
    ),
    "read_file": ToolDefinition(
        name="read_file",
        description="Read text content from a file. Supports limiting output lines.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute file path"},
                "max_lines": {"type": "integer", "description": "Max lines to return"},
            },
            "required": ["path"],
        },
        handler=read_file,
        requires_permission=False,
    ),
    "write_file": ToolDefinition(
        name="write_file",
        description="Write content to a file. Use append=True to append instead of overwrite.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute file path"},
                "content": {"type": "string", "description": "Content to write"},
                "append": {"type": "boolean", "description": "Append instead of overwrite", "default": False},
            },
            "required": ["path", "content"],
        },
        handler=write_file,
        requires_permission=True,
    ),
    "list_directory": ToolDefinition(
        name="list_directory",
        description="List files and directories at the specified path.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path", "default": "."},
                "recursive": {"type": "boolean", "description": "List recursively", "default": False},
            },
        },
        handler=list_directory,
        requires_permission=False,
    ),
    "delete_file": ToolDefinition(
        name="delete_file",
        description="Delete a file or directory. Use recursive=True for directories.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to delete"},
                "recursive": {"type": "boolean", "description": "Delete directory recursively", "default": False},
            },
            "required": ["path"],
        },
        handler=delete_file,
        requires_permission=True,
    ),
    "file_info": ToolDefinition(
        name="file_info",
        description="Get metadata about a file or directory (size, dates, permissions).",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File or directory path"},
            },
            "required": ["path"],
        },
        handler=file_info,
        requires_permission=False,
    ),
    "execute_shell": ToolDefinition(
        name="execute_shell",
        description="Execute a shell command (PowerShell on Windows, bash on Linux). Dangerous commands are blocked. Returns full stdout/stderr output.",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
                "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 300},
            },
            "required": ["command"],
        },
        handler=execute_shell,
        requires_permission=True,
    ),
    "open_app": ToolDefinition(
        name="open_app",
        description="Open an application or URL. Examples: 'msedge', 'chrome', 'notepad', 'https://youtube.com'. On Windows uses Start-Process.",
        parameters={
            "type": "object",
            "properties": {
                "app_name": {"type": "string", "description": "Application name, path, or URL to open"},
                "arguments": {"type": "string", "description": "Optional arguments (e.g., URL to open in browser)", "default": ""},
            },
            "required": ["app_name"],
        },
        handler=open_app,
        requires_permission=True,
    ),
    "cron_schedule": ToolDefinition(
        name="cron_schedule",
        description="Schedule a RECURRING task using cron expression. Format: 'minute hour day month weekday'. Examples: '0 * * * *' (every hour), '0 9 * * 1' (every Monday 9am), '30 8 * * *' (daily 8:30am). For ONE-TIME scheduling use schedule_once instead.",
        parameters={
            "type": "object",
            "properties": {
                "task_name": {"type": "string", "description": "Name for the scheduled task"},
                "cron_expression": {"type": "string", "description": "Cron expression (5 fields: min hour day month weekday)"},
                "commands": {"type": "array", "items": {"type": "string"}, "description": "List of shell commands to execute"},
            },
            "required": ["task_name", "cron_expression", "commands"],
        },
        handler=cron_schedule,
        requires_permission=True,
    ),
    "schedule_once": ToolDefinition(
        name="schedule_once",
        description="Schedule a ONE-TIME task at a specific datetime. Use this when user wants something done at a specific time (not recurring). run_at format: 'YYYY-MM-DDTHH:MM:SS' (e.g., '2026-06-05T21:18:00' for today at 21:18).",
        parameters={
            "type": "object",
            "properties": {
                "task_name": {"type": "string", "description": "Name for the scheduled task"},
                "run_at": {"type": "string", "description": "ISO datetime to run (YYYY-MM-DDTHH:MM:SS)"},
                "commands": {"type": "array", "items": {"type": "string"}, "description": "List of shell commands to execute"},
            },
            "required": ["task_name", "run_at", "commands"],
        },
        handler=schedule_once,
        requires_permission=True,
    ),
    "store_memory": ToolDefinition(
        name="store_memory",
        description="Store information in long-term memory for future recall. Types: fact, preference, task, decision, error.",
        parameters={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Memory content"},
                "memory_type": {"type": "string", "description": "Memory type", "default": "fact"},
                "metadata": {"type": "object", "description": "Optional metadata"},
            },
            "required": ["content"],
        },
        handler=store_memory,
        requires_permission=False,
    ),
    "search_memory": ToolDefinition(
        name="search_memory",
        description="Search long-term memory for relevant information.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "description": "Max results", "default": 10},
            },
            "required": ["query"],
        },
        handler=search_memory,
        requires_permission=False,
    ),
    "system_info": ToolDefinition(
        name="system_info",
        description="Get system information (OS, Python, hostname, user, cwd).",
        parameters={"type": "object", "properties": {}},
        handler=system_info,
        requires_permission=False,
    ),
    "current_time": ToolDefinition(
        name="current_time",
        description="Get current date and time.",
        parameters={"type": "object", "properties": {}},
        handler=current_time,
        requires_permission=False,
    ),
    "web_search": ToolDefinition(
        name="web_search",
        description="Search the web using DuckDuckGo. Returns titles and URLs. Use when user asks to search for something online.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "description": "Max results to return", "default": 5},
            },
            "required": ["query"],
        },
        handler=web_search,
        requires_permission=False,
    ),
    "youtube_search": ToolDefinition(
        name="youtube_search",
        description="Search YouTube for videos. Returns numbered list with titles and URLs. ALWAYS use this tool when user asks to search YouTube, find videos, or look for channels. Present results to user and ask which one to open BEFORE using open_app.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "description": "Max results to return", "default": 5},
            },
            "required": ["query"],
        },
        handler=youtube_search,
        requires_permission=False,
    ),
    "screenshot": ToolDefinition(
        name="screenshot",
        description="Take a screenshot of the current screen and save it as PNG.",
        parameters={
            "type": "object",
            "properties": {
                "save_path": {"type": "string", "description": "Path to save screenshot (default: Desktop/screenshot_TIMESTAMP.png)"},
            },
        },
        handler=screenshot,
        requires_permission=True,
    ),
    "clipboard_get": ToolDefinition(
        name="clipboard_get",
        description="Get the current text content from the system clipboard.",
        parameters={"type": "object", "properties": {}},
        handler=clipboard_get,
        requires_permission=False,
    ),
    "clipboard_set": ToolDefinition(
        name="clipboard_set",
        description="Set text content to the system clipboard.",
        parameters={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Text to copy to clipboard"},
            },
            "required": ["content"],
        },
        handler=clipboard_set,
        requires_permission=False,
    ),
    "process_list": ToolDefinition(
        name="process_list",
        description="List running processes sorted by memory usage. Can filter by name.",
        parameters={
            "type": "object",
            "properties": {
                "filter_name": {"type": "string", "description": "Filter processes by name (optional)", "default": ""},
                "limit": {"type": "integer", "description": "Max processes to show", "default": 20},
            },
        },
        handler=process_list,
        requires_permission=False,
    ),
    "kill_process": ToolDefinition(
        name="kill_process",
        description="Kill/terminate a running process by name or PID.",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Process name to kill", "default": ""},
                "pid": {"type": "integer", "description": "Process ID to kill", "default": 0},
            },
        },
        handler=kill_process,
        requires_permission=True,
    ),
    "send_notification": ToolDefinition(
        name="send_notification",
        description="Send a desktop notification with title and message. Duration in seconds (default: 5).",
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Notification title"},
                "message": {"type": "string", "description": "Notification message"},
                "duration": {"type": "integer", "description": "Display duration in seconds", "default": 5},
            },
            "required": ["title", "message"],
        },
        handler=send_notification,
        requires_permission=True,
    ),
    "system_stats": ToolDefinition(
        name="system_stats",
        description="Get current system statistics: CPU usage, memory usage, disk usage.",
        parameters={"type": "object", "properties": {}},
        handler=system_stats,
        requires_permission=False,
    ),
    "download_file": ToolDefinition(
        name="download_file",
        description="Download a file from URL. Saves to Downloads folder by default, or specify save_path.",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to download from"},
                "save_path": {"type": "string", "description": "Path to save file (optional, defaults to Downloads folder)"},
            },
            "required": ["url"],
        },
        handler=download_file,
        requires_permission=True,
    ),
    "find_file": ToolDefinition(
        name="find_file",
        description="Find files matching a pattern (e.g., '*.txt', 'report*.pdf') in a directory.",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "File pattern to search for (e.g., '*.txt', 'report*.pdf')"},
                "directory": {"type": "string", "description": "Directory to search in", "default": "."},
                "max_results": {"type": "integer", "description": "Maximum number of results", "default": 20},
            },
            "required": ["pattern"],
        },
        handler=find_file,
        requires_permission=False,
    ),
    "web_scrape": ToolDefinition(
        name="web_scrape",
        description="Scrape and extract text content from a web page. Removes HTML tags, scripts, and styles. Useful for reading articles or documentation.",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to scrape"},
                "max_chars": {"type": "integer", "description": "Maximum characters to return", "default": 10000},
            },
            "required": ["url"],
        },
        handler=web_scrape,
        requires_permission=False,
    ),
}


def get_tools_schema() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }
        for tool in TOOL_REGISTRY.values()
    ]
