import asyncio
import logging
import os
import secrets
import sqlite3
import string
import xml.etree.ElementTree as ET
from datetime import datetime, time as dt_time
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

import requests
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# =========================
# Configuration (Railway Variables)
# =========================
TOKEN = os.getenv("BOT_TOKEN", os.getenv("TOKEN", "")).strip()
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "").strip()
CHANNEL_URL = os.getenv("CHANNEL_URL", "").strip()
NEWS_CHANNEL_ID = os.getenv("NEWS_CHANNEL_ID", CHANNEL_USERNAME).strip()
TIMEZONE = os.getenv("TIMEZONE", "Asia/Yangon").strip()
DAILY_NEWS_HOUR = int(os.getenv("DAILY_NEWS_HOUR", "7"))
BREAKING_INTERVAL_MINUTES = max(5, int(os.getenv("BREAKING_INTERVAL_MINUTES", "15")))
DB_PATH = os.getenv("DB_PATH", "ck_helpbot.db")
REQUEST_TIMEOUT = 15

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("CkHelpBot")


# =========================
# Database
# =========================
def init_db():
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS subscribers (
                user_id INTEGER PRIMARY KEY
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS seen_news (
                url TEXT PRIMARY KEY,
                sent_at TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                note TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                task TEXT NOT NULL,
                done INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        db.commit()


def save_subscriber(user_id: int):
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        db.execute("INSERT OR IGNORE INTO subscribers (user_id) VALUES (?)", (user_id,))
        db.commit()


def subscriber_ids():
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        return [row[0] for row in db.execute("SELECT user_id FROM subscribers").fetchall()]


def news_was_sent(url: str) -> bool:
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        return db.execute("SELECT 1 FROM seen_news WHERE url = ?", (url,)).fetchone() is not None


def mark_news_sent(url: str):
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        db.execute(
            "INSERT OR IGNORE INTO seen_news (url, sent_at) VALUES (?, ?)",
            (url, datetime.now(ZoneInfo(TIMEZONE)).isoformat()),
        )
        db.commit()


# =========================
# Channel membership check
# =========================
async def is_joined(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not CHANNEL_USERNAME:
        return True
    user = update.effective_user
    if not user:
        return False
    try:
        member = await context.bot.get_chat_member(CHANNEL_USERNAME, user.id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        logger.warning("Could not check channel membership.", exc_info=True)
        return False


async def require_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if await is_joined(update, context):
        return True
    url = CHANNEL_URL or (f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}" if CHANNEL_USERNAME.startswith("@") else "")
    message = "ဒီ Bot ကို အသုံးပြုရန် Channel ကို အရင် Join လုပ်ပေးပါ။"
    if url:
        message += f"\n\nJoin လုပ်ရန်: {url}"
    message += "\nJoin ပြီးရင် /start ကို ထပ်နှိပ်ပါ။"
    await update.effective_message.reply_text(message)
    return False


# =========================
# News: Google News RSS
# =========================
def fetch_news(query: str, hl="en-US", gl="US", ceid="US:en", limit=5):
    rss_url = (
        "https://news.google.com/rss/search?q="
        + quote_plus(query)
        + f"&hl={hl}&gl={gl}&ceid={ceid}"
    )
    response = requests.get(
        rss_url,
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": "Mozilla/5.0 CkHelpBot/1.0"},
    )
    response.raise_for_status()
    root = ET.fromstring(response.content)
    items = []
    for item in root.findall(".//item")[:limit]:
        title = (item.findtext("title") or "Untitled").strip()
        link = (item.findtext("link") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        source = item.find("source")
        source_name = source.text.strip() if source is not None and source.text else "Google News"
        if link:
            items.append({
                "title": title,
                "link": link,
                "date": pub_date,
                "source": source_name,
            })
    return items


def format_news(items, heading):
    if not items:
        return f"{heading}\n\nလောလောဆယ် သတင်းမတွေ့ပါ။ နောက်မှ ထပ်စမ်းကြည့်ပါ။"
    lines = [heading, ""]
    for i, item in enumerate(items, 1):
        lines.append(f"{i}. {item['title']}")
        lines.append(f"📰 {item['source']}")
        if item["date"]:
            lines.append(f"🕒 {item['date']}")
        lines.append(f"🔗 {item['link']}")
        lines.append("")
    return "\n".join(lines).strip()[:3900]


async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_join(update, context):
        return
    await update.effective_message.reply_text("သတင်းရှာနေပါတယ်...")
    try:
        myanmar, world = await asyncio.gather(
            asyncio.to_thread(fetch_news, "Myanmar OR Burma news", "en-US", "US", "US:en", 5),
            asyncio.to_thread(fetch_news, "world news", "en-US", "US", "US:en", 5),
        )
        await update.effective_message.reply_text(
            format_news(myanmar, "📰 🇲🇲 မြန်မာသတင်းများ"),
            disable_web_page_preview=True,
        )
        await update.effective_message.reply_text(
            format_news(world, "🌍 ကမ္ဘာ့သတင်းများ"),
            disable_web_page_preview=True,
        )
    except Exception:
        logger.exception("Manual news search failed")
        await update.effective_message.reply_text("သတင်းရယူရာမှာ အမှားဖြစ်နေပါတယ်။ နောက်မှ ထပ်စမ်းပါ။")


async def breaking_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_join(update, context):
        return
    await update.effective_message.reply_text("🚨 Breaking News ရှာနေပါတယ်...")
    try:
        myanmar, world = await asyncio.gather(
            asyncio.to_thread(fetch_news, "Myanmar breaking news when:1h", "en-US", "US", "US:en", 5),
            asyncio.to_thread(fetch_news, "world breaking news when:1h", "en-US", "US", "US:en", 5),
        )
        items = myanmar + world
        if not items:
            await update.effective_message.reply_text("လတ်တလော Breaking News မတွေ့ပါ။")
            return
        output = []
        for i, item in enumerate(items[:8], 1):
            output.append(
                f"{i}. {item['title']}\n"
                f"📰 {item['source']}\n"
                f"🕒 {item['date'] or 'အချိန်မဖော်ပြထားပါ'}\n"
                f"🔗 {item['link']}"
            )
        await update.effective_message.reply_text(
            "🚨 BREAKING NEWS\n\n" + "\n\n".join(output),
            disable_web_page_preview=True,
        )
    except Exception:
        logger.exception("Breaking news command failed")
        await update.effective_message.reply_text("Breaking News ရယူရာမှာ အမှားဖြစ်နေပါတယ်။")


async def broadcast_message(context: ContextTypes.DEFAULT_TYPE, message: str):
    # Send to all users who have started the bot and then to the channel.
    targets = subscriber_ids()
    if NEWS_CHANNEL_ID:
        targets.append(NEWS_CHANNEL_ID)

    for chat_id in targets:
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=message[:3900],
                disable_web_page_preview=True,
            )
        except Exception:
            logger.warning("Broadcast failed for chat_id=%s", chat_id, exc_info=True)


async def daily_news_job(context: ContextTypes.DEFAULT_TYPE):
    try:
        myanmar, world = await asyncio.gather(
            asyncio.to_thread(fetch_news, "Myanmar OR Burma news", "en-US", "US", "US:en", 5),
            asyncio.to_thread(fetch_news, "world news", "en-US", "US", "US:en", 5),
        )
        await broadcast_message(context, format_news(myanmar, "📰 🇲🇲 နေ့စဉ် မြန်မာသတင်းများ"))
        await broadcast_message(context, format_news(world, "🌍 နေ့စဉ် ကမ္ဘာ့သတင်းများ"))
        logger.info("Daily news broadcast completed")
    except Exception:
        logger.exception("Daily news broadcast failed")


async def breaking_news_job(context: ContextTypes.DEFAULT_TYPE):
    try:
        myanmar, world = await asyncio.gather(
            asyncio.to_thread(fetch_news, "Myanmar breaking news when:1h", "en-US", "US", "US:en", 5),
            asyncio.to_thread(fetch_news, "world breaking news when:1h", "en-US", "US", "US:en", 5),
        )
        candidates = []
        for category, items in (("🇲🇲 Myanmar", myanmar), ("🌍 World", world)):
            for item in items:
                if not news_was_sent(item["link"]):
                    candidates.append((category, item))

        for category, item in candidates[:5]:
            message = (
                f"🚨 BREAKING NEWS | {category}\n\n"
                f"{item['title']}\n\n"
                f"📰 Source: {item['source']}\n"
                f"🕒 {item['date'] or 'အချိန်မဖော်ပြထားပါ'}\n"
                f"🔗 {item['link']}"
            )
            await broadcast_message(context, message)
            mark_news_sent(item["link"])
        logger.info("Breaking news check completed: %s candidates", len(candidates))
    except Exception:
        logger.exception("Breaking news broadcast failed")


async def post_init(application: Application):
    if not NEWS_CHANNEL_ID:
        logger.warning("NEWS_CHANNEL_ID မသတ်မှတ်ထားပါ။ Channel auto-post မလုပ်နိုင်ပါ။")
    queue = application.job_queue
    if queue is None:
        logger.error("JobQueue မရပါ။ requirements.txt ကို စစ်ပါ။")
        return

    tz = ZoneInfo(TIMEZONE)
    queue.run_daily(
        daily_news_job,
        time=dt_time(hour=DAILY_NEWS_HOUR, minute=0, tzinfo=tz),
        name="daily_news",
    )
    queue.run_repeating(
        breaking_news_job,
        interval=BREAKING_INTERVAL_MINUTES * 60,
        first=60,
        name="breaking_news",
    )
    logger.info("Scheduler started: daily hour=%s, breaking interval=%s minutes",
                DAILY_NEWS_HOUR, BREAKING_INTERVAL_MINUTES)


# =========================
# Bot commands
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user:
        save_subscriber(user.id)

    if not await require_join(update, context):
        return

    await update.effective_message.reply_text(
        "မင်္ဂလာပါ။ Ck_helpbot မှ ကြိုဆိုပါတယ်။\n\n"
        "အသုံးပြုနိုင်တဲ့ Command များ:\n"
        "/news - မြန်မာနဲ့ ကမ္ဘာ့သတင်း\n"
        "/breaking - Breaking News\n"
        "/time - လက်ရှိအချိန်\n"
        "/quote - အားပေးစကား\n"
        "/password - Password ထုတ်ရန်\n"
        "/bmi အလေးချိန်_kg အရပ်_cm - BMI တွက်ရန်\n"
        "/convert တန်ဖိုး ယူနစ်မှ ယူနစ်သို့ - ယူနစ်ပြောင်းရန်\n"
        "/note စာသား - မှတ်စုသိမ်းရန်\n"
        "/notes - မှတ်စုများကြည့်ရန်\n"
        "/todo အလုပ် - လုပ်စရာထည့်ရန်\n"
        "/todos - လုပ်စရာများကြည့်ရန်\n\n"
        "နေ့စဉ်သတင်းနှင့် Breaking News များကို အလိုအလျောက် လက်ခံရရှိနိုင်ပါတယ်။"
    )


async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_join(update, context):
        return
    now = datetime.now(ZoneInfo(TIMEZONE)).strftime("%Y-%m-%d %H:%M:%S")
    await update.effective_message.reply_text(f"🕒 မြန်မာစံတော်ချိန်: {now}")


async def quote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_join(update, context):
        return
    quotes = [
        "မစွန့်လွှတ်သရွေ့ ရှုံးနိမ့်ခြင်း မဟုတ်ပါ။",
        "အောင်မြင်မှုဆိုတာ နေ့စဉ်ကြိုးစားမှုလေးတွေ စုပေါင်းထားတာပါ။",
        "ဒီနေ့ရဲ့ သေးငယ်တဲ့ခြေလှမ်းက မနက်ဖြန်ရဲ့ ကြီးမားတဲ့ပြောင်းလဲမှု ဖြစ်နိုင်ပါတယ်။",
        "ကိုယ့်အရှိန်နဲ့ကိုယ် ဆက်လျှောက်ပါ။ ရပ်မသွားဖို့က အရေးကြီးပါတယ်။",
    ]
    import random
    await update.effective_message.reply_text("✨ " + random.choice(quotes))


async def password_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_join(update, context):
        return
    length = 16
    if context.args:
        try:
            length = max(8, min(64, int(context.args[0])))
        except ValueError:
            pass
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    password = "".join(secrets.choice(alphabet) for _ in range(length))
    await update.effective_message.reply_text(f"🔐 Password ({length} characters):\n`{password}`", parse_mode="Markdown")


async def bmi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_join(update, context):
        return
    if len(context.args) < 2:
        await update.effective_message.reply_text("အသုံးပြုပုံ: /bmi အလေးချိန်_kg အရပ်_cm\nဥပမာ: /bmi 60 170")
        return
    try:
        kg, cm = float(context.args[0]), float(context.args[1])
        if kg <= 0 or cm <= 0:
            raise ValueError
        bmi = kg / ((cm / 100) ** 2)
        await update.effective_message.reply_text(f"📊 BMI = {bmi:.1f}")
    except ValueError:
        await update.effective_message.reply_text("အလေးချိန်နဲ့ အရပ်ကို မှန်ကန်တဲ့ ကိန်းဂဏန်းအဖြစ် ထည့်ပါ။")


async def convert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_join(update, context):
        return
    if len(context.args) < 3:
        await update.effective_message.reply_text(
            "အသုံးပြုပုံ: /convert တန်ဖိုး ယူနစ်မှ ယူနစ်သို့\n"
            "ဥပမာ: /convert 5 km mile\n"
            "ရနိုင်သော ယူနစ်: km, mile, m, cm, kg, lb, c, f"
        )
        return
    try:
        value = float(context.args[0])
        source, target = context.args[1].lower(), context.args[2].lower()
        factors = {
            ("km", "mile"): lambda x: x * 0.621371,
            ("mile", "km"): lambda x: x / 0.621371,
            ("m", "cm"): lambda x: x * 100,
            ("cm", "m"): lambda x: x / 100,
            ("kg", "lb"): lambda x: x * 2.20462,
            ("lb", "kg"): lambda x: x / 2.20462,
            ("c", "f"): lambda x: x * 9 / 5 + 32,
            ("f", "c"): lambda x: (x - 32) * 5 / 9,
        }
        if source == target:
            result = value
        elif (source, target) in factors:
            result = factors[(source, target)](value)
        else:
            await update.effective_message.reply_text("ဒီယူနစ်ပြောင်းလဲမှုကို မထောက်ပံ့သေးပါ။")
            return
        await update.effective_message.reply_text(f"🔄 {value:g} {source} = {result:.4g} {target}")
    except ValueError:
        await update.effective_message.reply_text("တန်ဖိုးကို ကိန်းဂဏန်းအဖြစ် ထည့်ပါ။")


async def note_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_join(update, context):
        return
    user = update.effective_user
    note = " ".join(context.args).strip()
    if not note:
        await update.effective_message.reply_text("အသုံးပြုပုံ: /note သိမ်းချင်တဲ့စာသား")
        return
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        db.execute(
            "INSERT INTO notes (user_id, note, created_at) VALUES (?, ?, ?)",
            (user.id, note, datetime.now(ZoneInfo(TIMEZONE)).isoformat()),
        )
        db.commit()
    await update.effective_message.reply_text("📝 မှတ်စုသိမ်းပြီးပါပြီ။")


async def notes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_join(update, context):
        return
    user = update.effective_user
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        rows = db.execute(
            "SELECT id, note FROM notes WHERE user_id = ? ORDER BY id DESC LIMIT 10",
            (user.id,),
        ).fetchall()
    if not rows:
        await update.effective_message.reply_text("မှတ်စုမရှိသေးပါ။")
        return
    text = "\n\n".join(f"{row[0]}. {row[1]}" for row in rows)
    await update.effective_message.reply_text("📝 သင့်မှတ်စုများ:\n\n" + text[:3900])


async def todo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_join(update, context):
        return
    user = update.effective_user
    task = " ".join(context.args).strip()
    if not task:
        await update.effective_message.reply_text("အသုံးပြုပုံ: /todo လုပ်စရာ")
        return
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        db.execute(
            "INSERT INTO todos (user_id, task, created_at) VALUES (?, ?, ?)",
            (user.id, task, datetime.now(ZoneInfo(TIMEZONE)).isoformat()),
        )
        db.commit()
    await update.effective_message.reply_text("✅ လုပ်စရာစာရင်းထဲ ထည့်ပြီးပါပြီ။")


async def todos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_join(update, context):
        return
    user = update.effective_user
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        rows = db.execute(
            "SELECT id, task, done FROM todos WHERE user_id = ? ORDER BY id DESC LIMIT 20",
            (user.id,),
        ).fetchall()
    if not rows:
        await update.effective_message.reply_text("လုပ်စရာမရှိသေးပါ။")
        return
    text = "\n".join(f"{'☑️' if row[2] else '⬜'} {row[0]}. {row[1]}" for row in rows)
    await update.effective_message.reply_text("📋 လုပ်စရာများ:\n\n" + text[:3900])


async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_join(update, context):
        return
    if not context.args:
        await update.effective_message.reply_text("အသုံးပြုပုံ: /weather Yangon")
        return
    city = " ".join(context.args)
    try:
        url = f"https://wttr.in/{quote_plus(city)}?format=3"
        response = await asyncio.to_thread(requests.get, url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        await update.effective_message.reply_text("🌦️ " + response.text[:1000])
    except Exception:
        await update.effective_message.reply_text("ရာသီဥတုအချက်အလက် ရယူမရပါ။")


async def rates_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_join(update, context):
        return
    try:
        response = await asyncio.to_thread(
            requests.get, "https://open.er-api.com/v6/latest/USD", timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()
        rates = data.get("rates", {})
        wanted = ["MMK", "THB", "SGD", "MYR", "JPY", "EUR", "GBP"]
        lines = ["💱 USD ငွေလဲနှုန်း (အွန်လိုင်းရင်းမြစ်)"]
        for code in wanted:
            if code in rates:
                lines.append(f"1 USD ≈ {rates[code]} {code}")
        await update.effective_message.reply_text("\n".join(lines))
    except Exception:
        await update.effective_message.reply_text("ငွေလဲနှုန်း ရယူမရပါ။")


async def translate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_join(update, context):
        return
    text = " ".join(context.args).strip()
    if not text:
        await update.effective_message.reply_text("အသုံးပြုပုံ: /translate Hello, how are you?")
        return
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        response = await asyncio.to_thread(
            requests.get,
            url,
            params={"client": "gtx", "sl": "auto", "tl": "my", "dt": "t", "q": text},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        translated = "".join(part[0] for part in data[0] if part and part[0])
        await update.effective_message.reply_text("🌐 ဘာသာပြန်ချက်:\n" + translated[:3900])
    except Exception:
        await update.effective_message.reply_text("ဘာသာပြန်ရာမှာ အမှားဖြစ်နေပါတယ်။")


async def dictionary_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_join(update, context):
        return
    if not context.args:
        await update.effective_message.reply_text("အသုံးပြုပုံ: /define hello")
        return
    word = context.args[0]
    try:
        response = await asyncio.to_thread(
            requests.get,
            f"https://api.dictionaryapi.dev/api/v2/entries/en/{quote_plus(word)}",
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        meanings = []
        for meaning in data[0].get("meanings", [])[:3]:
            defs = meaning.get("definitions", [])
            if defs:
                meanings.append(f"{meaning.get('partOfSpeech', '')}: {defs[0].get('definition', '')}")
        await update.effective_message.reply_text(f"📖 {word}\n\n" + ("\n\n".join(meanings) or "အဓိပ္ပာယ်မတွေ့ပါ။"))
    except Exception:
        await update.effective_message.reply_text("ဒီစကားလုံးရဲ့ အဓိပ္ပာယ်ကို ရှာမတွေ့ပါ။")


async def water_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_join(update, context):
        return
    if not context.args:
        await update.effective_message.reply_text("အသုံးပြုပုံ: /water ကိုယ်အလေးချိန်_kg\nဥပမာ: /water 60")
        return
    try:
        kg = float(context.args[0])
        if kg <= 0:
            raise ValueError
        liters = kg * 0.033
        await update.effective_message.reply_text(
            f"💧 အကြမ်းဖျင်း ရေသောက်ပမာဏ: တစ်နေ့ {liters:.1f} လီတာခန့်။ "
            "ရာသီဥတု၊ လှုပ်ရှားမှုနဲ့ ကျန်းမာရေးအခြေအနေပေါ်မူတည်ပြီး ကွာခြားနိုင်ပါတယ်။"
        )
    except ValueError:
        await update.effective_message.reply_text("အလေးချိန်ကို မှန်ကန်တဲ့ ကိန်းဂဏန်းအဖြစ် ထည့်ပါ။")


async def qr_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_join(update, context):
        return
    text = " ".join(context.args).strip()
    if not text:
        await update.effective_message.reply_text("အသုံးပြုပုံ: /qr QR ထုတ်ချင်တဲ့စာသား သို့မဟုတ် URL")
        return
    try:
        from telegram import InputFile
        response = await asyncio.to_thread(
            requests.get,
            "https://api.qrserver.com/v1/create-qr-code/",
            params={"size": "300x300", "data": text},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        from io import BytesIO
        image = BytesIO(response.content)
        image.name = "qr.png"
        await update.effective_message.reply_photo(photo=InputFile(image), caption="QR Code")
    except Exception:
        await update.effective_message.reply_text("QR Code ဖန်တီးရာမှာ အမှားဖြစ်နေပါတယ်။")


async def unknown_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Avoid replying to every random message; guide the user to commands.
    if update.effective_message and update.effective_message.text:
        await update.effective_message.reply_text(
            "အသုံးပြုနိုင်တဲ့ Command တွေကြည့်ရန် /start ကိုနှိပ်ပါ။"
        )


def main():
    if not TOKEN:
        raise RuntimeError("Railway Variables ထဲမှာ BOT_TOKEN (သို့) TOKEN ထည့်ပေးပါ။")
    init_db()
    app = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("news", news_command))
    app.add_handler(CommandHandler("breaking", breaking_command))
    app.add_handler(CommandHandler("time", time_command))
    app.add_handler(CommandHandler("quote", quote_command))
    app.add_handler(CommandHandler("password", password_command))
    app.add_handler(CommandHandler("bmi", bmi_command))
    app.add_handler(CommandHandler("convert", convert_command))
    app.add_handler(CommandHandler("note", note_command))
    app.add_handler(CommandHandler("notes", notes_command))
    app.add_handler(CommandHandler("todo", todo_command))
    app.add_handler(CommandHandler("todos", todos_command))
    app.add_handler(CommandHandler("weather", weather_command))
    app.add_handler(CommandHandler("rates", rates_command))
    app.add_handler(CommandHandler("translate", translate_command))
    app.add_handler(CommandHandler("define", dictionary_command))
    app.add_handler(CommandHandler("water", water_command))
    app.add_handler(CommandHandler("qr", qr_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_text))

    logger.info("Ck_helpbot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
