import os
import re
import sqlite3
import logging
import asyncio
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

# =========================================================
# Configuration (set these in Railway -> Variables)
# =========================================================

TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS = {
    int(value.strip())
    for value in os.getenv("ADMIN_IDS", "").split(",")
    if value.strip().isdigit()
}
DB_PATH = os.getenv("DB_PATH", "movies_bot.db")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "").strip()
CHANNEL_URL = os.getenv("CHANNEL_URL", "").strip()
GAME_CHANNEL_ID = os.getenv("GAME_CHANNEL_ID", "").strip()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("ck_helpbot")

HEADERS = {"User-Agent": "CkHelpBot/1.0 (Telegram daily utility bot)"}
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
        db.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                note_text TEXT NOT NULL
            )
        """)
        db.commit()


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


# ---------------------- Daily Utilities ---------------------

def get_weather(city_name):
    """Open-Meteo API ဖြင့် မြို့အလိုက် ရာသီဥတုရှာဖွေရန်"""
    geo_data = get_json("https://geocoding-api.open-meteo.com/v1/search", {"name": city_name, "count": 1})
    if not geo_data or not geo_data.get("results"):
        return None
    
    loc = geo_data["results"][0]
    lat, lon = loc["latitude"], loc["longitude"]
    name = loc.get("name", city_name)
    country = loc.get("country", "")

    weather_data = get_json("https://api.open-meteo.com/v1/forecast", {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m"
    })
    
    if not weather_data or "current" not in weather_data:
        return None

    curr = weather_data["current"]
    return {
        "city": name,
        "country": country,
        "temp": curr.get("temperature_2m"),
        "feels_like": curr.get("apparent_temperature"),
        "humidity": curr.get("relative_humidity_2m"),
        "wind": curr.get("wind_speed_10m")
    }


def get_exchange_rates():
    """ငွေလဲနှုန်းများ ကြည့်ရန်"""
    data = get_json("https://open.er-api.com/v6/latest/USD")
    if not data or "rates" not in data:
        return None
    rates = data["rates"]
    return {
        "EUR": rates.get("EUR"),
        "THB": rates.get("THB"),
        "SGD": rates.get("SGD"),
        "MYR": rates.get("MYR"),
        "JPY": rates.get("JPY")
    }


# ----------------------- Country lookup --------------------

def get_country(query):
    query = query.strip()
    if not query:
        return None
    fields = "name,capital,region,subregion,population,languages,currencies,cca2,cca3"
    data = get_json(f"https://restcountries.com/v3.1/name/{quote(query, safe='')}", {"fullText": "true", "fields": fields})
    if not isinstance(data, list) or not data:
        data = get_json(f"https://restcountries.com/v3.1/name/{quote(query, safe='')}", {"fields": fields})
    if not isinstance(data, list) or not data:
        return None
    if len(data) == 1:
        return data[0]
    return None


def format_country(country):
    name_data = country.get("name") or {}
    common_name = name_data.get("common", "Unknown")
    official_name = name_data.get("official", common_name)
    capital = country.get("capital") or []
    languages = country.get("languages") or {}
    currencies = country.get("currencies") or {}
    currency_text = ", ".join(f"{item.get('name', code)}" for code, item in currencies.items())
    
    raw = (
        f"Country: {common_name}\nOfficial name: {official_name}\n"
        f"Capital: {', '.join(capital) if capital else 'Not available'}\n"
        f"Region: {country.get('region', 'Not available')}\n"
        f"Population: {country.get('population', 0):,}\n"
        f"Languages: {', '.join(languages.values()) if languages else 'Not available'}\n"
        f"Currencies: {currency_text or 'Not available'}"
    )
    return common_name, raw


# --------------------- Wikipedia search --------------------

def wikipedia_search(search_query, limit=5):
    data = get_json("https://en.wikipedia.org/w/api.php", {
        "action": "query", "list": "search", "srsearch": search_query,
        "srlimit": limit, "format": "json", "utf8": 1,
    })
    return data.get("query", {}).get("search", []) if data else []


def search_person_or_hero(query):
    query = query.strip()
    if not query:
        return None
    for language in ("my", "en"):
        base = f"https://{language}.wikipedia.org"
        exact = get_json(base + "/api/rest_v1/page/summary/" + quote(query.replace(" ", "_"), safe=""))
        if isinstance(exact, dict) and exact.get("extract") and exact.get("type") != "disambiguation":
            return exact
    return None


async def send_long_text(message, text, limit=3800):
    text = text or ""
    while text:
        if len(text) <= limit:
            await message.reply_text(text)
            break
        split_at = text.rfind("\n", 0, limit)
        if split_at < limit // 2:
            split_at = limit
        await message.reply_text(text[:split_at])
        text = text[split_at:].lstrip()


# ---------------------- Channel join gate ------------------

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
    
    notice = "🔒 ဘော့ကို ဆက်အသုံးပြုရန် အောက်ပါ Channel ကို အရင် Join လုပ်ပါ။"
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
            await query.message.reply_text("🎉 အတည်ပြုပြီးပါပြီ။ /start ကို နှိပ်ပါ။")
    else:
        await query.answer("Channel ကို မတွေ့ရသေးပါ။", show_alert=True)


# -------------------------- Commands -----------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    await update.effective_message.reply_text(
        "🤖 **Ck_helpbot (Daily Utility Version)** မှ ကြိုဆိုပါတယ်။\n\n"
        "📅 **နေ့စဉ်သုံး စနစ်များ:**\n"
        "🌤️ `/weather မြို့နာမည်` - ရာသီဥတုကြည့်ရန် (ဥပမာ: `/weather Yangon`)\n"
        "💱 `/rate` - နိုင်ငံခြားငွေလဲနှုန်းများ ကြည့်ရန်\n"
        "📝 `/note မှတ်စုစာသား` - ကိုယ်ပိုင်မှတ်စု သိမ်းရန်\n"
        "📋 `/mynotes` - သိမ်းထားသော မှတ်စုများကြည့်ရန်\n"
        "🌍 နိုင်ငံအမည် သို့မဟုတ် လူပုဂ္ဂိုလ်အမည်ရိုက်၍လည်း ရှာဖွေနိုင်ပါသည်။\n"
        "🎬 ရုပ်ရှင်နှင့် 🎮 ဂိမ်းရှာဖွေရန်လည်း အသုံးပြုနိုင်ပါသည်။"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    await update.effective_message.reply_text(
        "📖 **အသုံးပြုနည်းလမ်းညွှန်**\n\n"
        "• **ရာသီဥတု:** `/weather Yangon` သို့မဟုတ် `/weather Mandalay` ဟုသုံးပါ။\n"
        "• **ငွေလဲနှုန်း:** `/rate` ဖြင့် အမေရိကန်ဒေါ်လာနှင့် အခြားငွေကြေးနှုန်းထားများကို ကြည့်ပါ။\n"
        "• **ကိုယ်ပိုင်မှတ်စု:** `/note မနက်ဖြန် လုပ်စရာရှိတာလေးများ` ဟု ပို့၍ မှတ်သားပါ။\n"
        "• **နိုင်ငံအချက်အလက်:** နိုင်ငံအမည်ကို အင်္ဂလိပ်လို ရိုက်ထည့်ပါ။\n"
        "• **ရုပ်ရှင်နှင့်ဂိမ်း:** ရုပ်ရှင်အမည် သို့မဟုတ် `/game` ဖြင့် ရှာပါ။"
    )


async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    message = update.effective_message
    query = " ".join(context.args).strip()
    if not query:
        await message.reply_text("ကျေးဇူးပြု၍ မြို့အမည်ထည့်ပါ။ ဥပမာ: `/weather Yangon`")
        return
    
    w = await asyncio.to_thread(get_weather, query)
    if not w:
        await message.reply_text("❌ အဆိုပါမြို့၏ ရာသီဥတုအချက်အလက်ကို ရှာမတွေ့ပါ။")
        return
    
    text = (
        f"🌤️ **{w['city']}, {w['country']} ရာသီဥတု**\n\n"
        f"🌡️ အပူချိန်: {w['temp']}°C (ခံစားရ気温: {w['feels_like']}°C)\n"
        f"💧 စိုထိုင်းဆ: {w['humidity']}%\n"
        f"🌬️ လေတိုက်နှုန်း: {w['wind']} km/h"
    )
    await message.reply_text(text)


async def rate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    rates = await asyncio.to_thread(get_exchange_rates)
    if not rates:
        await message.reply_text("❌ ငွေလဲနှုန်း အချက်အလက်များကို ရယူ၍မရပါ။")
        return
    
    text = (
        "💱 **US Dollar (1 USD) လဲလှယ်နှုန်းများ**\n\n"
        f"💶 ယူရို (EUR): {rates.get('EUR')}\n"
        f"🇹🇭 ထိုင်းဘတ် (THB): {rates.get('THB')}\n"
        f"🇸🇬 စင်ကာပူဒေါ်လာ (SGD): {rates.get('SGD')}\n"
        f"🇲🇾 မလေးရှားရင်းဂစ် (MYR): {rates.get('MYR')}\n"
        f"🇯🇵 ဂျပန်ယန်း (JPY): {rates.get('JPY')}"
    )
    await update.effective_message.reply_text(text)


async def note_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    message = update.effective_message
    user = update.effective_user
    text = " ".join(context.args).strip()
    if not text:
        await message.reply_text("အသုံးပြုပုံ: `/note မှတ်သားလိုသည့်စာသား`")
        return
    
    try:
        with sqlite3.connect(DB_PATH, timeout=30) as db:
            db.execute("INSERT INTO notes (user_id, note_text) VALUES (?, ?)", (user.id, text))
            db.commit()
        await message.reply_text("✅ မှတ်စုကို သိမ်းဆည်းပြီးပါပြီ။ `/mynotes` ဖြင့် ပြန်ကြည့်နိုင်ပါသည်။")
    except sqlite3.Error:
        await message.reply_text("❌ မှတ်စုသိမ်းဆည်းရာတွင် အမှားအယွင်းရှိခဲ့ပါသည်။")


async def mynotes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    message = update.effective_message
    user = update.effective_user
    
    try:
        with sqlite3.connect(DB_PATH, timeout=30) as db:
            cursor = db.execute("SELECT id, note_text FROM notes WHERE user_id = ? ORDER BY id DESC LIMIT 10", (user.id,))
            rows = cursor.fetchall()
        if not rows:
            await message.reply_text("📭 သိမ်းဆည်းထားသော မှတ်စုများ မရှိသေးပါ။")
            return
        
        lines = ["📝 **သင်၏ မှတ်စုများ:**\n"]
        for idx, (note_id, text) in enumerate(rows, 1):
            lines.append(f"{idx}. {text}")
        await message.reply_text("\n".join(lines))
    except sqlite3.Error:
        await message.reply_text("❌ မှတ်စုများကို ဖတ်ရှုမရပါ။")


# ----------------------- Main message handler -----------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    message = update.effective_message
    if not message or not message.text:
        return

    query = message.text.strip()
    if not query or query.startswith("/"):
        return

    # နိုင်ငံအမည် ရှာရန်
    country = await asyncio.to_thread(get_country, query)
    if country:
        _, raw = format_country(country)
        translated = await asyncio.to_thread(translate_to_burmese, raw)
        await message.reply_text(f"🌍 **နိုင်ငံအချက်အလက်**\n\n{translated}")
        return

    # Wikipedia လူပုဂ္ဂိုလ်/အကြောင်းအရာ ရှာရန်
    data = await asyncio.to_thread(search_person_or_hero, query)
    if data and data.get("extract"):
        translated = await asyncio.to_thread(translate_to_burmese, data["extract"][:2500])
        await message.reply_text(f"📖 **{data.get('title', query)}**\n\n{translated}")
        return

    await message.reply_text("❓ ဤစကားစုအတွက် အချက်အလက် မတွေ့ပါ။ ရာသီဥတုကြည့်ရန် `/weather` သို့မဟုတ် အကူအညီအတွက် `/help` ကိုသုံးပါ။")


def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN မရှိပါ။ Railway Variables တွင် ထည့်ပါ။")

    init_db()
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("weather", weather_command))
    app.add_handler(CommandHandler("rate", rate_command))
    app.add_handler(CommandHandler("note", note_command))
    app.add_handler(CommandHandler("mynotes", mynotes_command))
    app.add_handler(CallbackQueryHandler(check_channel_join_callback, pattern="^check_channel_join$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Ck_helpbot is running with daily utility features")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
