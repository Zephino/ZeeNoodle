"""Read and update keys in the local .env file without committing it."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"


def set_env_value(key: str, value: str, path: Path = ENV_PATH) -> None:
    lines: list[str] = []
    found = False
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith(f"{key}=") or stripped.startswith(f"{key} ="):
                lines.append(f"{key}={value}")
                found = True
            else:
                lines.append(line)
    if not found:
        lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def validate_prefix(raw: str) -> str:
    prefix = raw.strip()
    if not prefix:
        raise ValueError("Prefix cannot be empty.")
    if prefix.startswith("/"):
        raise ValueError("Prefix cannot start with /.")
    return prefix
