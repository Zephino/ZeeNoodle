"""ZeeNoodle: delete lacewin-style scam spam and log it to #bot-incendents."""

from __future__ import annotations

import asyncio
import datetime
import io
import os
import random
import subprocess
import sys
import time
from pathlib import Path

import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv

from detector import Detector, IMAGE_SUFFIXES, Match
from envutil import ENV_PATH, set_env_value, validate_prefix
from github_backup import (
    backup_after_change,
    mirror_backup,
    run_manual_backup,
    run_restore,
)
from ignore_list import IgnoreStore
from paths import PROJECT_ROOT, data_root, ignore_file, references_dir, seed_data_dir

load_dotenv()
BOT_VERSION = (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip()
UPDATE_REPO = os.environ.get(
    "UPDATE_REPO",
    "https://raw.githubusercontent.com/Zephino/ZeeNoodle/main",
).rstrip("/")
UPDATE_FILES = (
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
)
INCIDENT_CHANNEL_ID = int(os.environ.get("INCIDENT_CHANNEL_ID", "1547016477104672798"))
HASH_DISTANCE = int(os.environ.get("HASH_DISTANCE", "10"))


def load_prefix() -> str:
    raw = os.environ.get("COMMAND_PREFIX", "!").strip() or "!"
    try:
        return validate_prefix(raw)
    except ValueError:
        return "!"


def _is_image_attachment(attachment: discord.Attachment) -> bool:
    if attachment.content_type and attachment.content_type.startswith("image/"):
        return True
    return Path(attachment.filename).suffix.lower() in IMAGE_SUFFIXES


def _message_text(message: discord.Message) -> str:
    chunks = [message.content]
    for embed in message.embeds:
        chunks.append(embed.title or "")
        chunks.append(embed.description or "")
        chunks.append(embed.url or "")
        if embed.author:
            chunks.append(embed.author.name or "")
            chunks.append(embed.author.url or "")
        if embed.footer:
            chunks.append(embed.footer.text or "")
        for item in embed.fields:
            chunks.append(item.name or "")
            chunks.append(item.value or "")
        if embed.image:
            chunks.append(embed.image.url or "")
        if embed.thumbnail:
            chunks.append(embed.thumbnail.url or "")
    return "\n".join(part for part in chunks if part)


def _is_admin(member: discord.Member | discord.User) -> bool:
    return isinstance(member, discord.Member) and member.guild_permissions.administrator



class ZeeNoodle(commands.Bot):
    def __init__(self) -> None:
        self.prefix_value = load_prefix()
        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True
        intents.guilds = True
        super().__init__(
            command_prefix=lambda bot, _message: bot.prefix_value,
            intents=intents,
            help_command=None,
        )
        seed_data_dir()
        self.detector = Detector(references_dir(), max_distance=HASH_DISTANCE)
        self.ignore_store = IgnoreStore(
            ignore_file(),
            always_ignore={INCIDENT_CHANNEL_ID},
        )
        self.session: aiohttp.ClientSession | None = None
        self._restart_pending: bool = False

    async def setup_hook(self) -> None:
        self.session = aiohttp.ClientSession()
        await self.add_cog(StaffCog(self))
        mirror_backup()
        self.loop.create_task(self._keepalive_loop())

    async def _keepalive_loop(self) -> None:
        """Write a heartbeat file at a random interval (12–20 h) to keep the
        hosting container active and avoid inactivity suspension."""
        heartbeat_path = data_root() / "heartbeat.txt"
        while not self.is_closed():
            delay = random.uniform(12 * 3600, 20 * 3600)  # 12–20 hours in seconds
            await asyncio.sleep(delay)
            try:
                heartbeat_path.write_text(
                    f"alive at {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n",
                    encoding="utf-8",
                )
                print(f"[keepalive] heartbeat written ({delay / 3600:.1f} h interval)")
            except Exception as exc:  # noqa: BLE001
                print(f"[keepalive] write failed: {exc}")

    async def close(self) -> None:
        if self.session:
            await self.session.close()
        await super().close()

    async def on_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        if isinstance(error, commands.CheckFailure):
            return
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                f"Missing `{error.param.name}`. Use `{self.prefix_value}help`."
            )
            return
        if isinstance(error, commands.BadArgument):
            await ctx.send("Could not use that channel or filename.")
            return
        print(f"Command error: {error}")

    async def on_ready(self) -> None:
        print(f"ZeeNoodle logged in as {self.user}")
        print(f"Command prefix: {self.prefix_value}")
        print(f"Loaded {len(self.detector.references)} reference image hashes")
        if not self.detector.references:
            print("Warning: no images in references/. Image matching is off.")

    async def on_message(self, message: discord.Message) -> None:
        if self.user is None or message.author.id == self.user.id:
            return
        ctx = await self.get_context(message)
        if ctx.valid:
            await self.invoke(ctx)
            return
        if message.content.startswith(self.prefix_value):
            return
        if message.guild is None:
            return
        if self.ignore_store.is_ignored(message.channel.id):
            return

        evidence, match = await self._inspect(message)
        if not match.matched:
            return

        try:
            await message.delete()
            deleted = True
        except discord.HTTPException as exc:
            deleted = False
            print(f"Could not delete message {message.id}: {exc}")

        await self._report(message, match, evidence, deleted)

    async def _inspect(self, message: discord.Message) -> tuple[list[tuple[str, bytes]], Match]:
        evidence: list[tuple[str, bytes]] = []
        image_hits = []
        for attachment in message.attachments:
            if not _is_image_attachment(attachment):
                continue
            try:
                data = await attachment.read()
            except discord.HTTPException:
                continue
            hits = self.detector.match_image(data)
            if hits:
                image_hits.extend(hits)
                evidence.append((attachment.filename, data))
        for url in _embed_image_urls(message):
            data = await self._download(url)
            if not data:
                continue
            hits = self.detector.match_image(data)
            if hits:
                image_hits.extend(hits)
                evidence.append(("embed.png", data))
        text_reasons = self.detector.match_text(_message_text(message))
        return evidence, Match(image_hits=tuple(image_hits), text_reasons=text_reasons)

    async def _download(self, url: str) -> bytes | None:
        if not self.session:
            return None
        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    return None
                return await response.read()
        except aiohttp.ClientError:
            return None

    async def _report(
        self,
        message: discord.Message,
        match: Match,
        evidence: list[tuple[str, bytes]],
        deleted: bool,
    ) -> None:
        channel = self.get_channel(INCIDENT_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            print(f"Incident channel {INCIDENT_CHANNEL_ID} is missing or not a text channel.")
            return
        if message.guild is None:
            return
        reason = match.summary()
        mention = message.channel.mention
        await self._post_incident(channel, message, reason, evidence, deleted)

    async def _post_incident(
        self,
        channel: discord.TextChannel,
        message: discord.Message,
        reason: str,
        evidence: list[tuple[str, bytes]],
        deleted: bool,
    ) -> None:
        embed = _incident_embed(message, reason, deleted)
        files = []
        if evidence:
            name, data = evidence[0]
            files.append(discord.File(io.BytesIO(data), filename=name))
        try:
            await channel.send(embed=embed, files=files)
        except discord.HTTPException as exc:
            print(f"Could not post incident: {exc}")

    def _eligible_channels(self, guild: discord.Guild) -> list[discord.TextChannel]:
        """Return public, non-ignored text channels the cleanup command may scan."""
        everyone = guild.default_role
        result = []
        for channel in guild.text_channels:
            if channel.id == INCIDENT_CHANNEL_ID:
                continue
            if self.ignore_store.is_ignored(channel.id):
                continue
            perms = channel.permissions_for(everyone)
            if not perms.read_messages:
                continue
            result.append(channel)
        return result

    async def _cleanup_channels(
        self,
        channels: list[discord.TextChannel],
        *,
        limit: int | None,
        after: datetime.datetime | None,
    ) -> tuple[int, int]:
        """Scan *channels* and delete scam messages.

        Returns ``(messages_deleted, channels_scanned)``.
        """
        cutoff = discord.utils.utcnow() - datetime.timedelta(days=14)
        bot_id = self.user.id if self.user else None
        total_deleted = 0
        channels_scanned = 0

        for channel in channels:
            to_delete: list[discord.Message] = []
            try:
                oldest_first = after is not None
                async for msg in channel.history(
                    limit=limit, after=after, oldest_first=oldest_first
                ):
                    if msg.author.id == bot_id:
                        # Clean up the bot's own add/command replies.
                        if msg.content.startswith(("Now matching:", "Sent to your DMs.")):
                            to_delete.append(msg)
                        continue
                    _, match = await self._inspect(msg)
                    if match.matched:
                        to_delete.append(msg)
            except discord.HTTPException as exc:
                print(f"[cleanup] could not read #{channel.name}: {exc}")
                continue

            if to_delete:
                recent = [m for m in to_delete if m.created_at >= cutoff]
                old = [m for m in to_delete if m.created_at < cutoff]
                # Bulk-delete messages under 14 days old (up to 100 at a time).
                for i in range(0, len(recent), 100):
                    batch = recent[i : i + 100]
                    try:
                        if len(batch) == 1:
                            await batch[0].delete()
                        else:
                            await channel.delete_messages(batch)
                    except discord.HTTPException as exc:
                        print(f"[cleanup] bulk delete failed in #{channel.name}: {exc}")
                # Delete older messages one by one.
                for msg in old:
                    try:
                        await msg.delete()
                    except discord.HTTPException as exc:
                        print(f"[cleanup] single delete failed: {exc}")
                total_deleted += len(to_delete)

            channels_scanned += 1

        return total_deleted, channels_scanned

    async def _remote_version(self) -> str | None:
        """Return the VERSION string from the remote update repo, or None on failure."""
        data = await self._download(f"{UPDATE_REPO}/VERSION")
        return data.decode("utf-8").strip() if data else None

    async def _apply_update(self) -> int:
        """Download every file in UPDATE_FILES from the remote and write to PROJECT_ROOT.

        Returns the number of files successfully written.
        """
        written = 0
        for name in UPDATE_FILES:
            data = await self._download(f"{UPDATE_REPO}/{name}")
            if data is None:
                print(f"[update] Could not fetch {name} — skipped.")
                continue
            (PROJECT_ROOT / name).write_bytes(data)
            written += 1
        return written

    async def push_backup(self, message: str) -> str | None:        if not self.session:
            return "HTTP session is not ready."
        return await backup_after_change(self.session, message)


class StaffCog(commands.Cog):
    def __init__(self, bot: ZeeNoodle) -> None:
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        if ctx.command is not None and ctx.command.name == "help":
            return True
        if ctx.guild is None or not _is_admin(ctx.author):
            await ctx.send("Administrators only.")
            return False
        return True

    @commands.command(name="help")
    async def help_command(self, ctx: commands.Context) -> None:
        prefix = self.bot.prefix_value
        lines = [
            f"ZeeNoodle {BOT_VERSION} commands (prefix `{prefix}`):",
            f"`{prefix}help` — list commands.",
            f"`{prefix}picture add` — attach an image to start matching it.",
            f"`{prefix}picture remove <filename>` — stop matching that image.",
            f"`{prefix}picture list` — show reference images.",
            f"`{prefix}ignore add #channel` — stop scanning that channel.",
            f"`{prefix}ignore remove #channel` — scan that channel again.",
            f"`{prefix}ignore list` — show ignored channels.",
            f"`{prefix}zeenoodletrigger <new>` — change the prefix (admins).",
            f"`{prefix}picture test` — attach an image to see if it would be deleted.",
            f"`{prefix}backup` — save pictures and ignore list (GitHub if configured).",
            f"`{prefix}restore` — pull that backup and put it back (`{prefix}pull` works too).",
            f"`{prefix}hostlink` — DMs you the hosting panel URL (set HOST_URL in .env).",
            f"`{prefix}cleanup last <x>` — delete scam messages from the last x messages in every public channel.",
            f"`{prefix}cleanup since <YYYY-MM-DD>` — delete scam messages since that date in every public channel.",
            f"`{prefix}cleanup here <x>` — delete scam messages from the last x messages in this channel only.",
            f"`{prefix}update` — check GitHub for a newer version and apply it (restarts automatically).",
        ]
        await ctx.send("\n".join(lines))

    @commands.group(name="picture", invoke_without_command=True)
    async def picture(self, ctx: commands.Context) -> None:
        prefix = self.bot.prefix_value
        await ctx.send(
            f"Use `{prefix}picture add`, `{prefix}picture remove <filename>`, "
            f"or `{prefix}picture list`."
        )

    @picture.command(name="add")
    async def picture_add(self, ctx: commands.Context) -> None:
        images = [item for item in ctx.message.attachments if _is_image_attachment(item)]
        if not images:
            await ctx.send("Attach an image to that message.")
            return
        added = []
        for attachment in images:
            data = await attachment.read()
            try:
                filename = self.bot.detector.add_image(data)
            except ValueError as exc:
                await ctx.send(str(exc))
                return
            added.append(filename)
        note = await self.bot.push_backup(f"Add reference picture {', '.join(added)}")
        text = "Now matching: " + ", ".join(added)
        if note:
            text += f"\n{note}"
        await ctx.send(text)

    @picture.command(name="remove")
    async def picture_remove(self, ctx: commands.Context, *, filename: str) -> None:
        name = Path(filename).name
        if not self.bot.detector.remove_image(name):
            await ctx.send(f"No reference named `{name}`.")
            return
        note = await self.bot.push_backup(f"Remove reference picture {name}")
        text = f"Stopped matching `{name}`."
        if note:
            text += f"\n{note}"
        await ctx.send(text)

    @picture.command(name="test")
    async def picture_test(self, ctx: commands.Context) -> None:
        images = [item for item in ctx.message.attachments if _is_image_attachment(item)]
        if not images:
            await ctx.send("Attach an image to test.")
            return
        lines: list[str] = []
        for attachment in images:
            data = await attachment.read()
            hits = self.bot.detector.match_image(data)
            if hits:
                reasons = ", ".join(
                    f"`{h.reference}` (distance {h.distance})" for h in hits
                )
                lines.append(f"`{attachment.filename}` **would be deleted** — matched {reasons}.")
            else:
                lines.append(f"`{attachment.filename}` would **not** match any reference image.")
        await ctx.send("\n".join(lines))

    @picture.command(name="list")
    async def picture_list(self, ctx: commands.Context) -> None:
        names = self.bot.detector.names()
        if not names:
            await ctx.send("No reference pictures yet.")
            return
        await ctx.send("Reference pictures:\n" + "\n".join(f"- `{name}`" for name in names))

    @commands.group(name="cleanup", invoke_without_command=True)
    async def cleanup(self, ctx: commands.Context) -> None:
        prefix = self.bot.prefix_value
        await ctx.send(
            f"Usage:\n"
            f"`{prefix}cleanup last <x>` — scan the last x messages in every public channel.\n"
            f"`{prefix}cleanup since <YYYY-MM-DD>` — scan all messages since that date.\n"
            f"`{prefix}cleanup here <x>` — scan the last x messages in this channel only."
        )

    @cleanup.command(name="last")
    async def cleanup_last(self, ctx: commands.Context, count: int) -> None:
        """Scan the last *count* messages in every eligible channel."""
        if count < 1 or count > 10000:
            await ctx.send("Count must be between 1 and 10 000.")
            return
        if ctx.guild is None:
            return
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass
        channels = self.bot._eligible_channels(ctx.guild)
        status = await ctx.send(
            f"Scanning last {count} messages across {len(channels)} channel(s)..."
        )
        deleted, scanned = await self.bot._cleanup_channels(
            channels, limit=count, after=None
        )
        await status.edit(
            content=f"Done. Deleted {deleted} message(s) across {scanned} channel(s)."
        )

    @cleanup.command(name="since")
    async def cleanup_since(self, ctx: commands.Context, date_str: str) -> None:
        """Scan all messages since *date_str* (YYYY-MM-DD) in every eligible channel."""
        try:
            dt = datetime.datetime.strptime(date_str, "%Y-%m-%d").replace(
                tzinfo=datetime.timezone.utc
            )
        except ValueError:
            await ctx.send("Use the format `YYYY-MM-DD`, e.g. `2026-09-13`.")
            return
        if ctx.guild is None:
            return
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass
        channels = self.bot._eligible_channels(ctx.guild)
        status = await ctx.send(
            f"Scanning messages since {date_str} across {len(channels)} channel(s)..."
        )
        deleted, scanned = await self.bot._cleanup_channels(
            channels, limit=None, after=dt
        )
        await status.edit(
            content=f"Done. Deleted {deleted} message(s) across {scanned} channel(s)."
        )

    @cleanup.command(name="here")
    async def cleanup_here(self, ctx: commands.Context, count: int) -> None:
        """Scan the last *count* messages in the current channel only."""
        if count < 1 or count > 10000:
            await ctx.send("Count must be between 1 and 10 000.")
            return
        if not isinstance(ctx.channel, discord.TextChannel):
            await ctx.send("This command only works in a text channel.")
            return
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass
        status = await ctx.send(f"Scanning last {count} messages in this channel...")
        deleted, _ = await self.bot._cleanup_channels(
            [ctx.channel], limit=count, after=None
        )
        await status.edit(content=f"Done. Deleted {deleted} message(s).")

    @commands.group(name="ignore", invoke_without_command=True)
    async def ignore(self, ctx: commands.Context) -> None:
        prefix = self.bot.prefix_value
        await ctx.send(
            f"Use `{prefix}ignore add #channel`, `{prefix}ignore remove #channel`, "
            f"or `{prefix}ignore list`."
        )

    @ignore.command(name="add")
    async def ignore_add(self, ctx: commands.Context, channel: discord.TextChannel) -> None:
        result = self.bot.ignore_store.add(channel.id)
        if result == "always":
            await ctx.send(f"{channel.mention} is already ignored (incident channel).")
            return
        if result == "exists":
            await ctx.send(f"{channel.mention} is already ignored.")
            return
        note = await self.bot.push_backup(f"Ignore channel {channel.id}")
        text = f"No longer scanning {channel.mention}."
        if note:
            text += f"\n{note}"
        await ctx.send(text)

    @ignore.command(name="remove")
    async def ignore_remove(
        self, ctx: commands.Context, channel: discord.TextChannel
    ) -> None:
        result = self.bot.ignore_store.remove(channel.id)
        if result == "always":
            await ctx.send("Cannot scan the incident channel.")
            return
        if result == "missing":
            await ctx.send(f"{channel.mention} was not on the ignore list.")
            return
        note = await self.bot.push_backup(f"Unignore channel {channel.id}")
        text = f"Scanning {channel.mention} again."
        if note:
            text += f"\n{note}"
        await ctx.send(text)

    @ignore.command(name="list")
    async def ignore_list(self, ctx: commands.Context) -> None:
        lines = [f"- <#{INCIDENT_CHANNEL_ID}> (incident, always)"]
        for channel_id in self.bot.ignore_store.extra_ids():
            lines.append(f"- <#{channel_id}>")
        await ctx.send("Ignored channels:\n" + "\n".join(lines))

    @commands.command(name="zeenoodletrigger")
    async def zeenoodletrigger(self, ctx: commands.Context, *, new_prefix: str) -> None:
        try:
            prefix = validate_prefix(new_prefix)
        except ValueError as exc:
            await ctx.send(str(exc))
            return
        self.bot.prefix_value = prefix
        os.environ["COMMAND_PREFIX"] = prefix
        set_env_value("COMMAND_PREFIX", prefix, ENV_PATH)
        await ctx.send(f"Prefix is now `{prefix}`. Example: `{prefix}help`.")

    @commands.command(name="backup")
    async def backup_command(self, ctx: commands.Context) -> None:
        await ctx.send("Saving backup...")
        text = await run_manual_backup(self.bot.session)
        await ctx.send(text)

    @commands.command(name="restore", aliases=["pull"])
    async def restore_command(self, ctx: commands.Context) -> None:
        await ctx.send("Restoring backup...")
        text = await run_restore(self.bot.session)
        if text.startswith("Restored"):
            self.bot.detector.reload()
            self.bot.ignore_store.load()
        await ctx.send(text)

    @commands.command(name="update")
    async def update_command(self, ctx: commands.Context) -> None:
        """Check GitHub for a newer version and apply it, then restart."""
        status = await ctx.send("Checking for updates...")
        remote_ver = await self.bot._remote_version()
        if remote_ver is None:
            await status.edit(content="Could not reach GitHub to check for updates.")
            return
        if remote_ver <= BOT_VERSION:
            await status.edit(content=f"Already up to date (v{BOT_VERSION}).")
            return
        await status.edit(
            content=f"Update found: v{BOT_VERSION} → v{remote_ver}. Downloading files..."
        )
        written = await self.bot._apply_update()
        # Re-install packages in a thread so the event loop stays alive.
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                [
                    sys.executable, "-m", "pip", "install",
                    "-r", str(PROJECT_ROOT / "requirements.txt"), "-q",
                ],
                check=False,
            ),
        )
        await status.edit(
            content=(
                f"Updated {written} file(s) to v{remote_ver}. "
                "Restarting in 3 seconds..."
            )
        )
        await asyncio.sleep(3)
        self.bot._restart_pending = True
        await self.bot.close()

    @commands.command(name="hostlink")
    async def hostlink_command(self, ctx: commands.Context) -> None:
        """DM the admin the hosting panel URL stored in HOST_URL."""
        load_dotenv(override=True)
        url = os.environ.get("HOST_URL", "").strip()
        if not url:
            await ctx.author.send(
                "HOST_URL is not set. Add `HOST_URL=<your panel URL>` to your .env file."
            )
        else:
            await ctx.author.send(f"Hosting panel: {url}")
        await ctx.send("Sent to your DMs.")


