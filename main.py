import os
import re
import sqlite3
import logging
import asyncio
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
        db.commit()

def translate_text(text, target_lang="my"):
    if not text: return ""
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {"client": "gtx", "sl": "auto", "tl": target_lang, "dt": "t", "q": str(text)[:3500]}
        response = requests.get(url, params=params, headers=HEADERS, timeout=HTTP_TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            if data and isinstance(data, list):
                return "".join(part[0] for part in data[0] if part and part[0])
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

def smart_ai_chat(prompt):
    """မေးသမျှကို မြန်မာလို အဓိပ္ပာယ်ရှိရှိ ပြန်ပေးမည့် AI စနစ်"""
    prompt_lower = prompt.lower()
    if any(w in prompt_lower for w in ["မင်္ဂလာပါ", "hello", "hi", "ောင်ရိုး"]):
        return "မင်္ဂလာပါရှင့်။ Ck_helpbot မှ ကြိုဆိုပါတယ်။ ယနေ့ ဘယ်လိုအကူအညီပေးရမလဲဗျ။"
    if "နေကောင်းလား" in prompt_lower or "how are you" in prompt_lower:
        return "ကျေးဇူးတင်ပါတယ်၊ ကျွန်တော် နေကောင်းပါတယ်။ သင်ရော နေကောင်းရဲ့လားရှင့်။"
    
    # Wikipedia မှ ရှာဖွေပြီး မြန်မာလို ပြန်ဆိုပေးခြင်း
    try:
        wiki_res = requests.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(prompt.replace(' ', '_'))}", timeout=HTTP_TIMEOUT).json()
        if isinstance(wiki_res, dict) and wiki_res.get("extract"):
            return translate_text(wiki_res.get("extract"), "my")
    except:
        pass
    
    # အထွေထွေ မေးခွန်းများအတွက် မြန်မာလို အလိုအလျောက် ဘာသာပြန်ဖြေကြားပေးခြင်း
    fallback_reply = f"မေးမြန်းချက် '{prompt}' နှင့် ပတ်သက်ပြီး လက်ရှိတွင် ဤအချက်အလက်ကို ရရှိထားပါသည်။ လိုအပ်သည်များကို ထပ်မံမေးမြန်းနိုင်ပါသည်။"
    return translate_text(fallback_reply, "my")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "🤖 **Ck_helpbot (Utility & Chat Version)** မှ ကြိုဆိုပါတယ်။\n\n"
        "💬 မည်သည့်စာသားကိုမဆို ရိုက်ပို့၍ ဆွေးနွေးမေးမြန်းနိုင်ပါပြီ။\n\n"
        "🛠️ **အသုံးဝင်သော အမိန့်ခေါ်ဆိုမှုများ:**\n"
        "🌤️ `/weather မြို့နာမည်` - ရာသီဥတုကြည့်ရန်\n"
        "💱 `/rate` - နိုင်ငံခြားငွေလဲနှုန်းများ\n"
        "🔤 `/tr စာသား` (သို့) `/tr en မင်္ဂလာပါ` - ဘာသာပြန်ရန်\n"
        "⏰ `/time` - လက်ရှိ အချိန်နှင့် ရက်စွဲ\n"
        "⚖️ `/bmi အရပ် ကိုယ်အလေးချိန်` - BMI တွက်ရန်\n"
        "📱 `/qr စာသား` - QR Code ထုတ်ရန်\n"
        "📝 `/note မှတ်စု` - မှတ်စုသိမ်းရန်\n"
        "📋 `/mynotes` - မှတ်စုများကြည့်ရန်"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("📖 အကူအညီအတွက် /start ကိုနှိပ်ပါ။")

async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args).strip()
    if not query:
        await update.effective_message.reply_text("အသုံးပြုပုံ: `/weather Yangon`")
        return
    res = await asyncio.to_thread(get_weather, query)
    await update.effective_message.reply_text(res or "❌ ရာသီဥတု အချက်အလက် ရှာမတွေ့ပါ။")

async def rate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    res = await asyncio.to_thread(get_exchange_rates)
    await update.effective_message.reply_text(res or "❌ ငွေလဲနှုန်း ရယူမရပါ။")

