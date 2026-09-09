"""Read and update keys in the local .env file without committing it."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"

# (key, label, required, hint shown when empty)
_STATUS_FIELDS: tuple[tuple[str, str, bool, str], ...] = (
    (
        "DISCORD_TOKEN",
        "Discord bot token",
        True,
        "Required. Copy it from the Bot tab in the Discord Developer Portal.",
    ),
    (
        "INCIDENT_CHANNEL_ID",
        "Incident channel ID",
        True,
        "Required. Channel where delete reports are posted.",
    ),
    (
        "COMMAND_PREFIX",
        "Command prefix",
        True,
        "Required. Character that starts staff commands, for example !",
    ),
    (
        "HASH_DISTANCE",
        "Image hash distance",
        False,
        "Optional. How close an image must be to a reference. Default is 10.",
    ),
    (
        "DATA_DIR",
        "Data directory",
        False,
        "Optional. Leave blank unless the host gives you a volume path.",
    ),
    (
        "GITHUB_REMOTE",
        "GitHub repo URL",
        False,
        "Optional. Your backup repo only. Leave blank if you are not using GitHub.",
    ),
    (
        "GITHUB_TOKEN",
        "GitHub token",
        False,
        "Needed if a GitHub repo URL is set. Use a Personal Access Token with repo scope.",
    ),
    (
        "GITHUB_BRANCH",
        "GitHub branch",
        False,
        "Optional. Default is main.",
    ),
)
_SECRET_KEYS = frozenset({"DISCORD_TOKEN", "GITHUB_TOKEN"})


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


def _read_env_map(path: Path = ENV_PATH) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _display_value(key: str, value: str) -> str:
    if key in _SECRET_KEYS:
        if len(value) <= 4:
            return "(set, hidden)"
        return f"(set, ends ...{value[-4:]})"
    return value


def print_env_status(path: Path = ENV_PATH) -> int:
    """Print what .env already has and what still needs a value. Return 1 if required keys are missing."""
    print()
    if not path.exists():
        print("No .env file yet. Open the setup form to fill these in:")
        for _key, label, required, hint in _STATUS_FIELDS:
            mark = "required" if required else "optional"
            print(f"  - {label} ({mark})")
            print(f"      {hint}")
        print()
        return 1

    values = _read_env_map(path)
    print(f"Reading {path.name}")
    print("What is already filled in, and what still needs a value:")
    print()
    missing: list[str] = []
    remote = values.get("GITHUB_REMOTE", "").strip()
    for key, label, required, hint in _STATUS_FIELDS:
        value = values.get(key, "").strip()
        token_needed = key == "GITHUB_TOKEN" and bool(remote)
        must_have = required or token_needed
        if value:
            print(f"  [ok]      {label}: {_display_value(key, value)}")
            continue
        if must_have:
            print(f"  [needed]  {label}: empty")
            print(f"            {hint}")
            missing.append(label)
        else:
            print(f"  [blank]   {label}: empty  ({hint})")

    print()
    if missing:
        print("Still need to fill in:")
        for label in missing:
            print(f"  - {label}")
        print("Open the setup form to add or change these.")
        return 1
    print("Required fields are set. Open the setup form only if you want to change them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(print_env_status())
