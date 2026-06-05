"""VaultSync backup and recovery tools for PlasmaAgent."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from plasmaagent.tools.file_ops import ToolResult


async def vault_backup(
    source_path: str,
    backup_type: str = "snapshot",
    compress: bool = True,
    encrypt: bool = True,
    recovery_key: str = "",
) -> ToolResult:
    """Create a backup of the specified directory."""
    try:
        from plasmaagent.core.database import get_database
        from plasmaagent.vaultsync.encryption_engine import EncryptionEngine
        from plasmaagent.vaultsync.backup_engine import BackupEngine
        
        db = get_database()
        await db.connect()
        
        encryption = EncryptionEngine()
        if recovery_key:
            encryption.set_recovery_key(recovery_key)
        else:
            recovery_key = encryption.generate_recovery_key()
            encryption.set_recovery_key(recovery_key)
        
        backup_engine = BackupEngine(db, encryption)
        result = await backup_engine.create_snapshot(
            Path(source_path),
            backup_type=backup_type,
            compress=compress,
            encrypt=encrypt,
        )
        
        await db.disconnect()
        
        output_lines = [
            f"{'✓' if result.success else '✗'} Backup {'Successful' if result.success else 'Failed'}",
            f"Backup ID: {result.backup_id}",
            f"Message: {result.message}",
        ]
        
        if result.success and encrypt:
            output_lines.extend([
                "",
                f"⚠️  IMPORTANT: Save this recovery key securely:",
                f"   {recovery_key}",
                "",
                "Without this key, you cannot decrypt your backups.",
            ])
        
        return ToolResult(
            result.success,
            "\n".join(output_lines),
            {**result.to_dict(), "recovery_key": recovery_key if encrypt else None},
        )
    except Exception as e:
        return ToolResult(False, f"Backup failed: {e}")


async def vault_restore(
    backup_id: str,
    restore_path: str = "",
    overwrite: bool = False,
    recovery_key: str = "",
) -> ToolResult:
    """Restore a backup."""
    try:
        from plasmaagent.vaultsync.encryption_engine import EncryptionEngine
        from plasmaagent.vaultsync.recovery_engine import RecoveryEngine
        
        encryption = EncryptionEngine()
        if recovery_key:
            encryption.set_recovery_key(recovery_key)
        
        recovery_engine = RecoveryEngine(encryption)
        
        result = await recovery_engine.restore_backup(
            backup_id,
            Path(restore_path) if restore_path else None,
            overwrite=overwrite,
        )
        
        return ToolResult(
            result.success,
            result.message,
            result.to_dict(),
        )
    except Exception as e:
        return ToolResult(False, f"Restore failed: {e}")


async def vault_list_backups(limit: int = 50) -> ToolResult:
    """List all available backups."""
    try:
        from plasmaagent.core.database import get_database
        from plasmaagent.vaultsync.encryption_engine import EncryptionEngine
        from plasmaagent.vaultsync.backup_engine import BackupEngine
        
        db = get_database()
        await db.connect()
        
        encryption = EncryptionEngine()
        backup_engine = BackupEngine(db, encryption)
        backups = await backup_engine.list_backups(limit)
        
        await db.disconnect()
        
        if not backups:
            return ToolResult(True, "No backups found", {"backups": []})
        
        output_lines = [f"Found {len(backups)} backups:", ""]
        for backup in backups:
            output_lines.extend([
                f"ID: {backup.backup_id}",
                f"  Type: {backup.backup_type}",
                f"  Created: {backup.created_at.isoformat()}",
                f"  Source: {backup.source_path}",
                f"  Files: {backup.total_files}",
                f"  Size: {backup.total_size_bytes:,} bytes",
                f"  Encrypted: {backup.encrypted}",
                f"  Compressed: {backup.compressed}",
                "",
            ])
        
        return ToolResult(
            True,
            "\n".join(output_lines),
            {"backups": [
                {
                    "backup_id": b.backup_id,
                    "backup_type": b.backup_type,
                    "created_at": b.created_at.isoformat(),
                    "source_path": b.source_path,
                    "total_files": b.total_files,
                    "total_size_bytes": b.total_size_bytes,
                    "encrypted": b.encrypted,
                    "compressed": b.compressed,
                }
                for b in backups
            ]},
        )
    except Exception as e:
        return ToolResult(False, f"Failed to list backups: {e}")


async def vault_delete_backup(backup_id: str) -> ToolResult:
    """Delete a backup."""
    try:
        from plasmaagent.core.database import get_database
        from plasmaagent.vaultsync.encryption_engine import EncryptionEngine
        from plasmaagent.vaultsync.backup_engine import BackupEngine
        
        db = get_database()
        await db.connect()
        
        encryption = EncryptionEngine()
        backup_engine = BackupEngine(db, encryption)
        success = await backup_engine.delete_backup(backup_id)
        
        await db.disconnect()
        
        if success:
            return ToolResult(True, f"Backup deleted: {backup_id}")
        return ToolResult(False, f"Backup not found: {backup_id}")
    except Exception as e:
        return ToolResult(False, f"Failed to delete backup: {e}")


async def vault_generate_recovery_key() -> ToolResult:
    """Generate a new recovery key."""
    try:
        from plasmaagent.vaultsync.encryption_engine import EncryptionEngine
        
        encryption = EncryptionEngine()
        recovery_key = encryption.generate_recovery_key()
        
        return ToolResult(
            True,
            f"Recovery Key: {recovery_key}\n\n⚠️  Save this key securely. You need it to decrypt backups.",
            {"recovery_key": recovery_key},
        )
    except Exception as e:
        return ToolResult(False, f"Failed to generate recovery key: {e}")
