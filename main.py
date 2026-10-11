import os
import re
import sqlite3
import logging
import asyncio
import tempfile
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

# =========================
# CONFIGURATION
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID_TEXT = os.getenv("OWNER_ID", "8062359539")
OWNER_ID = int(OWNER_ID_TEXT) if OWNER_ID_TEXT.isdigit() else None

MAX_AUDIO_SIZE = 45 * 1024 * 1024
SEARCH_RESULTS = 30          # Fetch up to 30 results per search
RESULTS_PER_PAGE = 5         # Show 5 choices per page
MAX_PARALLEL_DOWNLOADS = 2   # Limit concurrent downloads globally
MAX_DOWNLOADS_PER_USER = 1   # One active download per user
DB_PATH = os.getenv("DATABASE_PATH", "ckhelpbot.sqlite3")

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("CkHelpBot")

download_semaphore = asyncio.Semaphore(MAX_PARALLEL_DOWNLOADS)
user_download_locks = defaultdict(asyncio.Lock)


# =========================
# SQLITE WARNINGS
# =========================

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


# =========================
# HELPERS
# =========================

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    if not user or not chat:
        return False

    if OWNER_ID is not None and user.id == OWNER_ID:
        return True

    if chat.type == "private":
        return False

    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        return member.status in ("administrator", "creator")
    except Exception:
        logger.exception("Could not check administrator status")
        return False


async def reply(update: Update, message: str):
    if update.effective_message:
        await update.effective_message.reply_text(message)


async def get_target(update: Update):
    message = update.effective_message
    if not message or not message.reply_to_message:
        return None
    return message.reply_to_message.from_user


