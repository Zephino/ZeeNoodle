"""Keep ZeeNoodle running: restart bot.py after crashes.

Waifly suspends free servers that stay offline for 3 days. Use this as the
start command (``python run.py``) so a crash or memory restart never leaves
the bot offline.

The supervisor stays stopped when:
- The hosting panel's Stop button (SIGTERM / SIGINT) stops it.
- ``!update manual`` writes the stop flag before shutting the bot down.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from collections import deque
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

from paths import stop_flag_file  # noqa: E402  (needs .env loaded for DATA_DIR)

# bot.py exits with this code when it wants an immediate restart
# (after !update or a memory hard-limit restart). Not counted as a crash.
RESTART_EXIT_CODE = 75

RESTART_DELAY = 10            # seconds between normal restarts
CRASH_WINDOW = 5 * 60         # look at exits in the last 5 minutes
CRASH_LIMIT = 5               # this many exits in the window triggers back-off
BACKOFF_DELAY = 5 * 60        # back-off wait, so Discord logins are not spammed
STABLE_UPTIME = 10 * 60       # a run this long resets the crash counter

_stopping = False
_child: subprocess.Popen | None = None


def log(text: str) -> None:
    print(f"[supervisor] {text}", flush=True)


def _handle_stop(signum, _frame) -> None:
    global _stopping
    _stopping = True
    log(f"stop signal received ({signal.Signals(signum).name}), shutting down")
    if _child is not None and _child.poll() is None:
        try:
            _child.terminate()
        except OSError:
            pass


def _sleep(seconds: float) -> None:
    """Sleep in small steps so a stop signal is noticed quickly."""
    end = time.monotonic() + seconds
    while not _stopping and time.monotonic() < end:
        time.sleep(1)


def _clear_stop_flag() -> None:
    try:
        stop_flag_file().unlink(missing_ok=True)
    except OSError as exc:
        log(f"could not remove old stop flag: {exc}")


def _run_bot_once() -> int:
    global _child
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"   # show bot logs in the panel console right away
    env["ZEENOODLE_SUPERVISED"] = "1"
    _child = subprocess.Popen(
        [sys.executable, str(PROJECT_ROOT / "bot.py")],
        cwd=str(PROJECT_ROOT),
        env=env,
    )
    try:
        return _child.wait()
    except KeyboardInterrupt:
        _handle_stop(signal.SIGINT, None)
        try:
            return _child.wait(timeout=15)
        except subprocess.TimeoutExpired:
            _child.kill()
            return _child.wait()


def main() -> None:
    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)
    _clear_stop_flag()
    log("started")

    recent_exits: deque[float] = deque()
    while not _stopping:
        started = time.monotonic()
        code = _run_bot_once()
        uptime = time.monotonic() - started

        if _stopping:
            break
        if stop_flag_file().exists():
            log("bot stopped on purpose (stop flag found); not restarting")
            _clear_stop_flag()
            break
        if code == RESTART_EXIT_CODE:
            log("bot asked for a restart; restarting now")
            continue

        now = time.monotonic()
        if uptime >= STABLE_UPTIME:
            recent_exits.clear()
        recent_exits.append(now)
        while recent_exits and now - recent_exits[0] > CRASH_WINDOW:
            recent_exits.popleft()

        if len(recent_exits) >= CRASH_LIMIT:
            log(
                f"bot exited with code {code}; {len(recent_exits)} exits in "
                f"{CRASH_WINDOW // 60} min, backing off for {BACKOFF_DELAY // 60} min"
            )
            recent_exits.clear()
            _sleep(BACKOFF_DELAY)
        else:
            log(f"bot exited with code {code}, restarting in {RESTART_DELAY} s")
            _sleep(RESTART_DELAY)

    log("stopped")


if __name__ == "__main__":
    main()
