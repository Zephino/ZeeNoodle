"""Mirror backup/ and optionally create/push the operator's own GitHub remote."""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import quote

import aiohttp

from paths import (
    PROJECT_ROOT,
    backup_dir,
    backup_ignore_file,
    backup_references_dir,
    data_root,
    ignore_file,
    references_dir,
)

_REMOTE_RE = re.compile(
    r"(?:https?://github\.com/|git@github\.com:)"
    r"(?P<owner>[^/]+)/(?P<repo>[^/.]+?)(?:\.git)?/?$",
    re.IGNORECASE,
)


def parse_remote(url: str) -> tuple[str, str] | None:
    match = _REMOTE_RE.search(url.strip())
    if not match:
        return None
    return match.group("owner"), match.group("repo")


def github_configured() -> bool:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    remote = os.environ.get("GITHUB_REMOTE", "").strip()
    return bool(token and remote)


def _github_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ZeeNoodle",
    }


def mirror_backup() -> None:
    dest_refs = backup_references_dir()
    live_refs = references_dir()
    live_names = set()
    if live_refs.is_dir():
        for path in live_refs.iterdir():
            if not path.is_file():
                continue
            live_names.add(path.name)
            shutil.copy2(path, dest_refs / path.name)
    for path in dest_refs.iterdir():
        if path.is_file() and path.name not in live_names:
            path.unlink()
    live_ignore = ignore_file()
    dest_ignore = backup_ignore_file()
    if live_ignore.exists():
        shutil.copy2(live_ignore, dest_ignore)
    else:
        dest_ignore.write_text(
            json.dumps({"channel_ids": []}, indent=2) + "\n", encoding="utf-8"
        )


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=data_root(),
        check=check,
        capture_output=True,
        text=True,
    )


def _git_available() -> bool:
    try:
        _git("--version")
    except (OSError, subprocess.CalledProcessError):
        return False
    return True


async def ensure_github_repo(session: aiohttp.ClientSession) -> str | None:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    remote = os.environ.get("GITHUB_REMOTE", "").strip()
    parsed = parse_remote(remote)
    if not token or not parsed:
        return None
    owner, repo = parsed
    headers = _github_headers(token)
    async with session.get("https://api.github.com/user", headers=headers) as response:
        if response.status != 200:
            print(f"GitHub user lookup failed: HTTP {response.status}")
            return "GitHub token was rejected."
        user = await response.json()
    login = str(user.get("login", ""))
    async with session.get(
        f"https://api.github.com/repos/{owner}/{repo}", headers=headers
    ) as response:
        if response.status == 200:
            return None
        if response.status != 404:
            print(f"GitHub repo lookup failed: HTTP {response.status}")
            return "Could not check the GitHub repo."
    if login.lower() != owner.lower():
        return (
            f"Repo {owner}/{repo} does not exist, and this token is {login}, "
            "so ZeeNoodle will not create someone else's repo."
        )
    payload = {
        "name": repo,
        "private": True,
        "description": "ZeeNoodle project and backup",
        "auto_init": False,
    }
    async with session.post(
        "https://api.github.com/user/repos", headers=headers, json=payload
    ) as response:
        if response.status not in {201, 422}:
            print(f"GitHub create repo failed: HTTP {response.status}")
            return "Could not create the GitHub repo."
    return None


def _ensure_git_repo(remote: str, branch: str) -> None:
    root = data_root()
    if not (root / ".git").exists():
        _git("init")
        _git("checkout", "-B", branch)
    # Keep a .gitignore in data_root so .env is never committed.
    src = PROJECT_ROOT / ".gitignore"
    dest = root / ".gitignore"
    if src.exists() and (not dest.exists() or dest.read_bytes() != src.read_bytes()):
        shutil.copy2(src, dest)
    current = _git("remote", check=False)
    if "origin" not in current.stdout:
        _git("remote", "add", "origin", remote)
    else:
        _git("remote", "set-url", "origin", remote)


