# Changelog

All notable changes to the Discord Message Checker Bot are recorded here. The version source of truth is the repo-root `VERSION` file (`xx.xx.xx` odometer).

Each release heading uses **`## [xx.xx.xx] — Weekday, Month D, YYYY, h:mm AM/PM`** (12-hour local time). List changes under `### Added`, `### Changed`, or `### Fixed` as appropriate. Newest release goes at the top, below this intro.

---

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
