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
                        if d.get("example"):
                            result_text += f"  *(Ex: {d.get('example')})*\n"
                return result_text
    except:
        pass
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


# ---------------------- Command Handlers ------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    await update.effective_message.reply_text(
        "🤖 **Ck_helpbot (Ultimate Daily Utility Version)** မှ ကြိုဆိုပါတယ်။\n\n"
        "💬 မည်သည့်စာသားကိုမဆို ရိုက်ပို့၍ ဖော်ရွေစွာ စကားပြောဆိုနိုင်ပါပြီ။\n\n"
        "🛠️ **နေ့စဉ်သုံး အမိန့်ခေါ်ဆိုမှုများ:**\n"
        "🌤️ `/weather မြို့နာမည်` - ရာသီဥတုကြည့်ရန်\n"
        "💱 `/rate` - နိုင်ငံခြားငွေလဲနှုန်းများ\n"
        "🔤 `/tr စာသား` (သို့) `/tr en စာသား` - ဘာသာပြန်ရန်\n"
        "📖 `/define စကားလုံး` - အင်္ဂလိပ်အဘိဓာန် ရှာရန်\n"
        "💡 `/quote` - နေ့စဉ် အားပေးစကားများ\n"
        "⏰ `/time` - လက်ရှိ အချိန်နှင့် ရက်စွဲ\n"
        "⚖️ `/bmi အရပ် ကိုယ်အလေးချိန်` - BMI တွက်ရန်\n"
        "💧 `/water ကိုယ်အလေးချိန်` - ရေဓာတ်သောက်ရန်ပမာဏ\n"
        "🔄 `/conv kg lb 50` - ယူနစ်ပြောင်းရန်\n"
        "🔑 `/password` - စကားဝှက်ဖန်တီးရန်\n"
        "📱 `/qr စာသား` - QR Code ထုတ်ရန်\n"
        "📝 `/note မှတ်စု` - မှတ်စုသိမ်းရန်\n"
        "📋 `/mynotes` - မှတ်စုများကြည့်ရန်\n"
        "✅ `/todo လုပ်စရာ` - လုပ်စရာစာရင်းထည့်ရန်\n"
        "📌 `/mytodos` - လုပ်စရာစာရင်းများကြည့်ရန်"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    await update.effective_message.reply_text("📖 အကူအညီအတွက် /start ကိုနှိပ်ပါ။")

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

async def define_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    args = context.args
    if not args:
        await update.effective_message.reply_text("အသုံးပြုပုံ: `/define success`")
        return
    word = args[0].strip()
    res = await asyncio.to_thread(get_dictionary_definition, word)
    if res:
        await update.effective_message.reply_text(res)
    else:
        await update.effective_message.reply_text(f"❌ '{word}' ၏ အဓိပ္ပာယ်ကို ရှာမတွေ့ပါ။")

async def quote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    try:
        q_res = requests.get("https://api.quotable.io/random", timeout=HTTP_TIMEOUT).json()
        content = q_res.get("content", "Keep going, you are doing great!")
        author = q_res.get("author", "Unknown")
        translated_q = await asyncio.to_thread(translate_text, f'"{content}" - {author}', "my")
        await update.effective_message.reply_text(f"💡 **နေ့စဉ် ခွန်အားဖြစ်စေသော စကားစု:**\n\n{translated_q}")
    except:
        await update.effective_message.reply_text("💡 **နေ့စဉ် စကားစု:** ယုံကြည်မှုအပြည့်နဲ့ ရှေ့ဆက်ပါ။")

async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    now = datetime.now().strftime("%Y-%m-%d | %H:%M:%S")
    await update.effective_message.reply_text(f"⏰ **လက်ရှိ အချိန်နှင့် ရက်စွဲ:**\n\n📅 {now}")

async def bmi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
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

async def water_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    args = context.args
    if not args:
        await update.effective_message.reply_text("အသုံးပြုပုံ: `/water ကိုယ်အလေးချိန်(ကီလို)`\nဥပမာ: `/water 60`")
        return
    try:
        weight = float(args[0])
        water_ml = weight * 35
        water_liters = water_ml / 1000
        await update.effective_message.reply_text(f"💧 **ရေဓာတ်သောက်သုံးရန် ညွှန်ကြားချက်**\n\n• ကိုယ်အလေးချိန်: {weight} kg\n• တစ်နေ့တာ သောက်သင့်သော ရေပမာဏ: **{water_liters:.2f} လီတာ**")
    except:
        await update.effective_message.reply_text("❌ ကိုယ်အလေးချိန်ကို ဂဏန်းဖြင့် မှန်ကန်စွာ ထည့်ပါ။")

