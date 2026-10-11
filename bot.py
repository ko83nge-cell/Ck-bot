import os
import re
import sqlite3
import logging
import asyncio

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
SONGS_DIR = "songs"

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
        "/song သီချင်းအမည် - MP3 ဖိုင်ပို့ရန်"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "📚 Ck_helpbot Commands\n\n"
        "👤 General:\n"
        "/start - Bot စတင်ရန်\n"
        "/help - အကူအညီ\n"
        "/id - User ID နှင့် Chat ID\n"
        "/song song1 - songs/song1.mp3 ပို့ရန်\n\n"
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
# ADMIN CHECK
# =========================

async def is_admin(update, context):
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message

    if (
        not chat
        or chat.type not in ("group", "supergroup")
        or not user
    ):
        await message.reply_text(
            "ဒီ Command ကို Telegram Group ထဲမှာ သုံးပါ။"
        )
        return False

    try:
        member = await context.bot.get_chat_member(
            chat.id, user.id
        )

        if member.status not in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        ):
            await message.reply_text(
                "ဒီ Command ကို Group Admin ပဲ သုံးနိုင်ပါတယ်။"
            )
            return False

        return True

    except Exception:
        logger.exception("Admin check failed")

        await message.reply_text(
            "Admin စစ်ဆေးမရပါ။ Bot ကို Group ထဲထည့်ထားကြောင်း စစ်ပါ။"
        )
        return False


async def target_user(update, context):
    message = update.effective_message

    # Reply လုပ်ထားတဲ့ User ကို ရွေးမယ်
    if message.reply_to_message:
        target = message.reply_to_message.from_user

        if target and not target.is_bot:
            return target

        await message.reply_text(
            "ဒီ User ကို Target အဖြစ် မသုံးနိုင်ပါ။"
        )
        return None

    # User ID ဖြင့် ရွေးမယ်
    if context.args and context.args[0].isdigit():
        try:
            member = await context.bot.get_chat_member(
                update.effective_chat.id,
                int(context.args[0]),
            )

            if member.user.is_bot:
                await message.reply_text(
                    "Bot Account ကို Target မလုပ်နိုင်ပါ။"
                )
                return None

            return member.user

        except Exception:
            await message.reply_text(
                "User ကို မတွေ့ပါ။ User ID မှန်မမှန် စစ်ပါ။"
            )
            return None

    await message.reply_text(
        "အသုံးပြုပုံ:\n"
        "User ရဲ့စာကို Reply လုပ်ပြီး /warn, /ban, /mute သုံးပါ။"
    )

    return None


# =========================
# WARN
# =========================

async def warn_cmd(update, context):
    if not await is_admin(update, context):
        return

    target = await target_user(update, context)

    if not target:
        return

    chat_id = update.effective_chat.id

    try:
        member = await context.bot.get_chat_member(
            chat_id, target.id
        )

        if member.status in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        ):
            await update.effective_message.reply_text(
                "Admin ကို Warn မပေးနိုင်ပါ။"
            )
            return

        count = add_warn(chat_id, target.id)

        if count >= 3:
            await context.bot.ban_chat_member(
                chat_id, target.id
            )

            db.execute(
                "DELETE FROM warns WHERE chat_id=? AND user_id=?",
                (chat_id, target.id),
            )
            db.commit()

            await update.effective_message.reply_text(
                f"⚠️ {target.first_name} သည် Warn ၃ ကြိမ်ပြည့်သဖြင့် "
                "Ban လုပ်ပြီးပါပြီ။"
            )

        else:
            await update.effective_message.reply_text(
                f"⚠️ {target.first_name} ကို Warn ပေးလိုက်ပါပြီ။\n"
                f"Warn: {count}/3"
            )

    except Exception:
        logger.exception("Warn failed")

        await update.effective_message.reply_text(
            "Warn သို့မဟုတ် Auto-ban မအောင်မြင်ပါ။ "
            "Bot Admin Permission ကို စစ်ပါ။"
        )


async def warns_cmd(update, context):
    if not await is_admin(update, context):
        return

    target = await target_user(update, context)

    if not target:
        return

    count = get_warns(
        update.effective_chat.id,
        target.id,
    )

    await update.effective_message.reply_text(
        f"👤 {target.first_name}\n"
        f"⚠️ Warn: {count}/3"
    )


# =========================
# BAN / UNBAN
# =========================

async def ban_cmd(update, context):
    if not await is_admin(update, context):
        return

    target = await target_user(update, context)

    if not target:
        return

    try:
        member = await context.bot.get_chat_member(
            update.effective_chat.id,
            target.id,
        )

        if member.status in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        ):
            await update.effective_message.reply_text(
                "Admin ကို Ban မလုပ်နိုင်ပါ။"
            )
            return

        await context.bot.ban_chat_member(
            update.effective_chat.id,
            target.id,
        )

        await update.effective_message.reply_text(
            f"🔨 {target.first_name} ကို Ban လုပ်ပြီးပါပြီ။"
        )

    except Exception:
        logger.exception("Ban failed")

        await update.effective_message.reply_text(
            "Ban မအောင်မြင်ပါ။ Bot ကို Ban Users Permission ပေးပါ။"
        )