# =========================
# BASIC COMMANDS
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await reply(
        update,
        "မင်္ဂလာပါ 👋 Ck_helpbot မှ ကြိုဆိုပါတယ်။\n\n"
        "/help - Command များကြည့်ရန်\n"
        "/song သီချင်းအမည် - သီချင်းရှာရန်\n\n"
        "သီချင်း ၃၀ ပုဒ်အထိ ရှာပြီး စာမျက်နှာလိုက် ရွေးချယ်နိုင်ပါတယ်။\n"
        "Admin command များကို Group ထဲတွင် အသုံးပြုနိုင်ပါတယ်။"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await reply(
        update,
        "📚 Ck_helpbot Commands\n\n"
        "👤 အားလုံးအတွက်\n"
        "/start - Bot စတင်ရန်\n"
        "/help - အကူအညီကြည့်ရန်\n"
        "/song သီချင်းအမည် - သီချင်းရှာပြီး Audio ရယူရန်\n\n"
        "🛡️ Admin အတွက်\n"
        "/warn (reply လုပ်ရန်) - သတိပေးရန်\n"
        "/warnings (reply လုပ်ရန်) - Warning အရေအတွက်ကြည့်ရန်\n"
        "/ban (reply လုပ်ရန်) - Ban လုပ်ရန်\n"
        "/unban USER_ID - Unban လုပ်ရန်\n"
        "/mute (reply လုပ်ရန်) - Mute လုပ်ရန်\n"
        "/unmute (reply လုပ်ရန်) - Unmute လုပ်ရန်\n\n"
        "မှတ်ချက်: Audio ရယူနိုင်မှုသည် သီချင်းရင်းမြစ်၊ "
        "ဖိုင်အရွယ်အစားနှင့် Railway အရင်းအမြစ်များပေါ် မူတည်ပါတယ်။"
    )


# =========================
# SONG SEARCH AND PAGINATION
# =========================

def search_songs(query_text):
    options = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
        "socket_timeout": 20,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        result = ydl.extract_info(
            f"ytsearch{SEARCH_RESULTS}:{query_text}",
            download=False,
        )

    songs = []
    for item in result.get("entries") or []:
        video_id = item.get("id")
        if not video_id:
            continue

        # Only accept ordinary YouTube video IDs, preventing arbitrary URLs
        if not re.fullmatch(r"[A-Za-z0-9_-]{6,20}", str(video_id)):
            continue

        songs.append({
            "id": str(video_id),
            "title": str(item.get("title", "Unknown"))[:200],
            "url": f"https://www.youtube.com/watch?v={video_id}",
        })
    return songs


def make_song_keyboard(songs, offset=0):
    buttons = []
    page_items = songs[offset:offset + RESULTS_PER_PAGE]

    for index, item in enumerate(page_items, start=offset + 1):
        buttons.append([
            InlineKeyboardButton(
                f"{index}. {item['title'][:48]}",
                callback_data=f"songpick|{index - 1}",
            )
        ])

    navigation = []
    if offset > 0:
        navigation.append(
            InlineKeyboardButton("⬅️ အရင်", callback_data=f"songpage|{max(0, offset - RESULTS_PER_PAGE)}")
        )
    if offset + RESULTS_PER_PAGE < len(songs):
        navigation.append(
            InlineKeyboardButton("နောက်ထပ် ➡️", callback_data=f"songpage|{offset + RESULTS_PER_PAGE}")
        )
    if navigation:
        buttons.append(navigation)

    buttons.append([
        InlineKeyboardButton("❌ ပိတ်ရန်", callback_data="songclose")
    ])
    return InlineKeyboardMarkup(buttons)


async def song(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message:
        return

    query_text = " ".join(context.args).strip()
    if not query_text:
        await message.reply_text(
            "🎵 သီချင်းအမည် ရိုက်ထည့်ပါ။\n\n"
            "ဥပမာ - /song Shape of You"
        )
        return

    status = await message.reply_text("🔎 သီချင်းရှာဖွေနေပါတယ်...")

    try:
        results = await asyncio.to_thread(search_songs, query_text)
        if not results:
            await status.edit_text(
                "❌ သီချင်းမတွေ့ပါ။ အမည်ပြန်စစ်ကြည့်ပါ။"
            )
            return

        context.user_data["song_results"] = results
        context.user_data["song_owner"] = update.effective_user.id
        context.user_data["song_query"] = query_text

        keyboard = make_song_keyboard(results, 0)
        await status.edit_text(
            f"🎵 “{query_text[:100]}” အတွက် {len(results)} ပုဒ် ရှာတွေ့ပါတယ်။\n"
            "ကိုယ်လိုချင်တဲ့ သီချင်းကို ရွေးပါ။",
            reply_markup=keyboard,
        )

    except Exception:
        logger.exception("Song search failed")
        await status.edit_text(
            "❌ သီချင်းရှာမရပါ။ ခဏကြာပြီး ပြန်ကြိုးစားပါ။"
        )


async def song_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data:
        return

    owner_id = context.user_data.get("song_owner")
    if owner_id != query.from_user.id:
        await query.answer(
            "ဒီသီချင်းစာရင်းကို ရှာခဲ့တဲ့သူကသာ ရွေးချယ်နိုင်ပါတယ်။",
            show_alert=True,
        )
        return

    if query.data == "songclose":
        await query.answer()
        await query.edit_message_text("သီချင်းစာရင်းကို ပိတ်လိုက်ပါပြီ။")
        return

    if query.data.startswith("songpage|"):
        await query.answer()
        try:
            offset = int(query.data.split("|", 1)[1])
            songs = context.user_data.get("song_results", [])
            if offset < 0 or offset >= len(songs):
                raise ValueError("Invalid page")

            await query.edit_message_text(
                f"🎵 ရှာတွေ့ထားသော သီချင်းများ ({offset + 1}–"
                f"{min(offset + RESULTS_PER_PAGE, len(songs))} / {len(songs)})",
                reply_markup=make_song_keyboard(songs, offset),
            )
        except Exception:
            await query.edit_message_text(
                "စာရင်းသက်တမ်းကုန်သွားပါပြီ။ /song နဲ့ ပြန်ရှာပါ။"
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
        await query.answer("စာရင်းသက်တမ်းကုန်သွားပါပြီ။ /song နဲ့ ပြန်ရှာပါ။", show_alert=True)
        return

    await query.answer()
    await query.edit_message_text(
        f"⏳ Audio ပြင်ဆင်နေပါတယ်။\n🎵 {selected['title'][:150]}"
    )

    user_id = query.from_user.id
    lock = user_download_locks[user_id]

    if lock.locked():
        await query.edit_message_text(
            "⏳ သင့်အတွက် Download တစ်ခု လုပ်ဆောင်နေပြီးသားပါ။ "
            "ပြီးသွားတဲ့အထိ စောင့်ပါ။"
        )
        return

    async with lock:
        try:
            async with download_semaphore:
                with tempfile.TemporaryDirectory() as folder:
                    audio_path, title, performer = await asyncio.to_thread(
                        download_song, selected["id"], folder
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

            await query.edit_message_text(
                f"✅ Audio ပို့ပြီးပါပြီ။\n🎵 {title[:250]}"
            )

        except Exception:
            logger.exception("Song download or upload failed")
            try:
                await query.edit_message_text(
                    "❌ Audio ပို့မရပါ။ ဖြစ်နိုင်သောအကြောင်းရင်းများမှာ "
                    "FFmpeg မရှိခြင်း၊ သီချင်းရင်းမြစ်က ပိတ်ထားခြင်း၊ "
                    "ဖိုင်ကြီးလွန်းခြင်း သို့မဟုတ် Railway ကန့်သတ်ချက်တို့ ဖြစ်ပါတယ်။"
                )
            except Exception:
                pass


def download_song(video_id, folder):
    output_template = str(Path(folder) / "song.%(ext)s")
    options = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
        "max_filesize": MAX_AUDIO_SIZE,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    }

    url = f"https://www.youtube.com/watch?v={video_id}"
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)

    audio_path = Path(folder) / "song.mp3"
    if not audio_path.exists():
        raise RuntimeError("MP3 file was not created")
    if audio_path.stat().st_size > MAX_AUDIO_SIZE:
        raise RuntimeError("Audio file exceeds size limit")

    return (
        str(audio_path),
        info.get("title", "Unknown"),
        info.get("uploader", "Unknown"),
    )


# =========================
# ADMIN COMMANDS
# =========================

async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await reply(update, "❌ ဒီ command ကို Admin သာ အသုံးပြုနိုင်ပါတယ်။")
        return

    target = await get_target(update)
    if not target:
        await reply(update, "သတိပေးမယ့်သူရဲ့ message ကို Reply လုပ်ပြီး /warn ပို့ပါ။")
        return
    if target.is_bot:
        await reply(update, "Bot ကို Warning ပေးလို့မရပါ။")
        return

    count = await asyncio.to_thread(
        add_warning, update.effective_chat.id, target.id
    )
    await reply(
        update,
        f"⚠️ {target.full_name} ကို Warning ပေးပြီးပါပြီ။\n"
        f"စုစုပေါင်း Warning: {count}",
    )


async def warnings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = await get_target(update)
    if target:
        user_id = target.id
    elif context.args and context.args[0].isdigit():
        user_id = int(context.args[0])
    else:
        await reply(update, "အသုံးပြုပုံ: User ရဲ့ message ကို Reply လုပ်ပြီး /warnings ပို့ပါ။")
        return

    count = await asyncio.to_thread(
        get_warning_count, update.effective_chat.id, user_id
    )
    await reply(update, f"⚠️ Warning အရေအတွက်: {count}")


async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await reply(update, "❌ Admin သာ အသုံးပြုနိုင်ပါတယ်။")
        return

    target = await get_target(update)
    if not target:
        await reply(update, "Ban လုပ်မယ့်သူရဲ့ message ကို Reply လုပ်ပါ။")
        return
    if target.is_bot or target.id == OWNER_ID:
        await reply(update, "ဒီအကောင့်ကို Ban လုပ်လို့မရပါ။")
        return

    try:
        await context.bot.ban_chat_member(
            chat_id=update.effective_chat.id, user_id=target.id
        )
        await reply(update, f"🚫 {target.full_name} ကို Ban လုပ်ပြီးပါပြီ။")
    except Exception:
        logger.exception("Ban failed")
        await reply(update, "❌ Ban မလုပ်နိုင်ပါ။ Bot ရဲ့ Admin permission ကို စစ်ပါ။")


async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await reply(update, "❌ Unban မလုပ်နိုင်ပါ။ User ID နဲ့ Bot permission ကို စစ်ပါ။")


async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await reply(update, "❌ Admin သာ အသုံးပြုနိုင်ပါတယ်။")
        return
    target = await get_target(update)
    if not target:
        await reply(update, "Mute လုပ်မယ့်သူရဲ့ message ကို Reply လုပ်ပါ။")
        return
    if target.is_bot or target.id == OWNER_ID:
        await reply(update, "ဒီအကောင့်ကို Mute လုပ်လို့မရပါ။")
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
        await reply(update, "❌ Mute မလုပ်နိုင်ပါ။ Bot ရဲ့ Admin permission ကို စစ်ပါ။")


async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await reply(update, "❌ Admin သာ အသုံးပြုနိုင်ပါတယ်။")
        return
    target = await get_target(update)
    if not target:
        await reply(update, "Unmute လုပ်မယ့်သူရဲ့ message ကို Reply လုပ်ပါ။")
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
        await reply(update, "❌ Unmute မလုပ်နိုင်ပါ။ Bot ရဲ့ Admin permission ကို စစ်ပါ။")


# =========================
# ERROR HANDLING / STARTUP
# =========================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(
        "Unhandled error while processing update",
        exc_info=context.error,
    )


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN မရှိပါ။ Railway Variables ထဲတွင် ထည့်ပါ။")

    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("song", song))
    app.add_handler(
        CallbackQueryHandler(
            song_callback,
            pattern=r"^(songpick\||songpage\||songclose$)",
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
