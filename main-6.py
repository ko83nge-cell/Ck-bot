import os
import re
import sqlite3
import logging
import asyncio
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


# -------------------------- Commands -----------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_channel_join(update, context):
        return
    await update.effective_message.reply_text(
        "🤖 Ck_helpbot မှ ကြိုဆိုပါတယ်။\n\n"
        "🌍 နိုင်ငံအမည်ကို ရိုက်ထည့်ပါ။ Bot က အင်တာနက် API များမှ "
        "နိုင်ငံအချက်အလက်ကို ရှာဖွေပေးပါမယ်။\n\n"
        "ဥပမာအဖြစ် နိုင်ငံအမည်တစ်ခုခုကို ရိုက်ထည့်နိုင်ပါတယ်။ "
        "အမည်စာရင်းကို Code ထဲမှာ ကြိုတင်ထည့်ထားဖို့ မလိုပါ။\n\n"
        "📚 နိုင်ငံအချက်အလက်၊ သမိုင်းနဲ့ Wikipedia မှ "
        "ထင်ရှားသူများကို ရှာဖွေပေးပါမယ်။\n\n"
        "🎬 သိမ်းထားသော ရုပ်ရှင်ရှာရန် ရုပ်ရှင်အမည်ကို ရိုက်ပါ။\n"
        "🎮 Open-source ဂိမ်းရှာပြီး ရနိုင်သော GitHub release ဖိုင်ပို့ရန် ဂိမ်းအမည်ကို ရိုက်ပါ။\n"
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
        "• ဂိမ်းအမည်ကို ရိုက်ပါ။ GitHub public release မှ 45 MB အောက် APK/ZIP/archive ဖိုင်ရလျှင် ပို့ပေးမည်။ မရလျှင် Google Play, Steam, itch.io နှင့် GitHub ရှာဖွေရေးလင့်ခ်များ ပြမည်။\n"
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
    """Search a game and send a matching public release file when available."""
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
        description = (game.get("description") or "")[:350]
        asset = (game.get("assets") or [None])[0]
        if asset:
            await message.reply_text(
                f"🎮 {game['name']}\n{description}\n\n"
                f"⬇️ Download: {asset['name']} ({asset['size'] // (1024 * 1024)} MB)\n"
                f"🔗 Source: {game['release_url']}\n"
                "အများပြည်သူရရှိနိုင်သော GitHub release ဖိုင်ဖြစ်ပါတယ်။ ဖိုင်ကို မဖွင့်မီ မူရင်း project ကို စစ်ဆေးပါ။"
            )
            temp_path = None
            try:
                import tempfile
                suffix = Path(asset["name"]).suffix or ".bin"
                fd, temp_path = tempfile.mkstemp(prefix="ck_game_", suffix=suffix)
                os.close(fd)
                await asyncio.to_thread(download_github_asset, asset["url"], temp_path)
                with open(temp_path, "rb") as file_obj:
                    await message.reply_document(
                        document=file_obj,
                        filename=asset["name"],
                        caption=f"🎮 {game['name']}\n🔗 {game['release_url']}"[:1000],
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
            f"🎮 {game['name']}\n{description}\n\n"
            "တိုက်ရိုက်ပို့နိုင်တဲ့ APK/ZIP release ဖိုင် မတွေ့ပါ။ မူရင်း release ကို ကြည့်ပါ:\n"
            f"{game['release_url']}\n\nRepository: {game['repo_url']}"
        )
        return True
    return False


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


# ---------------------------- Main -------------------------

def main():
    if not TOKEN:
        raise RuntimeError(
            "BOT_TOKEN မရှိပါ။ Railway -> Variables ထဲတွင် BOT_TOKEN ထည့်ပါ။"
        )

    init_db()
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
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
