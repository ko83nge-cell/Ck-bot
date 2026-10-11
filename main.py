
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

try:
    OWNER_ID = int(os.getenv("OWNER_ID", "8062359539"))
except ValueError:
    OWNER_ID = 8062359539

YOUTUBE_COOKIES_B64 = os.getenv(
    "YOUTUBE_COOKIES_B64", ""
).strip()

MAX_AUDIO_SIZE = 45 * 1024 * 1024
SEARCH_RESULTS = 20
PAGE_SIZE = 5
MAX_PARALLEL_DOWNLOADS = 2

DB_PATH = os.getenv(
    "DATABASE_PATH", "ckhelpbot.sqlite3"
)

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
    db_path = Path(DB_PATH)

    if str(db_path.parent) not in ("", "."):
        db_path.parent.mkdir(
            parents=True,
            exist_ok=True,
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

        row = db.execute(
            """
            SELECT count FROM warnings
            WHERE chat_id = ? AND user_id = ?
            """,
            (chat_id, user_id),
        ).fetchone()

        return row[0] if row else 0


def get_warnings(chat_id, user_id):
    with sqlite3.connect(DB_PATH, timeout=20) as db:
        row = db.execute(
            """
            SELECT count FROM warnings
            WHERE chat_id = ? AND user_id = ?
            """,
            (chat_id, user_id),
        ).fetchone()

        return row[0] if row else 0


# ==========================================
# HELPERS
# ==========================================

async def reply(update, text):
    if update.effective_message:
        await update.effective_message.reply_text(text)


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
            chat.id,
            user.id,
        )

        return member.status in (
            "administrator",
            "creator",
        )

    except Exception:
        logger.exception("Admin check failed")
        return False


def error_text(exc):
    """Return a short error without exposing credentials."""

    text = " ".join(str(exc).split())

    text = re.sub(
        r"(?i)(cookie|authorization|token)"
        r"\s*[:=]\s*\S+",
        r"\1=[REDACTED]",
        text,
    )

    text = re.sub(
        r"(?i)(password|secret|api[_-]?key)"
        r"\s*[:=]\s*\S+",
        r"\1=[REDACTED]",
        text,
    )

    return f"{type(exc).__name__}: {text[:300]}"


# ==========================================
# YOUTUBE COOKIES
# ==========================================

