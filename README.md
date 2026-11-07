# CK BOT — Group / Channel Set Command Update

This build preserves the existing CK BOT features and adds registered command handlers for:

- `/groupmenu` — browse the existing Group modules.
- `/groupset <module_id> on|off` — enable/disable a Group module setting (Group Admin only).
- `/channelmenu @channelname` or `/channelmenu -100...` — view the Channel module catalog (Channel Admin only).
- `/channelset @channelname <setting_id> on|off` — enable/disable a Channel setting (Channel Admin only).
- `/sethelp` — Burmese usage guide.

## Channel catalog

- 50 Channel modules × 20 control entries = 1,000 individually stored settings.
- Channel settings are stored per channel in `ck_channel_settings`.
- Group module settings are stored per group in `ck_group_module_settings`.
- Existing Group module data remains in `ck_group_modules`.

## Important behavior note

The new handlers validate the caller's Group/Channel administrator status and persist each toggle in SQLite. These toggles are configuration records; they do **not** automatically enforce every policy on posts unless a corresponding moderation/automation handler is connected. The bot does not claim all 1,000 controls are separate active automation engines.

For Channel commands, use the command in the bot's private chat and provide the target channel username or numeric ID. The bot must be able to access the channel; add it as a Channel Admin for any channel-side operations you later connect.

## Telegram command menu

On startup, `setup_telegram_command_menus()` publishes supported commands:
- Private menu includes `/channelmenu`, `/channelset`, `/sethelp`.
- Group menu includes `/groupmenu`, `/groupset`, `/sethelp`.
- Existing commands are retained in their respective lists.

## Railway deployment

1. Replace `main.py`, `requirements.txt`, and `README.md` in the root of your GitHub repository.
2. Keep Railway start command: `python main.py`.
3. Keep `TELEGRAM_TOKEN` configured.
4. Keep `DB_PATH` pointed at persistent storage (recommended `/data/ck_bot.db` with a Railway Volume mounted at `/data`).
5. Redeploy.

The new tables are created automatically by `init_db()` and do not require manual SQL migration. Python syntax compilation passed. A live Telegram API test still requires deployment with a valid bot token and access to a test Group/Channel.
