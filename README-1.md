# Ck_helpbot for Railway

## Files
- `main.py`: Telegram bot source code
- `requirements.txt`: Python dependencies
- `Procfile`: Railway worker start command

## Railway setup
1. Upload/commit these files to your GitHub repository.
2. In Railway, connect the repository to a Worker service.
3. Add variables:
   - `BOT_TOKEN`: token from BotFather
   - `ADMIN_IDS`: comma-separated Telegram numeric user IDs
   - `DB_PATH`: optional, e.g. `/data/movies_bot.db` if a Railway Volume is mounted at `/data`
4. Set the start command to `python main.py` if Railway does not use the Procfile.
5. Check deployment logs and test `/start`.

Country data is retrieved dynamically from REST Countries; historical/person information comes from Wikipedia. Translation uses Google Translate's public endpoint. These third-party services may occasionally be unavailable or return incomplete results.

For persistent movie records, mount a Railway Volume and set `DB_PATH` to a file path inside the mounted volume. Keep your bot token private.
