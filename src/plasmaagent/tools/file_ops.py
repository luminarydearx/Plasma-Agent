"""File operation tools for PlasmaAgent."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ToolResult:
    success: bool
    output: str
    data: Any = None


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


async def find_file(pattern: str, directory: str = ".", max_results: int = 20) -> ToolResult:
    target = Path(directory).expanduser().resolve()
    if not _is_safe(target):
        return ToolResult(False, f"Access denied: {target}")
    if not target.exists():
        return ToolResult(False, f"Directory not found: {target}")
    if not target.is_dir():
        return ToolResult(False, f"Not a directory: {target}")
    
    matches = []
    for item in target.rglob(pattern):
        if item.name.startswith("."):
            continue
        matches.append({
            "path": str(item),
            "name": item.name,
            "size": item.stat().st_size if item.is_file() else 0,
        })
        if len(matches) >= max_results:
            break
    
    return ToolResult(
        True,
        f"Found {len(matches)} files matching '{pattern}'",
        {"matches": matches},
    )
