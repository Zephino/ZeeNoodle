# Changelog

All notable changes to the Discord Message Checker Bot are recorded here. The version source of truth is the repo-root `VERSION` file (`xx.xx.xx` odometer).

Each release heading uses **`## [xx.xx.xx] — Weekday, Month D, YYYY, h:mm AM/PM`** (12-hour local time). List changes under `### Added`, `### Changed`, or `### Fixed` as appropriate. Newest release goes at the top, below this intro.

---

## [01.00.34] — Wednesday, September 16, 2026, 7:48 AM

### Added
- Cross-channel spam check. Tracks image pixel hashes and normalized text fingerprints per author. When the same content appears in 2+ channels within `CROSSPOST_SECONDS` (default 120), the existing spam filters run; on a match, all tracked copies are deleted and `#bot-incendents` lists every channel hit with a `cross-posted` reason. Filenames are never used for matching.

---

## [01.00.33] — Sunday, September 13, 2026, 3:03 PM

### Changed
- `GITHUB_BRANCH` default changed from `main` to `data` in `.env.example` and README. The backup branch must not be the same as the code branch or code pushes will overwrite saved pictures and the ignore list.

---

## [01.00.32] — Sunday, September 13, 2026, 2:57 PM

### Changed
- `!update` now restores pictures and config from your personal GitHub backup after applying the code update, before restarting. This ensures custom reference images survive on hosts where the data directory is not persistent.

---

## [01.00.31] — Sunday, September 13, 2026, 2:56 PM

### Fixed
- `commit_and_push` was treating untracked code files (shown as `?? filename` in `git status --porcelain`) as staged changes. This caused `git commit` to run and fail with "nothing added to commit" whenever the hosted container had code files sitting next to the git repo. The check now filters out `??` lines so only genuinely staged changes trigger a commit.

---

## [01.00.30] — Sunday, September 13, 2026, 2:49 PM

### Fixed
- `data_root` was missing from the `paths` import in `github_backup.py`, causing a `NameError` on any backup command.

---

## [01.00.29] — Sunday, September 13, 2026, 2:45 PM

### Fixed
- GitHub backup now uses `data_root()` as the git working directory instead of `PROJECT_ROOT`. When `DATA_DIR` is set on a host, `backup/`, `references/`, and `config/` live inside `DATA_DIR`; the old code pointed git at the wrong location and the `git add` failed silently.
- `commit_and_push` and `upload_via_contents_api` now return the real git or API error text instead of a generic message, so the bot message shows exactly what went wrong.

---

## [01.00.28] — Sunday, September 13, 2026, 2:39 PM

### Changed
- Commands are now case-insensitive. `!Help`, `!HELP`, `!Cleanup Last 50` etc. all work.

---

## [01.00.27] — Sunday, September 13, 2026, 2:35 PM

### Fixed
- `SyntaxError` in `bot.py`: `push_backup` definition and its body were incorrectly joined onto one line by a previous edit. Split back onto separate lines.

---

## [01.00.26] — Sunday, September 13, 2026, 2:29 PM

### Added
- After an `!update` restart, the bot DMs the admin who triggered it once it is back online. The admin's user ID and new version are written to `.update_notify.json` before `os.execv` so the info survives the process replacement. `on_ready` reads and deletes the file, then sends the DM.

---

## [01.00.25] — Sunday, September 13, 2026, 2:27 PM

### Changed
- `!update` no longer posts anything in the channel it was run in. All progress and the changed-file list are DM'd to the issuing admin. On a successful update, a single line is posted to `#bot-incendents` naming the new version and who triggered it.

---

## [01.00.24] — Sunday, September 13, 2026, 2:25 PM

### Changed
- `!update` now compares each remote file to the local copy before writing, so only genuinely changed files are touched. The admin who ran the command receives a DM listing exactly which files were updated and any that could not be fetched.

---

## [01.00.23] — Sunday, September 13, 2026, 2:21 PM

