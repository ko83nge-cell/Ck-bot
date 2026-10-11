import os
import sqlite3
import logging
from urllib.parse import quote

from telegram import Update
from telegram.constants import ChatMemberStatus
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger(__name__)

# သတ်မှတ်ထားသော Bot Token နှင့် Owner ID ကို တိုက်ရိုက်ထည့်သွင်းထားပါသည်
BOT_TOKEN = "8824850208:AAGkmULcNJxWx-39-80r-8oJNtSc9g3bSTM"
OWNER_ID = 8062359539
DB_PATH = os.getenv("DB_PATH", "bot.db")

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
        (user_id,)
    )
    db.commit()


def get_warns(chat_id, user_id):
    row = db.execute(
        "SELECT count FROM warns WHERE chat_id=? AND user_id=?",
        (chat_id, user_id)
    ).fetchone()
    return row[0] if row else 0


def add_warn(chat_id, user_id):
    count = get_warns(chat_id, user_id) + 1
    db.execute(
        """INSERT INTO warns(chat_id,user_id,count)
        VALUES(?,?,?)
        ON CONFLICT(chat_id,user_id)
        DO UPDATE SET count=excluded.count""",
        (chat_id, user_id, count)
    )
    db.commit()
    return count


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user:
        remember_user(user.id)

    await update.effective_message.reply_text(
        "မင်္ဂလာပါ! 🤖 Ck_helpbot မှ ကြိုဆိုပါတယ်။\n"
        "/help ကိုနှိပ်ပြီး Commands များ ကြည့်ပါ။"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "📚 Ck_helpbot Commands\n\n"
        "အသုံးပြုသူများ:\n"
        "/start - Bot စတင်ရန်\n"
        "/help - အကူအညီ\n"
        "/id - User/Chat ID\n"
        "/song သီချင်းအမည် - သီချင်းရှာရန်\n\n"
        "Group Admin များ:\n"
        "/warn (reply) - သတိပေးရန်\n"
        "/warns (reply) - Warn အရေအတွက်\n"
        "/ban (reply) - Ban လုပ်ရန်\n"
        "/unban USER_ID - Ban ပြန်ဖြုတ်ရန်\n"
        "/mute (reply) - Mute လုပ်ရန်\n"
        "/unmute (reply) - Mute ပြန်ဖြုတ်ရန်\n\n"
        "Owner:\n"
        "/broadcast စာသား - Bot ကို စတင်ထားသူများထံ ပို့ရန်"
    )


async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    await update.effective_message.reply_text(
        f"User ID: {user.id if user else 'N/A'}\n"
        f"Chat ID: {chat.id if chat else 'N/A'}"
    )


async def is_admin(update, context):
    chat = update.effective_chat
    user = update.effective_user

    if not chat or chat.type not in ("group", "supergroup") or not user:
        await update.effective_message.reply_text(
            "ဒီ Command ကို Group ထဲမှာ အသုံးပြုပါ။"
        )
        return False

    member = await context.bot.get_chat_member(chat.id, user.id)
    if member.status not in (
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.OWNER,
    ):
        await update.effective_message.reply_text(
            "ဒီ Command ကို Group Admin ပဲ အသုံးပြုနိုင်ပါတယ်။"
        )
        return False

    return True


async def target_user(update, context):
    message = update.effective_message

    if message.reply_to_message:
        target = message.reply_to_message.from_user
        if target and not target.is_bot:
            return target

    if context.args:
        value = context.args[0]
        if value.isdigit():
            try:
                member = await context.bot.get_chat_member(
                    update.effective_chat.id, int(value)
                )
                return member.user
            except Exception:
                pass

    await message.reply_text(
        "အသုံးပြုပုံ: Command ကို အသုံးပြုသူရဲ့စာကို Reply လုပ်ပါ။"
    )
    return None


async def warn_cmd(update, context):
    if not await is_admin(update, context):
        return

    target = await target_user(update, context)
    if not target:
        return

    chat_id = update.effective_chat.id
    count = add_warn(chat_id, target.id)

    if count >= 3:
        try:
            await context.bot.ban_chat_member(chat_id, target.id)
            db.execute(
                "DELETE FROM warns WHERE chat_id=? AND user_id=?",
                (chat_id, target.id)
            )
            db.commit()
            await update.effective_message.reply_text(
                f"⚠️ {target.first_name} သည် Warn ၃ ကြိမ်ပြည့်သဖြင့် Ban လုပ်လိုက်ပါပြီ။"
            )
        except Exception as e:
            log.warning("Auto-ban failed: %s", e)
            await update.effective_message.reply_text(
                f"Warn {count}/3 ရရှိပါပြီ။ Auto-ban မအောင်မြင်ပါ။ "
                "Bot ကို Admin ပေးထားခြင်း ရှိမရှိ စစ်ပါ။"
            )
    else:
        await update.effective_message.reply_text(
            f"⚠️ {target.first_name} ကို Warn ပေးလိုက်ပါပြီ ({count}/3)"
        )