def write_cookies(folder):
    """
    Decode YOUTUBE_COOKIES_B64 into a temporary
    Netscape cookies.txt file.

    No cookies variable is required for public videos.
    Temporary files are removed after each operation.
    """

    if not YOUTUBE_COOKIES_B64:
        return None

    try:
        encoded = "".join(
            YOUTUBE_COOKIES_B64.split()
        )

        raw = base64.b64decode(
            encoded,
            validate=True,
        )

        content = raw.decode("utf-8-sig")

    except (
        binascii.Error,
        UnicodeDecodeError,
        ValueError,
    ):
        raise RuntimeError(
            "YOUTUBE_COOKIES_B64 ကို ဖတ်မရပါ။ "
            "Railway Variables ရှိ Base64 တန်ဖိုးကို စစ်ပါ။"
        )

    valid_header = (
        content.startswith("# Netscape HTTP Cookie File")
        or content.startswith("# HTTP Cookie File")
        or content.startswith("# This is a generated file!")
        or content.startswith("# Netscape")
    )

    if not valid_header:
        raise RuntimeError(
            "Cookies ဖိုင်ပုံစံ မမှန်ပါ။ "
            "Netscape cookies.txt ကို အသုံးပြုပါ။"
        )

    has_youtube_cookie = re.search(
        r"(?m)^(?:\.youtube\.com|youtube\.com|"
        r"#HttpOnly_\.youtube\.com)\s",
        content,
    )

    if not has_youtube_cookie:
        raise RuntimeError(
            "Cookies ဖိုင်ထဲတွင် YouTube domain မတွေ့ပါ။ "
            "Cookies ဖိုင်ကို စစ်ဆေးပါ။"
        )

    cookie_path = Path(folder) / "cookies.txt"

    cookie_path.write_text(
        content,
        encoding="utf-8",
    )

    try:
        cookie_path.chmod(0o600)
    except OSError:
        pass

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
        "Channel Join ဝင်ရန် မလိုအပ်ပါ။"
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
        "မှတ်ချက် - သီချင်းရယူနိုင်မှုသည် YouTube၊ "
        "Cookies နှင့် Railway အခြေအနေပေါ် မူတည်ပါတယ်။"
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

            video_id = item.get("id")

            if not video_id:
                continue

            if not re.fullmatch(
                r"[A-Za-z0-9_-]{6,20}",
                str(video_id),
            ):
                continue

            songs.append({
                "id": str(video_id),
                "title": str(
                    item.get("title") or "Unknown"
                )[:200],
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
                callback_data=(
                    f"page:{max(0, offset - PAGE_SIZE)}"
                ),
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
            "❌ ပိတ်ရန်",
            callback_data="close",
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
            search_songs,
            search_text,
        )

        if not songs:
            await status.edit_text(
                "❌ သီချင်းမတွေ့ပါ။ "
                "အမည်ပြန်စစ်ပြီး ထပ်ကြိုးစားပါ။"
            )
            return

        context.user_data["songs"] = songs
        context.user_data["song_owner"] = (
            update.effective_user.id
        )

        await status.edit_text(
            f"🎵 သီချင်း {len(songs)} ပုဒ် တွေ့ပါတယ်။\n"
            "လိုချင်တဲ့သီချင်းကို ရွေးပါ။",
            reply_markup=song_keyboard(songs),
        )

    except Exception as exc:
        logger.exception("Song search failed")

        await status.edit_text(
            "❌ သီချင်းရှာမရပါ။\n"
            "YouTube သို့မဟုတ် Network ပြဿနာ ဖြစ်နိုင်ပါတယ်။\n"
            "ခဏကြာပြီး ပြန်ကြိုးစားပါ။"
        )


# ==========================================
# AUDIO DOWNLOAD
# ==========================================

def download_song(video_id, folder):
    if not shutil.which("ffmpeg"):
        raise RuntimeError(
            "FFmpeg မတွေ့ပါ။ Railway မှာ FFmpeg "
            "တပ်ဆင်ထားခြင်း ရှိမရှိ စစ်ပါ။"
        )

    cookie_path = write_cookies(folder)

    output_template = str(
        Path(folder) / "audio.%(ext)s"
    )

    options = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 35,
        "retries": 3,
        "fragment_retries": 3,
        "file_access_retries": 2,
        "max_filesize": MAX_AUDIO_SIZE,
        "cachedir": False,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    }

    if cookie_path:
        options["cookiefile"] = cookie_path

    url = (
        "https://www.youtube.com/watch?v="
        + video_id
    )

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(
            url,
            download=True,
        )

    audio_path = Path(folder) / "audio.mp3"

    if not audio_path.exists():
        raise RuntimeError(
            "MP3 မဖန်တီးနိုင်ပါ။ FFmpeg နဲ့ yt-dlp ကို စစ်ပါ။"
        )

    file_size = audio_path.stat().st_size

    if file_size == 0:
        raise RuntimeError("MP3 ဖိုင် အလွတ်ဖြစ်နေပါတယ်။")

    if file_size > MAX_AUDIO_SIZE:
        raise RuntimeError(
            "Audio ဖိုင် 45 MB ထက် ကြီးနေပါတယ်။"
        )

    return (
        str(audio_path),
        str(info.get("title") or "Unknown"),
        str(info.get("uploader") or "Unknown"),
    )


# ==========================================
# SONG BUTTON CALLBACK
# ==========================================

