"""
utils/file_helpers.py
Hash / dedup utilities for downloaded attachments.
"""
import hashlib
import os

def compute_file_hash(filepath: str, algorithm: str = "sha256") -> str:
    """Return hex digest of a file's contents."""
    h = hashlib.new(algorithm)
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def compute_bytes_hash(data: bytes, algorithm: str = "sha256") -> str:
    """Return hex digest of raw bytes (for pre-save dedup)."""
    h = hashlib.new(algorithm)
    h.update(data)
    return h.hexdigest()

def safe_filename(name: str) -> str:
    """Strip characters that are unsafe in filenames."""
    keep = " ._-abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(c if c in keep else "_" for c in name).strip()

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)
