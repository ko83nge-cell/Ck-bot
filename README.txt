# Ck_helpbot (GitHub + Railway)

## Files
- `bot.py`: complete bot code with automatic daily news and breaking-news broadcast.
- `requirements.txt`: Python dependencies.

## Railway Variables
Required:
- `BOT_TOKEN`: Telegram bot token from BotFather.

Recommended:
- `CHANNEL_USERNAME`: required channel username for the existing join check, e.g. `@mychannel`
- `CHANNEL_URL`: join link, e.g. `https://t.me/mychannel`
- `NEWS_CHANNEL_ID`: channel destination, e.g. `@mychannel` (or numeric `-100...` ID for a private channel)
- `DAILY_NEWS_HOUR`: `7` (Myanmar time)
- `BREAKING_INTERVAL_MINUTES`: `15`
- `TIMEZONE`: `Asia/Yangon`
- `DB_PATH`: optional; default `ck_helpbot.db`

Add the bot as an administrator in the destination channel with permission to post messages.
For private channels, set `NEWS_CHANNEL_ID` to the numeric channel ID.

## Important
- Users must open the bot and press `/start` before they can receive private broadcast messages.
- This code stores subscriber IDs and sent-news URLs in SQLite. On Railway, attach a persistent volume and set `DB_PATH` to a path inside that volume (for example `/data/ck_helpbot.db`) so data survives redeploys/restarts.
- Breaking news is based on recent Google News RSS search results and is not a guarantee that every item is verified breaking news.
- If you already have a different bot.py with additional custom features, back it up before replacing it.
