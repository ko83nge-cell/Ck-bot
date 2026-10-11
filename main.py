import os
import re
import sqlite3
import logging
import asyncio
import tempfile
import shutil
import base64
from pathlib import Path
from collections import defaultdict

import yt_dlp
from telegram import (
    Update,
    ChatPermissions,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
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

OWNER_ID_TEXT = os.getenv("OWNER_ID", "8062359539").strip()
OWNER_ID = int(OWNER_ID_TEXT) if OWNER_ID_TEXT.isdigit() else None

MAX_AUDIO_SIZE = 45 * 1024 * 1024
SEARCH_RESULTS = 30
RESULTS_PER_PAGE = 5
MAX_PARALLEL_DOWNLOADS = 2

DB_PATH = os.getenv("DATABASE_PATH", "ckhelpbot.sqlite3")

# Optional: Base64 encoded Netscape-format cookies.txt
# Keep cookies in Railway Variables, never in GitHub.
YOUTUBE_COOKIES_B64 = os.getenv(
    "YOUTUBE_COOKIES_B64", ""
).strip()

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("CkHelpBot")

download_semaphore = asyncio.Semaphore(MAX_PARALLEL_DOWNLOADS)
user_download_locks = defaultdict(asyncio.Lock)


# ==========================================
# DATABASE
# ==========================================

def init_db():
    with sqlite3.connect(DB_PATH, timeout=20) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS warnings (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (chat_id, user_id)
            )
        """)
        db.commit()


def add_warning(chat_id, user_id):
    with sqlite3.connect(DB_PATH, timeout=20) as db:
        db.execute("""
            INSERT INTO warnings (chat_id, user_id, count)
            VALUES (?, ?, 1)
            ON CONFLICT(chat_id, user_id)
            DO UPDATE SET count = count + 1
        """, (chat_id, user_id))
        db.commit()

        row = db.execute(
            "SELECT count FROM warnings WHERE chat_id=? AND user_id=?",
            (chat_id, user_id),
        ).fetchone()

        return row[0] if row else 0


def get_warning_count(chat_id, user_id):
    with sqlite3.connect(DB_PATH, timeout=20) as db:
        row = db.execute(
            "SELECT count FROM warnings WHERE chat_id=? AND user_id=?",
            (chat_id, user_id),
        ).fetchone()

        return row[0] if row else 0


# ==========================================
# HELPERS
# ==========================================

async def reply(update, message):
    if update.effective_message:
        await update.effective_message.reply_text(message)


async def is_admin(update, context):
    user = update.effective_user
    chat = update.effective_chat

    if not user or not chat:
        return False

    if OWNER_ID is not None and user.id == OWNER_ID:
        return True

    if chat.type == "private":
        return False

    try:
        member = await context.bot.get_chat_member(
            chat.id, user.id
        )
        return member.status in ("administrator", "creator")
    except Exception:
        logger.exception("Admin check failed")
        return False


async def get_target(update):
    message = update.effective_message

    if not message or not message.reply_to_message:
        return None

    return message.reply_to_message.from_user


def short_error(exc, limit=500):
    text = " ".join(str(exc).split())
    return f"{type(exc).__name__}: {text[:limit]}"


def get_cookie_file(folder):
    """
    Optional Railway variable:
    YOUTUBE_COOKIES_B64 = Base64 of a Netscape-format cookies.txt.

    Never hardcode account cookies in this source file.
    """
    if not YOUTUBE_COOKIES_B64:
        return None

    try:
        cookie_bytes = base64.b64decode(
            YOUTUBE_COOKIES_B64,
            validate=True,
        )

        if not cookie_bytes:
            raise ValueError("Empty cookies file")

        cookie_path = Path(folder) / "cookies.txt"
        cookie_path.write_bytes(cookie_bytes)

        return str(cookie_path)

    except Exception as exc:
        raise RuntimeError(
            "YOUTUBE_COOKIES_B64 မမှန်ပါ။ "
            "Netscape-format cookies.txt ကို Base64 ပြောင်းထားမှုကို စစ်ပါ။"
        ) from exc


# ==========================================
# START / HELP
# ==========================================

async def start(update, context):
    await reply(
        update,
        "မင်္ဂလာပါ 👋 Ck_helpbot မှ ကြိုဆိုပါတယ်။\n\n"
        "🎵 သီချင်းရှာရန်:\n"
        "/song သီချင်းအမည်\n\n"
        "ဥပမာ: /song Shape of You\n\n"
        "/help - Command များကြည့်ရန်"
    )


async def help_command(update, context):
    await reply(
        update,
        "📚 Ck_helpbot Commands\n\n"
        "🎵 အားလုံးအတွက်\n"
        "/start - Bot စတင်ရန်\n"
        "/help - အကူအညီ\n"
        "/song သီချင်းအမည် - သီချင်းရှာရန်\n\n"
        "🛡️ Admin Commands (Group)\n"
        "/warn - Reply လုပ်ထားသူကို Warning ပေးရန်\n"
        "/warnings - Warning ကြည့်ရန်\n"
        "/ban - Reply လုပ်ထားသူကို Ban လုပ်ရန်\n"
        "/unban USER_ID - Unban လုပ်ရန်\n"
        "/mute - Reply လုပ်ထားသူကို Mute လုပ်ရန်\n"
        "/unmute - Reply လုပ်ထားသူကို Unmute လုပ်ရန်"
    )


# ==========================================
# SEARCH SONGS
# ==========================================

def search_songs(query_text):
    options = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
        "socket_timeout": 25,
        "noplaylist": True,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        result = ydl.extract_info(
            f"ytsearch{SEARCH_RESULTS}:{query_text}",
            download=False,
        )

    songs = []

    for item in (result or {}).get("entries") or []:
        if not item:
            continue

        video_id = item.get("id")

        if not video_id:
            continue

        if not re.fullmatch(r"[A-Za-z0-9_-]{6,20}", str(video_id)):
            continue

        songs.append({
            "id": str(video_id),
            "title": str(item.get("title") or "Unknown")[:200],
            "url": f"https://www.youtube.com/watch?v={video_id}",
        })

    return songs


def make_song_keyboard(songs, offset=0):
    buttons = []

    for index, item in enumerate(
        songs[offset:offset + RESULTS_PER_PAGE],
        start=offset + 1,
    ):
        buttons.append([
            InlineKeyboardButton(
                f"{index}. {item['title'][:48]}",
                callback_data=f"songpick|{index - 1}",
            )
        ])

    navigation = []

    if offset > 0:
        navigation.append(
            InlineKeyboardButton(
                "⬅️ အရင်",
                callback_data=f"songpage|{max(0, offset - RESULTS_PER_PAGE)}",
            )
        )

    if offset + RESULTS_PER_PAGE < len(songs):
        navigation.append(
            InlineKeyboardButton(
                "နောက်ထပ် ➡️",
                callback_data=f"songpage|{offset + RESULTS_PER_PAGE}",
            )
        )

    if navigation:
        buttons.append(navigation)

    buttons.append([
        InlineKeyboardButton(
            "❌ ပိတ်ရန်",
            callback_data="songclose",
        )
    ])

    return InlineKeyboardMarkup(buttons)


async def song(update, context):
    message = update.effective_message

    if not message:
        return

    query_text = " ".join(context.args).strip()

    if not query_text:
        await message.reply_text(
            "🎵 သီချင်းအမည် ရိုက်ထည့်ပါ။\n"
            "ဥပမာ: /song Shape of You"
        )
        return

    status = await message.reply_text(
        "🔎 သီချင်းရှာဖွေနေပါတယ်..."
    )

    try:
        results = await asyncio.to_thread(
            search_songs,
            query_text,
        )

        if not results:
            await status.edit_text(
                "❌ သီချင်းမတွေ့ပါ။ နာမည်ပြန်စစ်ပါ။"
            )
            return

        context.user_data["song_results"] = results
        context.user_data["song_owner"] = update.effective_user.id

        await status.edit_text(
            f"🎵 “{query_text[:100]}” အတွက် "
            f"{len(results)} ပုဒ် ရှာတွေ့ပါတယ်။\n"
            "လိုချင်တဲ့သီချင်းကို Button နဲ့ရွေးပါ။",
            reply_markup=make_song_keyboard(results),
        )

    except Exception as exc:
        logger.exception("Song search failed")

        await status.edit_text(
            "❌ သီချင်းရှာမရပါ။\n"
            f"အကြောင်းရင်း: {short_error(exc, 350)}"
        )


# ==========================================
# DOWNLOAD AND SEND AUDIO
# ==========================================

def download_song(video_id, folder):
    if not shutil.which("ffmpeg"):
        raise RuntimeError(
            "FFmpeg မတွေ့ပါ။ Railway Dockerfile ကိုစစ်ပါ။"
        )

    output_template = str(
        Path(folder) / "song.%(ext)s"
    )

    cookie_path = get_cookie_file(folder)

    options = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": False,
        "socket_timeout": 30,
        "retries": 2,
        "fragment_retries": 2,
        "max_filesize": MAX_AUDIO_SIZE,
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
        info = ydl.extract_info(
            url,
            download=True,
        )

    audio_path = Path(folder) / "song.mp3"

    if not audio_path.exists():
        raise RuntimeError(
            "MP3 ဖိုင်မဖန်တီးနိုင်ပါ။ "
            "Download နဲ့ FFmpeg ကိုစစ်ပါ။"
        )

    file_size = audio_path.stat().st_size

    if file_size > MAX_AUDIO_SIZE:
        raise RuntimeError(
            "Audio ဖိုင်က 45 MB ထက်ကြီးနေပါတယ်။"
        )

    return (
        str(audio_path),
        info.get("title", "Unknown"),
        info.get("uploader", "Unknown"),
    )


async def song_callback(update, context):
    query = update.callback_query

    if not query or not query.data:
        return

    owner_id = context.user_data.get("song_owner")

    if owner_id != query.from_user.id:
        await query.answer(
            "ဒီစာရင်းကို ရှာခဲ့တဲ့သူကသာ ရွေးချယ်နိုင်ပါတယ်။",
            show_alert=True,
        )
        return

    if query.data == "songclose":
        await query.answer()
        await query.edit_message_text(
            "သီချင်းစာရင်းကို ပိတ်လိုက်ပါပြီ။"
        )
        return

    if query.data.startswith("songpage|"):
        await query.answer()

        try:
            offset = int(query.data.split("|", 1)[1])
            songs = context.user_data.get("song_results", [])

            if offset < 0 or offset >= len(songs):
                raise ValueError("Invalid page")

            await query.edit_message_text(
                f"🎵 သီချင်းများ "
                f"({offset + 1}–"
                f"{min(offset + RESULTS_PER_PAGE, len(songs))}"
                f" / {len(songs)})",
                reply_markup=make_song_keyboard(songs, offset),
            )

        except Exception:
            await query.edit_message_text(
                "စာရင်းသက်တမ်းကုန်သွားပါပြီ။ "
                "/song နဲ့ ပြန်ရှာပါ။"
            )

        return

    if not query.data.startswith("songpick|"):
        await query.answer()
        return

    try:
        index = int(query.data.split("|", 1)[1])
        songs = context.user_data.get("song_results", [])

        if index < 0 or index >= len(songs):
            raise ValueError("Invalid song index")

        selected = songs[index]

    except Exception:
        await query.answer(
            "စာရင်းသက်တမ်းကုန်သွားပါပြီ။ "
            "/song နဲ့ ပြန်ရှာပါ။",
            show_alert=True,
        )
        return

    await query.answer()

    try:
        await query.edit_message_text(
            "⏳ Audio ပြင်ဆင်နေပါတယ်။\n"
            f"🎵 {selected['title'][:150]}"
        )
    except Exception:
        logger.exception(
            "Could not update selected-song message"
        )

    user_id = query.from_user.id
    lock = user_download_locks[user_id]

    if lock.locked():
        await query.message.reply_text(
            "⏳ Download တစ်ခု လုပ်ဆောင်နေပြီးသားပါ။ "
            "ခဏစောင့်ပါ။"
        )
        return

    async with lock:
        try:
            async with download_semaphore:
                with tempfile.TemporaryDirectory() as folder:
                    audio_path, title, performer = (
                        await asyncio.to_thread(
                            download_song,
                            selected["id"],
                            folder,
                        )
                    )

                    with open(audio_path, "rb") as audio_file:
                        await context.bot.send_audio(
                            chat_id=query.message.chat_id,
                            audio=audio_file,
                            title=title[:64],
                            performer=performer[:64],
                            read_timeout=120,
                            write_timeout=120,
                            connect_timeout=30,
                            pool_timeout=30,
                        )

            await query.message.reply_text(
                f"✅ Audio ပို့ပြီးပါပြီ။\n🎵 {title[:250]}"
            )

        except Exception as exc:
            logger.exception(
                "Song download or upload failed"
            )

            error_text = short_error(exc, 500)

            if (
                "Sign in to confirm" in str(exc)
                or "not a bot" in str(exc).lower()
            ):
                explanation = (
                    "\n\nYouTube က Server ကို Bot စစ်ဆေးမှုလုပ်နေပါတယ်။ "
                    "FFmpeg Error မဟုတ်ပါ။ Cookies မှန်ကန်စွာ "
                    "ပြင်ဆင်ထားရန် လိုနိုင်ပါတယ်။"
                )
            elif "ffmpeg" in str(exc).lower():
                explanation = (
                    "\n\nFFmpeg ကို Railway မှာ "
                    "တပ်ဆင်ထားမှုကို စစ်ပါ။"
                )
            else:
                explanation = (
                    "\n\nRailway Deploy Logs ကိုစစ်ပါ။"
                )

            await query.message.reply_text(
                "❌ Audio ရယူ/ပို့မရပါ။\n\n"
                f"Error: {error_text}"
                f"{explanation}"
            )


# ==========================================
# ADMIN COMMANDS
# ==========================================

async def warn(update, context):
    if not await is_admin(update, context):
        await reply(
            update,
            "❌ Admin သာ အသုံးပြုနိုင်ပါတယ်။",
        )
        return

    target = await get_target(update)

    if not target:
        await reply(
            update,
            "User ရဲ့ message ကို Reply လုပ်ပြီး /warn ပို့ပါ။",
        )
        return

    if target.is_bot:
        await reply(
            update,
            "Bot ကို Warning ပေးလို့မရပါ။",
        )
        return

    count = await asyncio.to_thread(
        add_warning,
        update.effective_chat.id,
        target.id,
    )

    await reply(
        update,
        f"⚠️ {target.full_name} ကို Warning ပေးပြီးပါပြီ။\n"
        f"စုစုပေါင်း Warning: {count}",
    )


async def warnings_command(update, context):
    target = await get_target(update)

    if target:
        user_id = target.id
    elif context.args and context.args[0].isdigit():
        user_id = int(context.args[0])
    else:
        await reply(
            update,
            "User ရဲ့ message ကို Reply လုပ်ပြီး /warnings ပို့ပါ။",
        )
        return

    count = await asyncio.to_thread(
        get_warning_count,
        update.effective_chat.id,
        user_id,
    )

    await reply(
        update,
        f"⚠️ Warning အရေအတွက်: {count}",
    )


async def ban(update, context):
    if not await is_admin(update, context):
        await reply(
            update,
            "❌ Admin သာ အသုံးပြုနိုင်ပါတယ်။",
        )
        return

    target = await get_target(update)

    if not target:
        await reply(
            update,
            "Ban လုပ်မယ့်သူရဲ့ message ကို Reply လုပ်ပါ။",
        )
        return

    if target.is_bot or (
        OWNER_ID is not None and target.id == OWNER_ID
    ):
        await reply(
            update,
            "ဒီအကောင့်ကို Ban လုပ်လို့မရပါ။",
        )
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

    except Exception:
        logger.exception("Ban failed")

        await reply(
            update,
            "❌ Ban မလုပ်နိုင်ပါ။ Bot Admin permission ကိုစစ်ပါ။",
        )


async def unban(update, context):
    if not await is_admin(update, context):
        await reply(
            update,
            "❌ Admin သာ အသုံးပြုနိုင်ပါတယ်။",
        )
        return

    if not context.args or not context.args[0].isdigit():
        await reply(
            update,
            "အသုံးပြုပုံ: /unban USER_ID",
        )
        return

    try:
        await context.bot.unban_chat_member(
            chat_id=update.effective_chat.id,
            user_id=int(context.args[0]),
            only_if_banned=True,
        )

        await reply(
            update,
            "✅ Unban လုပ်ပြီးပါပြီ။",
        )

    except Exception:
        logger.exception("Unban failed")

        await reply(
            update,
            "❌ Unban မလုပ်နိုင်ပါ။ "
            "User ID နဲ့ permission ကိုစစ်ပါ။",
        )


async def mute(update, context):
    if not await is_admin(update, context):
        await reply(
            update,
            "❌ Admin သာ အသုံးပြုနိုင်ပါတယ်။",
        )
        return

    target = await get_target(update)

    if not target:
        await reply(
            update,
            "Mute လုပ်မယ့်သူရဲ့ message ကို Reply လုပ်ပါ။",
        )
        return

    if target.is_bot or (
        OWNER_ID is not None and target.id == OWNER_ID
    ):
        await reply(
            update,
            "ဒီအကောင့်ကို Mute လုပ်လို့မရပါ။",
        )
        return

    try:
        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target.id,
            permissions=ChatPermissions(
                can_send_messages=False
            ),
        )

        await reply(
            update,
            f"🔇 {target.full_name} ကို Mute လုပ်ပြီးပါပြီ။",
        )

    except Exception:
        logger.exception("Mute failed")

        await reply(
            update,
            "❌ Mute မလုပ်နိုင်ပါ။ Bot Admin permission ကိုစစ်ပါ။",
        )


async def unmute(update, context):
    if not await is_admin(update, context):
        await reply(
            update,
            "❌ Admin သာ အသုံးပြုနိုင်ပါတယ်။",
        )
        return

    target = await get_target(update)

    if not target:
        await reply(
            update,
            "Unmute လုပ်မယ့်သူရဲ့ message ကို Reply လုပ်ပါ။",
        )
        return

    try:
        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target.id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_audios=True,
                can_send_documents=True,
                can_send_photos=True,
                can_send_vi 