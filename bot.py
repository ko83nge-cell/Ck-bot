import os
import re
import sqlite3
import logging
import asyncio
import aiohttp

from telegram import Update, ChatPermissions
from telegram.constants import ChatMemberStatus
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================
# SETTINGS
# =========================

BOT_TOKEN = "8824850208:AAGkmULcNJxWx-39-80r-8oJNtSc9g3bSTM"
OWNER_ID = 8062359539
DB_PATH = os.getenv("DB_PATH", "bot.db")
JAMENDO_CLIENT_ID = "957b221f"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


# =========================
# DATABASE
# =========================

db = sqlite3.connect(DB_PATH, check_same_thread=False)

db.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY
)
""")

db.execute("""
CREATE TABLE IF NOT EXISTS warns (
    chat_id INTEGER,
    user_id INTEGER,
    count INTEGER DEFAULT 0,
    PRIMARY KEY (chat_id, user_id)
)
""")

db.commit()


def remember_user(user_id):
    db.execute(
        "INSERT OR IGNORE INTO users(user_id) VALUES (?)",
        (user_id,),
    )
    db.commit()


def get_warns(chat_id, user_id):
    row = db.execute(
        "SELECT count FROM warns WHERE chat_id=? AND user_id=?",
        (chat_id, user_id),
    ).fetchone()

    return row[0] if row else 0


def add_warn(chat_id, user_id):
    count = get_warns(chat_id, user_id) + 1

    db.execute(
        """
        INSERT INTO warns(chat_id, user_id, count)
        VALUES (?, ?, ?)
        ON CONFLICT(chat_id, user_id)
        DO UPDATE SET count=excluded.count
        """,
        (chat_id, user_id, count),
    )
    db.commit()

    return count


# =========================
# START / HELP / ID
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if user:
        remember_user(user.id)

    await update.effective_message.reply_text(
        "မင်္ဂလာပါ! 🤖 Ck_helpbot မှ ကြိုဆိုပါတယ်။\n\n"
        "/help - Command များကြည့်ရန်\n"
        "/id - User ID ကြည့်ရန်\n"
        "/song သီချင်းအမည် - Jamendo မှ MP3 သီချင်းရှာဖွေရန်"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "📚 Ck_helpbot Commands\n\n"
        "👤 General:\n"
        "/start - Bot စတင်ရန်\n"
        "/help - အကူအညီ\n"
        "/id - User ID နှင့် Chat ID\n"
        "/song သီချင်းအမည် - Jamendo မှ သီချင်းရှာပြီး ပို့ရန်\n\n"
        "🛡 Group Admin:\n"
        "/warn - Reply လုပ်ပြီး Warn ပေးရန်\n"
        "/warns - Warn အရေအတွက်ကြည့်ရန်\n"
        "/ban - Reply လုပ်ပြီး Ban လုပ်ရန်\n"
        "/unban USER_ID - Ban ပြန်ဖြုတ်ရန်\n"
        "/mute - Reply လုပ်ပြီး Mute လုပ်ရန်\n"
        "/unmute - Reply လုပ်ပြီး Unmute လုပ်ရန်\n\n"
        "👑 Owner:\n"
        "/broadcast စာသား - Bot စတင်ထားသူများထံ ပို့ရန်"
    )


async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    await update.effective_message.reply_text(
        f"User ID: {user.id if user else 'N/A'}\n"
        f"Chat ID: {chat.id if chat else 'N/A'}"
    )


# =========================
# ADMIN CHECK & TARGET USER
# =========================

async def is_admin(update, context):
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message

    if not chat or chat.type not in ("group", "supergroup") or not user:
        await message.reply_text("ဒီ Command ကို Telegram Group ထဲမှာ သုံးပါ။")
        return False

    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status not in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        ):
            await message.reply_text("ဒီ Command ကို Group Admin ပဲ သုံးနိုင်ပါတယ်။")
            return False
        return True
    except Exception:
        logger.exception("Admin check failed")
        return False


async def target_user(update, context):
    message = update.effective_message
    if message.reply_to_message:
        target = message.reply_to_message.from_user
        if target and not target.is_bot:
            return target
    if context.args and context.args[0].isdigit():
        try:
            member = await context.bot.get_chat_member(
                update.effective_chat.id, int(context.args[0])
            )
            if not member.user.is_bot:
                return member.user
        except Exception:
            pass
    return None


# =========================
# WARN / BAN / MUTE COMMANDS
# =========================

async def warn_cmd(update, context):
    if not await is_admin(update, context):
        return
    target = await target_user(update, context)
    if not target:
        await update.effective_message.reply_text("အသုံးပြုပုံ: User ရဲ့စာကို Reply လုပ်ပြီး /warn သုံးပါ။")
        return

    chat_id = update.effective_chat.id
    count = add_warn(chat_id, target.id)

    if count >= 3:
        await context.bot.ban_chat_member(chat_id, target.id)
        db.execute("DELETE FROM warns WHERE chat_id=? AND user_id=?", (chat_id, target.id))
        db.commit()
        await update.effective_message.reply_text(f"⚠️ {target.first_name} သည် Warn ၃ ကြိမ်ပြည့်သဖြင့် Ban လုပ်လိုက်ပါပြီ။")
    else:
        await update.effective_message.reply_text(f"⚠️ {target.first_name} ကို Warn ပေးလိုက်ပါပြီ ({count}/3)")


async def warns_cmd(update, context):
    if not await is_admin(update, context):
        return
    target = await target_user(update, context)
    if not target:
        return
    count = get_warns(update.effective_chat.id, target.id)
    await update.effective_message.reply_text(f"👤 {target.first_name} - Warn: {count}/3")


async def ban_cmd(update, context):
    if not await is_admin(update, context):
        return
    target = await target_user(update, context)
    if not target:
        return
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, target.id)
        await update.effective_message.reply_text(f"🔨 {target.first_name} ကို Ban လုပ်ပြီးပါပြီ။")
    except Exception:
        await update.effective_message.reply_text("Ban မအောင်မြင်ပါ။ Permission စစ်ပါ။")


async def unban_cmd(update, context):
    if not await is_admin(update, context):
        return
    if not context.args or not context.args[0].isdigit():
        await update.effective_message.reply_text("အသုံးပြုပုံ: /unban USER_ID")
        return
    try:
        await context.bot.unban_chat_member(update.effective_chat.id, int(context.args[0]), only_if_banned=True)
        await update.effective_message.reply_text("✅ Unban အောင်မြင်ပါပြီ။")
    except Exception:
        await update.effective_message.reply_text("Unban မအောင်မြင်ပါ။")


async def mute_cmd(update, context):
    if not await is_admin(update, context):
        return
    target = await target_user(update, context)
    if not target:
        return
    try:
        await context.bot.restrict_chat_member(
            update.effective_chat.id,
            target.id,
            permissions=ChatPermissions(can_send_messages=False)
        )
        await update.effective_message.reply_text(f"🔇 {target.first_name} ကို Mute လုပ်ပြီးပါပြီ။")
    except Exception:
        await update.effective_message.reply_text("Mute မအောင်မြင်ပါ။")


async def unmute_cmd(update, context):
    if not await is_admin(update, context):
        return
    target = await target_user(update, context)
    if not target:
        return
    try:
        await context.bot.restrict_chat_member(
            update.effective_chat.id,
            target.id,
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
                can_add_web_page_previews=True
            )
        )
        await update.effective_message.reply_text(f"🔊 {target.first_name} ကို Unmute လုပ်ပြီးပါပြီ။")
    except Exception:
        await update.effective_message.reply_text("Unmute မအောင်မြင်ပါ။")


# =========================
# SONG - JAMENDO API INTEGRATION
# =========================

async def song_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.effective_message.reply_text(
            "🎵 သီချင်းအမည် ရိုက်ထည့်ပါ။\nဥပမာ: /song acoustic"
        )
        return

    query = " ".join(context.args)
    processing_msg = await update.effective_message.reply_text("🎵 သီချင်းရှာနေပါသည်...")

    api_url = "https://api.jamendo.com/v3.0/tracks/"
    params = {
        "client_id": JAMENDO_CLIENT_ID,
        "format": "jsonjson",
        "search": query,
        "limit": 1,
        "audioformat": "mp31",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, params=params) as response:
                if response.status != 200:
                    await processing_msg.edit_text("❌ သီချင်းရှာဖွေရာတွင် အမှားအယွင်း ရှိနေပါသည်။")
                    return
                
                data = await response.json()
                tracks = data.get("results", [])

                if not tracks:
                    await processing_msg.edit_text(f"🎵 '{query}' နှင့် ကိုက်ညီသော သီချင်း မတွေ့ပါ။")
                    return

                track = tracks[0]
                audio_url = track.get("audio")
                title = track.get("name", "Unknown Title")
                artist = track.get("artist_name", "Unknown Artist")

                if not audio_url:
                    await processing_msg.edit_text("❌ သီချင်းလင့်ခ် ရယူ၍ မရပါ။")
                    return

                await processing_msg.edit_text("🎵 သီချင်း ပို့နေပါပြီ...")
                await update.effective_message.reply_audio(
                    audio=audio_url,
                    title=title,
                    performer=artist,
                    caption=f"🎵 {title} - {artist}\nvia Jamendo API",
                )
    except Exception as e:
        logger.exception("Song search failed")
        await processing_msg.edit_text(f"❌ Error: {str(e)}")


# =========================
# BROADCAST
# =========================

async def broadcast_cmd(update, context):
    user = update.effective_user
    message = update.effective_message

    if not user or OWNER_ID == 0 or user.id != OWNER_ID:
        await message.reply_text("ဒီ Command ကို Bot Owner ပဲ သုံးနိုင်ပါတယ်။")
        return

    text = " ".join(context.args)
    if not text:
        await message.reply_text("အသုံးပြုပုံ: /broadcast မင်္ဂလာပါ")
        return

    rows = db.execute("SELECT user_id FROM users").fetchall()
    sent, failed = 0, 0

    for (user_id,) in rows:
        try:
            await context.bot.send_message(chat_id=user_id, text=text)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1

    await message.reply_text(f"📣 Broadcast ပြီးပါပြီ။\nပို့နိုင်: {sent}\nမပို့နိုင်: {failed}")


async def remember_private(update, context):
    user = update.effective_user
    chat = update.effective_chat
    if user and chat and chat.type == "private":
        remember_user(user.id)


async def error_handler(update, context):
    logger.error("Bot error", exc_info=context.error)


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("id", id_cmd))
    app.add_handler(CommandHandler("warn", warn_cmd))
    app.add_handler(CommandHandler("warns", warns_cmd))
    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))
    app.add_handler(CommandHandler("mute", mute_cmd))
    app.add_handler(CommandHandler("unmute", unmute_cmd))
    app.add_handler(CommandHandler("song", song_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))

    app.add_handler(MessageHandler(filters.ChatType.PRIVATE, remember_private), group=1)
    app.add_error_handler(error_handler)

    logger.info("Ck_helpbot is starting...")
    app.run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    main()

