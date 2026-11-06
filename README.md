# CK BOT — Updated

## Included
- Preserved `/tiktok` TikTok link Video/Photo retrieval system.
- Removed the Internet Search & Send commands and their web-catalog download implementation.
- Preserved the local Movie Library commands (`/movie`, `/movies`, `/moviedel`, `/movieadd`).
- Enabled the existing 100 offline tools inside groups using `/gtools`, `/gtool`, and `/toolhelp`.
- Preserved the existing group moderation, community hub, RPG, MLBB, reminders, expenses, and other systems.

## Group Tool 100
- `/gtools` — show the 100 tools in five pages.
- `/gtools 1` through `/gtools 5` — open a specific page.
- `/gtool wordcount Hello world` — example text tool.
- `/gtool calc 120*5` — example calculator.
- `/gtool coin` — coin flip.
- `/toolhelp` — list tool names and usage patterns.

## Deploy
1. Upload `main.py` and `requirements.txt` to the root of the GitHub repository.
2. Set the Railway start command to `python main.py` if it is not already configured.
3. Set the Railway variable `TELEGRAM_TOKEN`.
4. Keep your existing `DB_PATH` / Railway Volume settings if you already use persistent storage.
5. Redeploy the Railway service.

The code was checked with Python syntax compilation. A live Telegram/Railway integration test still requires the bot token and deployment environment.
