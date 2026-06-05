"""System information and process management tools for PlasmaAgent."""

from __future__ import annotations

import os
import platform
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ToolResult:
    success: bool
    output: str
    data: Any = None


async def system_info() -> ToolResult:
    info = {
        "os": platform.system(),
        "os_version": platform.version(),
        "os_release": platform.release(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "hostname": platform.node(),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "user": os.environ.get("USERNAME") or os.environ.get("USER") or "Unknown",
        "cwd": os.getcwd(),
    }
    return ToolResult(True, f"System: {info['os']} {info['os_release']}", info)


async def current_time() -> ToolResult:
    now = datetime.now()
    utc_now = datetime.utcnow()
    info = {
        "local": now.isoformat(),
        "utc": utc_now.isoformat(),
        "timezone": str(now.astimezone().tzinfo),
        "timestamp": int(now.timestamp()),
    }
    return ToolResult(True, now.strftime("%Y-%m-%d %H:%M:%S"), info)


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
        
        return ToolResult(
            True,
            f"CPU: {cpu_percent}%, RAM: {memory.percent}%, Disk: {disk.percent}%",
            stats,
        )
    except ImportError:
        return ToolResult(False, "psutil not installed. Run: pip install psutil")
    except Exception as e:
        return ToolResult(False, f"Failed to get stats: {e}")


async def process_list(filter_name: str = "", limit: int = 20) -> ToolResult:
    try:
        import psutil
        
        processes = []
        for proc in psutil.process_iter(["pid", "name", "memory_info"]):
            try:
                info = proc.info
                if filter_name and filter_name.lower() not in info["name"].lower():
                    continue
                processes.append({
                    "pid": info["pid"],
                    "name": info["name"],
                    "memory_mb": round(info["memory_info"].rss / (1024 * 1024), 2),
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        processes.sort(key=lambda x: x["memory_mb"], reverse=True)
        processes = processes[:limit]
        
        return ToolResult(
            True,
            f"Found {len(processes)} processes",
            {"processes": processes},
        )
    except ImportError:
        return ToolResult(False, "psutil not installed. Run: pip install psutil")
    except Exception as e:
        return ToolResult(False, f"Failed to list processes: {e}")


async def kill_process(name: str = "", pid: int = 0) -> ToolResult:
    try:
        import psutil
        
        if pid > 0:
            try:
                proc = psutil.Process(pid)
                proc_name = proc.name()
                proc.terminate()
                return ToolResult(True, f"Killed process {proc_name} (PID: {pid})")
            except psutil.NoSuchProcess:
                return ToolResult(False, f"Process with PID {pid} not found")
            except psutil.AccessDenied:
                return ToolResult(False, f"Access denied to kill PID {pid}")
        
        if name:
            killed = []
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    if name.lower() in proc.info["name"].lower():
                        proc.terminate()
                        killed.append(f"{proc.info['name']} (PID: {proc.info['pid']})")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            if killed:
                return ToolResult(True, f"Killed {len(killed)} processes: {', '.join(killed)}")
            return ToolResult(False, f"No processes found matching '{name}'")
        
        return ToolResult(False, "Specify either 'name' or 'pid' to kill a process")
    except ImportError:
        return ToolResult(False, "psutil not installed. Run: pip install psutil")
    except Exception as e:
        return ToolResult(False, f"Failed to kill process: {e}")
