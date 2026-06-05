from __future__ import annotations

import os
import hashlib
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend


class EncryptionEngine:
    """AES-256-GCM encryption engine with zero-knowledge key derivation."""
    
    SALT_SIZE = 32
    KEY_SIZE = 32
    NONCE_SIZE = 12
    ITERATIONS = 480000
    
    def __init__(self, recovery_key: Optional[str] = None):
        self._recovery_key = recovery_key
        self._encryption_key: Optional[bytes] = None
    
    def generate_recovery_key(self) -> str:
        """Generate a new recovery key (format: XXXX-XXXX-XXXX-XXXX)."""
        random_bytes = os.urandom(16)
        hex_str = random_bytes.hex().upper()
        return f"{hex_str[0:4]}-{hex_str[4:8]}-{hex_str[8:12]}-{hex_str[12:16]}"
    
    def derive_key(self, recovery_key: str, salt: bytes) -> bytes:
        """Derive encryption key from recovery key using PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.KEY_SIZE,
            salt=salt,
            iterations=self.ITERATIONS,
            backend=default_backend(),
        )
        return kdf.derive(recovery_key.encode("utf-8"))
    
    def encrypt_file(self, file_path: Path, output_path: Path) -> bytes:
        """Encrypt a file and return the salt used."""
        if not self._recovery_key:
            raise ValueError("Recovery key not set")
        
        salt = os.urandom(self.SALT_SIZE)
        key = self.derive_key(self._recovery_key, salt)
        nonce = os.urandom(self.NONCE_SIZE)
        
        aesgcm = AESGCM(key)
        
        with open(file_path, "rb") as f:
            plaintext = f.read()
        
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        
        with open(output_path, "wb") as f:
            f.write(salt)
            f.write(nonce)
            f.write(ciphertext)
        
        return salt
    
    def decrypt_file(self, encrypted_path: Path, output_path: Path) -> None:
        """Decrypt a file."""
        if not self._recovery_key:
            raise ValueError("Recovery key not set")
        
        with open(encrypted_path, "rb") as f:
            salt = f.read(self.SALT_SIZE)
            nonce = f.read(self.NONCE_SIZE)
            ciphertext = f.read()
        
        key = self.derive_key(self._recovery_key, salt)
        aesgcm = AESGCM(key)
        
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(plaintext)
    
    def encrypt_bytes(self, data: bytes) -> tuple[bytes, bytes, bytes]:
        """Encrypt bytes and return (salt, nonce, ciphertext)."""
        if not self._recovery_key:
            raise ValueError("Recovery key not set")
        
        salt = os.urandom(self.SALT_SIZE)
        key = self.derive_key(self._recovery_key, salt)
        nonce = os.urandom(self.NONCE_SIZE)
        
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, data, None)
        
        return salt, nonce, ciphertext
    
    def decrypt_bytes(self, salt: bytes, nonce: bytes, ciphertext: bytes) -> bytes:
        """Decrypt bytes."""
        if not self._recovery_key:
            raise ValueError("Recovery key not set")
        
        key = self.derive_key(self._recovery_key, salt)
        aesgcm = AESGCM(key)
        
        return aesgcm.decrypt(nonce, ciphertext, None)
    
    def hash_file(self, file_path: Path) -> str:
        """Generate SHA-256 hash of a file for deduplication."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def set_recovery_key(self, recovery_key: str) -> None:
        """Set the recovery key for encryption/decryption."""
        self._recovery_key = recovery_key
