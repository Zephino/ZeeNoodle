"""Build a Quaxly zip and walk through upload. Does not ask for Quaxly login."""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path
import webbrowser

from paths import PROJECT_ROOT

QUAXLY_URL = "https://quaxly.com/"
DIST_DIR = PROJECT_ROOT / "dist"
ZIP_PATH = DIST_DIR / "zeenoodle-quaxly.zip"
ENV_PATH = PROJECT_ROOT / ".env"

INCLUDE_FILES = (
    "bot.py",
    "detector.py",
    "envutil.py",
    "github_backup.py",
    "ignore_list.py",
    "paths.py",
    "setup.py",
    "deploy.py",
    "requirements.txt",
    "Procfile",
    "runtime.txt",
    "VERSION",
    ".env.example",
    ".gitignore",
)
INCLUDE_DIRS = ("references", "config", "backup")
SKIP_SUFFIXES = {".pyc", ".pyo"}
ENV_KEYS = (
    "DISCORD_TOKEN",
    "INCIDENT_CHANNEL_ID",
    "HASH_DISTANCE",
    "COMMAND_PREFIX",
    "DATA_DIR",
    "GITHUB_REMOTE",
    "GITHUB_TOKEN",
    "GITHUB_BRANCH",
)


def _env_status() -> dict[str, bool]:
    found = {key: False for key in ENV_KEYS}
    if not ENV_PATH.exists():
        return found
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key in found and value.strip():
            found[key] = True
    return found


def _should_skip(path: Path) -> bool:
    if path.name == ".env":
        return True
    if path.suffix in SKIP_SUFFIXES:
        return True
    if "__pycache__" in path.parts or ".git" in path.parts or ".venv" in path.parts:
        return True
    if "dist" in path.parts:
        return True
    return False


def build_zip() -> Path:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in INCLUDE_FILES:
            path = PROJECT_ROOT / name
            if path.is_file():
                archive.write(path, name)
        for folder in INCLUDE_DIRS:
            root = PROJECT_ROOT / folder
            if not root.is_dir():
                continue
            for path in root.rglob("*"):
                if path.is_file() and not _should_skip(path):
                    archive.write(path, path.relative_to(PROJECT_ROOT).as_posix())
    return ZIP_PATH


def _print_secret_hints() -> None:
    print("Start command: python bot.py")
    print("Set DATA_DIR to the volume path if Quaxly shows one.\n")
    print("Keys (copy values from your local .env; tokens are not printed):")
    for key, present in _env_status().items():
        mark = "set in local .env" if present else "not set locally"
        print(f"  {key}  ({mark})")


def main(update_existing: bool = False) -> None:
    print("ZeeNoodle Quaxly deploy helper")
    print("This script does not ask for a Quaxly password.")
    print("Log in at quaxly.com in your own browser.\n")

    zip_path = build_zip()
    print(f"Built {zip_path}")
    print("The zip does not include .env.\n")

    print("Step 1: Opening Quaxly.")
    webbrowser.open(QUAXLY_URL)
    input("Log in yourself, then press Enter...")

    if update_existing:
        print("\nStep 2: Open the ZeeNoodle bot you already host. Do not create a second bot.")
        print("Replace its files:")
        print("  - Zip upload: upload this new zip over the existing bot, then restart/redeploy.")
        print("  - GitHub connected: click Redeploy (or pull latest, then restart).")
        print(f"  Zip: {zip_path}")
        input("Press Enter after the hosted files are replaced...")
        print("\nStep 3: Leave existing secrets as they are unless you changed .env.")
        _print_secret_hints()
        input("\nPress Enter after the hosted bot has restarted...")
        print("\nStep 4: Open live logs.")
        print("Wait until you see: ZeeNoodle logged in as ...")
        print("The hosted bot should now be running the updated files.")
        return

    print("\nStep 2: Create a bot named ZeeNoodle.")
    print("Upload this zip, or connect YOUR GitHub repo (do not use someone else's).")
    print(f"  Zip: {zip_path}")
    input("Press Enter after the code is uploaded...")

    print("\nStep 3: Add encrypted environment variables in the Quaxly panel.")
    _print_secret_hints()
    input("\nPress Enter after you saved the secrets...")

    print("\nStep 4: Deploy and open live logs.")
    print("Wait until you see: ZeeNoodle logged in as ...")
    print("Done. Keep the Quaxly bot running 24/7.")


if __name__ == "__main__":
    main(update_existing="--update" in sys.argv)