### Added
- `!update` command (admin-only). Fetches the remote `VERSION`, compares it to the running version, and if newer: downloads all code files from `UPDATE_REPO`, runs `pip install -r requirements.txt`, then restarts the process automatically via `os.execv`. Admins no longer need to touch the hosting panel to apply updates.
- `UPDATE_REPO` env key (optional). Defaults to the official raw GitHub URL. Set it to a fork's raw URL to pull updates from a different repo.

---

## [01.00.22] — Sunday, September 13, 2026, 2:16 PM

### Changed
- Cleanup command placeholders changed from `<n>` to `<x>` in `!help` output and README.

---

## [01.00.21] — Sunday, September 13, 2026, 2:14 PM

### Changed
- `!help` header now reads `ZeeNoodle <version> commands (prefix ...)` so the running version is visible at a glance.

---

## [01.00.20] — Sunday, September 13, 2026, 10:20 AM

### Fixed
- `^hostlink` now calls `load_dotenv(override=True)` before reading `HOST_URL`, so changes to `.env` while the bot is running are picked up without a restart.

---

## [01.00.19] — Sunday, September 13, 2026, 10:15 AM

### Added
- `^cleanup last <n>` — scans the last n messages in every public, non-ignored channel and deletes any that match a reference image.
- `^cleanup since <YYYY-MM-DD>` — same scan but bounded by a date instead of a message count.
- `^cleanup here <n>` — same as `last` but scoped to the channel where the command is run.
- All three variants: delete the command message immediately; skip the incident channel and any ignored channels; skip channels where `@everyone` cannot read; bulk-delete messages under 14 days old, single-delete older ones; also remove the bot's own "Now matching:" and "Sent to your DMs." replies found in history.

---

## [01.00.18] — Sunday, September 13, 2026, 9:58 AM

### Removed
- Burst-grouping logic. Every detected scam message now posts its own incident in `#bot-incendents` immediately. Previously, multiple incidents from the same user within 30 seconds were silently merged into one edited post, making it look like nothing was being reported.

---

## [01.00.17] — Sunday, September 13, 2026, 9:57 AM

### Fixed
- GitHub backup now uses `git push --force` so the Waifly instance is always the source of truth. Previously the push was rejected if the remote had commits the hosted bot did not have locally.

---

## [01.00.16] — Sunday, September 13, 2026, 9:43 AM

### Added
- `!hostlink` command (admin-only). DMs the hosting panel URL to the admin who runs the command. URL is read from `HOST_URL` in `.env` so it is never visible in a public channel.
- `HOST_URL` key added to `.env.example`, the README env table, and `deploy.py` `ENV_KEYS` so the update walkthrough lists it.
- "Quick links" section near the top of README with direct links to Quaxly and Waifly homepages.

---

## [01.00.15] — Sunday, September 13, 2026, 9:37 AM

### Changed
- `picture add` no longer uses the Discord attachment filename. The bot now saves each image with an auto-generated timestamped name (e.g. `ref_20260913_093700.png`) and detects the format from the image content itself. This prevents name collisions and removes the dependency on whatever name Discord assigns to a pasted image.

---

## [01.00.14] — Tuesday, September 8, 2026, 9:12 PM

### Changed
- Waifly and Quaxly walkthroughs now say to click Start after `.env` is uploaded, then wait on the console through `pip install` until `ZeeNoodle logged in as ...`. The first install is slow and it was easy to stop after the file upload.

## [01.00.13] — Tuesday, September 8, 2026, 8:50 PM

### Added
- `start.bat` now reads `.env` and prints each setting as filled, blank, or still needed. Tokens stay hidden. Users were reopening the starter and could not tell what was already saved.

### Changed
- Starter asks whether to open the setup form after that readout. Changing values no longer requires remembering to run `setup.py` by hand.

## [01.00.12] — Tuesday, September 8, 2026, 8:33 PM

### Added
- `_keepalive_loop` background task in `bot.py`. Writes a timestamp to `heartbeat.txt` at a random interval between 12 and 20 hours. Keeps the Waifly container active so it is not suspended for inactivity.

## [01.00.11] — Tuesday, September 8, 2026, 8:28 PM

### Added
- `deploy.py --waifly` flag with a step-by-step Waifly upload walkthrough. Quaxly nodes were full so users need an alternative host.
- `deploy.py --waifly --update` path for refreshing an existing Waifly bot after a code update.
- `start.bat` host selection menu (Quaxly / Waifly / Self-host). Previously defaulted to Quaxly only with no way to pick Waifly.

