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
GAME_CHANNEL_ID = os.getenv("GAME_CHANNEL_ID", "").strip()

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("ck_helpbot")

HEADERS = {"User-Agent": "CkHelpBot/1.0"}
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

def get_json(url, params=None):
    try:
        res = requests.get(url, params=params, headers=HEADERS, timeout=HTTP_TIMEOUT)
        return res.json() if res.status_code == 200 else None
    except:
        return None

def translate_text(text, target_lang="my"):
    if not text: return ""
    data = get_json("https://translate.googleapis.com/translate_a/single", {"client": "gtx", "sl": "auto", "tl": target_lang, "dt": "t", "q": str(text)[:3500]})
    try:
        if data and isinstance(data, list):
            return "".join(part[0] for part in data[0] if part and part[0])
    except:
        pass
    return text

def smart_ai_chat(prompt):
    """API Key မလိုဘဲ အခမဲ့ အသုံးပြုနိုင်သော စမတ်ကျသည့် စကားပြောစနစ်"""
    prompt_lower = prompt.lower()
    
    # နှုတ်ဆက်စကားများအတွက်
    if any(word in prompt_lower for word in ["မင်္ဂလာပါ", "hello", "hi", "hey"]):
        return "မင်္ဂလာပါရှင့်။ Ck_helpbot မှ ကြိုဆိုပါတယ်။ ယနေ့ ဘယ်လိုအကူအညီပေးရမလဲဗျ။"
    
    if any(word in prompt_lower for word in ["နေကောင်းလား", "how are you"]):
        return "ကျေးဇူးတင်ပါတယ်၊ ကျွန်တော် နေကောင်းပါတယ်။ သင်ရော နေကောင်းရဲ့လားရှင့်။"

    # Wikipedia ကို အသုံးပြု၍ အချက်အလက်ရှာဖွေပြီး မြန်မာလို ဘာသာပြန်ဆိုပေးခြင်း
    summary = get_json("https://en.wikipedia.org/api/rest_v1/page/summary/" + quote(prompt.replace(" ", "_"), safe=""))
    if isinstance(summary, dict) and summary.get("extract"):
        return translate_text(summary.get("extract"), "my")
    
    # အကယ်၍ အထက်ပါတို့နှင့် မကိုက်ညီပါက အထွေထွေတုံ့ပြန်ချက်ပေးရန်
    return translate_text(f"I understand you are asking about '{prompt}'. Let me know how else I can assist you with this!", "my")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("🤖 **Ck_helpbot (Smart AI Version)**\n\nမင်္ဂလာပါ! မည်သည့်စာသားကိုမဆို မေးမြန်းနိုင်ပါပြီ။ Bot က လူတစ်ယောက်လို တိုက်ရိုက် ဖြေကြားပေးပါမည်။")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message or not message.text: return
    query = message.text.strip()
    if query.startswith("/"): return

    await context.bot.send_chat_action(chat_id=message.chat_id, action="typing")
    response_text = await asyncio.to_thread(smart_ai_chat, query)
    await message.reply_text(response_text)

def main():
    if not TOKEN: raise RuntimeError("BOT_TOKEN မရှိပါ။")
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
