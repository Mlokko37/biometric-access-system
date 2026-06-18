import os
import hashlib
from datetime import datetime

def generate_hash(data: bytes) -> str:
    """Generate SHA256 hash for data."""
    return hashlib.sha256(data).hexdigest()

def get_timestamp() -> str:
    """Get current timestamp string."""
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def ensure_directory(path: str):
    """Ensure directory exists."""
    os.makedirs(path, exist_ok=True)

def bytes_to_hex(data: bytes) -> str:
    """Convert bytes to hex string."""
    return data.hex()

def hex_to_bytes(hex_str: str) -> bytes:
    """Convert hex string to bytes."""
    return bytes.fromhex(hex_str)
