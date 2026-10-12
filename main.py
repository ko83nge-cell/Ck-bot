import os
import re
import sqlite3
import logging
import asyncio
from urllib.parse import quote

import requests
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
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


# -------------------------- Commands -----------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "🤖 Ck_helpbot မှ ကြိုဆိုပါတယ်။\n\n"
        "🌍 နိုင်ငံအမည်ကို ရိုက်ထည့်ပါ။ Bot က အင်တာနက် API များမှ "
        "နိုင်ငံအချက်အလက်ကို ရှာဖွေပေးပါမယ်။\n\n"
        "ဥပမာအဖြစ် နိုင်ငံအမည်တစ်ခုခုကို ရိုက်ထည့်နိုင်ပါတယ်။ "
        "အမည်စာရင်းကို Code ထဲမှာ ကြိုတင်ထည့်ထားဖို့ မလိုပါ။\n\n"
        "📚 နိုင်ငံအချက်အလက်၊ သမိုင်းနဲ့ Wikipedia မှ "
        "ထင်ရှားသူများကို ရှာဖွေပေးပါမယ်။\n\n"
        "🎬 ရုပ်ရှင်ရှာရန် ရုပ်ရှင်အမည်ကို ရိုက်ပါ။\n"
        "/help - အသုံးပြုနည်း"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "📖 အသုံးပြုနည်း\n\n"
        "• နိုင်ငံအမည်ကို ရိုက်ပို့ပါ။\n"
        "• ရှာဖွေမှုသည် REST Countries နှင့် Wikipedia API များကို အသုံးပြုသည်။\n"
        "• ရလဒ်မတွေ့ပါက နိုင်ငံအမည်ကို အင်္ဂလိပ်လို ပြန်စမ်းပါ။\n"
        "• ရုပ်ရှင်အမည်ဖြင့် သိမ်းထားသော ရုပ်ရှင်ကို ရှာနိုင်သည်။\n"
        "• Admin သည် video/document ဖိုင်ပို့၍ ရုပ်ရှင်သိမ်းနိုင်သည်။"
    )


# ------------------------ Movie storage --------------------

async def save_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        return

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
        return

    if not results:
        await message.reply_text(
            "❌ နိုင်ငံအချက်အလက် သို့မဟုတ် သိမ်းထားသော ရုပ်ရှင်ကို မတွေ့ပါ။\n"
            "နိုင်ငံအမည်ကို အင်္ဂလိပ်လို ရိုက်ပြီး ထပ်စမ်းကြည့်ပါ။"
        )
        return

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


# ----------------------- Main text handler -----------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    # Second: if not a country, try Wikipedia summary for the query.
    try:
        data = await asyncio.to_thread(wikipedia_summary, query)
        if data and data.get("extract"):
            translated = await asyncio.to_thread(
                translate_to_burmese, data["extract"][:3000]
            )
            title = data.get("title", query)
            await send_long_text(message, f"📚 {title}\n\n{translated}")
            return
    except Exception:
        logger.exception("Wikipedia lookup failed")

    # Finally: search locally stored movies.
    await search_movie(update, query)


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
