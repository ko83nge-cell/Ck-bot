import os
import re
import sqlite3
import logging
import asyncio
import random
import string
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urlparse

import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS = {
    int(value.strip())
    for value in os.getenv("ADMIN_IDS", "").split(",")
    if value.strip().isdigit()
}
DB_PATH = os.getenv("DB_PATH", "movies_bot.db")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "").strip()
CHANNEL_URL = os.getenv("CHANNEL_URL", "").strip()

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("ck_helpbot")

HEADERS = {"User-Agent": "Mozilla/5.0"}
HTTP_TIMEOUT = 15

def init_db():
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                note_text TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                task_text TEXT NOT NULL
            )
        """)
        # သတင်းများ သိမ်းဆည်းရန် ဇယား (Bot နှင့် Channel နှစ်ခုလုံးအတွက်)
        db.execute("""
            CREATE TABLE IF NOT EXISTS news_store (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                news_title TEXT,
                news_content TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.commit()

def translate_text(text, target_lang="my"):
    if not text: return ""
    try:
        lang_name = "Burmese (Myanmar)" if target_lang == "my" else target_lang
        ai_url = f"https://text.pollinations.ai/{quote(f'Translate the following text accurately into {lang_name}. Provide ONLY the translated text without extra explanation: ' + text)}"
        res = requests.get(ai_url, timeout=20)
        if res.status_code == 200 and res.text.strip():
            return res.text.strip()
    except Exception as e:
        logger.error(f"Translation error: {e}")
    return text

def get_weather(city_name):
    try:
        geo_res = requests.get("https://geocoding-api.open-meteo.com/v1/search", params={"name": city_name, "count": 1}, timeout=HTTP_TIMEOUT).json()
        if not geo_res.get("results"): return None
        loc = geo_res["results"][0]
        w_res = requests.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": loc["latitude"], "longitude": loc["longitude"],
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m"
        }, timeout=HTTP_TIMEOUT).json()
        curr = w_res.get("current", {})
        return f"🌤️ {loc.get('name')}, {loc.get('country', '')}\n🌡️ အပူချိန်: {curr.get('temperature_2m')}°C\n💧 စိုထိုင်းဆ: {curr.get('relative_humidity_2m')}%"
    except:
        return None

def get_exchange_rates():
    try:
        data = requests.get("https://open.er-api.com/v6/latest/USD", timeout=HTTP_TIMEOUT).json()
        rates = data.get("rates", {})
        return (
            "💱 **US Dollar (1 USD) လဲလှယ်နှုန်းများ**\n\n"
            f"💶 ယူရို (EUR): {rates.get('EUR')}\n"
            f"🇹🇭 ထိုင်းဘတ် (THB): {rates.get('THB')}\n"
            f"🇸🇬 စင်ကာပူဒေါ်လာ (SGD): {rates.get('SGD')}\n"
            f"🇲🇾 မလေးရှားရင်းဂစ် (MYR): {rates.get('MYR')}\n"
            f"🇯🇵 ဂျပန်ယန်း (JPY): {rates.get('JPY')}"
        )
    except:
        return None

def get_dictionary_definition(word):
    try:
        res = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{quote(word)}", timeout=HTTP_TIMEOUT)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list) and data:
                entry = data[0]
                word_str = entry.get("word", word)
                phonetic = entry.get("phonetic", "")
                meanings = entry.get("meanings", [])
                
                result_text = f"📖 **Word:** {word_str} {phonetic}\n"
                for m in meanings[:2]:
                    part_of_speech = m.get("partOfSpeech", "")
                    definitions = m.get("definitions", [])
                    result_text += f"\n🔹 *{part_of_speech}*\n"
                    for d in definitions[:2]:
                        result_text += f"• {d.get('definition')}\n"
                return result_text
    except:
        pass
    return None

def fetch_latest_news(category="world"):
    try:
        prompt = f"Give me recent major {category} news summary in clear Burmese language with bullet points."
        ai_url = f"https://text.pollinations.ai/{quote(prompt)}"
        res = requests.get(ai_url, timeout=25)
        if res.status_code == 200 and res.text.strip():
            return res.text.strip()
    except Exception as e:
        logger.error(f"News fetch error: {e}")
    return None

def free_social_ai_chat(prompt):
    try:
        ai_url = f"https://text.pollinations.ai/{quote('You are a friendly, polite, and warm Burmese AI assistant. Reply naturally and helpfully in Burmese: ' + prompt)}"
        res = requests.get(ai_url, timeout=20)
        if res.status_code == 200 and res.text.strip():
            return res.text.strip()
    except Exception as e:
        logger.error(f"AI Chat error: {e}")
    return "မင်္ဂလာပါရှင့်၊ အချက်အလက်များကို လက်ခံရရှိပါသည်။"


# ---------------------- Channel join verification ------------------

def channel_join_url():
    if CHANNEL_URL:
        return CHANNEL_URL
    username = CHANNEL_USERNAME.lstrip("@")
    return f"https://t.me/{username}" if username else ""