def _push_with_token(token: str, owner: str, repo: str, branch: str) -> None:
    encoded = quote(token, safe="")
    push_url = f"https://x-access-token:{encoded}@github.com/{owner}/{repo}.git"
    _git("push", "--force", "-u", push_url, f"HEAD:{branch}")


def commit_and_push(message: str) -> str | None:
    if not github_configured():
        return None
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    remote = os.environ.get("GITHUB_REMOTE", "").strip()
    branch = os.environ.get("GITHUB_BRANCH", "main").strip() or "main"
    parsed = parse_remote(remote)
    if not parsed:
        return "GITHUB_REMOTE is not a github.com URL."
    owner, repo = parsed
    try:
        _ensure_git_repo(remote, branch)
        _git("add", "backup", "references", "config", ".gitignore")
        status = _git("status", "--porcelain")
        # Lines starting with '??' are untracked — not staged, cannot be committed.
        staged = [l for l in status.stdout.splitlines() if not l.startswith("??")]
        if not staged:
            return None
        _git(
            "-c",
            "user.email=zeenoodle@local",
            "-c",
            "user.name=ZeeNoodle",
            "commit",
            "-m",
            message,
        )
        _push_with_token(token, owner, repo, branch)
    except subprocess.CalledProcessError as exc:
        err = (exc.stderr or exc.stdout or str(exc)).strip()
        print(f"GitHub backup failed: {err}")
        return err[:400] if err else "Git push failed with no output."
    return None


def _backup_files() -> list[Path]:
    files: list[Path] = []
    refs = backup_references_dir()
    if refs.is_dir():
        files.extend(path for path in sorted(refs.iterdir()) if path.is_file())
    ignore = backup_ignore_file()
    if ignore.exists():
        files.append(ignore)
    return files


def _remote_path(path: Path) -> str:
    try:
        return path.relative_to(backup_dir()).as_posix()
    except ValueError:
        return path.name


