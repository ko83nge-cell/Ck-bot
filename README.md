# Ck_helpbot

Telegram bot project with `/start`, `/help`, `/song`, `/warn`, `/warnings`, `/ban`, `/unban`, `/mute`, and `/unmute`.

## Security
- Do not put your Telegram bot token in source code or upload it to GitHub.
- The token previously pasted into chat should be revoked via `@BotFather` and replaced.
- Set `BOT_TOKEN` in your hosting provider's Environment Variables / Secrets.

## Files
- `main.py` — bot code
- `requirements.txt` — Python dependencies
- `Procfile` — worker process command for platforms that support Procfile
- `runtime.txt` — Python runtime hint for compatible hosts

## Run locally
Python 3.11+ recommended.

```bash
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows:
# .venv\Scripts\activate
pip install -r requirements.txt
```

Set environment variables before running:
- `BOT_TOKEN` (required): token from @BotFather
- `OWNER_ID` (optional): your numeric Telegram user ID
- `SONG_URL` (optional): direct HTTP(S) audio file URL
- `SONG_TITLE` and `SONG_ARTIST` (optional)
- `DATA_DIR` (optional): directory for SQLite warning database

Then run:

```bash
python main.py
```

## Railway / worker hosting
1. Upload these files to a **private** GitHub repository.
2. Create a Railway project from that repository.
3. Set `BOT_TOKEN` under Variables. Do not set it in `main.py`.
4. Set the start command to `python main.py` if the platform doesn't automatically use the Procfile.
5. Keep it as a worker/background service; this bot uses Telegram polling and does not need a public web port.
6. Check deployment logs for `Ck_helpbot is starting`.
7. Make sure only one running instance uses this token at a time.

A paid/always-on worker may be required for continuous operation. Review current hosting prices and limits before deploying. Warning counts use SQLite; on ephemeral hosting disks, attach persistent storage or the database may be lost after redeploy/restart.

## Current music behavior
`/song` sends the sample MP3 specified by `SONG_URL`. It does not search arbitrary songs by name. Set `SONG_URL` to a direct audio URL you have permission to distribute.