async def is_channel_member(context, user_id):
    if not CHANNEL_USERNAME:
        return True
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        status = getattr(member, "status", "")
        if status in ("creator", "administrator", "member"):
            return True
        return status == "restricted" and bool(getattr(member, "is_member", False))
    except Exception:
        return None

async def require_channel_join(update, context):
    user = update.effective_user
    message = update.effective_message
    if not user or user.id in ADMIN_IDS or not CHANNEL_USERNAME:
        return True
    
    membership = await is_channel_member(context, user.id)
    if membership is True:
        return True
    
    buttons = []
    url = channel_join_url()
    if url:
        buttons.append([InlineKeyboardButton("📢 Channel Join", url=url)])
    buttons.append([InlineKeyboardButton("✅ Join ပြီးပါပြီ", callback_data="check_channel_join")])
    keyboard = InlineKeyboardMarkup(buttons)
    
    notice = "🔒 ဘော့ကို ဆက်လက်အသုံးပြုရန် အောက်ပါ Channel ကို အရင် Join လုပ်ပေးပါ။"
    if update.callback_query:
        await update.callback_query.answer()
        if update.callback_query.message:
            await update.callback_query.message.reply_text(notice, reply_markup=keyboard)
    elif message:
        await message.reply_text(notice, reply_markup=keyboard)
    return False

async def check_channel_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    user = query.from_user
    membership = await is_channel_member(context, user.id)
    if membership is True:
        await query.answer("✅ အတည်ပြုပြီးပါပြီ။")
        if query.message:
            await query.message.reply_text("🎉 အတည်ပြုပြီးပါပြီ။ ယခု Bot ကို အသုံးပြုနိုင်ပါပြီ။ /start ကို နှိပ်ပါ။")
    else:
        await query.answer("Channel ကို မတွေ့ရသေးပါ။ ကျေးဇူးပြု၍ Join ပါ.", show_alert=True)


# ---------------------- Auto News Broadcast Job ------------------

async def auto_news_broadcast_job(context: ContextTypes.DEFAULT_TYPE):
    """သတင်းအသစ်များကို အလိုအလျောက် ဆွဲထုတ်ပြီး Database ထဲသိမ်းကာ Channel ထဲပို့ပေးမည့်စနစ်"""
    news_text = await asyncio.to_thread(fetch_latest_news, "global and Myanmar breaking news")
    if not news_text:
        return

    with sqlite3.connect(DB_PATH, timeout=30) as db:
        # တူညီသောသတင်း ရှိမရှိ စစ်ဆေးခြင်း
        cursor = db.execute("SELECT id FROM news_store WHERE news_content = ?", (news_text[:50],))
        if cursor.fetchone():
            return
        
        db.execute("INSERT INTO news_store (news_title, news_content) VALUES (?, ?)", ("Breaking/Latest News", news_text))
        db.commit()

    # Channel ထဲသို့ အလိုအလျောက် ပို့ရန်
    if CHANNEL_USERNAME:
        try:
            broadcast_msg = f"📰 **သတင်းစုံနှင့် အရေးပေါ် Breaking News** 📰\n\n{news_text}"
            await context.bot.send_message(chat_id=CHANNEL_USERNAME, text=broadcast_msg)
            logger.info("News successfully auto-broadcasted to channel.")
        except Exception as e:
            logger.error(f"Auto news channel send error: {e}")


# ---------------------- Command Handlers ------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    await update.effective_message.reply_text(
        "🤖 **Ck_helpbot (Dual News System)** မှ ကြိုဆိုပါတယ်။\n\n"
        "📰 `/news` - Database ထဲရှိ နောက်ဆုံးရသတင်းများကို Bot ထဲတွင် ကြည့်ရှုရန်\n"
        "💬 မည်သည့်စာသားကိုမဆို ရိုက်ပို့၍ AI နှင့် စကားပြောနိုင်ပါသည်။"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    await update.effective_message.reply_text("📖 အကူအညီအတွက် /start ကိုနှိပ်ပါ။")

