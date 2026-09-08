"""Project code root vs optional DATA_DIR for Quaxly persistent volumes."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def data_root() -> Path:
    raw = os.environ.get("DATA_DIR", "").strip()
    if not raw:
        return PROJECT_ROOT
    path = Path(raw)
    path.mkdir(parents=True, exist_ok=True)
    return path


def references_dir() -> Path:
    path = data_root() / "references"
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_dir() -> Path:
    path = data_root() / "config"
    path.mkdir(parents=True, exist_ok=True)
    return path


def ignore_file() -> Path:
    return config_dir() / "ignored_channels.json"


def backup_dir() -> Path:
    path = data_root() / "backup"
    path.mkdir(parents=True, exist_ok=True)
    return path


def backup_references_dir() -> Path:
    path = backup_dir() / "references"
    path.mkdir(parents=True, exist_ok=True)
    return path


def backup_ignore_file() -> Path:
    return backup_dir() / "ignored_channels.json"


def seed_data_dir() -> None:
    """Copy bundled references/config into DATA_DIR when that folder is empty."""
    if data_root() == PROJECT_ROOT:
        return
    dest = references_dir()
    if any(dest.iterdir()):
        return
    bundled = PROJECT_ROOT / "references"
    if not bundled.is_dir():
        return
    for path in bundled.iterdir():
        if path.is_file():
            shutil.copy2(path, dest / path.name)
    bundled_ignore = PROJECT_ROOT / "config" / "ignored_channels.json"
    if bundled_ignore.exists() and not ignore_file().exists():
        shutil.copy2(bundled_ignore, ignore_file())