def _embed_image_urls(message: discord.Message) -> list[str]:
    urls: list[str] = []
    for embed in message.embeds:
        if embed.image and embed.image.url:
            urls.append(embed.image.url)
        if embed.thumbnail and embed.thumbnail.url:
            urls.append(embed.thumbnail.url)
    return urls


def _incident_embed(
    message: discord.Message,
    reason: str,
    deleted: bool,
) -> discord.Embed:
    action = "Deleted" if deleted else "Could not delete"
    embed = discord.Embed(title=f"{action} scam message", color=discord.Color.red())
    embed.add_field(
        name="Who",
        value=f"{message.author.mention} (`{message.author.id}`)",
        inline=False,
    )
    embed.add_field(name="Channel", value=message.channel.mention, inline=False)
    embed.add_field(
        name="When",
        value=f"<t:{int(message.created_at.timestamp())}:F>",
        inline=False,
    )
    embed.add_field(name="Why", value=reason, inline=False)
    embed.add_field(name="Jump", value=message.jump_url, inline=False)
    embed.set_footer(text="ZeeNoodle")
    return embed


def main() -> None:
    token = os.environ.get("DISCORD_TOKEN", "").strip()
    if not token:
        raise SystemExit("DISCORD_TOKEN is missing. Run python setup.py first.")
    if not references_dir().is_dir():
        print("Warning: references/ folder is missing.")
    bot = ZeeNoodle()
    bot.run(token)
    if bot._restart_pending:
        print("[update] Restarting with updated code...")
        os.execv(sys.executable, [sys.executable, str(Path(__file__).resolve())])


if __name__ == "__main__":
    main()
