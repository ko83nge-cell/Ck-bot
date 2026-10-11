Python

import os
import re
import sqlite3
import logging
import asyncio
import tempfile
import shutil
import base64
import binascii
from pathlib import Path
from collections import defaultdict
from contextlib import suppress

import yt_dlp

from telegram import (
    Update,
    ChatPermissions,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ==========================================
# CONFIGURATION
# ==========================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID = int(os.getenv("OWNER_ID", "8062359539"))
YOUTUBE_COOKIES_B64 = os.getenv(
    "YOUTUBE_COOKIES_B64", ""
).strip()

DB_PATH = os.getenv(
    "DATABASE_PATH", "ckhelpbot.sqlite3"
)

MAX_AUDIO_SIZE = 45 * 1024 * 1024
SEARCH_RESULTS = 20
PAGE_SIZE = 5
MAX_PARALLEL_DOWNLOADS = 2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("yt_dlp").setLevel(logging.WARNING)

logger = logging.getLogger("CkHelpBot")

download_semaphore = asyncio.Semaphore(
    MAX_PARALLEL_DOWNLOADS
)
user_locks = defaultdict(asyncio.Lock)


# ==========================================
# DATABASE
# ==========================================

def init_db():
    Path(DB_PATH).parent.mkdir(
        parents=True, exist_ok=True
    )

    with sqlite3.connect(DB_PATH, timeout=20) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS warnings (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (chat_id, user_id)
            )
        """)


def add_warning(chat_id, user_id):
    with sqlite3.connect(DB_PATH, timeout=20) as db:
        db.execute("""
            INSERT INTO warnings (chat_id, user_id, count)
            VALUES (?, ?, 1)
            ON CONFLICT(chat_id, user_id)
            DO UPDATE SET count = count + 1
        """, (chat_id, user_id))

        row = db.execute("""
            SELECT count FROM warnings
            WHERE chat_id = ? AND user_id = ?
        """, (chat_id, user_id)).fetchone()

        return row[0] if row else 0


def get_warnings(chat_id, user_id):
    with sqlite3.connect(DB_PATH, timeout=20) as db:
        row = db.execute("""
            SELECT count FROM warnings
            WHERE chat_id = ? AND user_id = ?
        """, (chat_id, user_id)).fetchone()

        return row[0] if row else 0


# ==========================================
# HELPERS
# ==========================================

async def reply(update, text, **kwargs):
    if update.effective_message:
        await update.effective_message.reply_text(
            text, **kwargs
        )


async def get_target(update):
    message = update.effective_message

    if message and message.reply_to_message:
        return message.reply_to_message.from_user

    return None


async def is_admin(update, context):
    user = update.effective_user
    chat = update.effective_chat

    if not user or not chat:
        return False

    if user.id == OWNER_ID:
        return True

    if chat.type == "private":
        return False

    try:
        member = await context.bot.get_chat_member(
            chat.id, user.id
        )
        return member.status in ("administrator", "creator")

    except TelegramError:
        logger.exception("Admin check failed")
        return False


async def require_group(update):
    chat = update.effective_chat

    if not chat or chat.type not in ("group", "supergroup"):
        await reply(
            update,
            "❌ ဒီ command ကို Group ထဲမှာ အသုံးပြုပါ။",
        )
        return False

    return True


def write_cookies(folder):
    if not YOUTUBE_COOKIES_B64:
        return None

    try:
        encoded = "".join(YOUTUBE_COOKIES_B64.split())
        raw = base64.b64decode(encoded, validate=True)
        content = raw.decode("utf-8-sig")

    except (binascii.Error, UnicodeDecodeError, ValueError):
        raise RuntimeError(
            "YOUTUBE_COOKIES_B64 ပုံစံ မမှန်ပါ။"
        )

    headers = (
        "# Netscape HTTP Cookie File",
        "# HTTP Cookie File",
        "# This is a generated file!",
        "# Netscape",
    )

    if not content.startswith(headers):
        raise RuntimeError(
            "Netscape cookies.txt ပုံစံကို အသုံးပြုပါ။"
        )

    if not re.search(
        r"(?m)^(?:#HttpOnly_)?\.?youtube\.com\s",
        content,
    ):
        raise RuntimeError(
            "Cookies ထဲတွင် YouTube domain မတွေ့ပါ။"
        )

    cookie_path = Path(folder) / "cookies.txt"
    cookie_path.write_text(content, encoding="utf-8")

    with suppress(OSError):
        cookie_path.chmod(0o600)

    return str(cookie_path)


# ==========================================
# START / HELP
# ==========================================

async def start(update, context):
    await reply(
        update,
        "မင်္ဂလာပါ 👋 Ck_helpbot မှ ကြိုဆိုပါတယ်။\n\n"
        "🎵 သီချင်းရှာရန်\n"
        "/song Shape of You\n\n"
        "/help - အကူအညီကြည့်ရန်\n\n"
        "ℹ️ Channel Join မလိုအပ်ပါ။",
    )


async def help_command(update, context):
    await reply(
        update,
        "📚 Ck_helpbot Commands\n\n"
        "🎵 အသုံးပြုသူများ\n"
        "/start - Bot စတင်ရန်\n"
        "/help - အကူအညီကြည့်ရန်\n"
        "/song သီချင်းအမည် - သီချင်းရှာရန်\n\n"
        "🛡️ Group Admin Commands\n"
        "/warn - Reply လုပ်ထားသူကို Warning ပေးရန်\n"
        "/warnings - Warning ကြည့်ရန်\n"
        "/ban - Reply လုပ်ထားသူကို Ban လုပ်ရန်\n"
        "/unban USER_ID - Unban လုပ်ရန်\n"
        "/mute - Reply လုပ်ထားသူကို Mute လုပ်ရန်\n"
        "/unmute - Reply လုပ်ထားသူကို Unmute လုပ်ရန်\n\n"
        "သီချင်းရယူနိုင်မှုသည် YouTube၊ Railway၊ "
        "FFmpeg နှင့် Network အခြေအနေပေါ် မူတည်ပါတယ်။",
    )


# ==========================================
# SONG SEARCH
# ==========================================

def search_songs(search_text):
    with tempfile.TemporaryDirectory() as folder:
        cookie_path = write_cookies(folder)

        options = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "skip_download": True,
            "noplaylist": True,
            "socket_timeout": 25,
            "retries": 2,
            "cachedir": False,
        }

        if cookie_path:
            options["cookiefile"] = cookie_path

        with yt_dlp.YoutubeDL(options) as ydl:
            result = ydl.extract_info(
                f"ytsearch{SEARCH_RESULTS}:{search_text}",
                download=False,
            )

        songs = []

        for item in (result or {}).get("entries") or []:
            if not item:
                continue

            video_id = str(item.get("id") or "")

            if not re.fullmatch(r"[A-Za-z0-9_-]{6,20}", video_id):
                continue

            songs.append({
                "id": video_id,
                "title": str(item.get("title") or "Unknown")[:200],
            })

        return songs


def song_keyboard(songs, offset=0):
    buttons = []
    end = min(offset + PAGE_SIZE, len(songs))

    for index in range(offset, end):
        title = songs[index]["title"][:45]

        buttons.append([
            InlineKeyboardButton(
                f"{index + 1}. {title}",
                callback_data=f"pick:{index}",
            )
        ])

    navigation = []

    if offset > 0:
        navigation.append(
            InlineKeyboardButton(
                "⬅️ အရင်",
                callback_data=f"page:{offset - PAGE_SIZE}",
            )
        )

    if end < len(songs):
        navigation.append(
            InlineKeyboardButton(
                "နောက်ထပ် ➡️",
                callback_data=f"page:{end}",
            )
        )

    if navigation:
        buttons.append(navigation)

    buttons.append([
        InlineKeyboardButton(
            "❌ ပိတ်ရန်", callback_data="close"
        )
    ])

    return InlineKeyboardMarkup(buttons)


async def song(update, context):
    message = update.effective_message

    if not message:
        return

    search_text = " ".join(context.args).strip()

    if not search_text:
        await message.reply_text(
            "🎵 သီချင်းအမည် ထည့်ပါ။\n"
            "ဥပမာ - /song Shape of You"
        )
        return

    status = await message.reply_text(
        "🔎 သီချင်းရှာဖွေနေပါတယ်..."
    )

    try:
        songs = await asyncio.to_thread(
            search_songs, search_text
        )

        if not songs:
            await status.edit_text(
                "❌ သီချင်းမတွေ့ပါ။ အမည်ပြန်စစ်ပြီး ကြိုးစားပါ။"
            )
            return

        context.user_data["songs"] = songs
        context.user_data["song_owner"] = update.effective_user.id

        await status.edit_text(
            f"🎵 သီချင်း {len(songs)} ပုဒ် တွေ့ပါတယ်။\n"
            "လိုချင်တဲ့သီချင်းကို ရွေးပါ။",
            reply_markup=song_keyboard(songs),
        )

    except Exception:
        logger.exception("Song search failed")
        await status.edit_text(
            "❌ သီချင်းရှာမရပါ။ YouTube သို့မဟုတ် "
            "Network ပြဿနာ ဖြစ်နိုင်ပါတယ်။"
        )


# ==========================================
# AUDIO DOWNLOAD
# ==========================================

def download_song(video_id, folder):
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg မတွေ့ပါ။")

    cookie_path = write_cookies(folder)

    options = {
        "format": "bestaudio/best",
        "outtmpl": str(Path(folder) / "audio.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 35,
        "retries": 3,
        "fragment_retries": 3,
        "cachedir": False,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    }

    if cookie_path:
        options["cookiefile"] = cookie_path

    url = f"https://www.youtube.com/watch?v={video_id}"

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)

    audio_path = Path(folder) / "audio.mp3"

    if not audio_path.exists():
        raise RuntimeError("MP3 မဖန်တီးနိုင်ပါ။")

    size = audio_path.stat().st_size

    if size == 0:
        raise RuntimeError("MP3 ဖိုင် အလွတ်ဖြစ်နေပါတယ်။")

    if size > MAX_AUDIO_SIZE:
        raise RuntimeError("Audio ဖိုင် 45 MB ထက် ကြီးနေပါတယ်။")

    return (
        str(audio_path),
        str(info.get("title") or "Unknown"),
        str(info.get("uploader") or "Unknown"),
    )


# ==========================================
# SONG CALLBACK
# ==========================================

async def song_callback(update, context):
    query = update.callback_query

    if not query:
        return

    data = query.data or ""

    if context.user_data.get("song_owner") != query.from_user.id:
        await query.answer(
            "ဒီသီချင်းစာရင်းကို ရှာထားသူသာ ရွေးနိုင်ပါတယ်။",
            show_alert=True,
        )
        return

    if data == "close":
        await query.answer()
        await query.edit_message_text(
            "သီချင်းစာရင်းကို ပိတ်လိုက်ပါပြီ။"
        )
        return

    songs = context.user_data.get("songs", [])

    if data.startswith("page:"):
        try:
            offset = int(data.split(":", 1)[1])

            if offset < 0 or offset >= len(songs) or offset % PAGE_SIZE:
                raise ValueError

            await query.answer()
            await query.edit_message_text(
                f"🎵 သီချင်းစာရင်း ({offset + 1}–"
                f"{min(offset + PAGE_SIZE, len(songs))}"
                f" / {len(songs)})",
                reply_markup=song_keyboard(songs, offset),
            )

        except (ValueError, TelegramError):
            with suppress(TelegramError):
                await query.answer(
                    "စာရင်းကို ပြန်ရှာပါ။",
                    show_alert=True,
                )
        return

    if not data.startswith("pick:"):
        await query.answer()
        return

    try:
        index = int(data.split(":", 1)[1])
        selected = songs[index]
    except (ValueError, IndexError):
        await query.answer(
            "သီချင်းစာရင်းကို ပြန်ရှာပါ။",
            show_alert=True,
        )
        return

    await query.answer()

    user_id = query.from_user.id
    lock = user_locks[user_id]

    if lock.locked():
        await query.message.reply_text(
            "⏳ Audio ရယူနေပြီးသားပါ။ ပြီးသည်အထိ စောင့်ပါ။"
        )
        return

    await query.edit_message_text(
        "⏳ Audio ပြင်ဆင်နေပါတယ်။\n"
        + selected["title"][:150]
    )

    async with lock:
        try:
            async with download_semaphore:
                with tempfile.TemporaryDirectory() as folder:
                    audio_path, title, performer = await asyncio.to_thread(
                        download_song, selected["id"], folder
                    )

                    with open(audio_path, "rb") as audio:
                        await context.bot.send_audio(
                            chat_id=query.message.chat_id,
                            audio=audio,
                            title=title[:64],
                            performer=performer[:64],
                            read_timeout=180,
                            write_timeout=180,
                            connect_timeout=30,
                            pool_timeout=30,
                        )

            await query.message.reply_text(
                f"✅ Audio ပို့ပြီးပါပြီ။\n🎵 {title[:200]}"
            )

        except Exception as exc:
            logger.exception("Audio download/send failed")
            error = str(exc).lower()

            if "ffmpeg" in error:
                message = "❌ FFmpeg မရှိပါ။ Railway Build ကို စစ်ပါ။"
            elif any(word in error for word in (
                "sign in to confirm", "cookies",
                "login required", "confirm you're not a bot",
            )):
                message = (
                    "❌ YouTube က ဝင်ရောက်ခွင့်ကို ကန့်သတ်ထားပါတယ်။ "
                    "Cookies သက်တမ်းနဲ့ Railway Variables ကို စစ်ပါ။"
                )
            elif any(word in error for word in (
                "nsig extraction failed", "unable to extract",
                "javascript runtime", "page needs to be reloaded",
            )):
                message = (
                    "❌ YouTube ဖတ်မရပါ။ yt-dlp ဗားရှင်းနဲ့ "
                    "JavaScript Runtime ကို စစ်ပါ။"
                )
            elif "45 mb" in error:
                message = "❌ Audio ဖိုင် 45 MB ထက် ကြီးနေပါတယ်။"
            else:
                message = (
                    "❌ Audio ရယူမရပါ။ Railway Deploy Logs ကို စစ်ပါ။"
                )

            await query.message.reply_text(message)


# ==========================================
# ADMIN HELPERS
# ==========================================

async def admin_target(update, context, action):
    if not await require_group(update):
        return None

    if not await is_admin(update, context):
        await reply(update, "❌ Group Admin သာ အသုံးပြုနိုင်ပါတယ်။")
        return None

    target = await get_target(update)

    if not target:
        await reply(
            update,
            f"{action} လုပ်မယ့်သူရဲ့ message ကို Reply လုပ်ပါ။",
        )
        return None

    if target.is_bot or target.id == OWNER_ID:
        await reply(update, f"❌ ဒီအကောင့်ကို {action} မလုပ်နိုင်ပါ။")
        return None

    return target


# ==========================================
# WARN / WARNINGS
# ==========================================

async def warn(update, context):
    target = await admin_target(update, context, "Warning")

    if not target:
        return

    count = await asyncio.to_thread(
        add_warning, update.effective_chat.id, target.id
    )

    await reply(
        update,
        f"⚠️ {target.full_name} ကို Warning ပေးပြီးပါပြီ။\n"
        f"စုစုပေါင်း Warning: {count}",
    )


async def warnings_command(update, context):
    if not await require_group(update):
        return

    if not await is_admin(update, context):
        await reply(update, "❌ Group Admin သာ အသုံးပြုနိုင်ပါတယ်။")
        return

    target = await get_target(update)

    if target:
        user_id = target.id
    elif context.args and context.args[0].isdigit():
        user_id = int(context.args[0])
    else:
        await reply(
            update,
            "Reply လုပ်ပြီး /warnings ပို့ပါ၊ "
            "သို့မဟုတ် /warnings USER_ID သုံးပါ။",
        )
        return

    count = await asyncio.to_thread(
        get_warnings, update.effective_chat.id, user_id
    )

    await reply(update, f"⚠️ Warning အရေအတွက်: {count}")


# ==========================================
# BAN / UNBAN
# ==========================================

async def ban(update, context):
    target = await admin_target(update, context, "Ban")

    if not target:
        return

    try:
        await context.bot.ban_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target.id,
        )
        await reply(
            update,
            f"🚫 {target.full_name} ကို Ban လုပ်ပြီးပါပြီ။",
        )

    except TelegramError:
        logger.exception("Ban failed")
        await reply(
            update,
            "❌ Ban မလုပ်နိုင်ပါ။ Bot ကို Admin ခန့်ပြီး "
            "Ban Users permission ပေးထားကြောင်း စစ်ပါ။",
        )


async def unban(update, context):
    if not await require_group(update):
        return

    if not await is_admin(update, context):
        await reply(update, "❌ Group Admin သာ အသုံးပြုနိုင်ပါတယ်။")
        return

    target = await get_target(update)

    if target:
        user_id = target.id
    elif context.args and context.args[0].isdigit():
        user_id = int(context.args[0])
    else:
        await reply(
            update,
            "အသုံးပြုပုံ: /unban USER_ID\n"
            "သို့မဟုတ် User message ကို Reply လုပ်ပြီး /unban ပို့ပါ။",
        )
        return

    try:
        await context.bot.unban_chat_member(
            chat_id=update.effective_chat.id,
            user_id=user_id,
            only_if_banned=True,
        )
        await reply(update, f"✅ User {user_id} ကို Unban လုပ်ပြီးပါပြီ။")

    except TelegramError:
        logger.exception("Unban failed")
        await reply(
            update,
            "❌ Unban မလုပ်နိုင်ပါ။ USER_ID နဲ့ Bot permission ကို စစ်ပါ။",
        )


# ==========================================
# MUTE / UNMUTE
# ==========================================

async def mute(update, context):
    target = await admin_target(update, context, "Mute")

    if not target:
        return

    try:
        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target.id,
            permissions=ChatPermissions(
                can_send_messages=False,
                can_send_audios=False,
                can_send_documents=False,
                can_send_photos=False,
                can_send_videos=False,
                can_send_video_notes=False,
                can_send_voice_notes=False,
                can_send_polls=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False,
            ),
        )
        await reply(
            update,
            f"🔇 {target.full_name} ကို Mute လုပ်ပြီးပါပြီ။",
        )

    except TelegramError:
        logger.exception("Mute failed")
        await reply(
            update,
            "❌ Mute မလုပ်နိုင်ပါ။ Bot ကို Admin ခန့်ပြီး "
            "Restrict Members permission ပေးထားကြောင်း စစ်ပါ။",
        )


async def unmute(update, context):
    target = await admin_target(update, context, "Unmute")

    if not target:
        return

    try:
        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target.id,
            permissions=ChatPermissions.all_permissions(),
        )

        await reply(
            update,
            f"🔊 {target.full_name} ကို Unmute လုပ်ပြီးပါပြီ။",
        )

    except TelegramError:
        logger.exception("Unmute failed")

        await reply(
            update,
            "❌ Unmute မလုပ်နိုင်ပါ။ "
            "Bot ကို Admin ခန့်ထားခြင်းနဲ့ "
            "Restrict Members permission ကို စစ်ပါ။",
        )


# ==========================================
# ERROR HANDLER
# ==========================================

async def error_handler(update, context):
    logger.error(
        "Unhandled exception",
        exc_info=context.error,
    )


# ==========================================
# MAIN
# ==========================================

def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN မရှိပါ။ Railway Variables မှာ ထည့်ပါ။"
        )

    init_db()

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("song", song))

    app.add_handler(
        CallbackQueryHandler(
            song_callback,
            pattern=r"^(pick:\d+|page:\d+|close)$",
        )
    )

    app.add_handler(CommandHandler("warn", warn))
    app.add_handler(
        CommandHandler("warnings", warnings_command)
    )
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("unban", unban))
    app.add_handler(CommandHandler("mute", mute))
    app.add_handler(CommandHandler("unmute", unmute))

    app.add_error_handler(error_handler)

    logger.info("Ck_helpbot is starting...")

    app.run_polling(
        drop_pending_updates=False,
        allowed_updates=["message", "callback_query"],
    )


if __name__ == "__main__":
    main()
  
