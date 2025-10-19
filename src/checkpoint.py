"""
Checkpoint and Rollback Utility
-------------------------------
Handles snapshot creation, verification, and restoration of the CLAIP system
state.  Each checkpoint stores serialized objects (KnowledgeBase, GK, etc.)
plus a SHA256 hash for integrity checking.

Usage:
    from src import checkpoint

    checkpoint.create_checkpoint(agent, label="after_ingestion")
    restored_agent = checkpoint.restore_checkpoint("checkpoints/core_state_<timestamp>.pkl")
"""

import os
import pickle
import json
import hashlib
from datetime import datetime
from pathlib import Path

CHECKPOINT_DIR = Path("checkpoints")

def _timestamp():
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")

def _hash_file(path: Path) -> str:
    """Return SHA256 hash of file content."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def create_checkpoint(agent, label: str = "") -> Path:
    """
    Serialize the current agent state to a checkpoint file and write
    a companion metadata file with hash and timestamp.
    """
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    ts = _timestamp()
    base = f"core_state_{ts}"
    if label:
        base += f"_{label}"

    ckpt_path = CHECKPOINT_DIR / f"{base}.pkl"
    meta_path = CHECKPOINT_DIR / f"{base}.json"

    # --- Serialize agent state ---
    with open(ckpt_path, "wb") as f:
        pickle.dump(agent, f)

    file_hash = _hash_file(ckpt_path)

    metadata = {
        "timestamp": ts,
        "label": label,
        "path": str(ckpt_path),
        "sha256": file_hash,
    }

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"✅ Checkpoint created: {ckpt_path.name}")
    return ckpt_path

def verify_checkpoint(ckpt_path: Path) -> bool:
    """Validate file integrity using its .json metadata hash."""
    meta_path = ckpt_path.with_suffix(".json")
    if not meta_path.exists():
        print("⚠️  Metadata file not found.")
        return False

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    current_hash = _hash_file(ckpt_path)
    if current_hash == meta.get("sha256"):
        print("✅ Checksum verified.")
        return True
    else:
        print("❌ Hash mismatch — file may be corrupted.")
        return False

def restore_checkpoint(ckpt_filename: str):
    """
    Load an agent from a checkpoint file if hash verification passes.
    Returns the deserialized agent object.
    """
    ckpt_path = Path(ckpt_filename)
    if not ckpt_path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {ckpt_filename}")

    if not verify_checkpoint(ckpt_path):
        raise ValueError("Integrity check failed. Aborting restore.")

    with open(ckpt_path, "rb") as f:
        agent = pickle.load(f)

    print(f"🔁 Restored checkpoint: {ckpt_path.name}")
    return agent

def list_checkpoints(limit: int = 10):
    """List most recent checkpoint files with timestamps."""
    if not CHECKPOINT_DIR.exists():
        print("No checkpoints directory found.")
        return []
    files = sorted(CHECKPOINT_DIR.glob("core_state_*.pkl"), key=os.path.getmtime, reverse=True)
    for f in files[:limit]:
        print(f"- {f.name}")
    return files
