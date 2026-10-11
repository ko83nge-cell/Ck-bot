import os
import logging
import asyncio
import aiosqlite
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# တောင်းဆိုထားသော Bot Token ကို တိုက်ရိုက်ထည့်သွင်းထားပါသည်
BOT_TOKEN = "8824850208:AAGkmULcNJxWx-39-80r-8oJNtSc9g3bSTM"
OWNER_ID = int(os.getenv("OWNER_ID", "8062359539"))
DB_PATH = os.getenv("DB_PATH", "bot.db")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS groups_list (
                chat_id INTEGER PRIMARY KEY
            )
        """)
        await db.commit()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat and chat.type in ("group", "supergroup"):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR IGNORE INTO groups_list(chat_id) VALUES (?)",
                (chat.id,),
            )
            await db.commit()

    await update.effective_message.reply_text(
        "မင်္ဂလာပါ! 🤖\n/help ကိုနှိပ်ပြီး Bot Command တွေကြည့်နိုင်ပါတယ်။"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "အသုံးပြုနိုင်သော Command များ\n"
        "/start - Bot စတင်ရန်\n"
        "/help - အကူအညီ\n"
        "/id - ကိုယ်ပိုင် ID ကြည့်ရန်\n"
        "/song သီချင်းအမည် - သီချင်း Preview ရှာရန်\n"
        "/broadcast စာသား - Owner သာ အသုံးပြုရန်"
    )


async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        f"User ID: {update.effective_user.id}\n"
        f"Chat ID: {update.effective_chat.id}"
    )


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or user.id != OWNER_ID:
        await update.effective_message.reply_text("ဒီ Command ကို Owner သာ သုံးနိုင်ပါတယ်။")
        return

    message = " ".join(context.args).strip()
    if not message:
        await update.effective_message.reply_text(
            "အသုံးပြုပုံ: /broadcast ကြော်ငြာစာသား"
        )
        return

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT chat_id FROM groups_list") as cursor:
            rows = await cursor.fetchall()

    sent = 0
    for (chat_id,) in rows:
        try:
            await context.bot.send_message(chat_id=chat_id, text=message)
            sent += 1
        except Exception:
            log.exception("Broadcast failed for chat %s", chat_id)

    await update.effective_message.reply_text(f"ပို့ပြီးပါပြီ။ အောင်မြင်သောအဖွဲ့: {sent}")


async def post_init(application: Application):
    await init_db()


def main():
    if not BOT_TOKEN:
        raise RuntimeError("Bot Token ထည့်ရန် လိုအပ်ပါသည်။")

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("id", id_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast))
    log.info("Bot is starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
