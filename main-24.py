import os
import re
import sqlite3
import logging
import asyncio
import hashlib
import html
import time
from collections import defaultdict, deque
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
NEWS_CHANNEL_IDS = [x.strip() for x in os.getenv("NEWS_CHANNEL_IDS", "").split(",") if x.strip()]
if NEWS_CHANNEL_ID and NEWS_CHANNEL_ID not in NEWS_CHANNEL_IDS:
    NEWS_CHANNEL_IDS.insert(0, NEWS_CHANNEL_ID)
NEWS_TIMEZONE = ZoneInfo("Asia/Yangon")
NEWS_DAILY_HOUR = int(os.getenv("NEWS_DAILY_HOUR", "7"))  # Myanmar time
NEWS_CHECK_MINUTES = max(5, int(os.getenv("NEWS_CHECK_MINUTES", "15")))
# Optional self-hosted Telegram Local Bot API server. Required for files >50 MB.
TELEGRAM_API_BASE_URL = os.getenv("TELEGRAM_API_BASE_URL", "").strip()
TELEGRAM_FILE_BASE_URL = os.getenv("TELEGRAM_FILE_BASE_URL", "").strip()
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", "/tmp/ck_downloads"))
# Telegram Local Bot API accepts up to 2000 MB per upload; send larger assets as parts.
MAX_APP_DOWNLOAD_BYTES = int(os.getenv("MAX_APP_DOWNLOAD_GB", "20")) * 1024**3
TELEGRAM_PART_BYTES = 1900 * 1024 * 1024
SPAM_WINDOW_SECONDS = int(os.getenv("SPAM_WINDOW_SECONDS", "10"))
SPAM_MAX_MESSAGES = int(os.getenv("SPAM_MAX_MESSAGES", "8"))
# Consent-based anonymous chat sessions are in-memory; restart clears active pairings.
CHAT_WAITING = deque()
CHAT_PAIRS = {}
USER_MESSAGE_TIMES = defaultdict(deque)

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
        # Additive tables: keep the existing movie/news data untouched.
        db.execute("""CREATE TABLE IF NOT EXISTS social_users (
            user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
            joined_at TEXT NOT NULL, points INTEGER NOT NULL DEFAULT 0,
            referred_by INTEGER, is_banned INTEGER NOT NULL DEFAULT 0
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS referrals (
            referrer_id INTEGER NOT NULL, referred_id INTEGER NOT NULL UNIQUE,
            created_at TEXT NOT NULL, PRIMARY KEY(referrer_id, referred_id)
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS user_blocks (
            user_id INTEGER PRIMARY KEY, blocked_at TEXT NOT NULL
        )""")
        # Group/channel tools; per-chat settings and warning counts persist in SQLite.
        db.execute("""CREATE TABLE IF NOT EXISTS chat_settings (
            chat_id INTEGER PRIMARY KEY, rules TEXT NOT NULL DEFAULT '', welcome TEXT NOT NULL DEFAULT ''
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS chat_warnings (
            chat_id INTEGER NOT NULL, user_id INTEGER NOT NULL, count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(chat_id, user_id)
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS user_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER NOT NULL,
            reporter_id INTEGER NOT NULL, reported_user_id INTEGER,
            message_excerpt TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
        )""")
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
    for channel_id in NEWS_CHANNEL_IDS:
        try:
            await application.bot.send_message(
                chat_id=channel_id, text=text, disable_web_page_preview=True
            )
        except Exception as exc:
            logger.warning('News channel delivery failed for %s: %s', channel_id, exc)
    if not recipients and not NEWS_CHANNEL_IDS:
        logger.info('No news recipients configured yet; use /start and set NEWS_CHANNEL_ID(S).')


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
        now = datetime.now(NEWS_TIMEZONE).isoformat()
        referrer = None
        if context.args and context.args[0].startswith("ref_"):
            try:
                candidate = int(context.args[0][4:])
                if candidate != user.id:
                    referrer = candidate
            except ValueError:
                pass
        with sqlite3.connect(DB_PATH, timeout=30) as db:
            db.execute("INSERT OR IGNORE INTO news_subscribers(user_id, added_at) VALUES(?, ?)", (user.id, now))
            db.execute("""INSERT INTO social_users(user_id, username, first_name, joined_at, referred_by)
                VALUES(?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username, first_name=excluded.first_name""",
                (user.id, user.username, user.first_name or "", now, referrer))
            if referrer:
                inserted = db.execute("INSERT OR IGNORE INTO referrals(referrer_id,referred_id,created_at) VALUES(?,?,?)",
                                      (referrer, user.id, now)).rowcount
                if inserted:
                    db.execute("UPDATE social_users SET points=points+10 WHERE user_id=? AND is_banned=0", (referrer,))
                    db.execute("UPDATE social_users SET points=points+3 WHERE user_id=? AND is_banned=0", (user.id,))
            db.commit()
    await update.effective_message.reply_text(
        "🤖 Ck_helpbot All-in-One Social Bot မှ ကြိုဆိုပါတယ်။\n\n"
        "🌍 နိုင်ငံ/အချက်အလက်ရှာရန် အမည်ကို ရိုက်ပါ။\n"
        "🎮 /game အမည်  သို့မဟုတ်  /app အမည် — အများပြည်သူရရှိနိုင်သော App/Game release ရှာရန်\n"
        "📰 /news — Daily/Breaking News စနစ်\n"
        "🤖 /ask မေးခွန်း — အခမဲ့ AI (ပြင်ပ free service အသုံးပြုသည်)\n"
        "💬 /chat — သဘောတူညီမှုဖြင့် အမည်မဖော်သော chat ရှာရန်; /next /stop ဖြင့် ထိန်းချုပ်ရန်\n"
        "⭐ /points /leaderboard /referral — Points နှင့် မိတ်ဆွေဖိတ်ခေါ်မှု\n"
        "📖 /help — Command အားလုံး"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    await update.effective_message.reply_text(
        "📖 Ck_helpbot အသုံးပြုနည်း\n\n"
        "/start — စတင်အသုံးပြုရန်\n/news — သတင်းအချိန်ဇယား\n"
        "/app အမည်၊ /game အမည် — public release App/Game ရှာရန်\n"
        "/ask မေးခွန်း — အခမဲ့ AI (ပြင်ပ free service အသုံးပြုသည်)\n"
        "/chat — အမည်မဖော်သော chat ကို စတင်/ရှာရန်; /next — နောက်တစ်ယောက်; /stop — ရပ်ရန်\n"
        "/points — ကိုယ့် points; /leaderboard — အမှတ်အများဆုံး; /referral — ဖိတ်ခေါ်လင့်ခ်\n"
        "/poll မေးခွန်း | ရွေးချယ်မှု ၁ | ရွေးချယ်မှု ၂ — မဲပေးမှုဖန်တီးရန်\n"
        "/report — reply လုပ်ထားသောစာကို Admin ထံတိုင်ကြားရန်\n"
        "/grouphelp — Group/Channel စီမံခန့်ခွဲမှု command များ\n"
        "/admin — Admin help (Admin only)\n\n"
        "🛡️ Chat သည် သဘောတူညီမှုဖြင့်သာ ချိတ်ဆက်ပြီး Telegram username/ID ကို တစ်ဖက်လူထံ မဖော်ပြပါ။ "
        "Spam သို့မဟုတ် မသင့်လျော်သောအပြုအမူရှိပါက /stop နှင့် report လုပ်နိုင်သည်။\n"
        "📦 ဖိုင်ကြီးများအတွက် Railway storage နှင့် Telegram Local Bot API server ကို သီးခြားစီစဉ်ရနိုင်သည်။"
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

GAME_ASSET_EXTENSIONS = (".apk", ".xapk", ".apks", ".aab", ".zip", ".7z", ".tar.gz", ".tar.xz", ".tgz", ".rar")
MAX_GAME_DOWNLOAD_BYTES = MAX_APP_DOWNLOAD_BYTES


def game_store_links(query):
    """Official storefront/search pages used when no downloadable release exists."""
    q = quote(query.strip(), safe="")
    return [
        ("Google Play (Android)", f"https://play.google.com/store/search?q={q}&c=apps"),
        ("F-Droid (open-source Android apps)", f"https://search.f-droid.org/?q={q}"),
        ("GitHub public releases", f"https://github.com/search?q={q}+apk&type=repositories"),
    ]


def search_github_game(query):
    """Search public GitHub releases for downloadable app/game assets.

    This intentionally limits discovery to public GitHub release assets and does
    not scrape paid/pirated APK sites or bypass login/anti-bot protections.
    """
    query = query.strip()
    if not query or len(query) > 100:
        return []
    data = get_json(
        "https://api.github.com/search/repositories",
        params={"q": f'{query} in:name fork:false', "sort": "stars", "order": "desc", "per_page": 15},
    )
    repos = (data or {}).get("items", [])
    results = []
    query_terms = [part.casefold() for part in re.findall(r"[\w+-]+", query) if len(part) > 1]
    for repo in repos:
        full_name = repo.get("full_name", "")
        repo_name = (repo.get("name") or "").replace("-", " ").replace("_", " ").casefold()
        repo_description = (repo.get("description") or "").casefold()
        if query_terms and not all(term in repo_name for term in query_terms):
            if not all(term in repo_description for term in query_terms):
                continue
        release_data = get_json(f"https://api.github.com/repos/{full_name}/releases/latest")
        if not isinstance(release_data, dict) or not release_data.get("html_url"):
            continue
        assets = []
        for asset in release_data.get("assets", []):
            name = (asset.get("name") or "").casefold()
            size = int(asset.get("size") or 0)
            url = asset.get("browser_download_url") or ""
            if (name.endswith(GAME_ASSET_EXTENSIONS) and 0 < size <= MAX_GAME_DOWNLOAD_BYTES
                    and url.startswith("https://github.com/")):
                assets.append({"name": asset.get("name"), "size": size, "url": url})
        if assets:
            assets.sort(key=lambda a: (not a["name"].lower().endswith((".apk", ".xapk", ".apks")), -a["size"]))
        results.append({
            "name": repo.get("name") or full_name,
            "description": repo.get("description") or "Public release project",
            "repo_url": repo.get("html_url") or "",
            "release_url": release_data.get("html_url"),
            "assets": assets,
            "stars": repo.get("stargazers_count", 0),
        })
        if assets and len(results) >= 3:
            break
    return results


def download_github_asset(asset_url, destination, expected_size=0):
    """Stream a bounded public GitHub release asset to disk."""
    if not asset_url.startswith("https://github.com/"):
        raise ValueError("Unsupported download host")
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    with requests.get(asset_url, headers=HEADERS, timeout=(15, 60), stream=True, allow_redirects=True) as response:
        response.raise_for_status()
        final_host = urlparse(response.url).hostname or ""
        if final_host not in ("github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com"):
            raise ValueError("Unexpected download host")
        length = int(response.headers.get("Content-Length", "0") or 0)
        if length > MAX_GAME_DOWNLOAD_BYTES or (expected_size and expected_size > MAX_GAME_DOWNLOAD_BYTES):
            raise ValueError("File exceeds configured download limit")
        with open(destination, "wb") as out:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                written += len(chunk)
                if written > MAX_GAME_DOWNLOAD_BYTES:
                    raise ValueError("File exceeds configured download limit")
                out.write(chunk)
    if written == 0:
        raise ValueError("Empty download")
    return written


def split_file(path, part_size=TELEGRAM_PART_BYTES):
    """Split a downloaded file into Telegram-uploadable parts, if needed."""
    size = os.path.getsize(path)
    if size <= part_size:
        return [path]
    parts = []
    with open(path, "rb") as source:
        index = 1
        while True:
            chunk = source.read(part_size)
            if not chunk:
                break
            part_path = f"{path}.part{index:03d}"
            with open(part_path, "wb") as out:
                out.write(chunk)
            parts.append(part_path)
            index += 1
    return parts


async def search_game(update: Update, query: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Search public app/game release assets and send the file (or numbered parts)."""
    message = update.effective_message
    if not message:
        return False
    try:
        results = await asyncio.to_thread(search_github_game, query)
    except Exception:
        logger.exception("App/game search failed")
        return False
    candidate = next((g for g in results if g.get("assets")), None)
    if not candidate:
        return False
    asset = candidate["assets"][0]
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    import tempfile
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", asset["name"])[:80] or "download.bin"
    fd, temp_path = tempfile.mkstemp(prefix="ck_", suffix="_" + safe_name, dir=str(DOWNLOAD_DIR))
    os.close(fd)
    parts = []
    try:
        await message.reply_text(f"🔎 {candidate['name']} ဖိုင်ကို ရှာတွေ့ပါပြီ။\n📦 အရွယ်အစား: {asset['size'] / (1024**2):.1f} MB\n⬇️ ဒေါင်းလုဒ်လုပ်နေပါတယ်…")
        await asyncio.to_thread(download_github_asset, asset["url"], temp_path, asset["size"])
        parts = await asyncio.to_thread(split_file, temp_path)
        if len(parts) > 1:
            await message.reply_text(f"ဖိုင်ကြီးဖြစ်သောကြောင့် {len(parts)} ပိုင်းခွဲပို့ပါမယ်။ ပြန်ပေါင်းရန် part001, part002… အစဉ်လိုက်ပေါင်းပါ။")
        for i, part_path in enumerate(parts, 1):
            filename = Path(asset["name"]).name
            caption = f"📦 {candidate['name']}\nဖိုင်ပိုင်း {i}/{len(parts)}\nမူရင်း Release: {candidate['release_url']}"[:1000]
            with open(part_path, "rb") as f:
                await message.reply_document(
                    document=f,
                    filename=(filename if len(parts) == 1 else f"{filename}.part{i:03d}"),
                    caption=caption,
                    read_timeout=180,
                    write_timeout=180,
                    connect_timeout=30,
                    pool_timeout=30,
                )
        return True
    except Exception as exc:
        logger.warning("App/game download/send failed: %s", exc)
        await message.reply_text(
            "ဖိုင်ကို Telegram ထဲ တိုက်ရိုက်ပို့မအောင်မြင်ပါ။ Railway မှာ Local Bot API Server ချိတ်ထားပြီးသားလား စစ်ပါ။\n"
            f"မူရင်း Release: {candidate['release_url']}"
        )
        return True
    finally:
        for part_path in parts:
            if part_path != temp_path and os.path.exists(part_path):
                try: os.remove(part_path)
                except OSError: pass
        if os.path.exists(temp_path):
            try: os.remove(temp_path)
            except OSError: pass


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
        found = await search_game(update, query, context)
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
    if await handle_social_text(update, context):
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
        if await search_game(update, query, context):
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
        f"📦 ‘{query}’ အတွက် Bot က တိုက်ရိုက်ပို့နိုင်တဲ့ အများပြည်သူရရှိနိုင်သော release ဖိုင်ကို မတွေ့ပါ။\n\n"
        "အောက်ပါ မူရင်း/တရားဝင်ရှာဖွေရေးလင့်ခ်တွေကို စမ်းကြည့်ပါ။\n"
        "ဂိမ်းတိုင်းမှာ အခမဲ့ဒေါင်းလုဒ်ဖိုင် ရှိမယ်လို့ မအာမခံနိုင်ပါ။\n\n"
        + "\n".join(f"• {label}: {url}" for label, url in links)
    )


# --------------------- Social / AI / Admin features ---------------------

def is_banned(user_id: int) -> bool:
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        row = db.execute("SELECT is_banned FROM social_users WHERE user_id=?", (user_id,)).fetchone()
    return bool(row and row[0])


def register_social_user(user):
    if not user:
        return
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        db.execute("""INSERT INTO social_users(user_id,username,first_name,joined_at)
            VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET
            username=excluded.username, first_name=excluded.first_name""",
            (user.id, user.username, user.first_name or "", datetime.now(NEWS_TIMEZONE).isoformat()))
        db.commit()


def admin_only(user) -> bool:
    return bool(user and user.id in ADMIN_IDS)


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Public help: private users can view available commands; group commands are gated."""
    await update.effective_message.reply_text(
        "📖 Ck_helpbot Commands\n"
        "/start — စတင်အသုံးပြုရန်\n"
        "/news — သတင်းအချိန်ဇယား/သတင်းစာရင်း\n"
        "/app အမည်၊ /game အမည် — public release ရှာရန်\n"
        "/ask မေးခွန်း — အခမဲ့ AI\n"
        "/chat, /next, /stop — အမည်မဖော်သော chat\n"
        "/points, /leaderboard, /referral — points နှင့် referral\n"
        "/rules, /grouphelp — Group tools\n"
        "/poll မေးခွန်း | ရွေးချယ်မှု ၁ | ရွေးချယ်မှု ၂ — မဲပေးမှု\n"
        "/report — မသင့်လျော်သောအကြောင်းအရာ တိုင်ကြားရန်\n"
        "/stats — ကိုယ်ပိုင်စာရင်း/Group Admin စာရင်း\n"
        "/ban USER_ID, /unban USER_ID — Bot ပိုင်ရှင်သာ\n"
        "/broadcast စာသား — Bot ပိုင်ရှင်သာ\n\n"
        "🛡️ Private chat တွင် ပုံမှန် command များကို အသုံးပြုနိုင်ပါတယ်။ Group/Supergroup ထဲတွင် command အသုံးပြုသူသည် Group Admin သို့မဟုတ် Owner ဖြစ်ရပါမယ်။\n"
        "📣 /broadcast, /ban, /unban တို့ကို Bot ပိုင်ရှင်/Admin ID သတ်မှတ်ထားသူများသာ အသုံးပြုနိုင်ပါတယ်။"
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    # Private chat: show only the caller's own data to protect user privacy.
    if chat and chat.type == "private" and user and not admin_only(user):
        register_social_user(user)
        with sqlite3.connect(DB_PATH, timeout=30) as db:
            row = db.execute("SELECT points, is_banned, joined_at FROM social_users WHERE user_id=?", (user.id,)).fetchone()
            referrals = db.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (user.id,)).fetchone()[0]
        await update.effective_message.reply_text(
            f"📊 သင့်စာရင်း\nPoints: {row[0] if row else 0}\n"
            f"Referral: {referrals}\nBot အသုံးပြုခွင့်: {'ပိတ်ထားသည်' if row and row[1] else 'ဖွင့်ထားသည်'}"
        )
        return
    # In groups, group owners/admins may view statistics; in private, global admins may too.
    if chat and chat.type in ("group", "supergroup") and not await _is_chat_admin(update, context):
        await update.effective_message.reply_text("⛔ Group Admin/Owner သာ အသုံးပြုနိုင်ပါတယ်။")
        return
    if chat and chat.type == "private" and not admin_only(user):
        await update.effective_message.reply_text("ကိုယ်ပိုင်စာရင်းကိုသာ ပြသနိုင်ပါတယ်။")
        return
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        users = db.execute("SELECT COUNT(*) FROM social_users").fetchone()[0]
        subscribers = db.execute("SELECT COUNT(*) FROM news_subscribers").fetchone()[0]
        banned = db.execute("SELECT COUNT(*) FROM social_users WHERE is_banned=1").fetchone()[0]
        points = db.execute("SELECT COALESCE(SUM(points),0) FROM social_users").fetchone()[0]
    await update.effective_message.reply_text(f"📊 Ck_helpbot Stats\nUsers: {users}\nNews subscribers: {subscribers}\nBanned: {banned}\nTotal points: {points}")


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin_only(update.effective_user):
        await update.effective_message.reply_text("⛔ Admin သာ အသုံးပြုနိုင်ပါတယ်။")
        return
    text = " ".join(context.args).strip()
    if not text and update.effective_message.reply_to_message:
        text = update.effective_message.reply_to_message.text or update.effective_message.reply_to_message.caption or ""
    if not text:
        await update.effective_message.reply_text("အသုံးပြုပုံ: /broadcast ပို့လိုသောစာသား")
        return
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        ids = [row[0] for row in db.execute("SELECT user_id FROM news_subscribers").fetchall()]
    sent = failed = 0
    for uid in ids:
        try:
            await context.bot.send_message(chat_id=uid, text=text[:4000])
            sent += 1
        except Exception as exc:
            failed += 1
            logger.info("Broadcast to %s failed: %s", uid, exc)
        await asyncio.sleep(0.04)
    await update.effective_message.reply_text(f"📣 Broadcast ပြီးပါပြီ။ အောင်မြင်: {sent}၊ မအောင်မြင်: {failed}")


async def set_ban(update: Update, context: ContextTypes.DEFAULT_TYPE, banned: bool):
    chat = update.effective_chat
    actor = update.effective_user
    msg = update.effective_message
    args = list(context.args or [])

    # Prefer the replied-to member; allow USER_ID as a fallback.
    target = msg.reply_to_message.from_user if msg and msg.reply_to_message else None
    if target is None and msg and msg.reply_to_message and msg.reply_to_message.sender_chat:
        await msg.reply_text("ဒီ message က Channel/Anonymous Admin က ပို့ထားတာဖြစ်လို့ User ID မရနိုင်ပါ။")
        return
    if target is not None:
        uid = target.id
    elif args and args[0].isdigit():
        uid = int(args[0])
    else:
        await msg.reply_text(
            "အသုံးပြုပုံ: အသုံးပြုသူ message ကို Reply လုပ်ပြီး /ban သို့ /unban ပို့ပါ။\n"
            "သို့မဟုတ် /ban USER_ID /unban USER_ID ကို သုံးပါ။"
        )
        return

    # In groups, group admins can ban/unban members in that group only.
    if chat and chat.type in ("group", "supergroup"):
        if not await _is_chat_admin(update, context):
            await msg.reply_text("⛔ Group Admin/Owner သာ အသုံးပြုနိုင်ပါတယ်။")
            return
        if uid == (actor.id if actor else None):
            await msg.reply_text("ကိုယ့်ကိုယ်ကို Ban/Unban လုပ်ဖို့ မလိုပါ။")
            return
        try:
            if banned:
                await context.bot.ban_chat_member(chat_id=chat.id, user_id=uid)
                notice = f"🚫 {target.first_name if target else uid} ကို ဒီ Group မှ ban လုပ်ပြီးပါပြီ။"
            else:
                await context.bot.unban_chat_member(chat_id=chat.id, user_id=uid, only_if_banned=True)
                notice = f"✅ {target.first_name if target else uid} ကို ဒီ Group မှ unban လုပ်ပြီးပါပြီ။"
            await msg.reply_text(notice)
        except Exception as exc:
            await msg.reply_text(f"မအောင်မြင်ပါ။ Bot ကို Ban Users ခွင့်ပြုချက်ပါသော Admin အဖြစ် ထည့်ထားပါ။ ({str(exc)[:120]})")
        return

    # In private chat, global bot access bans remain restricted to configured bot admins.
    if not admin_only(actor):
        await msg.reply_text("⛔ Bot ပိုင်ရှင်/Admin သာ private chat မှ global ban/unban လုပ်နိုင်ပါတယ်။ Group ထဲတွင် Group Admin အခွင့်အရေးကို အသုံးပြုပါ။")
        return
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        db.execute("INSERT OR IGNORE INTO social_users(user_id,joined_at) VALUES(?,?)", (uid, datetime.now(NEWS_TIMEZONE).isoformat()))
        db.execute("UPDATE social_users SET is_banned=? WHERE user_id=?", (int(banned), uid))
        db.commit()
    await msg.reply_text(("🚫 Bot အသုံးပြုခွင့်ပိတ်ပြီးပါပြီ။" if banned else "✅ Bot အသုံးပြုခွင့် ပြန်ဖွင့်ပြီးပါပြီ။"))


async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_ban(update, context, True)


async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_ban(update, context, False)


async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Use the no-key Pollinations Classic text endpoint; AI is optional to the rest of the bot."""
    msg = update.effective_message
    prompt = " ".join(context.args).strip()
    if not prompt:
        await msg.reply_text("အသုံးပြုပုံ: /ask မေးလိုသောမေးခွန်း")
        return
    if is_banned(update.effective_user.id):
        await msg.reply_text("⛔ Bot အသုံးပြုခွင့် ပိတ်ထားပါတယ်။")
        return
    # Keep request URLs modest and avoid sending excessive user text to the external provider.
    prompt = prompt[:1200]
    full_prompt = (
        "You are Ck_helpbot, a helpful assistant. Reply in Burmese when the user writes Burmese. "
        "Keep answers safe and concise. User question: " + prompt
    )
    try:
        response = await asyncio.to_thread(
            requests.get,
            "https://text.pollinations.ai/" + quote(full_prompt, safe=""),
            headers=HEADERS,
            timeout=45,
        )
        response.raise_for_status()
        answer = response.text.strip()
        if not answer:
            raise ValueError("Empty AI response")
        for i in range(0, len(answer), 3900):
            await msg.reply_text(answer[i:i+3900])
    except Exception:
        logger.exception("Free AI request failed")
        await msg.reply_text(
            "⚠️ အခမဲ့ AI ဝန်ဆောင်မှုကို ယခုခဏ ခေါ်မရပါ။ နောက်မှ ပြန်စမ်းပါ။ "
            "News နဲ့ App/Game ရှာဖွေမှုတွေကိုတော့ ပုံမှန်ဆက်သုံးနိုင်ပါတယ်။"
        )


async def points_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_social_user(user)
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        row = db.execute("SELECT points FROM social_users WHERE user_id=?", (user.id,)).fetchone()
    await update.effective_message.reply_text(f"⭐ သင့် Points: {row[0] if row else 0}")


async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        rows = db.execute("SELECT first_name, points FROM social_users WHERE is_banned=0 ORDER BY points DESC, joined_at ASC LIMIT 10").fetchall()
    if not rows:
        await update.effective_message.reply_text("Leaderboard မရှိသေးပါ။")
        return
    lines = [f"{i}. {(name or 'User')[:30]} — ⭐ {points}" for i, (name, points) in enumerate(rows, 1)]
    await update.effective_message.reply_text("🏆 Leaderboard\n\n" + "\n".join(lines))


async def referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    me = await context.bot.get_me()
    link = f"https://t.me/{me.username}?start=ref_{user.id}"
    await update.effective_message.reply_text("🔗 သင့်ဖိတ်ခေါ်လင့်ခ်:\n" + link + "\n\nမိတ်ဆွေတစ်ဦး စတင်ဝင်ရောက်လျှင် သင့်ကို 10 points ပေးပါမယ်။")


async def chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = update.effective_message
    if not user or msg.chat.type != "private":
        await msg.reply_text("Anonymous Chat ကို Bot private chat မှာပဲ သုံးပါ။")
        return
    if is_banned(user.id):
        await msg.reply_text("⛔ Bot အသုံးပြုခွင့် ပိတ်ထားပါတယ်။")
        return
    register_social_user(user)
    if user.id in CHAT_PAIRS:
        await msg.reply_text("သင် chat partner တစ်ယောက်နဲ့ ချိတ်ဆက်ပြီးသားပါ။ /stop သို့ /next သုံးနိုင်ပါတယ်။")
        return
    while CHAT_WAITING:
        partner = CHAT_WAITING.popleft()
        if partner != user.id and partner not in CHAT_PAIRS:
            CHAT_PAIRS[user.id] = partner
            CHAT_PAIRS[partner] = user.id
            try:
                await context.bot.send_message(partner, "💬 Partner တွေ့ပါပြီ။ စာရိုက်ပို့ပါ။ /next နဲ့ နောက်တစ်ယောက်၊ /stop နဲ့ ရပ်နိုင်ပါတယ်။")
                await msg.reply_text("💬 Partner တွေ့ပါပြီ။ စာရိုက်ပို့ပါ။ /next နဲ့ နောက်တစ်ယောက်၊ /stop နဲ့ ရပ်နိုင်ပါတယ်။")
            except Exception:
                CHAT_PAIRS.pop(user.id, None); CHAT_PAIRS.pop(partner, None)
                await msg.reply_text("Partner ချိတ်ဆက်မှု မအောင်မြင်ပါ။ /chat ပြန်စမ်းပါ။")
            return
    if user.id not in CHAT_WAITING:
        CHAT_WAITING.append(user.id)
    await msg.reply_text("🔎 Partner ရှာနေပါတယ်။ ရပ်လိုပါက /stop နှိပ်ပါ။")


async def stop_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = update.effective_message
    if not user:
        return
    partner = CHAT_PAIRS.pop(user.id, None)
    if user.id in CHAT_WAITING:
        try: CHAT_WAITING.remove(user.id)
        except ValueError: pass
    if partner:
        CHAT_PAIRS.pop(partner, None)
        try: await context.bot.send_message(partner, "ℹ️ တစ်ဖက်လူက chat ကို ရပ်လိုက်ပါတယ်။ /chat နဲ့ partner အသစ်ရှာနိုင်ပါတယ်။")
        except Exception: pass
    await msg.reply_text("🛑 Chat ရပ်လိုက်ပါပြီ။")


async def next_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await stop_chat(update, context)
    await chat_command(update, context)


async def referral_link_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await referral_command(update, context)


async def handle_social_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Return True if consumed by anonymous chat or spam guard."""
    user = update.effective_user
    msg = update.effective_message
    if not user or not msg or not msg.text or msg.text.startswith("/"):
        return False
    if is_banned(user.id):
        await msg.reply_text("⛔ Bot အသုံးပြုခွင့် ပိတ်ထားပါတယ်။")
        return True
    now = time.monotonic()
    bucket = USER_MESSAGE_TIMES[user.id]
    while bucket and now - bucket[0] > SPAM_WINDOW_SECONDS:
        bucket.popleft()
    bucket.append(now)
    if len(bucket) > SPAM_MAX_MESSAGES:
        await msg.reply_text("🛡️ စာပို့နှုန်းများလွန်းနေပါတယ်။ ခဏစောင့်ပြီး ပြန်စမ်းပါ။")
        return True
    partner = CHAT_PAIRS.get(user.id)
    if partner:
        try:
            await context.bot.send_message(partner, msg.text[:4000])
            with sqlite3.connect(DB_PATH, timeout=30) as db:
                db.execute("UPDATE social_users SET points=points+1 WHERE user_id=? AND is_banned=0", (user.id,))
                db.commit()
        except Exception:
            logger.exception("Anonymous chat relay failed")
            await msg.reply_text("⚠️ စာပို့မရပါ။ /next သို့ /stop သုံးနိုင်ပါတယ်။")
        return True
    # Award a small daily-use point with a basic spam limit.
    register_social_user(user)
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        db.execute("UPDATE social_users SET points=points+1 WHERE user_id=? AND is_banned=0", (user.id,))
        db.commit()
    return False


# ---------------------- Polls and reports ----------------------

async def poll_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create a Telegram-native poll: /poll question | option 1 | option 2."""
    msg = update.effective_message
    chat = update.effective_chat
    if not msg or not chat:
        return
    raw = " ".join(context.args).strip()
    parts = [part.strip() for part in raw.split("|") if part.strip()]
    if len(parts) < 3 or len(parts) > 11:
        await msg.reply_text(
            "အသုံးပြုပုံ: /poll မေးခွန်း | ရွေးချယ်မှု ၁ | ရွေးချယ်မှု ၂\n"
            "မေးခွန်း ၁ ခုနှင့် ရွေးချယ်မှု ၂ ခုမှ ၁၀ ခုအထိ ထည့်ပါ။"
        )
        return
    question, options = parts[0][:300], [x[:100] for x in parts[1:]]
    try:
        await context.bot.send_poll(
            chat_id=chat.id, question=question, options=options,
            is_anonymous=True, allows_multiple_answers=False,
        )
    except Exception as exc:
        logger.exception("Poll creation failed")
        await msg.reply_text(
            "မဲပေးမှု မဖန်တီးနိုင်ပါ။ Channel တွင်ဆို Bot ကို Admin ထည့်ထားပါ။ "
            f"အမှား: {str(exc)[:120]}"
        )


async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    reporter = update.effective_user
    if not msg or not chat or not reporter:
        return
    target_msg = msg.reply_to_message
    if not target_msg:
        await msg.reply_text("တိုင်ကြားလိုသောစာကို Reply လုပ်ပြီး /report အကြောင်းပြချက် လို့ရေးပါ။")
        return
    target_user = target_msg.from_user
    reason = " ".join(context.args).strip()[:300]
    excerpt = (target_msg.text or target_msg.caption or "[စာသားမဟုတ်သော message]")[:500]
    created = datetime.now(NEWS_TIMEZONE).isoformat()
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        db.execute(
            "INSERT INTO user_reports(chat_id,reporter_id,reported_user_id,message_excerpt,created_at) VALUES(?,?,?,?,?)",
            (chat.id, reporter.id, target_user.id if target_user else None, excerpt, created),
        )
        db.commit()
        report_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    await msg.reply_text(f"✅ Report #{report_id} ကို Admin ထံ ပေးပို့ရန် မှတ်တမ်းတင်ပြီးပါပြီ။")
    admin_text = (
        f"🚨 Ck_helpbot Report #{report_id}\n"
        f"Chat: {chat.title or chat.full_name or chat.id} ({chat.id})\n"
        f"Reporter: {reporter.full_name} (ID {reporter.id})\n"
        f"Reported user: {(target_user.full_name + ' (ID ' + str(target_user.id) + ')') if target_user else 'unknown'}\n"
        f"Reason: {reason or 'မဖော်ပြထားပါ'}\n"
        f"Message: {excerpt}"
    )
    delivered = 0
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=admin_text[:3900])
            delivered += 1
        except Exception:
            logger.warning("Could not deliver report to admin %s", admin_id)
    if not delivered:
        logger.warning("Report #%s saved but no admin DM delivery succeeded", report_id)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg:
        return
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        users = db.execute("SELECT COUNT(*) FROM social_users").fetchone()[0]
        reports = db.execute("SELECT COUNT(*) FROM user_reports").fetchone()[0]
        subscribers = db.execute("SELECT COUNT(*) FROM news_subscribers").fetchone()[0]
    await msg.reply_text(
        "🟢 Ck_helpbot status: online\n"
        f"👥 Registered users: {users}\n📰 News subscribers: {subscribers}\n"
        f"🚩 Reports recorded: {reports}\n🗄️ Database: SQLite ({DB_PATH})"
    )


# ---------------------- Group & channel tools ----------------------

async def _is_chat_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return False
    if user.id in ADMIN_IDS:
        return True
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False

async def group_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "👥 Group/Channel Tools\n"
        "/rules — စည်းမျဉ်းကြည့်ရန်\n"
        "/setrules စာသား — စည်းမျဉ်းသတ်မှတ်ရန် (Admin)\n"
        "/setwelcome စာသား — အဖွဲ့ဝင်အသစ် ကြိုဆိုစာ (Admin)\n"
        "/warn ကို reply လုပ်ပြီး သတိပေးရန် (Admin)\n"
        "/mute ကို reply လုပ်ပြီး 10m/2h/1d (Admin)\n"
        "/unmute ကို reply လုပ်ပြီး အသံပြန်ဖွင့်ရန် (Admin)\n"
        "/pin ကို reply လုပ်ပြီး pin လုပ်ရန် (Admin)\n"
        "/purge ကို reply လုပ်ပြီး 1-50 စာ ဖျက်ရန် (Admin)\n"
        "/id — Chat/User ID ကြည့်ရန်"
    )

async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        row = db.execute("SELECT rules FROM chat_settings WHERE chat_id=?", (chat.id,)).fetchone()
    await update.effective_message.reply_text((row[0] if row and row[0] else "ဒီအဖွဲ့အတွက် စည်းမျဉ်း မသတ်မှတ်ရသေးပါ။")[:4000])

async def setrules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_chat_admin(update, context):
        await update.effective_message.reply_text("Admin များသာ အသုံးပြုနိုင်ပါတယ်။"); return
    value = " ".join(context.args).strip()[:3500]
    if not value:
        await update.effective_message.reply_text("အသုံးပြုပုံ: /setrules စည်းမျဉ်းစာသား"); return
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        db.execute("INSERT INTO chat_settings(chat_id,rules) VALUES(?,?) ON CONFLICT(chat_id) DO UPDATE SET rules=excluded.rules", (update.effective_chat.id, value)); db.commit()
    await update.effective_message.reply_text("✅ Group စည်းမျဉ်း သိမ်းပြီးပါပြီ။ /rules နဲ့ ကြည့်နိုင်ပါတယ်။")

async def setwelcome_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_chat_admin(update, context):
        await update.effective_message.reply_text("Admin များသာ အသုံးပြုနိုင်ပါတယ်။"); return
    value = " ".join(context.args).strip()[:1000]
    if not value:
        await update.effective_message.reply_text("အသုံးပြုပုံ: /setwelcome မင်္ဂလာပါ {name}"); return
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        db.execute("INSERT INTO chat_settings(chat_id,welcome) VALUES(?,?) ON CONFLICT(chat_id) DO UPDATE SET welcome=excluded.welcome", (update.effective_chat.id, value)); db.commit()
    await update.effective_message.reply_text("✅ ကြိုဆိုစာ သိမ်းပြီးပါပြီ။ {name} ကို နာမည်နဲ့ အစားထိုးပေးပါမယ်။")

async def welcome_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.new_chat_members: return
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        row = db.execute("SELECT welcome FROM chat_settings WHERE chat_id=?", (update.effective_chat.id,)).fetchone()
    template = row[0] if row and row[0] else "မင်္ဂလာပါ {name} 🎉 Group မှ ကြိုဆိုပါတယ်။ /grouphelp နဲ့ အသုံးဝင်တဲ့ command များ ကြည့်ပါ။"
    for member in msg.new_chat_members:
        if member.is_bot: continue
        await msg.reply_text(template.replace("{name}", member.first_name[:100]))

async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.effective_message.reply_text(f"Chat ID: {update.effective_chat.id}\nUser ID: {user.id if user else 'N/A'}")

async def _reply_target(update: Update):
    """Return the user whose message was replied to, with clear failure reasons."""
    msg = update.effective_message
    if not msg:
        return None
    replied = msg.reply_to_message
    if replied is None:
        await msg.reply_text(
            "⚠️ အသုံးပြုသူရဲ့ မူရင်း message ကို အရင် Reply လုပ်ပါ။\n"
            "ပြီးမှ /mute 10m (သို့) /mute 2h လို့ ပို့ပါ။\n"
            "Telegram command menu ကိုနှိပ်မယ့်အစား Reply ထဲမှာ command ကို တိုက်ရိုက်ရိုက်ပို့ပါ။"
        )
        return None
    if replied.from_user is None:
        await msg.reply_text(
            "⚠️ Reply လုပ်ထားတဲ့ message မှာ Telegram User ID မရှိပါ။ "
            "Anonymous Admin / Channel Post ကို mute လုပ်လို့မရပါ။ "
            "သာမန်အဖွဲ့ဝင်တစ်ဦးရဲ့ မူရင်း message ကို Reply လုပ်ပါ။"
        )
        return None
    return replied.from_user

async def warn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_chat_admin(update, context): await update.effective_message.reply_text("Admin များသာ အသုံးပြုနိုင်ပါတယ်။"); return
    target = await _reply_target(update)
    if not target: return
    chat_id = update.effective_chat.id
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        db.execute("INSERT INTO chat_warnings(chat_id,user_id,count) VALUES(?,?,1) ON CONFLICT(chat_id,user_id) DO UPDATE SET count=count+1", (chat_id,target.id))
        count = db.execute("SELECT count FROM chat_warnings WHERE chat_id=? AND user_id=?", (chat_id,target.id)).fetchone()[0]; db.commit()
    await update.effective_message.reply_text(f"⚠️ {target.first_name} ကို သတိပေးပြီးပါပြီ။ စုစုပေါင်း {count} ကြိမ်။ 3 ကြိမ်ရောက်လျှင် Admin က စစ်ဆေးပါ။")

async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_chat_admin(update, context):
        await update.effective_message.reply_text("Admin များသာ အသုံးပြုနိုင်ပါတယ်။")
        return

    msg = update.effective_message
    # Standard usage is a reply: /mute 10m. A numeric user ID is also accepted
    # as a fallback for clients that drop reply metadata when using command menus.
    replied = msg.reply_to_message if msg else None
    target = replied.from_user if replied else None
    args = list(context.args or [])
    if target is None and args and args[0].isdigit():
        try:
            member = await context.bot.get_chat_member(update.effective_chat.id, int(args[0]))
            target = member.user
            args = args[1:]
        except Exception:
            await msg.reply_text("ဒီ Group ထဲမှာ အဲဒီ User ID ကို မတွေ့ပါ။ User ID မှန်မမှန် စစ်ပါ။")
            return
    if target is None:
        await _reply_target(update)
        return
    if replied is not None and replied.from_user is None:
        await _reply_target(update)
        return

    duration = args[0].lower() if args else "10m"
    match = re.fullmatch(r"(\d+)(m|h|d)", duration)
    if not match or int(match.group(1)) < 1 or int(match.group(1)) > 7*24*60:
        await msg.reply_text("အသုံးပြုပုံ: မူရင်း message ကို Reply လုပ်ပြီး /mute 10m သို့ /mute 2h သို့ /mute 1d (အများဆုံး 7d)။ Reply အလုပ်မလုပ်ပါက /mute USER_ID 10m ကို သုံးနိုင်ပါတယ်။")
        return
    from datetime import timezone
    delta = int(match.group(1)) * {"m":60,"h":3600,"d":86400}[match.group(2)]
    until = datetime.now(timezone.utc) + timedelta(seconds=delta)
    try:
        from telegram import ChatPermissions
        await context.bot.restrict_chat_member(
            update.effective_chat.id,
            target.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until,
        )
        await msg.reply_text(f"🔇 {target.first_name} ကို {duration} mute လုပ်ပြီးပါပြီ။")
    except Exception as exc:
        await msg.reply_text(f"Mute မအောင်မြင်ပါ။ Bot ကို Group Admin နှင့် Restrict Members ခွင့်ပြုချက်ပေးထားကြောင်း စစ်ပါ။ ({str(exc)[:150]})")

async def unmute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_chat_admin(update, context):
        await update.effective_message.reply_text("Admin များသာ အသုံးပြုနိုင်ပါတယ်။")
        return
    msg = update.effective_message
    replied = msg.reply_to_message if msg else None
    target = replied.from_user if replied else None
    args = list(context.args or [])
    if target is None and args and args[0].isdigit():
        try:
            member = await context.bot.get_chat_member(update.effective_chat.id, int(args[0]))
            target = member.user
        except Exception:
            await msg.reply_text("ဒီ Group ထဲမှာ အဲဒီ User ID ကို မတွေ့ပါ။ User ID မှန်မမှန် စစ်ပါ။")
            return
    if target is None:
        await msg.reply_text(
            "Mute ဖြုတ်မည့်သူရဲ့ မူရင်း message ကို Reply လုပ်ပြီး /unmute ပို့ပါ။\n"
            "Reply အလုပ်မလုပ်ပါက /unmute USER_ID ကို သုံးနိုင်ပါတယ်။"
        )
        return
    try:
        from telegram import ChatPermissions
        await context.bot.restrict_chat_member(
            update.effective_chat.id,
            target.id,
            permissions=ChatPermissions(
                can_send_messages=True, can_send_audios=True, can_send_documents=True,
                can_send_photos=True, can_send_videos=True, can_send_video_notes=True,
                can_send_voice_notes=True, can_send_polls=True,
                can_send_other_messages=True, can_add_web_page_previews=True,
            ),
        )
        await msg.reply_text(f"🔊 {target.first_name} ကို Mute ဖြုတ်ပြီးပါပြီ။")
    except Exception as exc:
        await msg.reply_text(f"Unmute မအောင်မြင်ပါ။ Bot ကို Admin နှင့် Restrict Members ခွင့်ပြုချက်ပေးထားကြောင်း စစ်ပါ။ ({str(exc)[:120]})")


async def pin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_chat_admin(update, context): await update.effective_message.reply_text("Admin များသာ အသုံးပြုနိုင်ပါတယ်။"); return
    if not update.effective_message.reply_to_message: await update.effective_message.reply_text("Pin လုပ်မည့် message ကို Reply လုပ်ပါ။"); return
    try:
        await update.effective_message.reply_to_message.pin()
        await update.effective_message.reply_text("📌 Pin လုပ်ပြီးပါပြီ။")
    except Exception: await update.effective_message.reply_text("Pin မအောင်မြင်ပါ။ Bot ကို Pin Messages ခွင့်ပြုချက်ပေးပါ။")

async def purge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_chat_admin(update, context): await update.effective_message.reply_text("Admin များသာ အသုံးပြုနိုင်ပါတယ်။"); return
    msg = update.effective_message
    if not msg.reply_to_message: await msg.reply_text("ဖျက်မည့် ပထမ message ကို Reply လုပ်ပြီး /purge 10 လို့ရေးပါ။"); return
    try: count = max(1, min(50, int(context.args[0]) if context.args else 1))
    except ValueError: count = 1
    start_id = msg.reply_to_message.message_id
    deleted = 0
    for mid in range(start_id, min(msg.message_id, start_id + count)):
        try: await context.bot.delete_message(msg.chat_id, mid); deleted += 1
        except Exception: pass
    try: await msg.delete()
    except Exception: pass
    await context.bot.send_message(msg.chat_id, f"🧹 {deleted} message ဖျက်ပြီးပါပြီ။")

# ------------------------- Error handler -------------------

async def group_admin_gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Commands are public in private chat, but group commands require that chat's admin/owner."""
    chat = update.effective_chat
    if not chat or chat.type not in ("group", "supergroup"):
        return True
    if await _is_chat_admin(update, context):
        return True
    msg = update.effective_message
    if msg:
        await msg.reply_text("⛔ Group ထဲတွင် ဒီ command ကို Group Admin သို့မဟုတ် Owner သာ အသုံးပြုနိုင်ပါတယ်။")
    return False


def gate_group_commands(callback):
    async def guarded(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await group_admin_gate(update, context):
            return
        return await callback(update, context)
    guarded.__name__ = callback.__name__
    return guarded


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
    builder = Application.builder().token(TOKEN).post_init(post_init)
    if TELEGRAM_API_BASE_URL:
        builder = builder.base_url(TELEGRAM_API_BASE_URL)
    if TELEGRAM_FILE_BASE_URL:
        builder = builder.base_file_url(TELEGRAM_FILE_BASE_URL)
    app = builder.build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", gate_group_commands(help_command)))
    app.add_handler(CommandHandler("grouphelp", gate_group_commands(group_help)))
    app.add_handler(CommandHandler("rules", gate_group_commands(rules_command)))
    app.add_handler(CommandHandler("setrules", gate_group_commands(setrules_command)))
    app.add_handler(CommandHandler("setwelcome", gate_group_commands(setwelcome_command)))
    app.add_handler(CommandHandler("id", id_command))  # /id is public in private chats and groups
    app.add_handler(CommandHandler("warn", gate_group_commands(warn_command)))
    app.add_handler(CommandHandler("mute", gate_group_commands(mute_command)))
    app.add_handler(CommandHandler("unmute", gate_group_commands(unmute_command)))
    app.add_handler(CommandHandler("pin", gate_group_commands(pin_command)))
    app.add_handler(CommandHandler("purge", gate_group_commands(purge_command)))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_members))
    app.add_handler(CommandHandler("news", gate_group_commands(news_command)))
    app.add_handler(CommandHandler("poll", gate_group_commands(poll_command)))
    app.add_handler(CommandHandler("report", gate_group_commands(report_command)))
    app.add_handler(CommandHandler("status", gate_group_commands(status_command)))
    app.add_handler(CommandHandler("game", gate_group_commands(game_command)))
    app.add_handler(CommandHandler("app", gate_group_commands(game_command)))
    app.add_handler(CommandHandler("ask", gate_group_commands(ask_command)))
    app.add_handler(CommandHandler("chat", gate_group_commands(chat_command)))
    app.add_handler(CommandHandler("next", gate_group_commands(next_chat)))
    app.add_handler(CommandHandler("stop", gate_group_commands(stop_chat)))
    app.add_handler(CommandHandler("points", gate_group_commands(points_command)))
    app.add_handler(CommandHandler("leaderboard", gate_group_commands(leaderboard_command)))
    app.add_handler(CommandHandler("referral", gate_group_commands(referral_command)))
    app.add_handler(CommandHandler("admin", gate_group_commands(admin_command)))
    app.add_handler(CommandHandler("stats", gate_group_commands(stats_command)))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("ban", ban_command))
    app.add_handler(CommandHandler("unban", unban_command))
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