async def song_callback(update, context):
    query = update.callback_query

    if not query or not query.data:
        return

    data = query.data

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

            if (
                offset < 0
                or offset >= len(songs)
                or offset % PAGE_SIZE != 0
            ):
                raise ValueError("Invalid page")

            await query.answer()

            await query.edit_message_text(
                f"🎵 သီချင်းစာရင်း "
                f"({offset + 1}–"
                f"{min(offset + PAGE_SIZE, len(songs))}"
                f" / {len(songs)})",
                reply_markup=song_keyboard(
                    songs,
                    offset,
                ),
            )

        except Exception:
            await query.answer(
                "စာရင်းသက်တမ်းကုန်သွားပါပြီ။ "
                "/song နဲ့ ပြန်ရှာပါ။",
                show_alert=True,
            )

        return

    if not data.startswith("pick:"):
        await query.answer()
        return

    try:
        index = int(data.split(":", 1)[1])

        if index < 0 or index >= len(songs):
            raise ValueError("Invalid song index")

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
            "⏳ Audio တစ်ခု ရယူနေပြီးသားပါ။ "
            "ပြီးသွားတဲ့အထိ စောင့်ပါ။"
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
                    (
                        audio_path,
                        title,
                        performer,
                    ) = await asyncio.to_thread(
                        download_song,
                        selected["id"],
                        folder,
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
                f"✅ Audio ပို့ပြီးပါပြီ။\n"
                f"🎵 {title[:200]}"
            )

        except Exception as exc:
            logger.exception("Audio download/send failed")

            error = str(exc).lower()

            if (
                "sign in to confirm" in error
                or "cookies" in error
                or "login required" in error
                or "confirm you're not a bot" in error
            ):
                message = (
                    "❌ YouTube က ဝင်ရောက်ခွင့်ကို "
                    "ကန့်သတ်ထားပါတယ်။\n"
                    "Cookies ရဲ့ ပုံစံနဲ့ သက်တမ်းကို စစ်ပါ။ "
                    "Cookies ရှိရုံနဲ့ အမြဲအလုပ်လုပ်မည် "
                    "မဟုတ်ပါ။"
                )

            elif (
                "page needs to be reloaded" in error
                or "nsig extraction failed" in error
                or "unable to extract" in error
                or "no supported javascript runtime" in error
            ):
                message = (
                    "❌ YouTube ကို ဖတ်မရပါ။\n"
                    "Railway ရဲ့ yt-dlp ဗားရှင်း၊ "
                    "JavaScript Runtime နဲ့ Build ကို စစ်ပါ။"
                )

            elif "ffmpeg" in error:
                message = (
                    "❌ FFmpeg မရှိခြင်း သို့မဟုတ် "
                    "FFmpeg ပြဿနာ ဖြစ်နိုင်ပါတယ်။"
                )

            elif (
                "file is too large" in error
                or "request entity too large" in error
            ):
                message = (
                    "❌ Audio ဖိုင်ကြီးလွန်းနေပါတယ်။"
                )

            else:
                message = (
                    "❌ Audio ရယူမရပါ။\n"
                    "Railway Deploy Logs ကို စစ်ဆေးပါ။"
                )

            await query.message.reply_text(message)


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
            "User message ကို Reply လုပ်ပြီး /warn ပို့ပါ။",
        )
        return

    if target.is_bot or target.id == OWNER_ID:
        await reply(
            update,
            "ဒီအကောင့်ကို Warning ပေးလို့မရပါ။",
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
    if not await is_admin(update, context):
        await reply(
            update,
            "❌ Admin သာ အသုံးပြုနိုင်ပါတယ်။",
        )
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
        get_warnings,
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

    if target.is_bot or target.id == OWNER_ID:
        await reply(
            update,
            "ဒီအကောင့်ကို Ban မလုပ်နိုင်ပါ။",
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
                "❌ Ban မလုပ်နိုင်ပါ။ Bot Admin permission စစ်ပါ။",
            )


async def unban(update, context):
    if not await is_admin(update, context):
        await reply(update, "❌ Admin သာ အသုံးပြုနိုင်ပါတယ်။")
        return

    if not context.args or not context.args[0].isdigit():
        await reply(update, "အသုံးပြုပုံ: /unban USER_ID")
        return

    try:
        await context.bot.unban_chat_member(
            chat_id=update.effective_chat.id,
            user_id=int(context.args[0]),
            only_if_banned=True,
        )
        await reply(update, "✅ Unban လုပ်ပြီးပါပြီ။")
    except Exception:
        logger.exception("Unban failed")
        await reply(update, "❌ Unban မလုပ်နိုင်ပါ။")


async def mute(update, context):
    if not await is_admin(update, context):
        await reply(update, "❌ Admin သာ အသုံးပြုနိုင်ပါတယ်။")
        return

    target = await get_target(update)
    if not target:
        await reply(update, "Mute လုပ်မယ့်သူကို Reply လုပ်ပါ။")
        return

    if target.is_bot or target.id == OWNER_ID:
        await reply(update, "ဒီအကောင့်ကို Mute မလုပ်နိုင်ပါ။")
        return

    try:
        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target.id,
            permissions=ChatPermissions(can_send_messages=False),
        )
        await reply(update, f"🔇 {target.full_name} ကို Mute လုပ်ပြီးပါပြီ။")
    except Exception:
        logger.exception("Mute failed")
        await reply(update, "❌ Mute မလုပ်နိုင်ပါ။ Bot Admin permission စစ်ပါ။")


async def unmute(update, context):
    if not await is_admin(update, context):
        await reply(update, "❌ Admin သာ အသုံးပြုနိုင်ပါတယ်။")
        return

    target = await get_target(update)
    if not target:
        await reply(update, "Unmute လုပ်မယ့်သူကို Reply လုပ်ပါ။")
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
                can_send_videos=True,
                can_send_video_notes=True,
                can_send_voice_notes=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
            ),
        )
        await reply(update, f"🔊 {target.full_name} ကို Unmute လုပ်ပြီးပါပြီ။")
    except Exception:
        logger.exception("Unmute failed")
        await reply(update, "❌ Unmute မလုပ်နိုင်ပါ။ Bot Admin permission စစ်ပါ။")


async def error_handler(update, context):
    logger.error("Unhandled update error", exc_info=context.error)


def main():
    if not BOT_TOKEN:
        raise RuntimeError("Railway Variables ထဲမှာ BOT_TOKEN ထည့်ပါ။")

    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

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
    app.add_handler(CommandHandler("warnings", warnings_command))
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
