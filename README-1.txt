Ck_helpbot — Railway Group + Channel Upgrade
=============================================

This package upgrades the latest Ck_helpbot source additively. It retains existing
commands and SQLite data tables (movies, games, news subscribers/history, social users,
referrals and anonymous-chat state). New tables use CREATE TABLE IF NOT EXISTS; no
existing tables are dropped.

FEATURES
- Existing /start, /help, /news, /app, /game, /ask, /chat, /next, /stop,
  /points, /leaderboard, /referral, /admin, /stats, /broadcast, /ban, /unban.
- Burmese daily news (default 07:00 Asia/Yangon) and breaking-news checks (default
  every 15 minutes), sent to users who have started the bot and configured channels.
- Group tools: /grouphelp, /rules, /setrules, /setwelcome, /warn, /mute, /unmute,
  /pin, /purge, /id; welcome message for new members.
- /poll question | option 1 | option 2 — native Telegram anonymous poll (2–10 options).
- /report — reply to a message with /report [reason]; stores the report and attempts
  to notify configured ADMIN_IDS privately.
- /status — basic live/database status.
- App/Game discovery uses public releases and official storefront/search links; it does
  not bypass paywalls, private access, or publisher protections.
- /ask uses an external free AI endpoint. Availability, rate limits, and privacy terms
  are controlled by that provider; do not send secrets or sensitive personal data.
- Anonymous chat is opt-in; use /stop to disconnect. The app should be tested with
  trusted users before promoting it publicly.
- Basic spam rate-limiting, user bans, points, leaderboard, referrals and admin stats.

RAILWAY DEPLOYMENT
1. Unzip this package and copy main.py, requirements.txt, Procfile, README.txt and
   .env.example to the root of the existing Ck_helpbot GitHub repository. Review the
   diff before replacing live files.
2. Railway should deploy from that repository. Procfile starts `python main.py` as a
   worker; do not also run a second instance with the same bot token (polling conflicts).
3. Set Railway Variables (do not commit real tokens):
   - BOT_TOKEN: token from @BotFather (required)
   - ADMIN_IDS: your numeric Telegram user ID(s), comma-separated (required for admin tools)
   - DB_PATH: `/data/ckhelpbot.db` if using a mounted volume; otherwise `movies_bot.db`
   - NEWS_CHANNEL_IDS: comma-separated channel usernames or numeric IDs
   - NEWS_DAILY_HOUR=7, NEWS_CHECK_MINUTES=15, TIMEZONE=Asia/Yangon (optional defaults)
   - CHANNEL_USERNAME and CHANNEL_URL only if forced channel joining is wanted
   - GAME_CHANNEL_ID only if app/game files should be copied to a channel
   - MAX_APP_DOWNLOAD_GB and DOWNLOAD_DIR for app/game download limits
   - TELEGRAM_API_BASE_URL and TELEGRAM_FILE_BASE_URL only when using a separately
     hosted Telegram Local Bot API server; these do not create that server for you.
4. Attach a Railway Volume and mount it at `/data`; set DB_PATH to `/data/ckhelpbot.db`
   to preserve SQLite data across redeploys. Without a volume, local SQLite files may
   be lost on redeploy. SQLite is suitable for a single worker; do not run multiple
   bot replicas against the same SQLite file.
5. Add the bot as admin to every destination channel with permission to post messages.
   For group moderation, add it as admin with only the permissions it needs (delete,
   restrict members, pin messages). Telegram cannot moderate messages it cannot see;
   adjust group privacy settings if needed.
6. Test /start, /help, /news, /poll, /report, /grouphelp, /stats and channel delivery.
   Check Railway logs for errors. Never share BOT_TOKEN publicly.

IMPORTANT LIMITATIONS
- Railway storage is not itself a Telegram Local Bot API server. Telegram's hosted Bot
  API has file size limits; support for files over 2 GB requires a separately operated
  Local Bot API service and appropriate download/storage bandwidth. The included app
  search/file splitting cannot guarantee a single Telegram upload larger than Telegram's
  current API limit.
- Daily news / breaking news depends on upstream RSS and external translation availability.
- A poll command requires the bot to be able to send messages in the selected chat.
- /report records a report even if admin notifications fail; admins must have started the
  bot and not blocked it to receive private notifications.
