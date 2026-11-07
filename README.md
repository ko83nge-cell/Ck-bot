# CK BOT — Group System 500 + Burmese Help Menu

## Added in this update

- `/groupmenu` opens a separate Group System menu.
- The root menu includes **📖 အသုံးပြုနည်း** (How to Use).
- Every module has its own **📖 ဒီ Module အသုံးပြုနည်း** button.
- Help pages explain how to enable/disable controls, what the status icons mean, the required Telegram permissions, and important limitations.
- 25 modules × 20 separately stored controls = 500 configuration entries.
- Per-group settings are stored in SQLite (`ck_group500_settings`).
- Only Telegram Group Admins can change settings.
- The bot must be a Group Admin with Delete Messages permission for moderation removals.

## Important behavior note

The menu has 500 configuration entries, but the current automatic message-protection engine uses 20 shared policy types across the 25 modules. Therefore, the same policy may be represented in multiple modules; enabling that policy in one module can affect the whole group. This is not 500 independent moderation engines. The in-menu help explains this to group admins.

## Use

1. Add CK BOT to your Telegram group.
2. Promote CK BOT to Group Admin and allow Delete Messages.
3. Send `/groupmenu` in the group.
4. Tap a module, then tap a control to turn it on (`🟢`) or off (`⚪`).
5. Tap **📖 အသုံးပြုနည်း** for the general guide, or **📖 ဒီ Module အသုံးပြုနည်း** for module-specific help.

## Existing commands

- `/gtools` — existing offline tools menu.
- `/gtool wordcount Hello world` — example text tool.
- `/toolhelp` — existing tool help.

Existing CK BOT features and dependencies are retained. No new Python package is required.

## Railway deployment

1. Replace the files in the GitHub repository with `main.py`, `requirements.txt`, and this `README.md`.
2. Railway start command: `python main.py`.
3. Set `TELEGRAM_TOKEN` in Railway Variables.
4. Keep your existing `DB_PATH` and Railway Volume settings. For persistent storage, mount a Railway Volume at `/data` and set `DB_PATH=/data/ck_bot.db`.
5. Redeploy.

The updated Python file passed syntax compilation. A live Telegram test still requires deployment with the user's bot token and group permissions.