async def _put_file(
    session: aiohttp.ClientSession,
    owner: str,
    repo: str,
    branch: str,
    headers: dict[str, str],
    path: Path,
    message: str,
) -> None:
    remote_path = f"backup/{_remote_path(path)}"
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{remote_path}"
    sha = None
    async with session.get(url, headers=headers, params={"ref": branch}) as response:
        if response.status == 200:
            body = await response.json()
            sha = body.get("sha")
    payload = {
        "message": message,
        "content": base64.b64encode(path.read_bytes()).decode("ascii"),
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha
    async with session.put(url, headers=headers, json=payload) as response:
        if response.status not in {200, 201}:
            text = await response.text()
            raise RuntimeError(f"HTTP {response.status}: {text[:200]}")


async def upload_via_contents_api(
    session: aiohttp.ClientSession, message: str
) -> str | None:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    remote = os.environ.get("GITHUB_REMOTE", "").strip()
    branch = os.environ.get("GITHUB_BRANCH", "main").strip() or "main"
    parsed = parse_remote(remote)
    if not token or not parsed:
        return None
    owner, repo = parsed
    headers = _github_headers(token)
    try:
        for path in _backup_files():
            await _put_file(session, owner, repo, branch, headers, path, message)
    except (aiohttp.ClientError, RuntimeError, OSError) as exc:
        print(f"GitHub Contents API backup failed: {exc}")
        return str(exc)[:400]
    return None


def apply_backup_to_live() -> None:
    live = references_dir()
    src = backup_references_dir()
    live.mkdir(parents=True, exist_ok=True)
    kept: set[str] = set()
    if src.is_dir():
        for path in src.iterdir():
            if not path.is_file():
                continue
            shutil.copy2(path, live / path.name)
            kept.add(path.name)
    for path in live.iterdir():
        if path.is_file() and path.name not in kept:
            path.unlink()
    dest_ignore = ignore_file()
    src_ignore = backup_ignore_file()
    dest_ignore.parent.mkdir(parents=True, exist_ok=True)
    if src_ignore.exists():
        shutil.copy2(src_ignore, dest_ignore)
    else:
        dest_ignore.write_text(
            json.dumps({"channel_ids": []}, indent=2) + "\n", encoding="utf-8"
        )


async def _list_remote_files(
    session: aiohttp.ClientSession,
    owner: str,
    repo: str,
    branch: str,
    headers: dict[str, str],
    remote_dir: str,
) -> list[dict]:
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{remote_dir}"
    async with session.get(url, headers=headers, params={"ref": branch}) as response:
        if response.status == 404:
            return []
        if response.status != 200:
            text = await response.text()
            raise RuntimeError(f"HTTP {response.status}: {text[:200]}")
        items = await response.json()
    if not isinstance(items, list):
        return []
    files: list[dict] = []
    for item in items:
        if item.get("type") == "dir" and item.get("path"):
            files.extend(
                await _list_remote_files(
                    session, owner, repo, branch, headers, item["path"]
                )
            )
        elif item.get("type") == "file":
            files.append(item)
    return files


async def download_from_github(session: aiohttp.ClientSession) -> str | None:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    remote = os.environ.get("GITHUB_REMOTE", "").strip()
    branch = os.environ.get("GITHUB_BRANCH", "main").strip() or "main"
    parsed = parse_remote(remote)
    if not token or not parsed:
        return "GITHUB_REMOTE and GITHUB_TOKEN must be set to pull from GitHub."
    owner, repo = parsed
    headers = _github_headers(token)
    dest = backup_dir()
    dest.mkdir(parents=True, exist_ok=True)
    try:
        if _git_available():
            _ensure_git_repo(remote, branch)
            encoded = quote(token, safe="")
            fetch_url = f"https://x-access-token:{encoded}@github.com/{owner}/{repo}.git"
            _git("fetch", fetch_url, branch)
            _git("checkout", "FETCH_HEAD", "--", "backup")
            return None
        files = await _list_remote_files(
            session, owner, repo, branch, headers, "backup"
        )
        if not files:
            return "No backup folder on GitHub yet. Run backup first."
        for item in files:
            download_url = item.get("download_url")
            path_name = str(item.get("path", ""))
            if not download_url or not path_name.startswith("backup/"):
                continue
            rel = path_name[len("backup/") :]
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            async with session.get(download_url) as response:
                if response.status != 200:
                    raise RuntimeError(f"Download failed for {path_name}")
                target.write_bytes(await response.read())
    except (aiohttp.ClientError, RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print(f"GitHub restore failed: {exc}")
        return "Could not pull the backup from GitHub."
    return None


async def backup_after_change(
    session: aiohttp.ClientSession, message: str
) -> str | None:
    mirror_backup()
    if not github_configured():
        return None
    created = await ensure_github_repo(session)
    if created:
        return created
    if _git_available():
        return commit_and_push(message)
    return await upload_via_contents_api(session, message)


def _local_backup_empty() -> bool:
    refs = backup_references_dir()
    has_pics = refs.is_dir() and any(path.is_file() for path in refs.iterdir())
    return not backup_ignore_file().exists() and not has_pics


async def run_manual_backup(session: aiohttp.ClientSession | None) -> str:
    if session is None:
        return "HTTP session is not ready."
    err = await backup_after_change(session, "Manual backup")
    if not github_configured():
        return (
            "Saved pictures and ignore list in backup/ on this machine. "
            "Set your GITHUB_REMOTE and GITHUB_TOKEN to store it on GitHub."
        )
    if err:
        return f"Saved locally. GitHub: {err}"
    return "Saved locally and sent to your GitHub."


async def run_restore(session: aiohttp.ClientSession | None) -> str:
    if session is None:
        return "HTTP session is not ready."
    if github_configured():
        err = await download_from_github(session)
        if err:
            return err
    elif _local_backup_empty():
        return (
            "No local backup found. Set GITHUB_REMOTE and GITHUB_TOKEN, "
            "run backup, then restore."
        )
    apply_backup_to_live()
    return "Restored pictures and ignore list from backup."