async def convert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    args = context.args
    if len(args) < 3:
        await update.effective_message.reply_text("အသုံးပြုပုံ: `/conv ယူနစ်ဟောင်း ယူနစ်သစ် ပမာဏ`\nဥပမာ: `/conv kg lb 50`")
        return
    try:
        u_from, u_to, val = args[0].lower(), args[1].lower(), float(args[2])
        res = None
        if u_from == "kg" and u_to == "lb": res = val * 2.20462
        elif u_from == "lb" and u_to == "kg": res = val / 2.20462
        elif u_from == "c" and u_to == "f": res = (val * 9/5) + 32
        elif u_from == "f" and u_to == "c": res = (val - 32) * 5/9
        
        if res is not None:
            await update.effective_message.reply_text(f"🔄 **ယူနစ်ပြောင်းလဲမှု:**\n\n{val} {u_from.upper()} = **{res:.2f} {u_to.upper()}**")
        else:
            await update.effective_message.reply_text("❌ kg/lb နှင့် c/f များကိုသာ တိုက်ရိုက်ပြောင်းပေးနိုင်ပါသည်။")
    except:
        await update.effective_message.reply_text("❌ အချက်အလက်များ မှားယွင်းနေပါသည်။")

async def password_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    pwd = "".join(random.choice(chars) for _ in range(12))
    await update.effective_message.reply_text(f"🔑 **လုံခြုံသော စကားဝှက်အသစ်:**\n\n`{pwd}`")

async def qr_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    text = " ".join(context.args).strip()
    if not text:
        await update.effective_message.reply_text("အသုံးပြုပုံ: `/qr စာသား သို့မဟုတ် လင့်ခ်`")
        return
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={quote(text)}"
    await update.effective_message.reply_photo(photo=qr_url, caption=f"📱 QR Code: {text[:100]}")

async def note_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
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
    if not await require_channel_join(update, context):
        return
    user = update.effective_user
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        rows = db.execute("SELECT note_text FROM notes WHERE user_id = ? ORDER BY id DESC LIMIT 10", (user.id,)).fetchall()
    if not rows:
        await update.effective_message.reply_text("📭 မှတ်စုများ မရှိသေးပါ။")
        return
    lines = ["📝 **သင်၏ မှတ်စုများ:**\n"] + [f"{i}. {r[0]}" for i, r in enumerate(rows, 1)]
    await update.effective_message.reply_text("\n".join(lines))

async def todo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    user = update.effective_user
    text = " ".join(context.args).strip()
    if not text:
        await update.effective_message.reply_text("အသုံးပြုပုံ: `/todo လုပ်စရာရှိသည့်အလုပ်`")
        return
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        db.execute("INSERT INTO todos (user_id, task_text) VALUES (?, ?)", (user.id, text))
        db.commit()
    await update.effective_message.reply_text("✅ လုပ်စရာစာရင်းထဲသို့ ထည့်သွင်းပြီးပါပြီ။")

async def mytodos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    user = update.effective_user
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        rows = db.execute("SELECT task_text FROM todos WHERE user_id = ? ORDER BY id DESC LIMIT 10", (user.id,)).fetchall()
    if not rows:
        await update.effective_message.reply_text("📭 လုပ်စရာစာရင်းများ မရှိသေးပါ။")
        return
    lines = ["✅ **သင်၏ လုပ်စရာစာရင်းများ (ToDo):**\n"] + [f"• {r[0]}" for r in rows]
    await update.effective_message.reply_text("\n".join(lines))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    message = update.effective_message
    if not message or not message.text: return
    query = message.text.strip()
    if not query or query.startswith("/"): return

    await context.bot.send_chat_action(chat_id=message.chat_id, action="typing")
    resp = await asyncio.to_thread(free_social_ai_chat, query)
    await update.effective_message.reply_text(resp)

def main():
    if not TOKEN: raise RuntimeError("BOT_TOKEN မရှိပါ။")
    init_db()
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
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