async def warns_cmd(update, context):
    if not await is_admin(update, context):
        return
    target = await target_user(update, context)
    if target:
        count = get_warns(update.effective_chat.id, target.id)
        await update.effective_message.reply_text(
            f"{target.first_name}: Warn {count}/3"
        )


async def ban_cmd(update, context):
    if not await is_admin(update, context):
        return
    target = await target_user(update, context)
    if not target:
        return
    try:
        await context.bot.ban_chat_member(
            update.effective_chat.id, target.id
        )
        await update.effective_message.reply_text(
            f"🔨 {target.first_name} ကို Ban လုပ်ပြီးပါပြီ။"
        )
    except Exception as e:
        log.warning("Ban failed: %s", e)
        await update.effective_message.reply_text(
            "Ban မအောင်မြင်ပါ။ Bot Admin Permission ကို စစ်ပါ။"
        )


async def unban_cmd(update, context):
    if not await is_admin(update, context):
        return
    if not context.args or not context.args[0].isdigit():
        await update.effective_message.reply_text(
            "အသုံးပြုပုံ: /unban USER_ID"
        )
        return
    try:
        await context.bot.unban_chat_member(
            update.effective_chat.id, int(context.args[0]),
            only_if_banned=True
        )
        await update.effective_message.reply_text("✅ Unban အောင်မြင်ပါပြီ။")
    except Exception as e:
        log.warning("Unban failed: %s", e)
        await update.effective_message.reply_text(
            "Unban မအောင်မြင်ပါ။ User ID နဲ့ Permission ကို စစ်ပါ။"
        )


async def mute_cmd(update, context):
    if not await is_admin(update, context):
        return
    target = await target_user(update, context)
    if not target:
        return
    try:
        from telegram import ChatPermissions
        await context.bot.restrict_chat_member(
            update.effective_chat.id,
            target.id,
            permissions=ChatPermissions(can_send_messages=False)
        )
        await update.effective_message.reply_text(
            f"🔇 {target.first_name} ကို Mute လုပ်ပြီးပါပြီ။"
        )
    except Exception as e:
        log.warning("Mute failed: %s", e)
        await update.effective_message.reply_text(
            "Mute မအောင်မြင်ပါ။ Bot Admin Permission ကို စစ်ပါ။"
        )


async def unmute_cmd(update, context):
    if not await is_admin(update, context):
        return
    target = await target_user(update, context)
    if not target:
        return
    try:
        from telegram import ChatPermissions
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
        await update.effective_message.reply_text(
            f"🔊 {target.first_name} ကို Unmute လုပ်ပြီးပါပြီ။"
        )
    except Exception as e:
        log.warning("Unmute failed: %s", e)
        await update.effective_message.reply_text(
            "Unmute မအောင်မြင်ပါ။ Bot Admin Permission ကို စစ်ပါ။"
        )


async def song_cmd(update, context):
    if not context.args:
        await update.effective_message.reply_text(
            "အသုံးပြုပုံ: /song သီချင်းအမည်\nဥပမာ: /song Myanmar songs"
        )
        return

    query = " ".join(context.args)
    url = "https://www.youtube.com/results?search_query=" + quote(query)
    await update.effective_message.reply_text(
        f"🎵 သီချင်းရှာရန်: {query}\n{url}\n\n"
        "မှတ်ချက်: ဒီ Command က ရှာဖွေရေး Link ပေးတာပါ။ "
        "Group Voice Chat ထဲ တိုက်ရိုက်ဖွင့်ပေးတာ မဟုတ်ပါ။"
    )


async def broadcast_cmd(update, context):
    user = update.effective_user
    message = update.effective_message

    if not user or user.id != OWNER_ID:
        await message.reply_text("ဒီ Command ကို Bot Owner ပဲ သုံးနိုင်ပါတယ်။")
        return

    text = " ".join(context.args)
    if not text:
        await message.reply_text("အသုံးပြုပုံ: /broadcast မင်္ဂလာပါ")
        return

    rows = db.execute("SELECT user_id FROM users").fetchall()
    sent = 0
    failed = 0

    for (user_id,) in rows:
        try:
            await context.bot.send_message(chat_id=user_id, text=text)
            sent += 1
        except Exception as e:
            log.info("Broadcast failed for %s: %s", user_id, e)
            failed += 1

    await message.reply_text(
        f"📣 Broadcast ပြီးပါပြီ။\n"
        f"ပို့နိုင်: {sent}\nမပို့နိုင်: {failed}"
    )


async def remember_private(update, context):
    user = update.effective_user
    if user and update.effective_chat and update.effective_chat.type == "private":
        remember_user(user.id)


async def error_handler(update, context):
    log.error("Unhandled bot error: %s", context.error)


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN မရှိပါ။")

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
        MessageHandler(filters.ChatType.PRIVATE, remember_private),
        group=1
    )
    app.add_error_handler(error_handler)

    log.info("Ck_helpbot is starting...")
    app.run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    main()

