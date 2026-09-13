# ZeeNoodle

ZeeNoodle is a Discord bot for a 3D printing community. It deletes lacewin-style crypto casino scam images and matching text, then logs the incident in `#bot-incendents`.

## Quick links

- [Quaxly](https://quaxly.com/) — primary hosting
- [Waifly](https://waifly.com/) — fallback hosting

It does **not** treat normal print photos, slicer screenshots, or real filament giveaways as spam.

Current version is in `VERSION` (`xx.xx.xx`).

## What it matches

- Pictures close to the files in `references/` (perceptual hash)
- Narrow text such as `lacewin.com` or crypto-casino bonus wording
- Not generic words like `giveaway` or “this print is EPIC”

`#bot-incendents` is always ignored. You can ignore more channels with commands.

## Windows start

1. Double-click `start.bat`. You can run it again anytime.
2. It installs Python packages if needed.
3. **Update ZeeNoodle from GitHub first? [y/N]** — optional `git pull` plus pip install, then refresh the bot you already host (new Quaxly zip/redeploy, or restart a local process).
4. **Use Quaxly? [Y/n]**
   - **Y** (default): Discord setup if `.env` is missing, then the Quaxly upload walkthrough.
   - **n**: self-host menu (setup, run on this PC, server steps, or update again).

`start.bat` never asks for a Quaxly password. You log in at [quaxly.com](https://quaxly.com/) in your browser.

## Discord application

Run `python setup.py` or use `start.bat`. A window opens with text boxes.

1. Create an application named **ZeeNoodle** at the [Developer Portal](https://discord.com/developers/applications).
2. Bot tab: copy the token, enable **Message Content Intent**, save.
3. Paste the token and Application ID into the setup window.
4. Click **Save and open invite**, then add the bot to your server.

Invite permissions: View Channels, Send Messages, Manage Messages, Embed Links, Attach Files, Read Message History.

Values are stored in `.env` on your PC only. Do not commit `.env` or upload it to Quaxly. Paste the same keys as secrets in the Quaxly panel.

## Commands

The prefix is set in setup (default `!`). Change it with `zeenoodletrigger`.

Anyone:

- `!help` — list commands

Administrators only:

**Pictures**

- `!picture add` — attach an image to start matching it
- `!picture remove <filename>` — stop matching that image
- `!picture list` — show reference images
- `!picture test` — attach an image to see if it would be deleted (and which reference it matched)

**Ignore list**

- `!ignore add #channel` — stop scanning that channel
- `!ignore remove #channel` — scan that channel again
- `!ignore list` — show ignored channels

**Cleanup**

- `!cleanup last <n>` — scan the last n messages in every public, non-ignored channel and delete any scam messages (max 10 000)
- `!cleanup since <YYYY-MM-DD>` — same scan but starting from a specific date
- `!cleanup here <n>` — same as `last` but scoped to the current channel only

**Other**

- `!zeenoodletrigger <new>` — change the command prefix
- `!backup` — save pictures and ignore list (GitHub if you configured **your** remote)
- `!restore` or `!pull` — restore from that backup
- `!hostlink` — DMs you the hosting panel URL (set `HOST_URL` in `.env`)

## Hosting on Quaxly

[Quaxly](https://quaxly.com/) keeps the bot online 24/7. Free tier: 3 bots, 512 MB RAM, 1 GB disk.

1. Run `start.bat` and accept Quaxly, or run `python deploy.py`.
2. Upload `dist/zeenoodle-quaxly.zip` (no `.env`) or connect **your** GitHub repo.
3. Set secrets in the Quaxly panel. Start command: `python bot.py`.
4. If Quaxly shows a volume path, set `DATA_DIR` so pictures survive deploys.
5. Click Start or Deploy, then stay on the logs. The first install can take several minutes. Wait for `ZeeNoodle logged in as ...` before you leave.

## Hosting on Waifly

[Waifly](https://waifly.com/) is the fallback when Quaxly nodes are full. Run `start.bat` and choose Waifly, or run `python deploy.py --waifly`.

1. Create a Python server named ZeeNoodle.
2. Upload `dist/zeenoodle-quaxly.zip` on the Files tab, then Unarchive.
3. Upload your local `.env` into the same folder as `bot.py`.
4. Confirm Startup Command 1 is `pip install -r requirements.txt` and Command 2 is `python bot.py`.
5. Open Console and click **Start**. The bot stays offline until you do this.
6. Stay on Console. `pip install` can take several minutes. Do not click Start again.
7. Wait until you see `ZeeNoodle logged in as ...`. That line means login finished.

## GitHub backup (optional)

Leave `GITHUB_REMOTE` and `GITHUB_TOKEN` blank unless the repo is yours. Downloaders must not inherit someone else’s URL.

If both are set, `backup` and picture/ignore changes can push to that repo. Random Discord members cannot push. Seeing a public repo is not write access.

## Environment keys

See `.env.example`. Typical keys:

| Key | Purpose |
|---|---|
| `DISCORD_TOKEN` | Bot token |
| `INCIDENT_CHANNEL_ID` | Staff log channel |
| `COMMAND_PREFIX` | Command trigger (not `/`) |
| `HASH_DISTANCE` | Image match tightness (default `10`) |
| `DATA_DIR` | Optional persistent folder on a host |
| `GITHUB_REMOTE` | Your repo URL only |
| `GITHUB_TOKEN` | Your personal access token only |
| `GITHUB_BRANCH` | Default `main` |
| `HOST_URL` | Your hosting panel URL (sent via DM by `!hostlink`) |

## Self-host

```text
python -m pip install -r requirements.txt
python setup.py
python bot.py
```

Keep the process running (this PC, Task Scheduler, or systemd on a server).

## License

Use and change this for your own Discord server. Do not use it to run or spread scams.
