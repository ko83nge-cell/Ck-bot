Ck_helpbot — Music Removed Build
================================

This build removes the old Music Player completely and replaces it with a Smart Direct File Assistant:
- /fetch https://example.com/file.zip : downloads a public direct file URL and sends it back (maximum 45 MB per file).
- /urlinfo https://example.com/file.zip : checks public URL response status, content type and declared size.

Existing News scheduling, Channel delivery, Group moderation, App/Game search, AI question command, anonymous chat, points/referrals, admin tools, and other existing features are retained from the supplied main.py.

PRIVATE TELEGRAM ACCOUNT AUTO-REPLY
===================================
Auto Reply runs independently in auto_reply.py; it does not depend on Music.
Railway Variables:
- AUTO_REPLY_ENABLED=true
- AUTO_REPLY_COOLDOWN_SECONDS=1800 (minimum 60 seconds)
- API_ID, API_HASH, SESSION_STRING: required for personal Telegram account auto-reply
Keep existing BOT_TOKEN, ADMIN_IDS, channel IDs, database variables and all other existing variables.
Never paste API_HASH or SESSION_STRING into chat or GitHub. If session credentials were exposed, terminate that Telegram session in Settings -> Devices and generate a new one.

RAILWAY
=======
- Start Command: python main.py
- Keep a single replica/worker to avoid duplicate Telegram polling and user-account sessions.
- This direct-file helper accepts only public HTTP(S) URLs and rejects local/private destinations. It does not bypass login, DRM, paywalls or website restrictions.
- Files are limited to 45 MB to fit the standard Telegram Bot API upload limit. Larger files require a separately configured Telegram Local Bot API server and further code/configuration.
- /fetch supports direct file URLs, not arbitrary webpages whose download button hides the actual file URL.
- Syntax checks are not a live test. After deploying, test /start, /news, group moderation commands, /fetch, /urlinfo, and private auto-reply from a second Telegram account. Check Railway logs for errors.
