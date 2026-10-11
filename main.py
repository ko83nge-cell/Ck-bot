import os
import io
import sqlite3
import logging
from pathlib import Path

import httpx
from telegram import Update, ChatPermissions
from telegram.ext import Application, CommandHandler, ContextTypes

# =========================
# SETTINGS
# =========================

BOT_TOKEN = "8824850208:AAExGzmfMD8Kn0I9fHtYRHAXU8FtjBH2m78"
OWNER_ID = 8062359539

SONG_URL = os.getenv(
    "SONG_URL",
    "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
).strip()
SONG_TITLE = os.getenv("SONG_TITLE", "Relaxing Melody").strip()
SONG_ARTIST = os.getenv("SONG_ARTIST", "Bot Music").strip()

DATA_DIR = Path(os.getenv("DATA_DIR", "."))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "ck_helpbot.sqlite3"

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("ck_helpbot")


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS warnings (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (chat_id, user_id)
            )"""
        )
        conn.commit()


def get_warning_count(chat_id: int, user_id: int) -> int:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT count FROM warnings WHERE chat_id=? AND user_id=?",
            (chat_id, user_id),
        ).fetchone()
    return int(row[0]) if row else 0


def add_warning(chat_id: int, user_id: int) -> int:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """INSERT INTO warnings(chat_id, user_id, count) VALUES (?, ?, 1)
               ON CONFLICT(chat_id, user_id)
               DO UPDATE SET count = count + 1""",
            (chat_id, user_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT count FROM warnings WHERE chat_id=? AND user_id=?",
            (chat_id, user_id),
        ).fetchone()
    return int(row[0])


async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.effective_user or not update.effective_chat:
        return False
    member = await context.bot.get_chat_member(
        update.effective_chat.id, update.effective_user.id
    )
    return member.status in ("administrator", "creator")


async def admin_only(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat:
        return False
    if chat.type == "private":
        await message.reply_text("ဒီ Command ကို Group ထဲမှာ သုံးပါ။")
        return False
    try:
        if not await is_admin(update, context):
            await message.reply_text("ဒီ Command ကို Group Admin ပဲ သုံးနိုင်ပါတယ်။")
            return False
    except Exception:
        logger.exception("Failed to check admin status")
        await message.reply_text("Admin အခြေအနေ စစ်မရပါ။ Bot ရဲ့ Group permission ကို စစ်ပါ။")
        return False
    return True


def replied_user(update: Update):
    message = update.effective_message
    if message and message.reply_to_message:
        return message.reply_to_message.from_user
    return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "မင်္ဂလာပါ! 🤖\n\n"
        "Music & Group Management Bot ပါ။\n\n"
        "/song - သီချင်းဖိုင် ပို့ရန်\n"
        "/help - Command အားလုံးကြည့်ရန်"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "🎵 MUSIC\n"
        "/song - သီချင်း ပို့ရန်\n\n"
        "🛡️ ADMIN COMMANDS (Group ထဲတွင် target message ကို Reply လုပ်ပါ)\n"
        "/warn - သတိပေးရန်\n"
        "/warnings - Warn အရေအတွက်ကြည့်ရန်\n"
        "/ban - Ban လုပ်ရန်\n"
        "/unban USER_ID - Ban ပြန်ဖြုတ်ရန်\n"
        "/mute - Mute လုပ်ရန်\n"
        "/unmute - Mute ပြန်ဖြုတ်ရန်"
    )


async def song(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message:
        return

    status = await message.reply_text("🔎 သီချင်းဖိုင် ရယူနေပါပြီ...")
    try:
        timeout = httpx.Timeout(45.0, connect=15.0)
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "CkHelpbot/1.0"},
        ) as client:
            response = await client.get(SONG_URL)
            response.raise_for_status()
            data = response.content

        if not data:
            raise RuntimeError("Audio URL returned an empty response")
        if len(data) > 49 * 1024 * 1024:
            raise RuntimeError("Audio file is too large to upload")

        audio = io.BytesIO(data)
        audio.name = "relaxing_melody.mp3"
        audio.seek(0)

        await status.edit_text("🎵 သီချင်း ပို့နေပါပြီ...")
        await message.reply_audio(
            audio=audio,
            title=SONG_TITLE,
            performer=SONG_ARTIST,
            caption=f"🎵 {SONG_TITLE}\n🎤 {SONG_ARTIST}",
            read_timeout=60,
            write_timeout=60,
            connect_timeout=20,
            pool_timeout=20,
        )
        await status.delete()
    except Exception:
        logger.exception("Song command failed")
        try:
            await status.edit_text(
                "❌ သီချင်းဖိုင် ရယူ/ပို့မရပါ။ Hosting Logs နဲ့ SONG_URL ကို စစ်ပါ။"
            )
        except Exception:
            pass


async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return
    target = replied_user(update)
    if not target or target.is_bot:
        await update.effective_message.reply_text("သတိပေးမယ့်သူရဲ့ Message ကို Reply လုပ်ပါ။")
        return
    count = add_warning(update.effective_chat.id, target.id)
    await update.effective_message.reply_text(
        f"⚠️ {target.full_name} ကို Warn ပေးပြီးပါပြီ။ (Warn: {count})"
    )


async def warnings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat, user = update.effective_chat, update.effective_user
    if not chat or not user:
        return
    target = replied_user(update)
    target_id = target.id if target else user.id
    count = get_warning_count(chat.id, target_id)
    await update.effective_message.reply_text(f"⚠️ Warn အရေအတွက်: {count}")


async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return
    target = replied_user(update)
    if not target or target.id == update.effective_user.id or target.is_bot:
        await update.effective_message.reply_text("Ban လုပ်မယ့်သူရဲ့ Message ကို Reply လုပ်ပါ။")
        return
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, target.id)
        await update.effective_message.reply_text(f"🚫 {target.full_name} ကို Ban လိုက်ပါပြီ။")
    except Exception:
        logger.exception("Ban command failed")
        await update.effective_message.reply_text("Ban မအောင်မြင်ပါ။ Bot Admin permission ကို စစ်ပါ။")


async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return
    if not context.args:
        await update.effective_message.reply_text("အသုံးပြုပုံ: /unban USER_ID")
        return
    try:
        user_id = int(context.args[0])
        await context.bot.unban_chat_member(
            update.effective_chat.id, user_id, only_if_banned=True
        )
        await update.effective_message.reply_text(f"✅ User ID {user_id} ကို Unban လုပ်ပြီးပါပြီ။")
    except ValueError:
        await update.effective_message.reply_text("USER_ID ကို နံပါတ်ဖြင့် ထည့်ပါ။")
    except Exception:
        logger.exception("Unban command failed")
        await update.effective_message.reply_text("Unban မအောင်မြင်ပါ။ User ID နဲ့ Bot Permission ကို စစ်ပါ။")


async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return
    target = replied_user(update)
    if not target or target.id == update.effective_user.id or target.is_bot:
        await update.effective_message.reply_text("Mute လုပ်မယ့်သူရဲ့ Message ကို Reply လုပ်ပါ။")
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
        await update.effective_message.reply_text(f"🔇 {target.full_name} ကို Mute လုပ်ပြီးပါပြီ။")
    except Exception:
        logger.exception("Mute command failed")
        await update.effective_message.reply_text("Mute မအောင်မြင်ပါ။ Bot Admin permission ကို စစ်ပါ။")


async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return
    target = replied_user(update)
    if not target:
        await update.effective_message.reply_text("Unmute လုပ်မယ့်သူရဲ့ Message ကို Reply လုပ်ပါ။")
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
        await update.effective_message.reply_text(f"🔊 {target.full_name} ကို Unmute လုပ်ပြီးပါပြီ။")
    except Exception:
        logger.exception("Unmute command failed")
        await update.effective_message.reply_text("Unmute မအောင်မြင်ပါ။ Bot Admin permission ကို စစ်ပါ။")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Unhandled Telegram update error", exc_info=context.error)


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN မသတ်မှတ်ရသေးပါ။")

    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("song", song))
    app.add_handler(CommandHandler("warn", warn))
    app.add_handler(CommandHandler("warnings", warnings_command))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("unban", unban))
    app.add_handler(CommandHandler("mute", mute))
    app.add_handler(CommandHandler("unmute", unmute))
    app.add_error_handler(error_handler)

    logger.info("Ck_helpbot is starting")
    app.run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    main()

