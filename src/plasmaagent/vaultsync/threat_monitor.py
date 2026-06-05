from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Optional


@dataclass
class ThreatEvent:
    timestamp: datetime
    event_type: str
    severity: str
    description: str
    file_count: int = 0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ThreatReport:
    start_time: datetime
    end_time: datetime
    events: list[ThreatEvent] = field(default_factory=list)
    risk_score: float = 0.0
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "risk_score": round(self.risk_score, 2),
            "events_count": len(self.events),
            "events": [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "event_type": e.event_type,
                    "severity": e.severity,
                    "description": e.description,
                    "file_count": e.file_count,
                    "details": e.details,
                }
                for e in self.events
            ],
        }


class ThreatMonitor:
    """Behavior-based threat detection for ransomware and malware."""
    
    MASS_MODIFICATION_THRESHOLD = 50
    MASS_MODIFICATION_WINDOW = 60
    EXTENSION_CHANGE_THRESHOLD = 20
    DELETION_THRESHOLD = 30
    SUSPICIOUS_EXTENSIONS = {".encrypted", ".locked", ".crypto", ".crypted", ".crypt"}
    
    def __init__(self, watch_directories: Optional[list[Path]] = None):
        self._watch_dirs = watch_directories or [Path.home()]
        self._events: list[ThreatEvent] = []
        self._file_modifications: dict[str, datetime] = {}
        self._extension_changes: dict[str, datetime] = {}
        self._deletions: dict[str, datetime] = {}
        self._monitoring = False
        self._callbacks: list[Callable[[ThreatEvent], None]] = []
    
    def add_callback(self, callback: Callable[[ThreatEvent], None]) -> None:
        """Add a callback to be called when a threat is detected."""
        self._callbacks.append(callback)
    
    async def start_monitoring(self, interval: int = 5) -> None:
        """Start monitoring for threats."""
        self._monitoring = True
        
        while self._monitoring:
            await self._scan_directories()
            await asyncio.sleep(interval)
    
    def stop_monitoring(self) -> None:
        """Stop monitoring."""
        self._monitoring = False
    
    async def _scan_directories(self) -> None:
        """Scan watched directories for suspicious activity."""
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=self.MASS_MODIFICATION_WINDOW)
        
        for watch_dir in self._watch_dirs:
            if not watch_dir.exists():
                continue
            
            try:
                await self._scan_directory(watch_dir, cutoff)
            except Exception:
                continue
    
    async def _scan_directory(self, directory: Path, cutoff: datetime) -> None:
        """Scan a single directory for suspicious patterns."""
        recent_modifications = 0
        recent_extension_changes = 0
        recent_deletions = 0
        
        try:
            for item in directory.rglob("*"):
                if item.is_file():
                    try:
                        mtime = datetime.fromtimestamp(item.stat().st_mtime)
                        if mtime >= cutoff:
                            recent_modifications += 1
                            
                            if item.suffix.lower() in self.SUSPICIOUS_EXTENSIONS:
                                recent_extension_changes += 1
                    except (OSError, PermissionError):
                        continue
        except (OSError, PermissionError):
            return
        
        if recent_modifications >= self.MASS_MODIFICATION_THRESHOLD:
            event = ThreatEvent(
                timestamp=datetime.utcnow(),
                event_type="MASS_FILE_MODIFICATION",
                severity="HIGH",
                description=f"{recent_modifications} files modified in {self.MASS_MODIFICATION_WINDOW}s",
                file_count=recent_modifications,
                details={"directory": str(directory)},
            )
            self._events.append(event)
            await self._trigger_callbacks(event)
        
        if recent_extension_changes >= self.EXTENSION_CHANGE_THRESHOLD:
            event = ThreatEvent(
                timestamp=datetime.utcnow(),
                event_type="SUSPICIOUS_EXTENSION_CHANGE",
                severity="CRITICAL",
                description=f"{recent_extension_changes} files with suspicious extensions",
                file_count=recent_extension_changes,
                details={"directory": str(directory), "extensions": list(self.SUSPICIOUS_EXTENSIONS)},
            )
            self._events.append(event)
            await self._trigger_callbacks(event)
    
    async def _trigger_callbacks(self, event: ThreatEvent) -> None:
        """Trigger all registered callbacks."""
        for callback in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception:
                continue
    
    def get_report(self, hours: int = 24) -> ThreatReport:
        """Get threat report for the specified time period."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        filtered_events = [e for e in self._events if e.timestamp >= cutoff]
        
        risk_score = 0.0
        for event in filtered_events:
            if event.severity == "CRITICAL":
                risk_score += 50.0
            elif event.severity == "HIGH":
                risk_score += 30.0
            elif event.severity == "MEDIUM":
                risk_score += 15.0
            else:
                risk_score += 5.0
        
        return ThreatReport(
            start_time=cutoff,
            end_time=datetime.utcnow(),
            events=filtered_events,
            risk_score=min(risk_score, 100.0),
        )
    
    def clear_events(self) -> None:
        """Clear all recorded events."""
        self._events.clear()