## [01.00.10] — Tuesday, September 8, 2026, 7:44 PM

### Added
- `picture test` command. Attach an image and the bot replies whether it would be deleted and which reference it matched. Needed a quick way to check images before adding them as references.

## [01.00.09] — Tuesday, September 8, 2026, 7:41 PM

### Added
- `deploy.py --update` and a starter path that replaces files on the ZeeNoodle bot already hosted on Quaxly (or restarts a local copy). A local git pull alone does not update the running host.

## [01.00.08] — Tuesday, September 8, 2026, 7:40 PM

### Added
- Optional GitHub update step in `start.bat` when you rerun it. Operators need a way to pull new code, then keep using Quaxly or self-host.

## [01.00.07] — Tuesday, September 8, 2026, 7:38 PM

### Added
- `README.md` with start, setup, commands, Quaxly, and GitHub notes. New users need a single place to learn how to run ZeeNoodle.

## [01.00.06] — Tuesday, September 8, 2026, 7:35 PM

### Added
- `backup` and `restore` (`pull`) commands. Staff need a way to save pictures and ignore lists, then put that copy back from GitHub or the local `backup/` folder.

## [01.00.05] — Tuesday, September 8, 2026, 7:31 PM

### Added
- Setup window with text boxes for the Discord token, Application ID, prefix, and optional GitHub fields. Users need a place to paste portal values so `.env` is stored on this PC.

## [01.00.04] — Tuesday, September 8, 2026, 7:29 PM

### Changed
- `start.bat` now defaults to the Quaxly install walkthrough. Users who have their own server can answer no and get a self-host menu plus server steps.

## [01.00.03] — Tuesday, September 8, 2026, 7:25 PM

### Added
- Quaxly hosting files (`Procfile`, `runtime.txt`), optional `DATA_DIR`, `deploy.py`, and `start.bat`. The bot needs a 24/7 host and a Windows way to install deps, then run setup, the bot, or the Quaxly zip walkthrough.
- GitHub Contents API backup when `git` is missing. Quaxly containers may not have git.

### Changed
- Live `references/`, `config/`, and `backup/` follow `DATA_DIR` when that env is set. Hosted files must survive deploys.

## [01.00.02] — Tuesday, September 8, 2026, 7:16 PM

### Added
- Prefix commands `picture add/remove/list`, `ignore add/remove/list`, `help`, and `zeenoodletrigger`. Staff need a way to manage scam pictures and skipped channels without slash commands.
- `config/ignored_channels.json` plus a `backup/` mirror of pictures and ignore IDs. Lists must survive a restart and stay copyable.
- Optional GitHub create/push using only the operator's `GITHUB_REMOTE` and `GITHUB_TOKEN` from `.env`. Downloaders must not inherit someone else's repo URL.

### Changed
- `setup.py` now asks for a command prefix (not `/`) and optional blank GitHub fields. First-time setup has to store those values locally.

## [01.00.01] — Tuesday, September 8, 2026, 6:58 PM

### Added
- ZeeNoodle bot (`bot.py`, `detector.py`) that deletes lacewin-style scam images and narrow casino text in every channel, then reports to `#bot-incendents`. Needed a live filter for the screenshot spam hitting the 3D printing server.
- Perceptual hashes of the four `references/` screenshots, plus text checks for lacewin and crypto-casino wording only. Generic giveaway posts must stay up.
- Burst logging that updates one staff report when the same user hits many channels within 30 seconds. Stops `#bot-incendents` from being flooded too.
- `setup.py` walkthrough that writes `.env` and builds the invite URL. Creating a Discord application has to be done in the Developer Portal by hand.

## [01.00.00] — Tuesday, September 8, 2026, 6:35 PM

### Added
- Four reference screenshots under `references/`. Needed the lacewin-style scam pattern on disk for later detection work.
- Always-on Cursor rules for ask-then-wait, Google developer documentation style, version odometer bumps, and changelog entries. Later code changes need a consistent process, version, and explanation.