async def unban_cmd(update, context):
    if not await is_admin(update, context):
        return

    if not context.args or not context.args[0].isdigit():
        await update.effective_message.reply_text(
            "အသုံးပြုပုံ:\n/unban USER_ID"
        )
        return

    user_id = int(context.args[0])

    try:
        await context.bot.unban_chat_member(
            update.effective_chat.id,
            user_id,
            only_if_banned=True,
        )

        await update.effective_message.reply_text(
            "✅ Unban အောင်မြင်ပါပြီ။"
        )

    except Exception:
        logger.exception("Unban failed")

        await update.effective_message.reply_text(
            "Unban မအောင်မြင်ပါ။ User ID နှင့် Permission ကို စစ်ပါ။"
        )


# =========================
# MUTE / UNMUTE
# =========================

async def mute_cmd(update, context):
    if not await is_admin(update, context):
        return

    target = await target_user(update, context)

    if not target:
        return

    try:
        member = await context.bot.get_chat_member(
            update.effective_chat.id,
            target.id,
        )

        if member.status in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        ):
            await update.effective_message.reply_text(
                "Admin ကို Mute မလုပ်နိုင်ပါ။"
            )
            return

        await context.bot.restrict_chat_member(
            update.effective_chat.id,
            target.id,
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

        await update.effective_message.reply_text(
            f"🔇 {target.first_name} ကို Mute လုပ်ပြီးပါပြီ။"
        )

    except Exception:
        logger.exception("Mute failed")

        await update.effective_message.reply_text(
            "Mute မအောင်မြင်ပါ။ Bot ကို Restrict Members Permission ပေးပါ။"
        )


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
                can_add_web_page_previews=True,
            ),
        )

        await update.effective_message.reply_text(
            f"🔊 {target.first_name} ကို Unmute လုပ်ပြီးပါပြီ။"
        )

    except Exception:
        logger.exception("Unmute failed")

        await update.effective_message.reply_text(
            "Unmute မအောင်မြင်ပါ။ Bot Admin Permission ကို စစ်ပါ။"
        )


# =========================
# SONG - SEND MP3 FILE
# =========================

async def song_cmd(update, context):
    if not context.args:
        await update.effective_message.reply_text(
            "🎵 သီချင်းအမည် ရိုက်ပေးပါ။\n\n"
            "ဥပမာ: /song song1\n"
            "ဒီ Command က songs/song1.mp3 ကို ပို့ပေးပါမယ်။"
        )
        return

    # ဖိုင်နာမည်ကို လုံခြုံစွာ စစ်ဆေးမယ်
    name = "_".join(context.args)

    if (
        not re.fullmatch(r"[\w\- ]+", name, flags=re.UNICODE)
        or name in (".", "..")
    ):
        await update.effective_message.reply_text(
            "သီချင်းဖိုင်နာမည် မမှန်ပါ။"
        )
        return

    filename = name + ".mp3"
    path = os.path.join(SONGS_DIR, filename)

    if not os.path.isfile(path):
        await update.effective_message.reply_text(
            f"🎵 '{name}' သီချင်းဖိုင် မတွေ့ပါဘူး။\n\n"
            "အသုံးပြုခွင့်ရှိတဲ့ MP3 ဖိုင်ကို GitHub ရှိ songs Folder ထဲ "
            "ထည့်ပေးပါ။"
        )
        return

    try:
        with open(path, "rb") as audio:
            await update.effective_message.reply_audio(
                audio=audio,
                title=name.replace("_", " "),
                caption="🎵 Ck_helpbot Music",
            )

    except Exception:
        logger.exception("Song sending failed")

        await update.effective_message.reply_text(
            "သီချင်းပို့မရပါ။ ဖိုင်အရွယ်အစားနဲ့ Format ကို စစ်ပါ။"
        )


# =========================
# BROADCAST
# =========================

async def broadcast_cmd(update, context):
    user = update.effective_user
    message = update.effective_message

    if not user or OWNER_ID == 0 or user.id != OWNER_ID:
        await message.reply_text(
            "ဒီ Command ကို Bot Owner ပဲ သုံးနိုင်ပါတယ်။"
        )
        return

    text = " ".join(context.args)

    if not text:
        await message.reply_text(
            "အသုံးပြုပုံ:\n/broadcast မင်္ဂလာပါ"
        )
        return

    rows = db.execute(
        "SELECT user_id FROM users"
    ).fetchall()

    sent = 0
    failed = 0

    for (user_id,) in rows:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=text,
            )
            sent += 1

            # Telegram rate limit ကို လျှော့ချရန်
            await asyncio.sleep(0.05)

        except Exception:
            logger.warning(
                "Broadcast failed for user %s",
                user_id,
            )
            failed += 1

    await message.reply_text(
        "📣 Broadcast ပြီးပါပြီ။\n"
        f"ပို့နိုင်: {sent}\n"
        f"မပို့နိုင်: {failed}"
    )


# =========================
# REMEMBER PRIVATE USERS
# =========================

async def remember_private(update, context):
    user = update.effective_user
    chat = update.effective_chat

    if user and chat and chat.type == "private":
        remember_user(user.id)


# =========================
# ERROR HANDLER
# =========================

async def error_handler(update, context):
    logger.error(
        "Bot error",
        exc_info=context.error,
    )


# =========================
# MAIN
# =========================

def main():
    os.makedirs(SONGS_DIR, exist_ok=True)

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

    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE,
            remember_private,
        ),
        group=1,
    )

    app.add_error_handler(error_handler)

    logger.info("Ck_helpbot is starting...")

    app.run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    main()
            
