import os
import re
import sqlite3
import logging
import asyncio
from urllib.parse import quote

import requests
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from google_play_scraper import search as playstore_search

# =========================================================
# Configuration (Railway Variables ထဲတွင် ထည့်ရန်)
# =========================================================

TOKEN = os.getenv("BOT_TOKEN", "").strip()
FORCE_CHANNEL = os.getenv("FORCE_CHANNEL", "").strip()  # ဥပမာ - @mygamechannel
ADMIN_IDS = {
    int(value.strip())
    for value in os.getenv("ADMIN_IDS", "").split(",")
    if value.strip().isdigit()
}
DB_PATH = os.getenv("DB_PATH", "movies_bot.db")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("ck_helpbot")

HEADERS = {"User-Agent": "CkHelpBot/1.0 (Telegram information bot)"}
HTTP_TIMEOUT = 15


# ------------------------- Database -------------------------

def init_db():
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS movies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                file_id TEXT NOT NULL,
                caption TEXT
            )
        """)
        db.commit()


# ---------------------- Forced Subscription Check ----------------------

async def check_user_subscription(bot, user_id: int) -> bool:
    if not FORCE_CHANNEL:
        return True
    try:
        member = await bot.get_chat_member(chat_id=FORCE_CHANNEL, user_id=user_id)
        if member.status in ["creator", "administrator", "member"]:
            return True
        return False
    except Exception as exc:
        logger.warning("Could not check subscription: %s", exc)
        return False


async def verify_subscription_middleware(update: Update) -> bool:
    if not FORCE_CHANNEL:
        return True
    
    user = update.effective_user
    message = update.effective_message
    if not user or not message:
        return False

    is_member = await check_user_subscription(update.get_bot(), user.id)
    if not is_member:
        channel_url = f"https://t.me/{FORCE_CHANNEL.replace('@', '')}"
        keyboard = [
            [InlineKeyboardButton("📢 Channel Join ရန်", url=channel_url)],
            [InlineKeyboardButton("🔄 စစ်ဆေးမည် (Joined)", callback_data="check_sub")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await message.reply_text(
            "⚠️ **ကျေးဇူးပြု၍ ပထမဦးစွာ ကျွန်ုပ်တို့၏ Channel ကို Join ပေးပါ။**\n\n"
            "Join ပြီးပါက အောက်ပါ '🔄 စစ်ဆေးမည် (Joined)' ခလုတ်ကို နှိပ်ပါ။",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        return False
    return True


# ---------------------- API utilities ----------------------

def get_json(url, params=None):
    try:
        response = requests.get(
            url, params=params, headers=HEADERS, timeout=HTTP_TIMEOUT
        )
        if response.status_code != 200:
            return None
        return response.json()
    except (requests.RequestException, ValueError):
        return None


def translate_to_burmese(text):
    if not text:
        return ""
    text = str(text)[:3500]
    data = get_json(
        "https://translate.googleapis.com/translate_a/single",
        {"client": "gtx", "sl": "auto", "tl": "my", "dt": "t", "q": text},
    )
    try:
        if data and isinstance(data, list):
            return "".join(part[0] for part in data[0] if part and part[0])
    except (IndexError, TypeError):
        pass
    return text


# -------------------------- Commands -----------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await verify_subscription_middleware(update):
        return

    await update.effective_message.reply_text(
        "🤖 **Game & App Finder Bot မှ ကြိုဆိုပါတယ်။**\n\n"
        "🎮 လိုချင်တဲ့ Play Store ဂိမ်းနာမည် (သို့) ရုပ်ရှင်အမည်ကို ရိုက်ထည့်ပါ။\n\n"
        "/help - အသုံးပြုနည်း"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "📖 **အသုံးပြုနည်း**\n\n"
        "• Bot မသုံးမီ သတ်မှတ်ထားသော Channel ကို အရင် Join ရပါမည်။\n"
        "• ဂိမ်း သို့မဟုတ် အက်ပ်နာမည်ကို ရိုက်ထည့်ပါက Play Store မှ ရှာဖွေပေးပါမည်။\n"
        "• Admin များအတွက် ဖိုင်ပို့ပြီး Database ထဲ သိမ်းဆည်းနိုင်ပါသည်။"
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "check_sub":
        user_id = query.from_user.id
        is_member = await check_user_subscription(context.bot, user_id)
        if is_member:
            await query.message.edit_text(
                "✅ ကျေးဇူးတင်ပါတယ်! ယခု Bot ကို အပြည့်အစုံ အသုံးပြုနိုင်ပါပြီ။\n\n"
                "လိုချင်သော ဂိမ်းနာမည်ကို ဆက်လက်ရိုက်ထည့်ပါ။"
            )
        else:
            await query.answer("❌ ကျေးဇူးပြု၍ Channel ကို အရင် Join ပေးပါ။", show_alert=True)


# ------------------------ Storage & Search --------------------

async def save_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    user = update.effective_user
    if not message or not user:
        return

    if user.id not in ADMIN_IDS:
        await message.reply_text("⚠️ ဖိုင်တင်ခွင့်ကို Admin များသာ အသုံးပြုနိုင်ပါတယ်။")
        return

    if message.video:
        file_id = message.video.file_id
        title = message.caption or getattr(message.video, "file_name", None) or "Untitled File"
    elif message.document:
        file_id = message.document.file_id
        title = message.caption or message.document.file_name or "Untitled File"
    else:
        return

    try:
        with sqlite3.connect(DB_PATH, timeout=30) as db:
            db.execute(
                "INSERT INTO movies (title, file_id, caption) VALUES (?, ?, ?)",
                (title.lower(), file_id, title),
            )
            db.commit()
        await message.reply_text(f"✅ ဖိုင်ကို Database ထဲသို့ သိမ်းဆည်းပြီးပါပြီ။\n📥 {title}")
    except sqlite3.Error:
        logger.exception("Could not save file")
        await message.reply_text("❌ ဒေတာဘေ့စ်ထဲသို့ သိမ်းဆည်းမရပါ။")


async def search_local_db(query: str):
    try:
        with sqlite3.connect(DB_PATH, timeout=30) as db:
            results = db.execute(
                """
                SELECT title, file_id, caption FROM movies
                WHERE LOWER(title) LIKE ?
                ORDER BY id DESC LIMIT 3
                """,
                (f"%{query.lower()}%",),
            ).fetchall()
            return results
    except sqlite3.Error:
        return []


def search_playstore(query: str):
    """Google Play Store မှ ဂိမ်း/အက်ပ်များကို ရှာဖွေပေးခြင်း"""
    try:
        results = playstore_search(query, lang="en", country="us", n_hits=1)
        if results:
            app = results[0]
            app_name = app.get("title")
            app_id = app.get("appId")
            developer = app.get("developer")
            score = app.get("score")
            icon = app.get("icon")
            link = f"https://play.google.com/store/apps/details?id={app_id}"
            
            return {
                "name": app_name,
                "developer": developer,
                "score": score,
                "icon": icon,
                "link": link
            }
    except Exception as e:
        logger.error(f"Playstore search error: {e}")
    return None


# ----------------------- Main text handler -----------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await verify_subscription_middleware(update):
        return

    message = update.effective_message
    if not message or not message.text:
        return

    query = message.text.strip()
    if not query or query.startswith("/"):
        return

    # ၁။ ပထမဦးစွာ Local Database (သိမ်းထားသောဖိုင်များ) ထဲတွင် ရှာမည်
    local_results = await search_local_db(query)
    if local_results:
        for title, file_id, caption in local_results:
            caption_text = f"📥 {caption or title}\n\nGame Bot"
            try:
                await message.reply_video(video=file_id, caption=caption_text[:1000])
                return
            except Exception:
                try:
                    await message.reply_document(document=file_id, caption=caption_text[:1000])
                    return
                except Exception:
                    pass

    # ၂။ Local ထဲ မရှိပါက Google Play Store ပေါ်တွင် ရှာဖွေပေးမည်
    await message.reply_text(f"🔍 '{query}' ကို Play Store ပေါ်တွင် ရှာဖွေနေပါပြီ...")
    
    playstore_result = await asyncio.to_thread(search_playstore, query)
    if playstore_result:
        response_text = (
            f"🎮 **{playstore_result['name']}**\n\n"
            f"👤 ဖန်တီးသူ: {playstore_result['developer']}\n"
            f"⭐ Rating: {playstore_result['score']}\n\n"
            f"🔗 **Play Store တွင် ဒေါင်းလုဒ်လုပ်ရန်:**\n{playstore_result['link']}"
        )
        await message.reply_text(response_text, parse_mode="Markdown")
    else:
        await message.reply_text(
            "❌ မည်သည့်ရလဒ်မှ မတွေ့ပါ။ (Local Database နှင့် Play Store နှစ်ခုစလုံးတွင် ရှာမတွေ့ပါ)"
        )


# ---------------------------- Main -------------------------

def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN မရှိပါ။ Railway Variables ထဲတွင် BOT_TOKEN ထည့်ပါ။")

    init_db()
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(
        MessageHandler(filters.VIDEO | filters.Document.ALL, save_movie)
    )
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    logger.info("Bot with Play Store Search & Force Sub is running...")
    app.run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    main()
