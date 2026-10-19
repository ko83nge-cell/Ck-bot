Ck_helpbot + Group Voice Chat Music Player (Merged Build)
========================================================

This package keeps the existing Ck_helpbot code and adds group voice-chat music commands.

Music commands (group/supergroup only; available to all members):
- /play SONG NAME : search and play audio in an already-started group Voice Chat
- /pause : pause current stream
- /resume : resume current stream
- /skip : skip to the next queued song
- /stopmusic : stop and leave the voice chat
- /queue : show current song and queued songs

Railway Variables:
- BOT_TOKEN: existing Ck_helpbot BotFather token
- API_ID: API ID from https://my.telegram.org -> API development tools
- API_HASH: API Hash from the same API application
- SESSION_STRING: user-account session string for the dedicated music account
- Keep existing variables (ADMIN_IDS, channel IDs, database settings, etc.) unchanged.

Important:
1. API_ID and API_HASH are API application credentials, not the user's Telegram ID.
2. SESSION_STRING must be generated from the dedicated Telegram user account that will join the group voice chat. Never share it. Since a session string was previously pasted into chat, terminate that session in Telegram Settings -> Devices and generate a fresh one before deploying.
3. Add the dedicated music account to the group and ensure it can join the voice chat. A group admin must start the Voice Chat first.
4. FFmpeg is included in nixpacks.toml. If Railway uses Railpack instead of Nixpacks, configure RAILPACK_DEPLOY_APT_PACKAGES=ffmpeg if supported by your service setup.
5. Procfile starts `python main.py`. Use a single worker/replica for this bot to avoid duplicate polling and voice clients.
6. The music player uses yt-dlp search (`ytsearch1`) to find audio. Only play material you have permission to use; platform availability and copyright rules apply.
7. This is a code integration, not live-tested against your Telegram account or Railway deployment. After deploy, inspect Railway logs and test in a group where a Voice Chat is already active.
8. Queue support is basic; automatic next-track handling may need adjustments depending on PyTgCalls API/version behavior.
