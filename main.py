import os
import re
import sqlite3
import logging
import asyncio
import hashlib
import html
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
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
# BOT_TOKEN: Telegram bot token
# GAME_CHANNEL_ID: optional destination channel for game files (@username or -100... ID)
# ADMIN_IDS: comma-separated Telegram user IDs, e.g. 12345,67890
# DB_PATH: optional SQLite path; Railway Volume recommended
# =========================================================

TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS = {
    int(value.strip())
    for value in os.getenv("ADMIN_IDS", "").split(",")
    if value.strip().isdigit()
}
DB_PATH = os.getenv("DB_PATH", "movies_bot.db")
# Optional forced-join gate. Set CHANNEL_USERNAME (e.g. @mychannel) in Railway.
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "").strip()
CHANNEL_URL = os.getenv("CHANNEL_URL", "").strip()
# Optional destination for game files. Use @publicchannel or a numeric chat ID (-100...).
GAME_CHANNEL_ID = os.getenv("GAME_CHANNEL_ID", "").strip()
# News destination. Bot must be an administrator in this channel.
NEWS_CHANNEL_ID = os.getenv("NEWS_CHANNEL_ID", "").strip()
NEWS_TIMEZONE = ZoneInfo("Asia/Yangon")
NEWS_DAILY_HOUR = int(os.getenv("NEWS_DAILY_HOUR", "7"))  # Myanmar time
NEWS_CHECK_MINUTES = max(5, int(os.getenv("NEWS_CHECK_MINUTES", "15")))

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
        db.execute("""
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                file_id TEXT NOT NULL,
                caption TEXT
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS news_subscribers (
                user_id INTEGER PRIMARY KEY,
                added_at TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS news_seen (
                url TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                first_seen TEXT NOT NULL,
                breaking_sent INTEGER NOT NULL DEFAULT 0
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS news_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
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
            logger.info("API returned HTTP %s for %s", response.status_code, url)
            return None
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("API request failed: %s", exc)
        return None


def translate_to_burmese(text):
    """Translate API content to Burmese. Return original text if translation fails."""
    if not text:
        return ""
    text = str(text)[:3500]
    data = get_json(
        "https://translate.googleapis.com/translate_a/single",
        {
            "client": "gtx",
            "sl": "auto",
            "tl": "my",
            "dt": "t",
            "q": text,
        },
    )
    try:
        if data and isinstance(data, list):
            return "".join(part[0] for part in data[0] if part and part[0])
    except (IndexError, TypeError):
        pass
    return text


# ----------------------- Country lookup --------------------

def get_country(query):
    """
    Search REST Countries dynamically. No built-in list of country names.
    First try exact name, then use the API's name search result.
    """
    query = query.strip()
    if not query:
        return None

    fields = (
        "name,capital,region,subregion,population,languages,"
        "currencies,cca2,cca3"
    )

    # Try exact match first; the API supports fullText=true.
    data = get_json(
        "https://restcountries.com/v3.1/name/" + quote(query, safe=""),
        {"fullText": "true", "fields": fields},
    )

    # If exact match failed, try a broader name search.
    if not isinstance(data, list) or not data:
        data = get_json(
            "https://restcountries.com/v3.1/name/" + quote(query, safe=""),
            {"fields": fields},
        )

    if not isinstance(data, list) or not data:
        return None

    query_lower = query.casefold()
    for country in data:
        name = country.get("name") or {}
        common = name.get("common", "")
        official = name.get("official", "")
        native_names = name.get("nativeName") or {}
        native_values = []
        for item in native_names.values():
            if isinstance(item, dict):
                native_values.extend(
                    [item.get("common", ""), item.get("official", "")]
                )

        candidates = [common, official] + native_values
        if any(
            candidate and candidate.casefold() == query_lower
            for candidate in candidates
        ):
            return country

    # If the API found one unambiguous result, use it.
    if len(data) == 1:
        return data[0]

    # Avoid returning a random country for a broad/ambiguous query.
    return None


def format_country(country):
    name_data = country.get("name") or {}
    common_name = name_data.get("common", "Unknown")
    official_name = name_data.get("official", common_name)
    capital = country.get("capital") or []
    languages = country.get("languages") or {}
    currencies = country.get("currencies") or {}

    currency_text = ", ".join(
        f"{item.get('name', code)}"
        + (f" ({item.get('symbol')})" if item.get("symbol") else "")
        for code, item in currencies.items()
    )

    raw = (
        f"Country: {common_name}\n"
        f"Official name: {official_name}\n"
        f"Capital: {', '.join(capital) if capital else 'Not available'}\n"
        f"Region: {country.get('region', 'Not available')}\n"
        f"Subregion: {country.get('subregion', 'Not available')}\n"
        f"Population: {country.get('population', 0):,}\n"
        f"Languages: {', '.join(languages.values()) if languages else 'Not available'}\n"
        f"Currencies: {currency_text or 'Not available'}\n"
        f"Country codes: {country.get('cca2', '')} / {country.get('cca3', '')}"
    )
    return common_name, raw


# --------------------- Wikipedia search --------------------

def wikipedia_search(search_query, limit=5):
    data = get_json(
        "https://en.wikipedia.org/w/api.php",
        {
            "action": "query",
            "list": "search",
            "srsearch": search_query,
            "srlimit": limit,
            "format": "json",
            "utf8": 1,
        },
    )
    if not data:
        return []
    return data.get("query", {}).get("search", [])


def wikipedia_summary(title):
    url = (
        "https://en.wikipedia.org/api/rest_v1/page/summary/"
        + quote(title.replace(" ", "_"), safe="")
    )
    data = get_json(url)
    if not isinstance(data, dict):
        return None
    if data.get("type") == "disambiguation":
        return None
    if not data.get("extract"):
        return None
    return data



def search_person_or_hero(query):
    """
    Search a typed hero/person name dynamically, first on Burmese Wikipedia,
    then English Wikipedia. Falls back to Wikipedia search results if the exact
    page title does not exist. No list of names is hard-coded.
    """
    query = query.strip()
    if not query:
        return None

    for language in ("my", "en"):
        base = f"https://{language}.wikipedia.org"
        # Try an exact page title.
        exact = get_json(
            base + "/api/rest_v1/page/summary/" + quote(query.replace(" ", "_"), safe="")
        )
        if (
            isinstance(exact, dict)
            and exact.get("extract")
            and exact.get("type") != "disambiguation"
        ):
            return exact

        # Search Wikipedia's index, then retrieve the article summary.
        results = get_json(
            base + "/w/api.php",
            {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": 5,
                "format": "json",
                "utf8": 1,
            },
        )
        items = (results or {}).get("query", {}).get("search", [])
        for item in items:
            title = (item.get("title") or "").strip()
            if not title:
                continue
            summary = get_json(
                base + "/api/rest_v1/page/summary/"
                + quote(title.replace(" ", "_"), safe="")
            )
            if (
                isinstance(summary, dict)
                and summary.get("extract")
                and summary.get("type") != "disambiguation"
            ):
                return summary
    return None

def get_country_history(country_name):
    data = wikipedia_summary(country_name)
    if data:
        return data.get("extract", "")
    # If exact page title differs, search Wikipedia and use the first useful page.
    for item in wikipedia_search(f"{country_name} country history", limit=3):
        summary = wikipedia_summary(item.get("title", ""))
        if summary:
            return summary.get("extract", "")
    return ""


def get_famous_people(country_name, limit=5):
    """
    Search Wikipedia dynamically for historical figures, independence leaders,
    and notable people associated with the country. Results are not guaranteed
    to be official national heroes.
    """
    search_queries = [
        f"notable people from {country_name}",
        f"historical figures of {country_name}",
        f"independence leaders of {country_name}",
    ]
    results = []
    seen = set()

    for search_query in search_queries:
        for item in wikipedia_search(search_query, limit=6):
            title = (item.get("title") or "").strip()
            if not title or title.casefold() in seen:
                continue

            # Exclude list/category pages; keep individual biography pages.
            lower = title.casefold()
            if lower.startswith(("list of ", "category:", "history of ")):
                continue

            summary = wikipedia_summary(title)
            if not summary:
                continue

            extract = summary.get("extract", "").strip()
            if not extract:
                continue

            seen.add(lower)
            results.append({"name": title, "description": extract})
            if len(results) >= limit:
                return results

    return results


# ---------------------- Country response -------------------

async def send_long_text(message, text, limit=3800):
    """Split long messages without exceeding Telegram's text length limit."""
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


async def send_country_info(update, country):
    message = update.effective_message
    if not message:
        return

    country_name, raw_info = format_country(country)

    translated_info = await asyncio.to_thread(translate_to_burmese, raw_info)
    history = await asyncio.to_thread(get_country_history, country_name)

    if history:
        translated_history = await asyncio.to_thread(
            translate_to_burmese, history[:1800]
        )
    else:
        translated_history = (
            "လက်ရှိတွင် Wikipedia မှ သမိုင်းအချက်အလက်ကို မရရှိနိုင်ပါ။"
        )

    await send_long_text(
        message,
        f"🌍 နိုင်ငံအကြောင်း: {country_name}\n\n"
        f"📚 အထွေထွေအချက်အလက်\n{translated_info}\n\n"
        f"🏛️ သမိုင်းအကျဉ်း\n{translated_history}",
    )

    people = await asyncio.to_thread(get_famous_people, country_name)

    if not people:
        await message.reply_text(
            "🛡️ ထင်ရှားသူများ\n\n"
            "Wikipedia မှ ယုံကြည်စိတ်ချရသော ကိုက်ညီသည့်ရလဒ်ကို "
            "ယခုအချိန်တွင် မရရှိနိုင်ပါ။ နောက်မှ ထပ်စမ်းကြည့်ပါ။"
        )
        return

    lines = [
        f"🛡️ {country_name} မှ သမိုင်းဝင်/ထင်ရှားသူများ",
        "",
        "မှတ်ချက် - အောက်ပါအမည်များသည် Wikipedia ရှာဖွေမှုမှ "
        "ရရှိထားသော သမိုင်းဝင်ပုဂ္ဂိုလ်များ သို့မဟုတ် ထင်ရှားသူများဖြစ်သည်။ "
        "အားလုံးကို တရားဝင် 'သူရဲကောင်း' ဟု သတ်မှတ်ထားခြင်း မဟုတ်ပါ။",
        "",
    ]

    for index, person in enumerate(people, 1):
        translated_name = await asyncio.to_thread(
            translate_to_burmese, person["name"]
        )
        translated_description = await asyncio.to_thread(
            translate_to_burmese, person["description"][:550]
        )
        lines.append(
            f"{index}. {translated_name} ({person['name']})\n"
            f"{translated_description}\n"
        )

    await send_long_text(message, "\n".join(lines))


# ---------------------- Required channel join ----------------------

def channel_join_url():
    if CHANNEL_URL:
        return CHANNEL_URL
    username = CHANNEL_USERNAME.lstrip("@")
    return f"https://t.me/{username}" if username else ""


async def is_channel_member(context, user_id):
    """Return True if channel gating is disabled or the user is a member."""
    if not CHANNEL_USERNAME:
        return True
    try:
        member = await context.bot.get_chat_member(
            chat_id=CHANNEL_USERNAME, user_id=user_id
        )
        status = getattr(member, "status", "")
        if status in ("creator", "administrator", "member"):
            return True
        return status == "restricted" and bool(getattr(member, "is_member", False))
    except Exception:
        logger.exception("Could not verify required channel membership")
        return None


async def require_channel_join(update, context):
    """Gate bot features until the user joins the configured channel."""
    user = update.effective_user
    message = update.effective_message
    if not user or user.id in ADMIN_IDS or not CHANNEL_USERNAME:
        return True

    membership = await is_channel_member(context, user.id)
    if membership is True:
        return True

    if membership is None:
        notice = (
            "⚠️ Channel membership ကို စစ်ဆေးမရပါ။ Bot ကို Channel ထဲမှာ Admin အဖြစ် "
            "ထည့်ထားပြီး Railway Variables ကို ပြန်စစ်ပေးပါ။"
        )
        keyboard = None
    else:
        notice = (
            "🔒 ဘော့ကို ဆက်အသုံးပြုရန် အောက်ပါ Channel ကို အရင် Join လုပ်ပါ။\n"
            "Join ပြီးရင် “✅ Join ပြီးပါပြီ” ကို နှိပ်ပါ။"
        )
        buttons = []
        url = channel_join_url()
        if url:
            buttons.append([InlineKeyboardButton("📢 Channel Join", url=url)])
        buttons.append([InlineKeyboardButton("✅ Join ပြီးပါပြီ", callback_data="check_channel_join")])
        keyboard = InlineKeyboardMarkup(buttons)

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
    if user.id in ADMIN_IDS or not CHANNEL_USERNAME:
        await query.answer("အသုံးပြုနိုင်ပါပြီ။")
        if query.message:
            await query.message.reply_text("✅ စစ်ဆေးမှု မလိုအပ်ပါ။ /start ကို နှိပ်ပါ။")
        return

    membership = await is_channel_member(context, user.id)
    if membership is True:
        await query.answer("✅ Join ဖြစ်ကြောင်း အတည်ပြုပြီးပါပြီ။")
        if query.message:
            await query.message.reply_text("🎉 အတည်ပြုပြီးပါပြီ။ ယခု Bot ကို ဆက်အသုံးပြုနိုင်ပါပြီ။ /start ကို နှိပ်ပါ။")
    elif membership is False:
        await query.answer("Channel ကို Join မလုပ်ရသေးပါ။", show_alert=True)
    else:
        await query.answer("Membership စစ်ဆေးမရပါ။ Bot ကို Channel Admin ထည့်ထားပါ။", show_alert=True)


# ----------------------- Burmese news system -----------------------
# Google News RSS queries provide Myanmar-language coverage and English/world coverage.
NEWS_FEEDS = [
    ("သတင်းရင်းမြစ်: မြန်မာသတင်း", "https://news.google.com/rss/search?q=မြန်မာသတင်း&hl=my&gl=MM&ceid=MM:my", False),
    ("သတင်းရင်းမြစ်: မြန်မာနိုင်ငံ", "https://news.google.com/rss/search?q=Myanmar&hl=my&gl=MM&ceid=MM:my", False),
    ("Source: World news", "https://news.google.com/rss/search?q=world+news&hl=en-US&gl=US&ceid=US:en", True),
    ("Source: Breaking world news", "https://news.google.com/rss/search?q=breaking+news&hl=en-US&gl=US&ceid=US:en", True),
]
BREAKING_TERMS = (
    "breaking", "urgent", "just in", "live:", "explosion", "earthquake",
    "airstrike", "attack", "coup", "evacuation", "tsunami", "flood",
    "ငလျင်", "ပေါက်ကွဲ", "တိုက်ခိုက်", "အရေးပေါ်", "ရေကြီး", "မုန်တိုင်း",
    "လေကြောင်းတိုက်ခိုက်", "သတိပေး", "အရေးကြီးသတင်း",
)


def fetch_news_feed(url, source_label, english):
    """Read RSS with the standard library so no feedparser dependency is needed."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        items = []
        for item in root.findall('.//item')[:15]:
            title = (item.findtext('title') or '').strip()
            link = (item.findtext('link') or '').strip()
            description = (item.findtext('description') or '').strip()
            pub_date = (item.findtext('pubDate') or '').strip()
            if not title or not link:
                continue
            description = html.unescape(re.sub(r'<[^>]+>', ' ', description))
            description = re.sub(r'\s+', ' ', description).strip()
            items.append({
                'title': title,
                'link': link,
                'description': description[:900],
                'pub_date': pub_date,
                'source': source_label,
                'english': english,
            })
        return items
    except Exception as exc:
        logger.warning('News RSS fetch failed (%s): %s', source_label, exc)
        return []


def fetch_latest_news():
    results, seen = [], set()
    for label, url, english in NEWS_FEEDS:
        for item in fetch_news_feed(url, label, english):
            if item['link'] in seen:
                continue
            seen.add(item['link'])
            results.append(item)
    return results


def contains_burmese(text):
    """Return True when text contains Myanmar Unicode characters."""
    return bool(text and re.search(r"[\u1000-\u109F\uAA60-\uAA7F]", str(text)))


def translate_news_field(text):
    """Translate a news field and only accept it if Burmese text is returned."""
    if not text:
        return ""
    if contains_burmese(text):
        return text
    translated = translate_to_burmese(text)
    if translated and translated.strip() != text.strip() and contains_burmese(translated):
        return translated.strip()
    # Never silently publish an English title/summary as if it were Burmese.
    return ""


def render_news_item(item, index=None):
    """Render news in Burmese; skip an item if its headline cannot be translated."""
    original_title = item.get('title', '').strip()
    title = translate_news_field(original_title)
    if not title:
        logger.warning("Skipping news item because Burmese translation failed: %s", item.get('link', ''))
        return None

    desc = (item.get('description') or '').strip()
    if desc and not contains_burmese(desc):
        desc = translate_news_field(desc[:700])
    elif desc:
        # If an RSS summary mixes languages, translate it as a whole to avoid leaking English.
        translated_desc = translate_to_burmese(desc[:700])
        if contains_burmese(translated_desc):
            desc = translated_desc.strip()
        else:
            desc = ''

    prefix = f"{index}. " if index is not None else "• "
    text = f"{prefix}📰 {title}"
    if desc:
        text += f"\n{desc[:700]}"
    if item.get('pub_date'):
        text += f"\n🕒 ထုတ်ပြန်ချိန်: {item['pub_date']}"
    text += f"\n🔗 မူရင်းသတင်းလင့်ခ်: {item['link']}"
    return text


def get_subscriber_ids():
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        rows = db.execute('SELECT user_id FROM news_subscribers').fetchall()
    return [int(row[0]) for row in rows]


async def broadcast_news(application, text):
    """Send a news message to all /start subscribers and the configured news channel."""
    recipients = get_subscriber_ids()
    for user_id in recipients:
        try:
            await application.bot.send_message(chat_id=user_id, text=text, disable_web_page_preview=True)
        except Exception as exc:
            # A blocked bot or deleted account should not stop the rest of the broadcast.
            logger.info('News DM failed for user %s: %s', user_id, exc)
    if NEWS_CHANNEL_ID:
        try:
            await application.bot.send_message(
                chat_id=NEWS_CHANNEL_ID, text=text, disable_web_page_preview=True
            )
        except Exception as exc:
            logger.warning('News channel delivery failed: %s', exc)
    elif not recipients:
        logger.info('No news recipients configured yet; use /start and set NEWS_CHANNEL_ID.')


async def send_daily_news(application):
    items = await asyncio.to_thread(fetch_latest_news)
    if not items:
        logger.warning('Daily news: no RSS items fetched')
        return
    # Ensure the daily digest includes both Myanmar-language coverage and English/world coverage.
    myanmar_items = [item for item in items if not item.get('english')]
    english_items = [item for item in items if item.get('english')]
    selected = myanmar_items[:4] + english_items[:4]
    if len(selected) < 8:
        already = {item['link'] for item in selected}
        selected.extend(item for item in items if item['link'] not in already and len(selected) < 8)
    chunks = []
    current = '🇲🇲🌍 နေ့စဉ်သတင်းအကျဉ်းချုပ်\n\n'
    rendered_count = 0
    for i, item in enumerate(selected, 1):
        rendered = await asyncio.to_thread(render_news_item, item, i)
        if not rendered:
            continue
        rendered_count += 1
        block = rendered + '\n\n'
        if len(current) + len(block) > 3600 and current.strip():
            chunks.append(current.rstrip())
            current = '📰 နေ့စဉ်သတင်း (ဆက်လက်)\n\n'
        current += block
    if rendered_count and current.strip():
        chunks.append(current.rstrip())
    for chunk in chunks:
        await broadcast_news(application, chunk)


async def check_breaking_news(application):
    items = await asyncio.to_thread(fetch_latest_news)
    for item in items:
        url = item['link']
        title_lower = item['title'].casefold()
        is_breaking = any(term.casefold() in title_lower for term in BREAKING_TERMS)
        with sqlite3.connect(DB_PATH, timeout=30) as db:
            row = db.execute('SELECT breaking_sent FROM news_seen WHERE url=?', (url,)).fetchone()
            if row is not None:
                continue
            db.execute(
                'INSERT OR IGNORE INTO news_seen(url,title,first_seen,breaking_sent) VALUES(?,?,?,?)',
                (url, item['title'], datetime.now(NEWS_TIMEZONE).isoformat(), int(is_breaking)),
            )
            db.commit()
        if is_breaking:
            rendered = await asyncio.to_thread(render_news_item, item)
            if not rendered:
                continue
            await broadcast_news(
                application,
                '🚨 အရေးပေါ်သတင်း\n\n' + rendered,
            )


async def news_scheduler(application):
    """Daily at 07:00 Myanmar time; check potential breaking stories every 15 min."""
    last_check_slot = None
    while True:
        now = datetime.now(NEWS_TIMEZONE)
        today = now.date().isoformat()
        with sqlite3.connect(DB_PATH, timeout=30) as db:
            row = db.execute("SELECT value FROM news_state WHERE key='daily_attempt_date'").fetchone()
        last_daily_date = row[0] if row else None
        if now.hour >= NEWS_DAILY_HOUR and last_daily_date != today:
            # Persist the attempt date to prevent duplicate daily blasts after restarts.
            with sqlite3.connect(DB_PATH, timeout=30) as db:
                db.execute(
                    "INSERT OR REPLACE INTO news_state(key,value) VALUES('daily_attempt_date',?)",
                    (today,),
                )
                db.commit()
            try:
                await send_daily_news(application)
            except Exception:
                logger.exception('Daily news job failed')
        slot = (now.date(), now.hour, now.minute // NEWS_CHECK_MINUTES)
        if now.minute % NEWS_CHECK_MINUTES == 0 and slot != last_check_slot:
            try:
                await check_breaking_news(application)
            except Exception:
                logger.exception('Breaking news check failed')
            last_check_slot = slot
        await asyncio.sleep(30)


async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    await update.effective_message.reply_text(
        '📰 နေ့စဉ်သတင်းကို မြန်မာသတင်း RSS နှင့် အင်္ဂလိပ်ကမ္ဘာ့သတင်း RSS နှစ်မျိုးမှ ရယူပြီး '
        'အင်္ဂလိပ်ခေါင်းစဉ်/အကျဉ်းချုပ်ကို မြန်မာလို ဘာသာပြန်ပို့ပေးပါတယ်။ '
        'နေ့စဉ်ပို့ချိန် 07:00 (မြန်မာစံတော်ချိန်) ဖြစ်ပြီး Breaking News ကို မိနစ် 15 တိုင်း စစ်ဆေးပါတယ်.'
    )


# -------------------------- Commands -----------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    user = update.effective_user
    if user and update.effective_chat and update.effective_chat.type == "private":
        with sqlite3.connect(DB_PATH, timeout=30) as db:
            db.execute(
                "INSERT OR IGNORE INTO news_subscribers(user_id, added_at) VALUES(?, ?)",
                (user.id, datetime.now(NEWS_TIMEZONE).isoformat()),
            )
            db.commit()
    await update.effective_message.reply_text(
        "🤖 Ck_helpbot မှ ကြိုဆိုပါတယ်။\n\n"
        "🌍 နိုင်ငံအမည်ကို ရိုက်ထည့်ပါ။ Bot က အင်တာနက် API များမှ "
        "နိုင်ငံအချက်အလက်ကို ရှာဖွေပေးပါမယ်။\n\n"
        "ဥပမာအဖြစ် နိုင်ငံအမည်တစ်ခုခုကို ရိုက်ထည့်နိုင်ပါတယ်။ "
        "အမည်စာရင်းကို Code ထဲမှာ ကြိုတင်ထည့်ထားဖို့ မလိုပါ။\n\n"
        "📚 နိုင်ငံအချက်အလက်၊ သမိုင်းနဲ့ Wikipedia မှ "
        "ထင်ရှားသူများကို ရှာဖွေပေးပါမယ်။\n\n"
        "🎬 သိမ်းထားသော ရုပ်ရှင်ရှာရန် ရုပ်ရှင်အမည်ကို ရိုက်ပါ။\n"
        "🎮 ဂိမ်းဖိုင်ရှာရန် /game ဂိမ်းအမည် ဟု ရိုက်ပါ။\n"
        "ဥပမာ: /game SuperTuxKart\n"
        "📰 မြန်မာသတင်းနှင့် အင်္ဂလိပ်သတင်းဘာသာပြန်များကို အလိုအလျောက် ရရှိပါမယ်။\n"
        "/news - သတင်းပို့ချိန်နှင့် ရင်းမြစ်အကြောင်း\n"
        "/help - အသုံးပြုနည်း"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    await update.effective_message.reply_text(
        "📖 အသုံးပြုနည်း\n\n"
        "• နိုင်ငံအမည်ကို ရိုက်ပို့ပါ။\n"
        "• ရှာဖွေမှုသည် REST Countries နှင့် Wikipedia API များကို အသုံးပြုသည်။\n"
        "• ရလဒ်မတွေ့ပါက နိုင်ငံအမည်ကို အင်္ဂလိပ်လို ပြန်စမ်းပါ။\n"
        "• ရုပ်ရှင်အမည်ဖြင့် သိမ်းထားသော ရုပ်ရှင်ကို ရှာနိုင်သည်။\n"
        "• ဂိမ်းဖိုင်ရှာရန် /game ဂိမ်းအမည် ဟု သုံးပါ။ ဥပမာ /game SuperTuxKart။ GitHub public release မှ 45 MB အောက် APK/ZIP/archive ဖိုင်ရလျှင် ပို့ပေးမည်။ မရလျှင် တရားဝင်ရှာဖွေရေးလင့်ခ်များ ပြမည်။\n"
        "• Commercial/paid ဂိမ်းများ၏ ခွင့်ပြုချက်မရှိသော မိတ္တူများကို မရှာပေးပါ။\n"
        "• Admin သည် video/document ဖိုင်ပို့၍ ရုပ်ရှင်သိမ်းနိုင်သည်။"
    )


# ------------------------ Movie storage --------------------

async def save_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    message = update.effective_message
    user = update.effective_user
    if not message or not user:
        return

    if user.id not in ADMIN_IDS:
        await message.reply_text(
            "⚠️ ရုပ်ရှင်ဖိုင်တင်ခွင့်ကို Admin များသာ အသုံးပြုနိုင်ပါတယ်။"
        )
        return

    if message.video:
        file_id = message.video.file_id
        title = message.caption or getattr(message.video, "file_name", None) or "Untitled Movie"
    elif message.document:
        file_id = message.document.file_id
        title = message.caption or message.document.file_name or "Untitled Movie"
    else:
        return

    try:
        with sqlite3.connect(DB_PATH, timeout=30) as db:
            db.execute(
                "INSERT INTO movies (title, file_id, caption) VALUES (?, ?, ?)",
                (title.lower(), file_id, title),
            )
            db.commit()
        await message.reply_text(f"✅ ရုပ်ရှင်သိမ်းဆည်းပြီးပါပြီ။\n🎬 {title}")
    except sqlite3.Error:
        logger.exception("Could not save movie")
        await message.reply_text("❌ ဒေတာဘေ့စ်ထဲသို့ သိမ်းဆည်းမရပါ။")


async def search_movie(update: Update, query: str):
    message = update.effective_message
    if not message:
        return False

    try:
        with sqlite3.connect(DB_PATH, timeout=30) as db:
            results = db.execute(
                """
                SELECT title, file_id, caption FROM movies
                WHERE LOWER(title) LIKE ?
                ORDER BY id DESC LIMIT 5
                """,
                (f"%{query.lower()}%",),
            ).fetchall()
    except sqlite3.Error:
        logger.exception("Movie search failed")
        await message.reply_text("❌ ရုပ်ရှင်ဒေတာဘေ့စ်ကို ဖတ်မရပါ။")
        return False

    if not results:
        return False

    for title, file_id, caption in results:
        caption_text = f"🎬 {caption or title}\n\nCk_helpbot"
        try:
            await message.reply_video(video=file_id, caption=caption_text[:1000])
        except Exception:
            try:
                await message.reply_document(
                    document=file_id, caption=caption_text[:1000]
                )
            except Exception:
                logger.exception("Could not send movie file")
                await message.reply_text(f"❌ ဖိုင်ပို့မရပါ: {caption or title}")
    return True


# --------------------- Game search/download -----------------

GAME_ASSET_EXTENSIONS = (".apk", ".zip", ".7z", ".tar.gz", ".tar.xz", ".tgz", ".rar")
MAX_GAME_DOWNLOAD_BYTES = 45 * 1024 * 1024  # Keep below common Telegram Bot API limits.


def game_store_links(query):
    """Official storefront/search links when a direct, public release is unavailable."""
    q = quote(query.strip(), safe="")
    return [
        ("Google Play (Android)", f"https://play.google.com/store/search?q={q}&c=apps"),
        ("Steam (PC)", f"https://store.steampowered.com/search/?term={q}"),
        ("itch.io (indie games)", f"https://itch.io/search?q={q}"),
        ("GitHub (open-source projects/releases)", f"https://github.com/search?q={q}+game&type=repositories"),
    ]


def search_github_game(query):
    """Find a matching open-source game's latest GitHub release and assets.

    This intentionally searches public release assets rather than pirated copies
    or arbitrary file-hosting sites. Results depend on GitHub's public API.
    """
    query = query.strip()
    if not query or len(query) > 100:
        return []
    data = get_json(
        "https://api.github.com/search/repositories",
        params={"q": f'{query} in:name fork:false', "sort": "stars", "order": "desc", "per_page": 12},
    )
    repos = (data or {}).get("items", [])
    results = []
    query_terms = [part.casefold() for part in re.findall(r"[\w+-]+", query) if len(part) > 1]
    for repo in repos:
        full_name = repo.get("full_name", "")
        repo_name = (repo.get("name") or "").replace("-", " ").replace("_", " ").casefold()
        # Require the repository name to meaningfully match the typed game name.
        if query_terms and not all(term in repo_name for term in query_terms):
            # Skip clearly unrelated projects, but allow a repository description
            # to match when the game's repository uses a different project name.
            repo_description = (repo.get("description") or "").casefold()
            if not all(term in repo_description for term in query_terms):
                continue
        release_data = get_json(f"https://api.github.com/repos/{full_name}/releases/latest")
        if not isinstance(release_data, dict) or not release_data.get("html_url"):
            continue
        assets = []
        for asset in release_data.get("assets", []):
            name = (asset.get("name") or "").casefold()
            size = asset.get("size") or 0
            url = asset.get("browser_download_url") or ""
            if name.endswith(GAME_ASSET_EXTENSIONS) and size > 0 and size <= MAX_GAME_DOWNLOAD_BYTES and url.startswith("https://github.com/"):
                assets.append({"name": asset.get("name"), "size": size, "url": url})
        results.append({
            "name": repo.get("name") or full_name,
            "description": repo.get("description") or "Open-source game project",
            "repo_url": repo.get("html_url") or "",
            "release_url": release_data.get("html_url"),
            "assets": assets,
            "stars": repo.get("stargazers_count", 0),
        })
        if len(results) >= 3:
            break
    return results


def download_github_asset(asset_url, destination):
    """Download only a bounded-size GitHub release asset."""
    if not asset_url.startswith("https://github.com/"):
        raise ValueError("Unsupported download host")
    with requests.get(asset_url, headers=HEADERS, timeout=(10, 30), stream=True, allow_redirects=True) as response:
        response.raise_for_status()
        final_host = urlparse(response.url).hostname or ""
        if final_host not in ("github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com"):
            raise ValueError("Unexpected download host")
        length = int(response.headers.get("Content-Length", "0") or 0)
        if length > MAX_GAME_DOWNLOAD_BYTES:
            raise ValueError("File is too large for the bot to send")
        written = 0
        with open(destination, "wb") as out:
            for chunk in response.iter_content(chunk_size=1024 * 256):
                if not chunk:
                    continue
                written += len(chunk)
                if written > MAX_GAME_DOWNLOAD_BYTES:
                    raise ValueError("File is too large for the bot to send")
                out.write(chunk)
        if written == 0:
            raise ValueError("Empty download")


async def search_game(update: Update, query: str) -> bool:
    """Search a game and send only the matching public release file when available."""
    message = update.effective_message
    if not message:
        return False
    try:
        results = await asyncio.to_thread(search_github_game, query)
    except Exception:
        logger.exception("Game search failed")
        return False
    if not results:
        return False

    for index, game in enumerate(results, 1):
        asset = (game.get("assets") or [None])[0]
        if asset:
            temp_path = None
            try:
                import tempfile
                suffix = Path(asset["name"]).suffix or ".bin"
                fd, temp_path = tempfile.mkstemp(prefix="ck_game_", suffix=suffix)
                os.close(fd)
                await asyncio.to_thread(download_github_asset, asset["url"], temp_path)
                caption = f"🎮 {game['name']}\n🔗 {game['release_url']}"[:1000]
                # If configured, publish the game file to the designated Telegram channel.
                # The bot must be an administrator with permission to post messages.
                if GAME_CHANNEL_ID:
                    with open(temp_path, "rb") as channel_file:
                        await context.bot.send_document(
                            chat_id=GAME_CHANNEL_ID,
                            document=channel_file,
                            filename=asset["name"],
                            caption=caption,
                            read_timeout=60,
                            write_timeout=60,
                        )
                    await message.reply_text("✅ ဂိမ်းဖိုင်ကို Channel ထဲ ပို့ပြီးပါပြီ။")
                # Also send the file to the user who searched for it.
                with open(temp_path, "rb") as user_file:
                    await message.reply_document(
                        document=user_file,
                        filename=asset["name"],
                        caption=caption,
                        read_timeout=60,
                        write_timeout=60,
                    )
            except Exception as exc:
                logger.warning("Game asset download/send failed: %s", exc)
                await message.reply_text(
                    "ဖိုင်ကို Bot က တိုက်ရိုက်ပို့မရပါ။ မူရင်း Release စာမျက်နှာမှ စစ်ဆေးပြီး ဒေါင်းလုဒ်လုပ်ပါ:\n"
                    + game["release_url"]
                )
            finally:
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass
            return True
        # Release exists but has no supported small archive/APK asset.
        await message.reply_text(
            f"🎮 {game['name']} အတွက် Bot က ပို့နိုင်တဲ့ APK/ZIP ဖိုင် မတွေ့ပါ။\n"
            f"မူရင်း Release: {game['release_url']}"
        )
        return True
    return False


async def game_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Use /game <name> to search games without country/Wikipedia fallback."""
    if not await require_channel_join(update, context):
        return
    message = update.effective_message
    if not message:
        return
    query = " ".join(context.args).strip()
    if not query:
        await message.reply_text("အသုံးပြုပုံ: /game ဂိမ်းအမည်\nဥပမာ: /game SuperTuxKart")
        return
    try:
        found = await search_game(update, query)
    except Exception:
        logger.exception("/game command failed")
        found = False
    if not found:
        links = game_store_links(query)
        await message.reply_text(
            f"🎮 ‘{query}’ အတွက် ကိုက်ညီတဲ့ GitHub Release ဖိုင် မတွေ့ပါ။\n\n"
            "အောက်ပါ တရားဝင်ရှာဖွေရေးလင့်ခ်များကို စမ်းကြည့်ပါ။\n"
            + "\n".join(f"• {label}: {url}" for label, url in links)
        )


# ----------------------- Main text handler -----------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    message = update.effective_message
    if not message or not message.text:
        return

    query = message.text.strip()
    if not query or query.startswith("/"):
        return

    # First: search country API dynamically.
    try:
        country = await asyncio.to_thread(get_country, query)
        if country:
            await send_country_info(update, country)
            return
    except Exception:
        logger.exception("Country lookup failed")

    # Second: try a public GitHub release for a game name. A matching release
    # must exist and the repository name must match the query; otherwise keep
    # processing the query as a person/hero name or locally stored movie.
    try:
        if await search_game(update, query):
            return
    except Exception:
        logger.exception("Game search handler failed")

    # Third: search a typed hero/person name dynamically on Burmese/English Wikipedia.
    # This also works for names listed in the country response.
    try:
        data = await asyncio.to_thread(search_person_or_hero, query)
        if data and data.get("extract"):
            translated = await asyncio.to_thread(
                translate_to_burmese, data["extract"][:3000]
            )
            title = data.get("title", query)
            await send_long_text(
                message,
                f"🛡️ {title}\n\n{translated}\n\n"
                "🔎 အချက်အလက်ရင်းမြစ်: Wikipedia"
            )
            return
    except Exception:
        logger.exception("Wikipedia person search failed")

    # Fourth: search locally stored movies.
    try:
        if await search_movie(update, query):
            return
    except Exception:
        logger.exception("Movie search handler failed")

    # Finally: give official storefront/search links instead of claiming that
    # every game can be downloaded directly. Store links are not direct files.
    links = game_store_links(query)
    await message.reply_text(
        f"🎮 ‘{query}’ အတွက် Bot က တိုက်ရိုက်ပို့နိုင်တဲ့ အများပြည်သူရရှိနိုင်သော release ဖိုင်ကို မတွေ့ပါ။\n\n"
        "အောက်ပါ မူရင်း/တရားဝင်ရှာဖွေရေးလင့်ခ်တွေကို စမ်းကြည့်ပါ။\n"
        "ဂိမ်းတိုင်းမှာ အခမဲ့ဒေါင်းလုဒ်ဖိုင် ရှိမယ်လို့ မအာမခံနိုင်ပါ။\n\n"
        + "\n".join(f"• {label}: {url}" for label, url in links)
    )


# ------------------------- Error handler -------------------

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(
        "Unhandled Telegram error",
        exc_info=(type(context.error), context.error, context.error.__traceback__)
        if context.error else None,
    )


async def post_init(application: Application):
    # Application.create_task keeps the scheduler tied to Telegram application's lifecycle.
    application.create_task(news_scheduler(application), name="burmese_news_scheduler")


# ---------------------------- Main -------------------------

def main():
    if not TOKEN:
        raise RuntimeError(
            "BOT_TOKEN မရှိပါ။ Railway -> Variables ထဲတွင် BOT_TOKEN ထည့်ပါ။"
        )

    init_db()
    app = Application.builder().token(TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("news", news_command))
    app.add_handler(CommandHandler("game", game_command))
    app.add_handler(CallbackQueryHandler(check_channel_join_callback, pattern="^check_channel_join$"))
    app.add_handler(
        MessageHandler(filters.VIDEO | filters.Document.ALL, save_movie)
    )
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    app.add_error_handler(error_handler)

    logger.info("Ck_helpbot is starting")
    app.run_polling(
        drop_pending_updates=False,
        allowed_updates=Update.ALL_TYPES,
    )


if __name__ == "__main__":
    main()
