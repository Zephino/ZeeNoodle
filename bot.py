"""ZeeNoodle: delete lacewin-style scam spam and log it to #bot-incendents."""

from __future__ import annotations

import asyncio
import io
import os
import random
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
from paths import data_root, ignore_file, references_dir, seed_data_dir

load_dotenv()
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

    async def push_backup(self, message: str) -> str | None:
        if not self.session:
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
            f"ZeeNoodle commands (prefix `{prefix}`):",
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

    @commands.command(name="hostlink")
    async def hostlink_command(self, ctx: commands.Context) -> None:
        """DM the admin the hosting panel URL stored in HOST_URL."""
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


if __name__ == "__main__":
    main()
