from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from plasmaagent.vaultsync.encryption_engine import EncryptionEngine
from plasmaagent.vaultsync.backup_engine import BackupMetadata


@dataclass
class RecoveryResult:
    success: bool
    message: str
    files_restored: int = 0
    restore_path: Optional[str] = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "files_restored": self.files_restored,
            "restore_path": self.restore_path,
        }


class RecoveryEngine:
    """Recovery engine for restoring from backups."""
    
    def __init__(self, encryption_engine: EncryptionEngine, backup_dir: Optional[Path] = None):
        self._encryption = encryption_engine
        self._backup_dir = backup_dir or Path.home() / ".plasmaagent" / "vaultsync" / "backups"
    
    async def restore_backup(
        self,
        backup_id: str,
        restore_path: Optional[Path] = None,
        overwrite: bool = False,
    ) -> RecoveryResult:
        """Restore a backup to the specified path."""
        backup_path = self._backup_dir / backup_id
        metadata_file = backup_path / "metadata.json"
        
        if not metadata_file.exists():
            return RecoveryResult(
                success=False,
                message=f"Backup not found: {backup_id}",
            )
        
        try:
            with open(metadata_file) as f:
                metadata_dict = json.load(f)
            
            metadata = BackupMetadata(
                backup_id=metadata_dict["backup_id"],
                backup_type=metadata_dict["backup_type"],
                created_at=datetime.fromisoformat(metadata_dict["created_at"]),
                source_path=metadata_dict["source_path"],
                total_files=metadata_dict["total_files"],
                total_size_bytes=metadata_dict["total_size_bytes"],
                encrypted=metadata_dict.get("encrypted", False),
                compressed=metadata_dict.get("compressed", True),
                file_hashes=metadata_dict.get("file_hashes", {}),
                metadata_path=str(metadata_file),
            )
            
            if restore_path is None:
                restore_path = Path(metadata.source_path)
            
            if restore_path.exists() and not overwrite:
                return RecoveryResult(
                    success=False,
                    message=f"Restore path exists: {restore_path}. Use overwrite=True to replace.",
                )
            
            temp_dir = Path(tempfile.mkdtemp())
            
            try:
                if metadata.compressed:
                    archive_path = backup_path / "backup.zip"
                    
                    if metadata.encrypted:
                        encrypted_path = backup_path / "backup.zip.enc"
                        if not encrypted_path.exists():
                            return RecoveryResult(
                                success=False,
                                message="Encrypted backup file not found",
                            )
                        self._encryption.decrypt_file(encrypted_path, archive_path)
                    
                    if not archive_path.exists():
                        return RecoveryResult(
                            success=False,
                            message="Backup archive not found",
                        )
                    
                    with zipfile.ZipFile(archive_path, "r") as zf:
                        zf.extractall(temp_dir)
                    
                    if metadata.encrypted and archive_path.exists():
                        archive_path.unlink()
                else:
                    for item in backup_path.iterdir():
                        if item.name != "metadata.json" and item.is_file():
                            dest = temp_dir / item.name
                            if metadata.encrypted:
                                self._encryption.decrypt_file(item, dest)
                            else:
                                shutil.copy2(item, dest)
                
                files_restored = 0
                restore_path.mkdir(parents=True, exist_ok=True)
                
                for item in temp_dir.rglob("*"):
                    if item.is_file():
                        rel_path = item.relative_to(temp_dir)
                        dest = restore_path / rel_path
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(item, dest)
                        files_restored += 1
                
                return RecoveryResult(
                    success=True,
                    message=f"Restored {files_restored} files to {restore_path}",
                    files_restored=files_restored,
                    restore_path=str(restore_path),
                )
            
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)
        
        except Exception as e:
            return RecoveryResult(
                success=False,
                message=f"Restore failed: {e}",
            )
    
    async def restore_file(
        self,
        backup_id: str,
        file_path: str,
        restore_path: Optional[Path] = None,
    ) -> RecoveryResult:
        """Restore a single file from a backup."""
        backup_path = self._backup_dir / backup_id
        metadata_file = backup_path / "metadata.json"
        
        if not metadata_file.exists():
            return RecoveryResult(
                success=False,
                message=f"Backup not found: {backup_id}",
            )
        
        try:
            with open(metadata_file) as f:
                metadata_dict = json.load(f)
            
            metadata = BackupMetadata(
                backup_id=metadata_dict["backup_id"],
                backup_type=metadata_dict["backup_type"],
                created_at=datetime.fromisoformat(metadata_dict["created_at"]),
                source_path=metadata_dict["source_path"],
                total_files=metadata_dict["total_files"],
                total_size_bytes=metadata_dict["total_size_bytes"],
                encrypted=metadata_dict.get("encrypted", False),
                compressed=metadata_dict.get("compressed", True),
                file_hashes=metadata_dict.get("file_hashes", {}),
                metadata_path=str(metadata_file),
            )
            
            if file_path not in metadata.file_hashes:
                return RecoveryResult(
                    success=False,
                    message=f"File not found in backup: {file_path}",
                )
            
            if restore_path is None:
                restore_path = Path(file_path)
            
            temp_dir = Path(tempfile.mkdtemp())
            
            try:
                if metadata.compressed:
                    archive_path = backup_path / "backup.zip"
                    
                    if metadata.encrypted:
                        encrypted_path = backup_path / "backup.zip.enc"
                        self._encryption.decrypt_file(encrypted_path, archive_path)
                    
                    with zipfile.ZipFile(archive_path, "r") as zf:
                        zf.extract(file_path, temp_dir)
                    
                    if metadata.encrypted and archive_path.exists():
                        archive_path.unlink()
                
                extracted_file = temp_dir / file_path
                if not extracted_file.exists():
                    return RecoveryResult(
                        success=False,
                        message=f"File not found in archive: {file_path}",
                    )
                
                restore_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(extracted_file, restore_path)
                
                return RecoveryResult(
                    success=True,
                    message=f"Restored file to {restore_path}",
                    files_restored=1,
                    restore_path=str(restore_path),
                )
            
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)
        
        except Exception as e:
            return RecoveryResult(
                success=False,
                message=f"File restore failed: {e}",
            )
