from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import select, func

from plasmaagent.core.database import Database
from plasmaagent.vaultsync.encryption_engine import EncryptionEngine


@dataclass
class BackupMetadata:
    backup_id: str
    backup_type: str
    created_at: datetime
    source_path: str
    total_files: int
    total_size_bytes: int
    encrypted: bool
    compressed: bool
    file_hashes: dict[str, str] = field(default_factory=dict)
    metadata_path: Optional[str] = None


@dataclass
class BackupResult:
    success: bool
    backup_id: str
    message: str
    metadata: Optional[BackupMetadata] = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "backup_id": self.backup_id,
            "message": self.message,
            "metadata": {
                "backup_id": self.metadata.backup_id,
                "backup_type": self.metadata.backup_type,
                "created_at": self.metadata.created_at.isoformat(),
                "source_path": self.metadata.source_path,
                "total_files": self.metadata.total_files,
                "total_size_bytes": self.metadata.total_size_bytes,
                "encrypted": self.metadata.encrypted,
                "compressed": self.metadata.compressed,
            } if self.metadata else None,
        }


class BackupEngine:
    """Backup engine with deduplication, compression, and encryption."""
    
    def __init__(self, db: Database, encryption_engine: EncryptionEngine, backup_dir: Optional[Path] = None):
        self._db = db
        self._encryption = encryption_engine
        self._backup_dir = backup_dir or Path.home() / ".plasmaagent" / "vaultsync" / "backups"
        self._backup_dir.mkdir(parents=True, exist_ok=True)
    
    async def create_snapshot(
        self,
        source_path: Path,
        backup_type: str = "snapshot",
        compress: bool = True,
        encrypt: bool = True,
    ) -> BackupResult:
        """Create an instant snapshot of a directory."""
        backup_id = str(uuid4())
        backup_path = self._backup_dir / backup_id
        
        try:
            backup_path.mkdir(parents=True, exist_ok=True)
            
            files = list(source_path.rglob("*"))
            files = [f for f in files if f.is_file()]
            
            file_hashes: dict[str, str] = {}
            total_size = 0
            processed_files = 0
            
            temp_dir = Path(tempfile.mkdtemp())
            
            try:
                for file_path in files:
                    try:
                        rel_path = file_path.relative_to(source_path)
                        file_hash = self._encryption.hash_file(file_path)
                        
                        if file_hash in file_hashes.values():
                            continue
                        
                        dest_path = temp_dir / rel_path
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(file_path, dest_path)
                        
                        file_hashes[str(rel_path)] = file_hash
                        total_size += file_path.stat().st_size
                        processed_files += 1
                    except (OSError, PermissionError):
                        continue
                
                if compress:
                    archive_path = backup_path / "backup.zip"
                    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
                        for file_path in temp_dir.rglob("*"):
                            if file_path.is_file():
                                arcname = file_path.relative_to(temp_dir)
                                zf.write(file_path, arcname)
                    
                    if encrypt:
                        encrypted_path = backup_path / "backup.zip.enc"
                        self._encryption.encrypt_file(archive_path, encrypted_path)
                        archive_path.unlink()
                
                metadata = BackupMetadata(
                    backup_id=backup_id,
                    backup_type=backup_type,
                    created_at=datetime.utcnow(),
                    source_path=str(source_path),
                    total_files=processed_files,
                    total_size_bytes=total_size,
                    encrypted=encrypt,
                    compressed=compress,
                    file_hashes=file_hashes,
                    metadata_path=str(backup_path / "metadata.json"),
                )
                
                with open(backup_path / "metadata.json", "w") as f:
                    json.dump({
                        "backup_id": metadata.backup_id,
                        "backup_type": metadata.backup_type,
                        "created_at": metadata.created_at.isoformat(),
                        "source_path": metadata.source_path,
                        "total_files": metadata.total_files,
                        "total_size_bytes": metadata.total_size_bytes,
                        "encrypted": metadata.encrypted,
                        "compressed": metadata.compressed,
                        "file_hashes": metadata.file_hashes,
                    }, f, indent=2)
                
                await self._save_backup_to_db(metadata)
                
                return BackupResult(
                    success=True,
                    backup_id=backup_id,
                    message=f"Snapshot created: {processed_files} files, {total_size} bytes",
                    metadata=metadata,
                )
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)
        
        except Exception as e:
            if backup_path.exists():
                shutil.rmtree(backup_path, ignore_errors=True)
            return BackupResult(
                success=False,
                backup_id=backup_id,
                message=f"Backup failed: {e}",
            )
    
    async def _save_backup_to_db(self, metadata: BackupMetadata) -> None:
        """Save backup metadata to database."""
        from plasmaagent.core.schema import Base
        from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text
        from sqlalchemy.dialects.sqlite import JSON
        
        class BackupRecord(Base):
            __tablename__ = "vaultsync_backups"
            
            id = Column(String, primary_key=True)
            backup_type = Column(String, nullable=False)
            created_at = Column(DateTime, nullable=False)
            source_path = Column(Text, nullable=False)
            total_files = Column(Integer, nullable=False)
            total_size_bytes = Column(Integer, nullable=False)
            encrypted = Column(Boolean, default=False)
            compressed = Column(Boolean, default=True)
            file_hashes = Column(JSON, nullable=False)
            metadata_path = Column(Text, nullable=True)
        
        async with self._db.session() as session:
            async with session.begin():
                await session.run_sync(
                    lambda s: s.connection().exec_driver_sql(
                        "CREATE TABLE IF NOT EXISTS vaultsync_backups ("
                        "id TEXT PRIMARY KEY, "
                        "backup_type TEXT NOT NULL, "
                        "created_at TIMESTAMP NOT NULL, "
                        "source_path TEXT NOT NULL, "
                        "total_files INTEGER NOT NULL, "
                        "total_size_bytes INTEGER NOT NULL, "
                        "encrypted BOOLEAN DEFAULT 0, "
                        "compressed BOOLEAN DEFAULT 1, "
                        "file_hashes JSON NOT NULL, "
                        "metadata_path TEXT"
                        ")"
                    )
                )
                
                await session.run_sync(
                    lambda s: s.connection().exec_driver_sql(
                        "INSERT INTO vaultsync_backups "
                        "(id, backup_type, created_at, source_path, total_files, total_size_bytes, "
                        "encrypted, compressed, file_hashes, metadata_path) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            metadata.backup_id,
                            metadata.backup_type,
                            metadata.created_at,
                            metadata.source_path,
                            metadata.total_files,
                            metadata.total_size_bytes,
                            1 if metadata.encrypted else 0,
                            1 if metadata.compressed else 0,
                            json.dumps(metadata.file_hashes),
                            metadata.metadata_path,
                        ),
                    )
                )
    
    async def list_backups(self, limit: int = 50) -> list[BackupMetadata]:
        """List all backups."""
        backups = []
        
        for backup_dir in self._backup_dir.iterdir():
            if backup_dir.is_dir():
                metadata_file = backup_dir / "metadata.json"
                if metadata_file.exists():
                    try:
                        with open(metadata_file) as f:
                            data = json.load(f)
                        backups.append(BackupMetadata(
                            backup_id=data["backup_id"],
                            backup_type=data["backup_type"],
                            created_at=datetime.fromisoformat(data["created_at"]),
                            source_path=data["source_path"],
                            total_files=data["total_files"],
                            total_size_bytes=data["total_size_bytes"],
                            encrypted=data.get("encrypted", False),
                            compressed=data.get("compressed", True),
                            file_hashes=data.get("file_hashes", {}),
                            metadata_path=str(metadata_file),
                        ))
                    except Exception:
                        continue
        
        backups.sort(key=lambda x: x.created_at, reverse=True)
        return backups[:limit]
    
    async def delete_backup(self, backup_id: str) -> bool:
        """Delete a backup."""
        backup_path = self._backup_dir / backup_id
        if backup_path.exists():
            shutil.rmtree(backup_path, ignore_errors=True)
            
            async with self._db.session() as session:
                await session.run_sync(
                    lambda s: s.connection().exec_driver_sql(
                        "DELETE FROM vaultsync_backups WHERE id = ?",
                        (backup_id,),
                    )
                )
                await session.commit()
            
            return True
        return False
