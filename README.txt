Ck_helpbot — All-in-One Telegram Social Bot
===========================================

This is an additive upgrade of the existing Ck_helpbot main.py. Existing country lookup,
Wikipedia lookup, movie search, public GitHub app/game release search, forced-channel
join check, daily news, breaking news, and news history tables are retained. New database
tables are added with CREATE TABLE IF NOT EXISTS; existing movies/news tables are not deleted.

FEATURES
- Daily news (default 07:00 Asia/Yangon) and breaking-news checks (default every 15 min)
- Sends news to private users who have started the bot and every channel in NEWS_CHANNEL_IDS
- /app and /game public GitHub release search; larger files are split into parts
- /ask AI chat via Pollinations Classic no-key endpoint (free availability/rate limits are not guaranteed)
- /chat, /next, /stop consent-based anonymous text chat
- /points, /leaderboard, /referral
- /admin, /stats, /broadcast, /ban, /unban
- Basic anti-spam rate limiting

DEPLOY TO GITHUB + RAILWAY
1. Upload main.py, requirements.txt, Procfile, README.txt and .env.example to the existing
   Ck_helpbot GitHub repository. Review the diff before replacing any live file.
2. Railway should deploy the repository with start command `python main.py` (Procfile uses worker).
3. Add variables from .env.example to Railway Variables. Never commit real BOT_TOKEN or API keys.
4. Set ADMIN_IDS to your numeric Telegram user ID(s), comma-separated.
5. Add the bot as an administrator to both news channels with permission to post messages.
   NEWS_CHANNEL_IDS accepts comma-separated usernames or numeric chat IDs.
6. Attach a Railway Volume and set DB_PATH to a path inside its mount (e.g. /data/ckhelpbot.db)
   to keep SQLite data across deploys. Do not use ephemeral filesystem for durable user data.
7. If the old bot is already running, avoid running a second polling instance with the same token.
   Deploy by updating the existing Railway service, not creating a parallel worker.

FREE AI
The /ask command uses the Pollinations Classic text endpoint and does not require OPENAI_API_KEY.
This free external service may rate-limit, change, or become unavailable. The prompt is sent to that
provider, so do not send passwords, private information, or sensitive personal data. News and App/Game
search do not depend on this AI endpoint and continue working if AI is unavailable.

LARGE FILE LIMITS
The standard Telegram Bot API has a much smaller upload limit than the Local Bot API server.
For large uploads, deploy a compatible Telegram Local Bot API server with persistent disk and set
TELEGRAM_API_BASE_URL / TELEGRAM_FILE_BASE_URL to its endpoints. The app/game downloader streams
public GitHub release assets only, enforces MAX_APP_DOWNLOAD_GB, and splits large files into parts.
Files larger than 2 GB are not a guarantee: the source must host the file, Railway disk/memory/time
limits must permit it, and the Local Bot API server must support the configured size. For large
assets, use adequate persistent storage; /tmp may be cleared or run out of space.

ANONYMOUS CHAT NOTES
Pairings are in-memory and clear on process restart. This first version relays text only, does not
reveal usernames/IDs to partners, and does not store chat transcripts. Users can /stop at any time.
Do not claim that this provides end-to-end encryption or a fully moderated social network.

TEST STATUS
Run `python -m py_compile main.py` before deployment. External Telegram/API delivery, Railway
persistence, free AI endpoint availability, and large-file transfer must be tested in your own deployed environment.