async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    
    # Bot ထဲလာမေးသော အသုံးပြုသူများအတွက် Database ထဲက နောက်ဆုံးရသတင်းကို ထုတ်ပြပေးခြင်း
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        cursor = db.execute("SELECT news_content FROM news_store ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
    
    if row:
        await update.effective_message.reply_text(f"🌐 **နောက်ဆုံးရ သတင်းများနှင့် Breaking News:**\n\n{row[0]}")
    else:
        # Database ထဲ မရှိသေးပါက ချက်ချင်း အသစ်ဆွဲထုတ်ပေးမည်
        news_res = await asyncio.to_thread(fetch_latest_news, "global and Myanmar")
        if news_res:
            await update.effective_message.reply_text(f"🌐 **နောက်ဆုံးရ သတင်းများ:**\n\n{news_res}")
        else:
            await update.effective_message.reply_text("❌ သတင်း အချက်အလက် ခေတ္တမရရှိပါ။")

async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    query = " ".join(context.args).strip()
    if not query:
        await update.effective_message.reply_text("အသုံးပြုပုံ: `/weather Yangon`")
        return
    res = await asyncio.to_thread(get_weather, query)
    await update.effective_message.reply_text(res or "❌ ရာသီဥတု အချက်အလက် ရှာမတွေ့ပါ။")

async def rate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    res = await asyncio.to_thread(get_exchange_rates)
    await update.effective_message.reply_text(res or "❌ ငွေလဲနှုန်း ရယူမရပါ။")

async def translate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    args = context.args
    if not args:
        await update.effective_message.reply_text("အသုံးပြုပုံ: `/tr en မင်္ဂလာပါ`")
        return
    res = await asyncio.to_thread(translate_text, " ".join(args[1:]) if len(args)>1 else " ".join(args), args[0] if len(args)>1 else "my")
    await update.effective_message.reply_text(f"🔤 **ဘာသာပြန်ဆိုချက်:**\n\n{res}")

async def define_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    args = context.args
    if not args: return
    res = await asyncio.to_thread(get_dictionary_definition, args[0].strip())
    await update.effective_message.reply_text(res or "❌ အဓိပ္ပာယ် မတွေ့ပါ။")

async def quote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    await update.effective_message.reply_text("💡 ယုံကြည်မှုအပြည့်နဲ့ ရှေ့ဆက်ပါ။")

async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    await update.effective_message.reply_text(f"⏰ {datetime.now().strftime('%Y-%m-%d | %H:%M:%S')}")

async def bmi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    args = context.args
    if len(args) < 2: return
    h, w = float(args[0]) / 100, float(args[1])
    await update.effective_message.reply_text(f"⚖️ BMI: {w / (h ** 2):.2f}")

async def water_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    args = context.args
    if not args: return
    await update.effective_message.reply_text(f"💧 ရေပမာဏ: {(float(args[0]) * 35) / 1000:.2f} လီတာ")

async def convert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    await update.effective_message.reply_text("🔄 ယူနစ်ပြောင်းရန်...")

async def password_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    pwd = "".join(random.choice(string.ascii_letters + string.digits) for _ in range(12))
    await update.effective_message.reply_text(f"🔑 `{pwd}`")

async def qr_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    text = " ".join(context.args).strip()
    if not text: return
    await update.effective_message.reply_photo(photo=f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={quote(text)}")

async def note_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        db.execute("INSERT INTO notes (user_id, note_text) VALUES (?, ?)", (update.effective_user.id, " ".join(context.args)))
        db.commit()
    await update.effective_message.reply_text("✅ မှတ်စုသိမ်းပြီးပါပြီ။")

async def mynotes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        rows = db.execute("SELECT note_text FROM notes WHERE user_id = ?", (update.effective_user.id,)).fetchall()
    await update.effective_message.reply_text("\n".join([r[0] for r in rows]) or "📭 မှတ်စုမရှိပါ။")

async def todo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        db.execute("INSERT INTO todos (user_id, task_text) VALUES (?, ?)", (update.effective_user.id, " ".join(context.args)))
        db.commit()
    await update.effective_message.reply_text("✅ ToDo ထည့်ပြီးပါပြီ။")

async def mytodos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        rows = db.execute("SELECT task_text FROM todos WHERE user_id = ?", (update.effective_user.id,)).fetchall()
    await update.effective_message.reply_text("\n".join([r[0] for r in rows]) or "📭 ToDo မရှိပါ။")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    message = update.effective_message
    if not message or not message.text or message.text.startswith("/"): return
    await context.bot.send_chat_action(chat_id=message.chat_id, action="typing")
    resp = await asyncio.to_thread(free_social_ai_chat, message.text.strip())
    await update.effective_message.reply_text(resp)

def main():
    if not TOKEN: raise RuntimeError("BOT_TOKEN မရှိပါ။")
    init_db()
    app = Application.builder().token(TOKEN).build()
    
    # ဤ Job က သတ်မှတ်ချိန်တိုင်း (ဥပမာ- ၁ နာရီတစ်ကြိမ်) သတင်းအသစ်ကို Channel ထဲသို့ အလိုအလျောက် ပို့ပေးမည်
    if app.job_queue:
        app.job_queue.run_repeating(auto_news_broadcast_job, interval=3600, first=10)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("news", news_command))
    app.add_handler(CommandHandler("weather", weather_command))
    app.add_handler(CommandHandler("rate", rate_command))
    app.add_handler(CommandHandler("tr", translate_command))
    app.add_handler(CommandHandler("define", define_command))
    app.add_handler(CommandHandler("quote", quote_command))
    app.add_handler(CommandHandler("time", time_command))
    app.add_handler(CommandHandler("bmi", bmi_command))
    app.add_handler(CommandHandler("water", water_command))
    app.add_handler(CommandHandler("conv", convert_command))
    app.add_handler(CommandHandler("password", password_command))
    app.add_handler(CommandHandler("qr", qr_command))
    app.add_handler(CommandHandler("note", note_command))
    app.add_handler(CommandHandler("mynotes", mynotes_command))
    app.add_handler(CommandHandler("todo", todo_command))
    app.add_handler(CommandHandler("mytodos", mytodos_command))
    app.add_handler(CallbackQueryHandler(check_channel_join_callback, pattern="^check_channel_join$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()