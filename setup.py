"""Walk through creating the ZeeNoodle Discord application and writing .env."""

from __future__ import annotations

import webbrowser
from pathlib import Path
from tkinter import BooleanVar, Button, Checkbutton, Entry, Label, Text, Tk, messagebox
from tkinter.constants import END, W

from envutil import validate_prefix

PORTAL_URL = "https://discord.com/developers/applications"
PERMISSIONS = 125952
DEFAULT_NAME = "ZeeNoodle"
DEFAULT_CHANNEL_ID = "1547016477104672798"
DEFAULT_DISTANCE = "10"
DEFAULT_PREFIX = "!"
DEFAULT_BRANCH = "main"
ENV_PATH = Path(__file__).resolve().parent / ".env"


def _write_env(
    token: str,
    channel_id: str,
    distance: str,
    prefix: str,
    github_remote: str,
    github_token: str,
    github_branch: str,
) -> None:
    ENV_PATH.write_text(
        f"DISCORD_TOKEN={token}\n"
        f"INCIDENT_CHANNEL_ID={channel_id}\n"
        f"HASH_DISTANCE={distance}\n"
        f"COMMAND_PREFIX={prefix}\n"
        f"DATA_DIR=\n"
        f"GITHUB_REMOTE={github_remote}\n"
        f"GITHUB_TOKEN={github_token}\n"
        f"GITHUB_BRANCH={github_branch}\n",
        encoding="utf-8",
    )


def _invite_url(app_id: str) -> str:
    return (
        "https://discord.com/oauth2/authorize"
        f"?client_id={app_id}&permissions={PERMISSIONS}&scope=bot"
    )


def _save_from_form(fields: dict[str, Entry], replace_var: BooleanVar, window: Tk) -> None:
    token = fields["token"].get().strip()
    app_id = fields["app_id"].get().strip()
    channel_id = fields["channel_id"].get().strip() or DEFAULT_CHANNEL_ID
    distance = fields["distance"].get().strip() or DEFAULT_DISTANCE
    github_remote = fields["github_remote"].get().strip()
    github_token = fields["github_token"].get().strip()
    github_branch = fields["github_branch"].get().strip() or DEFAULT_BRANCH
    try:
        prefix = validate_prefix(fields["prefix"].get())
    except ValueError as exc:
        messagebox.showerror("ZeeNoodle setup", str(exc))
        return
    if not token:
        messagebox.showerror("ZeeNoodle setup", "Paste the Discord bot token.")
        return
    if not app_id:
        messagebox.showerror("ZeeNoodle setup", "Paste the Application ID.")
        return
    if ENV_PATH.exists() and not replace_var.get():
        messagebox.showerror(
            "ZeeNoodle setup",
            ".env already exists. Check the box to replace it.",
        )
        return
    _write_env(
        token,
        channel_id,
        distance,
        prefix,
        github_remote,
        github_token,
        github_branch,
    )
    invite = _invite_url(app_id)
    webbrowser.open(invite)
    messagebox.showinfo(
        "ZeeNoodle setup",
        "Saved .env on this PC.\n\n"
        "Authorize ZeeNoodle on your server in the browser tab that just opened.\n"
        "Then use start.bat to put it on Quaxly, or run the bot here.\n"
        "Do not upload .env to Quaxly; paste the same values as secrets there.",
    )
    print(f"Wrote {ENV_PATH}")
    print(f"Invite URL: {invite}")
    window.destroy()


def main() -> None:
    webbrowser.open(PORTAL_URL)

    window = Tk()
    window.title("ZeeNoodle setup")
    window.geometry("640x620")

    help_box = Text(window, height=10, wrap="word")
    help_box.grid(row=0, column=0, columnspan=2, padx=12, pady=8, sticky="ew")
    help_box.insert(
        END,
        "The Discord Developer Portal just opened. You paste the values here so ZeeNoodle can store them in .env.\n\n"
        "1. Click New Application. Name it ZeeNoodle.\n"
        "2. Open the Bot tab. Reset Token, copy it, paste it below.\n"
        "3. Enable Message Content Intent. Save Changes.\n"
        "4. Open General Information. Copy Application ID and paste it below.\n"
        "5. Click Save. A browser tab will open so you can invite the bot.\n\n"
        "GitHub fields are optional. Leave them blank unless the repo is yours.",
    )
    help_box.configure(state="disabled")

    labels = [
        ("name", "Bot display name", DEFAULT_NAME, False),
        ("token", "Discord bot token", "", True),
        ("app_id", "Application ID", "", False),
        ("channel_id", "Incident channel ID", DEFAULT_CHANNEL_ID, False),
        ("prefix", "Command prefix (not /)", DEFAULT_PREFIX, False),
        ("distance", "Image hash distance", DEFAULT_DISTANCE, False),
        ("github_remote", "Your GitHub repo URL (optional)", "", False),
        ("github_token", "Your GitHub token (optional)", "", True),
        ("github_branch", "GitHub branch", DEFAULT_BRANCH, False),
    ]
    fields: dict[str, Entry] = {}
    for index, (key, title, default, secret) in enumerate(labels, start=1):
        Label(window, text=title).grid(row=index, column=0, sticky=W, padx=12, pady=4)
        box = Entry(window, width=56, show="*" if secret else "")
        box.grid(row=index, column=1, padx=12, pady=4, sticky="ew")
        if default:
            box.insert(0, default)
        fields[key] = box

    replace_var = BooleanVar(value=not ENV_PATH.exists())
    Checkbutton(
        window,
        text="Replace existing .env",
        variable=replace_var,
    ).grid(row=len(labels) + 1, column=0, columnspan=2, sticky=W, padx=12, pady=6)

    Button(
        window,
        text="Save and open invite",
        command=lambda: _save_from_form(fields, replace_var, window),
    ).grid(row=len(labels) + 2, column=0, columnspan=2, pady=12)

    window.columnconfigure(1, weight=1)
    window.mainloop()


if __name__ == "__main__":
    main()
