"""Build a Quaxly zip and walk through upload. Does not ask for Quaxly login."""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path
import webbrowser

from paths import PROJECT_ROOT

QUAXLY_URL = "https://quaxly.com/"
WAIFLY_URL = "https://waifly.com/"
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


def _print_wait_for_login(*, click_start: bool = True) -> None:
    if click_start:
        print("  - Go to the Console tab.")
        print("  - Click Start. Do this as soon as .env is in the same folder as bot.py.")
    print("  - The first start runs pip install. That can take several minutes.")
    print("  - Stay on the Console tab. Do not click Start again while it installs.")
    print("  - Lines like Collecting ... or Installing ... are normal. Wait.")
    print("  - The bot is not ready until you see: ZeeNoodle logged in as ...")


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
        input("\nPress Enter after you clicked Restart or Deploy...")
        print("\nStep 4: Open live logs and wait.")
        _print_wait_for_login(click_start=False)
        input("\nPress Enter only after you see ZeeNoodle logged in as ...")
        print("The hosted bot should now be running the updated files.")
        return

    print("\nStep 2: Create a bot named ZeeNoodle.")
    print("Upload this zip, or connect YOUR GitHub repo (do not use someone else's).")
    print(f"  Zip: {zip_path}")
    input("Press Enter after the code is uploaded...")

    print("\nStep 3: Add encrypted environment variables in the Quaxly panel.")
    _print_secret_hints()
    input("\nPress Enter after you saved the secrets...")

    print("\nStep 4: Deploy, then open live logs.")
    print("  Click Deploy or Start after secrets are saved.")
    _print_wait_for_login(click_start=False)
    input("\nPress Enter only after you see ZeeNoodle logged in as ...")
    print("Done. Keep the Quaxly bot running 24/7.")


def main_waifly(update_existing: bool = False) -> None:
    print("ZeeNoodle Waifly deploy helper")
    print("This script does not ask for a Waifly password.")
    print("Log in at waifly.com in your own browser.\n")

    zip_path = build_zip()
    print(f"Built {zip_path}")
    print("The zip does not include .env — you upload that separately.\n")

    print("Step 1: Opening Waifly.")
    webbrowser.open(WAIFLY_URL)
    input("Log in, then press Enter...\n")

    if update_existing:
        print("Step 2: Open the ZeeNoodle server you already have.")
        print("Go to the Files tab.")
        print("Delete the old files (select all, delete), then:")
        print(f"  Upload this zip: {zip_path}")
        print("  Right-click the zip in the file manager -> Unarchive.")
        print("  Delete the zip file once extracted.")
        print("  Your .env is already there — do NOT delete it.")
        input("\nPress Enter after files are replaced...\n")
        print("Step 3: Go to the Console tab and click Restart.")
        _print_wait_for_login(click_start=False)
        input("\nPress Enter only after you see ZeeNoodle logged in as ...")
        print("The hosted bot is now running the updated files.")
        return

    print("Step 2: Create a new server.")
    print("  - Click 'Create a server' on the dashboard.")
    print("  - Server Name: ZeeNoodle")
    print("  - Egg (Server Type): Python")
    print("  - Location: pick any available one.")
    print("  - Leave CPU / RAM / Disk at their defaults.")
    print("  - Click Create.")
    input("\nPress Enter after the server is created...\n")

    print("Step 3: Open the server panel.")
    print("  - Click the gear icon next to ZeeNoodle.")
    print("  - Copy the Panel URL and open it.")
    print("  - Accept the privacy consent if prompted.")
    input("\nPress Enter once you are inside the panel...\n")

    print("Step 4: Upload your bot files.")
    print("  - Go to the Files tab in the left sidebar.")
    print(f"  - Upload this zip: {zip_path}")
    print("  - Right-click the zip -> Unarchive (or Extract).")
    print("  - Delete the zip file once extracted.")
    input("\nPress Enter after files are uploaded and extracted...\n")

    print("Step 5: Upload your .env file.")
    if ENV_PATH.exists():
        print(f"  Your .env is at: {ENV_PATH}")
    else:
        print("  WARNING: .env not found locally. Run setup.py first.")
    print("  In the Files tab, upload your .env file to the same folder as bot.py.")
    print("  After .env is there, you still have to start the bot. That is the next step.")
    input("\nPress Enter after .env is uploaded. Next: check Startup, then click Start.\n")

    print("Step 6: Check startup settings.")
    print("  - Go to the Startup tab.")
    print("  - Startup Command 1 should be: pip install -r requirements.txt")
    print("  - Startup Command 2 should be: python bot.py")
    print("  - Leave everything else as is.")
    input("\nPress Enter after confirming startup settings. Next: click Start.\n")

    print("Step 7: Start the bot now.")
    print("  Do not close the panel after uploading .env. The bot is still offline.")
    _print_wait_for_login(click_start=True)
    input("\nPress Enter only after you see ZeeNoodle logged in as ...\n")
    print("Done. ZeeNoodle is now running 24/7 on Waifly.")
    print("Note: Waifly suspends servers idle for 3 days. Keep the bot running.")


if __name__ == "__main__":
    if "--waifly" in sys.argv:
        main_waifly(update_existing="--update" in sys.argv)
    else:
        main(update_existing="--update" in sys.argv)