async def translate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.effective_message.reply_text("အသုံးပြုပုံ:\n• မြန်မာလိုပြန်ရန်: `/tr welcome`\n• အခြားဘာသာပြန်ရန်: `/tr en မင်္ဂလာပါ`")
        return
    
    if len(args) > 1 and len(args[0]) == 2:
        target_lang = args[0]
        text_to_translate = " ".join(args[1:])
    else:
        target_lang = "my"
        text_to_translate = " ".join(args)

    res = await asyncio.to_thread(translate_text, text_to_translate, target_lang)
    await update.effective_message.reply_text(f"🔤 **ဘာသာပြန်ဆိုချက် ({target_lang}):**\n\n{res}")

async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now().strftime("%Y-%m-%d | %H:%M:%S")
    await update.effective_message.reply_text(f"⏰ **လက်ရှိ အချိန်နှင့် ရက်စွဲ:**\n\n📅 {now}")

async def bmi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.effective_message.reply_text("အသုံးပြုပုံ: `/bmi အရပ်(စင်တီမီတာ) ကိုယ်အလေးချိန်(ကီလို)`\nဥပမာ: `/bmi 170 65`")
        return
    try:
        h, w = float(args[0]) / 100, float(args[1])
        bmi = w / (h ** 2)
        status = "ပုံမှန်ဖြစ်ပါသည်" if 18.5 <= bmi < 25 else ("ကိုယ်အလေးချိန် နည်းနေပါသည်" if bmi < 18.5 else "ကိုယ်အလေးချိန် ပိုနေပါသည်")
        await update.effective_message.reply_text(f"⚖️ **BMI:** {bmi:.2f}\n• အခြေအနေ: {status}")
    except:
        await update.effective_message.reply_text("❌ ဂဏန်းများကို မှန်ကန်စွာ ထည့်သွင်းပါ။")

async def qr_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args).strip()
    if not text:
        await update.effective_message.reply_text("အသုံးပြုပုံ: `/qr စာသား သို့မဟုတ် လင့်ခ်`")
        return
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={quote(text)}"
    await update.effective_photo(photo=qr_url, caption=f"📱 QR Code: {text[:100]}")

async def note_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = " ".join(context.args).strip()
    if not text:
        await update.effective_message.reply_text("အသုံးပြုပုံ: `/note မှတ်သားလိုသည့်စာသား`")
        return
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        db.execute("INSERT INTO notes (user_id, note_text) VALUES (?, ?)", (user.id, text))
        db.commit()
    await update.effective_message.reply_text("✅ မှတ်စုကို သိမ်းဆည်းပြီးပါပြီ။")

async def mynotes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        rows = db.execute("SELECT note_text FROM notes WHERE user_id = ? ORDER BY id DESC LIMIT 10", (user.id,)).fetchall()
    if not rows:
        await update.effective_message.reply_text("📭 မှတ်စုများ မရှိသေးပါ။")
        return
    lines = ["📝 **သင်၏ မှတ်စုများ:**\n"] + [f"{i}. {r[0]}" for i, r in enumerate(rows, 1)]
    await update.effective_message.reply_text("\n".join(lines))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message or not message.text: return
    query = message.text.strip()
    if not query or query.startswith("/"): return

    await context.bot.send_chat_action(chat_id=message.chat_id, action="typing")
    resp = await asyncio.to_thread(smart_ai_chat, query)
    await update.effective_message.reply_text(f"🤖 **Bot Assistant:**\n\n{resp}")

def main():
    if not TOKEN: raise RuntimeError("BOT_TOKEN မရှိပါ။")
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("weather", weather_command))
    app.add_handler(CommandHandler("rate", rate_command))
    app.add_handler(CommandHandler("tr", translate_command))
    app.add_handler(CommandHandler("time", time_command))
    app.add_handler(CommandHandler("bmi", bmi_command))
    app.add_handler(CommandHandler("qr", qr_command))
    app.add_handler(CommandHandler("note", note_command))
    app.add_handler(CommandHandler("mynotes", mynotes_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
