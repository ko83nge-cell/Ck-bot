import os
import json
import time
import random
import logging
import sqlite3
import math
import struct
import wave
import tempfile
import asyncio
import re
import difflib
import urllib.request
import urllib.parse
import subprocess
import sys
from html import unescape
from html.parser import HTMLParser
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup, Update, BotCommand,
    BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats,
)
from telegram.helpers import escape_markdown
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Railway Variables:
# TELEGRAM_TOKEN = Telegram bot token
# DB_PATH = /data/ck_bot.db (recommended when a Railway Volume is mounted at /data)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DB_PATH = os.getenv("DB_PATH", "ck_bot.db")
BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", "0") or 0)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("ck_astrology_rpg_bot")

# ------------------------- EXISTING ASTROLOGY / GAME DATA -------------------------

ZODIAC_NAMES = {
    "aries": "မိဿရာသီ (Aries)",
    "taurus": "ပြိဿရာသီ (Taurus)",
    "gemini": "မေထုန်ရာသီ (Gemini)",
    "cancer": "ကရကဋ်ရာသီ (Cancer)",
    "leo": "သိဟ်ရာသီ (Leo)",
    "virgo": "ကန်ရာသီ (Virgo)",
    "libra": "တူရာသီ (Libra)",
    "scorpio": "ဗြိစ္ဆာရာသီ (Scorpio)",
    "sagittarius": "ဓနုရာသီ (Sagittarius)",
    "capricorn": "မကာရရာသီ (Capricorn)",
    "aquarius": "ကုမ်ရာသီ (Aquarius)",
    "pisces": "မိန်ရာသီ (Pisces)",
}

TOMORROW_EVENTS = [
    "မမျှော်လင့်ထားတဲ့ ငွေကြေးဝင်ရောက်မှု သို့မဟုတ် အကျိုးအမြတ်အသစ်တွေ ကိုယ့်ဆီ ရောက်လာပါလိမ့်မယ်။",
    "လုပ်ငန်းခွင် သို့မဟုတ် ပညာရေးမှာ ကိုယ့်ရဲ့ ကြိုးစားအားထုတ်မှုကို အထက်လူကြီးများက အသိအမှတ်ပြုလာမယ့် နေ့တစ်နေ့ ဖြစ်ပါတယ်။",
    "ရှုပ်ထွေးနေတဲ့ ပြဿနာဟောင်းတစ်ခုကို မိတ်ဆွေကောင်းတွေရဲ့ အကူအညီနဲ့ အလွယ်တကူ ဖြေရှင်းနိုင်သွားပါမယ်။",
]
TOMORROW_AVOIDS = [
    "စကားပြောဆိုရာမှာ အလောတကြီး ဆုံးဖြတ်ပြောဆိုမိခြင်းနဲ့ အထင်အမြင်လွဲမှားမှုများကို အထူးသတိပြုပါ။",
    "အရေးကြီးတဲ့ ဆုံးဖြတ်ချက်တွေ ချမှတ်တဲ့အခါ သူတစ်ပါးရဲ့ စကားကို အလွယ်တကူ မယုံကြည်ဘဲ ကိုယ်တိုင်သေချာ စဉ်းစားပါ။",
]
TRAITS_POOL = [
    "ခေါင်းဆောင်မှု အပြည့်အဝရှိပြီး ကိုယ်ပိုင်ဆုံးဖြတ်ချက် ခိုင်မာသူ ဖြစ်ပါတယ်။",
    "အရာရာကို လက်တွေ့ကျကျနဲ့ စနစ်တကျ ဦးဆောင်လုပ်ကိုင်တတ်တဲ့ သဘာဝရှိပါတယ်။",
]
LOVE_POOL = [
    "အချစ်ရေးမှာ တဖက်လူအပေါ် အလွန်ဂရုစိုက်ပေးတတ်ပေမယ့် တစ်ခါတရံ မာနကိုတော့ လျှော့ချသင့်ပါတယ်။",
]
CAREER_POOL = [
    "လုပ်ငန်းခွင်နဲ့ စီးပွားရေးမှာ ကိုယ်ပိုင်ဖန်တီးမှုအသစ်တွေနဲ့ ထိပ်ဆုံးကို ရောက်ရှိနိုင်ပါတယ်။",
]
TAROT_DECK = [
    {"name": "The Fool (လူမိုက်)", "vibe": "ခရီးအသစ်စတင်ခြင်း၊ စွန့်စားရဲခြင်း၊ အကောင်းမြင်စိတ်ဖြင့် ရှေ့ဆက်ခြင်း"},
    {"name": "The Magician (ပညာရှင်)", "vibe": "စွမ်းရည်များကို အပြည့်အဝအသုံးချပြီး ရည်မှန်းချက်အောင်မြင်မည့် ကာလ"},
    {"name": "The High Priestess (အတွင်းဉာဏ်)", "vibe": "အတွင်းစိတ်အသံကို နားထောင်ပြီး အချက်အလက်ကို သေချာလေ့လာရန်"},
    {"name": "The Empress (ဘုရင်မ)", "vibe": "တိုးတက်မှု၊ ဖန်တီးနိုင်စွမ်းနှင့် အောင်မြင်သော ဆက်ဆံရေး"},
    {"name": "The Chariot (ရထား)", "vibe": "စိတ်ဓာတ်ခိုင်မာမှုနှင့် ရည်မှန်းချက်ဆီသို့ တက်ကြွစွာ ရှေ့ဆက်ခြင်း"},
]
SAVED_TRIVIA_QUESTIONS = [
    {
        "q": "မြန်မာနိုင်ငံ၏ အမြင့်ဆုံးတောင်ထိပ်မှာ အမည်မှာ အဘယ်နည်း?",
        "options": ["ခါကာဘိုရာဇီ", "ဇွဲကပင်", "ပုပ္ပား", "တောင်ကြီး"],
        "answer": 0,
    },
]
LUCKY_PRIZES = [
    "🎉 ဂုဏ်ယူပါတယ်! ယနေ့ သင်၏ ကံကောင်းခြင်း လက်ဆောင်မှာ **'ထီပေါက်ကံစမ်းခြင်း အထူးကောင်းမွန်ခြင်း'** ဖြစ်ပါသည်။",
    "💰 ရွှေလိုမိုးလို ကျမည့်နေ့ပါ! **'ငွေကြေးဝင်ရောက်မည့်ကံ'** အထူးတလည် တောက်ပနေပါသည်။",
]

# ------------------------- ADVENTURE RPG GAME -------------------------
RPG_START_COINS = 150
RPG_XP_PER_LEVEL = 100
RPG_MONSTERS = [
    {"name": "တောဝက်ဘီလူး", "hp": 35, "power": 8, "xp": 25, "coins": (15, 35)},
    {"name": "အရိုးစုစစ်သည်", "hp": 45, "power": 11, "xp": 35, "coins": (25, 45)},
    {"name": "မီးနဂါးငယ်", "hp": 65, "power": 15, "xp": 50, "coins": (40, 70)},
]
RPG_ITEMS = {
    "sword": {"name": "သံဓား", "price": 120, "attack": 5, "kind": "weapon"},
    "blade": {"name": "မီးဓား", "price": 350, "attack": 12, "kind": "weapon"},
    "potion": {"name": "အသက်ဆေး", "price": 45, "heal": 35, "kind": "potion"},
}


def _fetch_json(url, timeout=20):
    """Fetch JSON from the MLBB MediaWiki API with a descriptive User-Agent."""
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "CKBot/1.0 (MLBB hero image quiz; contact: bot administrator)",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read(4 * 1024 * 1024 + 1)
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError("API response is too large")
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Unexpected API response")
    if payload.get("error"):
        raise RuntimeError("MediaWiki API error: " + str(payload["error"].get("info", "unknown")))
    return payload


def db_connect():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    parent = os.path.dirname(DB_PATH)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with db_connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS rpg_players (
            user_id INTEGER PRIMARY KEY, username TEXT NOT NULL DEFAULT '',
            coins INTEGER NOT NULL DEFAULT 150, level INTEGER NOT NULL DEFAULT 1,
            xp INTEGER NOT NULL DEFAULT 0, hp INTEGER NOT NULL DEFAULT 100,
            weapon TEXT NOT NULL DEFAULT 'fist', potions INTEGER NOT NULL DEFAULT 0,
            daily_at TEXT NOT NULL DEFAULT '', mission_day TEXT NOT NULL DEFAULT '',
            mission_count INTEGER NOT NULL DEFAULT 0, wins INTEGER NOT NULL DEFAULT 0,
            losses INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS rpg_duels (
            id INTEGER PRIMARY KEY AUTOINCREMENT, challenger_id INTEGER NOT NULL,
            target_id INTEGER NOT NULL, chat_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending', created_at INTEGER NOT NULL)""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_rpg_rank ON rpg_players(level DESC, xp DESC)")
        conn.execute("""CREATE TABLE IF NOT EXISTS game_rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER NOT NULL, game TEXT NOT NULL,
            host_id INTEGER NOT NULL, host_name TEXT NOT NULL, guest_id INTEGER, guest_name TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'waiting', turn INTEGER NOT NULL DEFAULT 0, round_no INTEGER NOT NULL DEFAULT 0,
            score_host INTEGER NOT NULL DEFAULT 0, score_guest INTEGER NOT NULL DEFAULT 0, state_json TEXT NOT NULL DEFAULT '{}',
            created_at INTEGER NOT NULL)""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_game_rooms_chat ON game_rooms(chat_id,status)")
        conn.execute("""CREATE TABLE IF NOT EXISTS arcade50_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER NOT NULL, game_id INTEGER NOT NULL,
            game_name TEXT NOT NULL, host_id INTEGER NOT NULL, players_json TEXT NOT NULL,
            scores_json TEXT NOT NULL, round_no INTEGER NOT NULL DEFAULT 0,
            question_json TEXT NOT NULL DEFAULT '{}', answered_json TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'waiting', created_at INTEGER NOT NULL)""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_arcade50_chat ON arcade50_sessions(chat_id,status)")
        conn.execute("""CREATE TABLE IF NOT EXISTS leisure_camps (
            chat_id INTEGER PRIMARY KEY, state_json TEXT NOT NULL,
            updated_at INTEGER NOT NULL DEFAULT 0)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS leisure_pets (
            user_id INTEGER PRIMARY KEY, pet_name TEXT NOT NULL DEFAULT 'မိုမို',
            food INTEGER NOT NULL DEFAULT 70, joy INTEGER NOT NULL DEFAULT 70,
            clean INTEGER NOT NULL DEFAULT 70, level INTEGER NOT NULL DEFAULT 1,
            updated_at INTEGER NOT NULL DEFAULT 0)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS leisure_gardens (
            user_id INTEGER PRIMARY KEY, seeds INTEGER NOT NULL DEFAULT 3,
            flowers INTEGER NOT NULL DEFAULT 0, water INTEGER NOT NULL DEFAULT 3,
            updated_at INTEGER NOT NULL DEFAULT 0)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS leisure_daily (
            user_id INTEGER PRIMARY KEY, claim_day TEXT NOT NULL DEFAULT '',
            streak INTEGER NOT NULL DEFAULT 0, coins INTEGER NOT NULL DEFAULT 0)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS creative_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            username TEXT NOT NULL, prompt TEXT NOT NULL, entry TEXT NOT NULL,
            created_at INTEGER NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS mlbb_hero_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT, hero TEXT NOT NULL UNIQUE,
            image_path TEXT NOT NULL, source_url TEXT NOT NULL, created_at INTEGER NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS mlbb_image_sessions (
            chat_id INTEGER PRIMARY KEY, hero TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active',
            round_no INTEGER NOT NULL DEFAULT 1, hint_used INTEGER NOT NULL DEFAULT 0,
            started_at INTEGER NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS mlbb_image_scores (
            user_id INTEGER PRIMARY KEY, username TEXT NOT NULL DEFAULT '',
            points INTEGER NOT NULL DEFAULT 0, wins INTEGER NOT NULL DEFAULT 0)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS life50_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, tool_id INTEGER NOT NULL,
            entry TEXT NOT NULL, created_at INTEGER NOT NULL)""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_life50_user_tool ON life50_entries(user_id,tool_id,created_at)")

        conn.execute("""CREATE TABLE IF NOT EXISTS user_reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL, remind_at INTEGER NOT NULL, message TEXT NOT NULL,
            repeat_daily INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'active',
            created_at INTEGER NOT NULL)""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reminders_due ON user_reminders(status,remind_at)")
        conn.execute("""CREATE TABLE IF NOT EXISTS user_expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            amount REAL NOT NULL, category TEXT NOT NULL DEFAULT 'အထွေထွေ',
            note TEXT NOT NULL DEFAULT '', created_at INTEGER NOT NULL)""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_expenses_user_date ON user_expenses(user_id,created_at)")
        conn.execute("CREATE TABLE IF NOT EXISTS profanity_permissions (user_id INTEGER PRIMARY KEY, granted_by INTEGER NOT NULL, granted_at INTEGER NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS profanity_settings (chat_id INTEGER PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 1)")
        # Safe migration for existing Railway SQLite databases.
        profanity_cols = {row[1] for row in conn.execute("PRAGMA table_info(profanity_settings)").fetchall()}
        if "activated_by" not in profanity_cols:
            conn.execute("ALTER TABLE profanity_settings ADD COLUMN activated_by INTEGER NOT NULL DEFAULT 0")
        conn.execute("""CREATE TABLE IF NOT EXISTS user_budgets (
            user_id INTEGER PRIMARY KEY, monthly_limit REAL NOT NULL,
            updated_at INTEGER NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS random_chat_queue (
            user_id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL,
            display_name TEXT NOT NULL DEFAULT '', queued_at INTEGER NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS random_chat_pairs (
            user_id INTEGER PRIMARY KEY, partner_id INTEGER NOT NULL,
            created_at INTEGER NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS random_chat_blocks (
            user_id INTEGER NOT NULL, blocked_id INTEGER NOT NULL,
            created_at INTEGER NOT NULL, PRIMARY KEY(user_id,blocked_id))""")
        # CK Community & engagement systems (additive, backwards-compatible).
        conn.execute("""CREATE TABLE IF NOT EXISTS ck_profiles (
            user_id INTEGER PRIMARY KEY, username TEXT NOT NULL DEFAULT '',
            display_name TEXT NOT NULL DEFAULT '', points INTEGER NOT NULL DEFAULT 0,
            xp INTEGER NOT NULL DEFAULT 0, level INTEGER NOT NULL DEFAULT 1,
            streak INTEGER NOT NULL DEFAULT 0, last_daily TEXT NOT NULL DEFAULT '',
            joined_at INTEGER NOT NULL, last_seen INTEGER NOT NULL DEFAULT 0,
            bio TEXT NOT NULL DEFAULT '')""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ck_profiles_rank ON ck_profiles(points DESC, xp DESC)")
        conn.execute("""CREATE TABLE IF NOT EXISTS ck_group_modules (
            id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER NOT NULL,
            module_key TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL DEFAULT '',
            created_by INTEGER NOT NULL, created_at INTEGER NOT NULL,
            UNIQUE(chat_id,module_key,id))""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ck_group_modules ON ck_group_modules(chat_id,module_key,id)")
        conn.execute("""CREATE TABLE IF NOT EXISTS ck_group_module_settings (
            chat_id INTEGER NOT NULL, module_id INTEGER NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 0, updated_by INTEGER NOT NULL DEFAULT 0,
            updated_at INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(chat_id,module_id))""")
        conn.execute("""CREATE TABLE IF NOT EXISTS ck_channel_settings (
            channel_id INTEGER NOT NULL, setting_id INTEGER NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 0, updated_by INTEGER NOT NULL DEFAULT 0,
            updated_at INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(channel_id,setting_id))""")

        conn.execute("""CREATE TABLE IF NOT EXISTS ck_daily_claims (
            user_id INTEGER NOT NULL, claim_day TEXT NOT NULL, reward INTEGER NOT NULL,
            PRIMARY KEY(user_id, claim_day))""")
        conn.execute("""CREATE TABLE IF NOT EXISTS ck_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            username TEXT NOT NULL DEFAULT '', category TEXT NOT NULL DEFAULT 'အကြံပြုချက်',
            message TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'new', created_at INTEGER NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS ck_user_settings (
            user_id INTEGER PRIMARY KEY, language TEXT NOT NULL DEFAULT 'my',
            notifications INTEGER NOT NULL DEFAULT 1, privacy TEXT NOT NULL DEFAULT 'normal')""")
        conn.execute("""CREATE TABLE IF NOT EXISTS ck_group_rules (
            chat_id INTEGER PRIMARY KEY, rules TEXT NOT NULL, updated_by INTEGER NOT NULL,
            updated_at INTEGER NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS ck_group_welcome (
            chat_id INTEGER PRIMARY KEY, welcome TEXT NOT NULL, updated_by INTEGER NOT NULL,
            updated_at INTEGER NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS ck_group_stats (
            chat_id INTEGER PRIMARY KEY, messages INTEGER NOT NULL DEFAULT 0,
            members_seen INTEGER NOT NULL DEFAULT 0, updated_at INTEGER NOT NULL DEFAULT 0)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS ck_user_message_daily (
            user_id INTEGER NOT NULL, day TEXT NOT NULL, messages INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(user_id, day))""")
        conn.execute("""CREATE TABLE IF NOT EXISTS ck_badges (
            user_id INTEGER NOT NULL, badge_key TEXT NOT NULL, earned_at INTEGER NOT NULL,
            PRIMARY KEY(user_id,badge_key))""")
        conn.execute("""CREATE TABLE IF NOT EXISTS ck_referrals (
            invited_id INTEGER PRIMARY KEY, inviter_id INTEGER NOT NULL, created_at INTEGER NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS ck_saved_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            title TEXT NOT NULL, body TEXT NOT NULL, created_at INTEGER NOT NULL)""")
        conn.commit()


def rpg_player(user):
    with db_connect() as conn:
        row = conn.execute("SELECT * FROM rpg_players WHERE user_id=?", (user.id,)).fetchone()
        if row is None:
            conn.execute("INSERT INTO rpg_players(user_id,username,created_at) VALUES(?,?,?)",
                         (user.id, user.username or user.first_name, int(time.time())))
            conn.commit()
            row = conn.execute("SELECT * FROM rpg_players WHERE user_id=?", (user.id,)).fetchone()
        elif user.username and row["username"] != user.username:
            conn.execute("UPDATE rpg_players SET username=? WHERE user_id=?", (user.username, user.id))
            conn.commit()
            row = conn.execute("SELECT * FROM rpg_players WHERE user_id=?", (user.id,)).fetchone()
        return dict(row)


def rpg_update(uid, **values):
    allowed = {"coins", "level", "xp", "hp", "weapon", "potions", "daily_at", "mission_day", "mission_count", "wins", "losses"}
    if not values or any(k not in allowed for k in values):
        raise ValueError("Invalid RPG update")
    sql = ", ".join(f"{k}=?" for k in values)
    with db_connect() as conn:
        conn.execute(f"UPDATE rpg_players SET {sql} WHERE user_id=?", (*values.values(), uid))
        conn.commit()


def rpg_gain_xp(player, amount):
    xp, level = player["xp"] + amount, player["level"]
    messages = []
    while xp >= RPG_XP_PER_LEVEL * level:
        xp -= RPG_XP_PER_LEVEL * level
        level += 1
        messages.append(f"🎉 Level {level} သို့ တက်သွားပါပြီ!")
    rpg_update(player["user_id"], xp=xp, level=level)
    return "\n".join(messages)


def rpg_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚔️ စွန့်စားခန်းထွက်မည်", callback_data="rpg_explore"), InlineKeyboardButton("🧪 အသက်ဆေးသုံးမည်", callback_data="rpg_potion")],
        [InlineKeyboardButton("🛒 ပစ္စည်းဆိုင်", callback_data="rpg_shop"), InlineKeyboardButton("🎁 Daily Reward", callback_data="rpg_daily")],
        [InlineKeyboardButton("📜 နေ့စဉ်မစ်ရှင်", callback_data="rpg_mission"), InlineKeyboardButton("🏆 Ranking", callback_data="rpg_rank")],
        [InlineKeyboardButton("🔄 အခြေအနေပြန်ကြည့်", callback_data="rpg_home"), InlineKeyboardButton("🎮 ဂိမ်းမီနူး", callback_data="menu_games")],
    ])


def rpg_status_text(user):
    p = rpg_player(user)
    weapon = "လက်ဗလာ" if p["weapon"] == "fist" else RPG_ITEMS.get(p["weapon"], {}).get("name", p["weapon"])
    attack = 10 + RPG_ITEMS.get(p["weapon"], {}).get("attack", 0)
    return (f"🛡️ **ADVENTURE RPG — ဇာတ်ကောင်အခြေအနေ**\n━━━━━━━━━━━━━━━━━━\n"
            f"🧙 ကစားသမား: {escape_markdown(p['username'], version=1)}\n⭐ Level: **{p['level']}** | XP: {p['xp']}/{RPG_XP_PER_LEVEL*p['level']}\n"
            f"❤️ HP: **{p['hp']}/100** | ⚔️ တိုက်ခိုက်အား: **{attack}**\n"
            f"💰 ရွှေဒင်္ဂါး: **{p['coins']}** | 🧪 ဆေး: **{p['potions']}**\n"
            f"🗡️ လက်နက်: **{weapon}**\n🏆 အနိုင်: {p['wins']} | ရှုံး: {p['losses']}\n\n"
            "စွန့်စားခန်းထွက်ပြီး ဘီလူးတွေကို အနိုင်ယူပါ။ XP နဲ့ ရွှေစု၊ Level တက်ပြီး ပိုအားကောင်းတဲ့ လက်နက်တွေ ဝယ်ပါ။")


async def rpg_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_group_bot_admin(update, context): return
    await update.effective_message.reply_text(rpg_status_text(update.effective_user), parse_mode="Markdown", reply_markup=rpg_keyboard())


async def rpg_pvp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_group_bot_admin(update, context): return
    msg = update.effective_message
    if not msg.reply_to_message or not msg.reply_to_message.from_user:
        await msg.reply_text("⚔️ Group ထဲမှာ ပြိုင်ချင်သူရဲ့ စာကို Reply လုပ်ပြီး /pvp ပို့ပါ။")
        return
    target = msg.reply_to_message.from_user
    challenger = update.effective_user
    if target.is_bot or target.id == challenger.id:
        await msg.reply_text("ကိုယ့်ကိုယ်ကိုယ် သို့မဟုတ် Bot ကို စိန်ခေါ်လို့မရပါ။")
        return
    rpg_player(challenger); rpg_player(target)
    with db_connect() as conn:
        cur = conn.execute("INSERT INTO rpg_duels(challenger_id,target_id,chat_id,created_at) VALUES(?,?,?,?)",
                           (challenger.id, target.id, msg.chat_id, int(time.time())))
        duel_id = cur.lastrowid
        conn.commit()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⚔️ စိန်ခေါ်မှု လက်ခံမည်", callback_data=f"rpg_accept_{duel_id}"),
                                InlineKeyboardButton("❌ ငြင်းမည်", callback_data=f"rpg_decline_{duel_id}")]])
    await msg.reply_text(f"⚔️ {target.first_name} ကို {challenger.first_name} က PvP တိုက်ပွဲ စိန်ခေါ်လိုက်ပါတယ်။", reply_markup=kb)


async def rpg_callback(query, context, data):
    user = query.from_user
    p = rpg_player(user)
    uid = user.id
    if data in ("rpg_home", "rpg_open"):
        await query.edit_message_text(rpg_status_text(user), parse_mode="Markdown", reply_markup=rpg_keyboard()); return
    if data == "rpg_daily":
        today = datetime.now(timezone.utc).date().isoformat()
        if p["daily_at"] == today:
            await query.edit_message_text("ဒီနေ့ Daily Reward ယူပြီးပါပြီ။", reply_markup=rpg_keyboard()); return
        rpg_update(uid, coins=p["coins"]+100, daily_at=today)
        p = rpg_player(user); level_msg = rpg_gain_xp(p, 25)
        await query.edit_message_text("🎁 Daily Reward ရရှိပါပြီ!\n💰 +100 Coins\n⭐ +25 XP\n"+level_msg, reply_markup=rpg_keyboard()); return
    if data == "rpg_mission":
        today = datetime.now(timezone.utc).date().isoformat()
        count = p["mission_count"] if p["mission_day"] == today else 0
        await query.edit_message_text(f"📜 **နေ့စဉ်မစ်ရှင်**\nဘီလူး ၃ ကောင် အနိုင်ယူပါ။\nတိုးတက်မှု: {min(count,3)}/3\nပြီးမြောက်လျှင် 150 Coins + 60 XP ရရှိမည်။", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ RPG သို့", callback_data="rpg_home")]])); return
    if data == "rpg_rank":
        with db_connect() as conn:
            rows = conn.execute("SELECT username,level,xp,wins FROM rpg_players ORDER BY level DESC,xp DESC,wins DESC LIMIT 10").fetchall()
        lines = ["🏆 **ADVENTURE RPG TOP 10**"] + [f"{i}. {r['username']} — Lv.{r['level']} ({r['xp']} XP) | 🏅{r['wins']} wins" for i,r in enumerate(rows,1)]
        await query.edit_message_text("\n".join(lines), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ RPG သို့", callback_data="rpg_home")]])); return
    if data == "rpg_shop":
        rows = [[InlineKeyboardButton(f"{v['name']} — {v['price']} 💰", callback_data=f"rpg_buy_{k}")] for k,v in RPG_ITEMS.items()]
        rows.append([InlineKeyboardButton("⬅️ RPG သို့", callback_data="rpg_home")])
        await query.edit_message_text(f"🛒 **ပစ္စည်းဆိုင်**\nလက်ကျန်: {p['coins']} 💰", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(rows)); return
    if data.startswith("rpg_buy_"):
        key = data.replace("rpg_buy_", "", 1); item = RPG_ITEMS.get(key)
        if not item: return
        if p["coins"] < item["price"]:
            await query.edit_message_text("💰 ငွေမလောက်ပါ။ ပိုက်ဆံစုဆောင်းပြီး ပြန်လာပါ။", reply_markup=rpg_keyboard()); return
        if item["kind"] == "potion": rpg_update(uid, coins=p["coins"]-item["price"], potions=p["potions"]+1)
        else: rpg_update(uid, coins=p["coins"]-item["price"], weapon=key)
        await query.edit_message_text(f"✅ {item['name']} ဝယ်ယူပြီးပါပြီ။", reply_markup=rpg_keyboard()); return
    if data == "rpg_potion":
        if p["potions"] < 1 or p["hp"] >= 100:
            await query.edit_message_text("🧪 အသက်ဆေးမရှိသေးပါ သို့မဟုတ် HP ပြည့်နေပါပြီ။", reply_markup=rpg_keyboard()); return
        rpg_update(uid, potions=p["potions"]-1, hp=min(100,p["hp"]+35))
        await query.edit_message_text("🧪 အသက်ဆေးသုံးပြီး HP 35 ပြန်ရရှိပါပြီ။", reply_markup=rpg_keyboard()); return
    if data == "rpg_explore":
        monster = random.choice(RPG_MONSTERS)
        attack = 10 + RPG_ITEMS.get(p["weapon"], {}).get("attack", 0)
        damage = random.randint(max(4,attack-4), attack+5)
        monster_hp = monster["hp"] - damage
        if monster_hp <= 0:
            reward = random.randint(*monster["coins"]); rpg_update(uid, coins=p["coins"]+reward, hp=min(100,p["hp"]+5))
            fresh = rpg_player(user); level_msg = rpg_gain_xp(fresh, monster["xp"])
            today = datetime.now(timezone.utc).date().isoformat(); count = (p["mission_count"] if p["mission_day"] == today else 0)+1
            if count >= 3:
                fresh = rpg_player(user); rpg_update(uid, coins=fresh["coins"]+150, mission_count=3, mission_day=today)
                fresh = rpg_player(user); rpg_gain_xp(fresh,60); mission_msg = "\n🎉 နေ့စဉ်မစ်ရှင်ပြီးပါပြီ! +150 Coins +60 XP"
            else:
                rpg_update(uid, mission_count=count, mission_day=today); mission_msg = f"\n📜 မစ်ရှင်: {count}/3"
            result = f"🏆 **အနိုင်ရပါပြီ!**\n{monster['name']} ကို အနိုင်ယူခဲ့တယ်။\n⚔️ ထိခိုက်မှု: {damage}\n💰 +{reward} Coins | ⭐ +{monster['xp']} XP\n{level_msg}{mission_msg}"
        else:
            hp_loss = random.randint(8,16); rpg_update(uid, hp=max(0,p["hp"]-hp_loss))
            result = f"💥 **တိုက်ပွဲမှာ အရေးနိမ့်သွားပါတယ်။**\n{monster['name']} HP {monster_hp} ကျန်နေသေးတယ်။\n❤️ HP -{hp_loss}\nအသက်ဆေးဝယ်ပြီး ပြန်ကြိုးစားပါ။"
        await query.edit_message_text(result, parse_mode="Markdown", reply_markup=rpg_keyboard()); return
    if data.startswith("rpg_accept_") or data.startswith("rpg_decline_"):
        duel_id = int(data.rsplit("_",1)[1])
        with db_connect() as conn:
            duel = conn.execute("SELECT * FROM rpg_duels WHERE id=?",(duel_id,)).fetchone()
            if not duel or duel["status"] != "pending":
                await query.edit_message_text("ဒီစိန်ခေါ်မှု မရှိတော့ပါ။"); return
            if data.startswith("rpg_accept_") and uid != duel["target_id"]:
                await query.edit_message_text("ဒီစိန်ခေါ်မှုကို ပစ်မှတ်ထားခံရသူသာ လက်ခံနိုင်ပါတယ်။"); return
            status = "accepted" if data.startswith("rpg_accept_") else "declined"
            conn.execute("UPDATE rpg_duels SET status=? WHERE id=?",(status,duel_id)); conn.commit()
        if status == "declined":
            await query.edit_message_text("စိန်ခေါ်မှုကို ငြင်းပယ်လိုက်ပါပြီ။"); return
        with db_connect() as conn:
            a = conn.execute("SELECT * FROM rpg_players WHERE user_id=?",(duel["challenger_id"],)).fetchone()
            b = conn.execute("SELECT * FROM rpg_players WHERE user_id=?",(duel["target_id"],)).fetchone()
        if not a or not b: return
        ap = 10 + RPG_ITEMS.get(a["weapon"],{}).get("attack",0) + random.randint(0,15)
        bp = 10 + RPG_ITEMS.get(b["weapon"],{}).get("attack",0) + random.randint(0,15)
        winner, loser = (a,b) if ap >= bp else (b,a)
        rpg_update(winner["user_id"], coins=winner["coins"]+75, wins=winner["wins"]+1)
        rpg_update(loser["user_id"], losses=loser["losses"]+1, hp=max(20,loser["hp"]-15))
        await query.edit_message_text(f"⚔️ **PvP တိုက်ပွဲပြီးဆုံး!**\n🏆 အနိုင်ရသူ: **{winner['username']}**\nတိုက်ခိုက်အား {ap} vs {bp}\n💰 အနိုင်ရသူ +75 Coins", parse_mode="Markdown"); return


# ------------------------- GROUP BOT-ADMIN ACCESS GATE -------------------------
async def group_bot_is_admin(chat, context):
    """Group features are enabled only after the bot is promoted to admin."""
    if chat.type == "private":
        return True
    try:
        me = await context.bot.get_me()
        member = await context.bot.get_chat_member(chat.id, me.id)
        return member.status in ("administrator", "creator")
    except Exception:
        logger.exception("Unable to verify bot admin status in chat %s", chat.id)
        return False


async def require_group_bot_admin(update_or_query, context):
    message = getattr(update_or_query, "effective_message", None)
    if message is None and hasattr(update_or_query, "message"):
        message = update_or_query.message
    chat = getattr(message, "chat", None)
    if chat is None or chat.type == "private":
        return True
    if await group_bot_is_admin(chat, context):
        return True
    warning = ("⚠️ ဒီ Group မှာ CK Bot ရဲ့ စနစ်တွေ အသုံးပြုဖို့ Bot ကို Group ထဲထည့်ပြီး "
               "Admin အဖြစ် ရာထူးပေးထားဖို့ လိုအပ်ပါတယ်။\n\n"
               "Group Settings → Administrators → Add Administrator မှာ CK Bot ကို ရွေးပေးပါ။")
    if hasattr(update_or_query, "answer") and hasattr(update_or_query, "data"):
        await update_or_query.answer("Bot ကို Group Admin ပေးထားဖို့ လိုပါတယ်။", show_alert=True)
    elif message:
        await message.reply_text(warning)
    return False

# ------------------------- MINI GAME CENTER -------------------------
WORD_PUZZLES = [
    ("မိုးပေါ်မှာရှိပြီး လက်နဲ့မဖမ်းနိုင်တာ ဘာလဲ?", "တိမ်"),
    ("သွားမရှိဘဲ ကိုက်တတ်တာ ဘာလဲ?", "အအေး"),
    ("နေ့တိုင်းတက်လာပြီး ညတိုင်းပျောက်သွားတာ ဘာလဲ?", "နေ"),
]


def games_menu_keyboard(chat_type="private"):
    is_group = chat_type != "private"
    mode_tag = "(၂ ယောက်)" if is_group else "(တစ်ယောက်တည်း)"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("♟️ Chess Puzzle", callback_data="mini_chess"), InlineKeyboardButton("⭕ Tic Tac Toe", callback_data="mini_ttt")],
        [InlineKeyboardButton("🐍 Snake", callback_data="mini_snake"), InlineKeyboardButton("💎 Treasure Hunt", callback_data="mini_treasure")],
        [InlineKeyboardButton("🔤 Word Puzzle", callback_data="mini_word"), InlineKeyboardButton("🚀 Space Shooter", callback_data="mini_space")],
        [InlineKeyboardButton("🛡️ Adventure RPG", callback_data="rpg_open")],
        [InlineKeyboardButton("🗡️ MLBB Hero ပုံခန့်မှန်း", callback_data="mlbbi_start")],
        [InlineKeyboardButton("🧠 Trivia", callback_data="game_trivia"), InlineKeyboardButton("🎁 Lucky", callback_data="game_lucky")],
        [InlineKeyboardButton("🦹 Thief", callback_data="thief_start"), InlineKeyboardButton("🏠 ပင်မမီနူး", callback_data="menu_start")],
        [InlineKeyboardButton("🕹️ ဂိမ်းအသစ် ၅၀ မျိုး ကြည့်ရန်", callback_data="a50_page_0")],
        [InlineKeyboardButton("🌈 Relax & Fun Center", callback_data="life_open")],
        [InlineKeyboardButton(f"🏠 Monopoly {mode_tag}", callback_data="room_create_monopoly"), InlineKeyboardButton(f"🃏 Poker {mode_tag}", callback_data="room_create_poker")],
        [InlineKeyboardButton(f"🎴 UNO {mode_tag}", callback_data="room_create_uno"), InlineKeyboardButton(f"🕵️ Detective {mode_tag}", callback_data="room_create_detective")],
        [InlineKeyboardButton(f"🏰 Tower Defense {mode_tag}", callback_data="room_create_tower"), InlineKeyboardButton(f"🏎️ Car Racing {mode_tag}", callback_data="room_create_racing")],
        [InlineKeyboardButton(f"⚽ Football {mode_tag}", callback_data="room_create_football"), InlineKeyboardButton(f"🧠 Brain Battle {mode_tag}", callback_data="room_create_brain")],
        [InlineKeyboardButton("🎁 Mystery Box", callback_data="room_create_mystery" if is_group else "new_mystery"), InlineKeyboardButton("✊ Rock Paper Scissors", callback_data="room_create_rps" if is_group else "new_rps")],
        [InlineKeyboardButton("🐉 Monster Battle", callback_data="room_create_monster" if is_group else "new_monster"), InlineKeyboardButton("🔎 Hidden Object", callback_data="room_create_hidden" if is_group else "new_hidden")],
        [InlineKeyboardButton("🚪 Choose a Door", callback_data="room_create_door" if is_group else "new_door"), InlineKeyboardButton("🖼️ Picture Quiz", callback_data="room_create_picture" if is_group else "new_picture")],
        [InlineKeyboardButton("🧠 Memory Match", callback_data="room_create_memory" if is_group else "new_memory"), InlineKeyboardButton("⚔️ Weapon Choice", callback_data="room_create_weapon" if is_group else "new_weapon")],
    ])


def ttt_keyboard(board, group_state=None):
    rows=[]
    for r in range(3):
        row=[]
        for c in range(3):
            v=board[r*3+c]
            row.append(InlineKeyboardButton(v if v else "⬜", callback_data=f"mini_ttt_{r*3+c}" if not v else "mini_noop"))
        rows.append(row)
    if group_state is not None and not group_state.get("player_o"):
        rows.append([InlineKeyboardButton("🙋 ဒုတိယကစားသမား ဝင်မည်", callback_data="mini_ttt_join")])
    rows.append([InlineKeyboardButton("🔄 အသစ်စမည်", callback_data="mini_ttt"), InlineKeyboardButton("🎮 ဂိမ်းမီနူး", callback_data="menu_games")])
    return InlineKeyboardMarkup(rows)


def mini_ttt_result(board):
    lines=((0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6))
    for a,b,c in lines:
        if board[a] and board[a]==board[b]==board[c]: return board[a]
    return "draw" if all(board) else None


async def mini_game_callback(query, context, data):
    ud=context.user_data
    chat = query.message.chat
    is_group = chat.type != "private"
    if is_group and data not in ("mini_ttt", "mini_ttt_join") and not data.startswith("mini_ttt_"):
        await query.answer("Group မှာ နှစ်ယောက်ကစားနိုင်တဲ့ Tic Tac Toe သို့မဟုတ် အောက်က ၂ ယောက်ဂိမ်းခန်းကို အသုံးပြုပါ။ တစ်ယောက်တည်းဂိမ်းများကို Private Chat မှာ ကစားနိုင်ပါတယ်။", show_alert=True)
        return
    if data == "mini_noop":
        await query.answer("ဒီကွက်ကို ရွေးပြီးပါပြီ။", show_alert=False); return
    if data == "mini_chess":
        ud["mini_chess_answer"]="မြင်း"
        kb=InlineKeyboardMarkup([[InlineKeyboardButton(x,callback_data="mini_chess_wrong" if x!="မြင်း" else "mini_chess_right")] for x in ("ဘုရင်","မြင်း","ခံတပ်")]+[[InlineKeyboardButton("🎮 ဂိမ်းမီနူး",callback_data="menu_games")]])
        await query.edit_message_text("♟️ **Chess Puzzle**\n\nစစ်တုရင်မှာ L ပုံစံ ရွေ့လျားနိုင်တဲ့ အရုပ်က ဘယ်ဟာလဲ?",parse_mode="Markdown",reply_markup=kb); return
    if data in ("mini_chess_right","mini_chess_wrong"):
        await query.edit_message_text("🎉 မှန်ပါတယ်!" if data.endswith("right") else "❌ မမှန်ပါ။ အဖြေက မြင်း ဖြစ်ပါတယ်။",reply_markup=games_menu_keyboard(query.message.chat.type)); return
    if data == "mini_ttt":
        board=[""]*9
        if is_group:
            state={"board":board,"player_x":query.from_user.id,"player_x_name":query.from_user.first_name,
                   "player_o":None,"player_o_name":"","turn":"X","status":"waiting"}
            context.chat_data["group_ttt"] = state
            text=("⭕ **Tic Tac Toe — Group နှစ်ယောက်ကစားမုဒ်**\n\n"
                  f"❌ X: {query.from_user.first_name}\n⭕ O: ဒုတိယကစားသမားကို စောင့်နေသည်\n\n"
                  "ဒုတိယကစားသမားက အောက်က Join ခလုတ်ကို နှိပ်ပါ။ နှစ်ယောက်ပြည့်မှ ပွဲစပါမယ်။")
            await query.edit_message_text(text,parse_mode="Markdown",reply_markup=ttt_keyboard(board,state)); return
        ud["ttt_board"]=board; ud["ttt_turn"]="X"
        await query.edit_message_text("⭕ **Tic Tac Toe — တစ်ယောက်တည်းကစားမုဒ်**\nသင်က X၊ Bot က O ဖြစ်ပါတယ်။",parse_mode="Markdown",reply_markup=ttt_keyboard(board)); return
    if data == "mini_ttt_join":
        state=context.chat_data.get("group_ttt")
        if not state or state.get("status") != "waiting":
            await query.answer("ဝင်လို့ရတဲ့ ပွဲမရှိတော့ပါ။",show_alert=True); return
        if query.from_user.id == state["player_x"]:
            await query.answer("ပွဲစတင်ဖို့ အခြားကစားသမားတစ်ယောက် လိုပါတယ်။",show_alert=True); return
        state["player_o"]=query.from_user.id
        state["player_o_name"]=query.from_user.first_name
        state["status"]="playing"
        await query.edit_message_text(
            f"⭕ **Tic Tac Toe — Group နှစ်ယောက်ကစားမုဒ်**\n\n❌ X: {state['player_x_name']}\n⭕ O: {state['player_o_name']}\n\n❌ X ရဲ့ အလှည့်ပါ။",
            parse_mode="Markdown",reply_markup=ttt_keyboard(state["board"],state)); return
    if data.startswith("mini_ttt_"):
        try: idx=int(data.rsplit("_",1)[1])
        except ValueError: return
        if is_group:
            state=context.chat_data.get("group_ttt")
            if not state or state.get("status") != "playing":
                await query.answer("ကစားသမား ၂ ယောက် Join ပြီးမှ ပွဲစနိုင်ပါတယ်။",show_alert=True); return
            mark="X" if query.from_user.id == state["player_x"] else "O" if query.from_user.id == state["player_o"] else None
            if mark is None:
                await query.answer("ဒီပွဲမှာ ပါဝင်ထားတဲ့ ကစားသမား မဟုတ်ပါ။",show_alert=True); return
            if mark != state["turn"]:
                await query.answer("အခု သင့်အလှည့် မဟုတ်သေးပါ။",show_alert=True); return
            board=state["board"]
            if board[idx]:
                await query.answer("ဒီကွက်ကို ရွေးပြီးပါပြီ။",show_alert=False); return
            board[idx]=mark
            result=mini_ttt_result(board)
            if result:
                state["status"]="finished"
                msg=(f"🏆 အနိုင်ရသူ: {state['player_x_name']}" if result=="X" else
                     f"🏆 အနိုင်ရသူ: {state['player_o_name']}" if result=="O" else "🤝 သရေကျပါတယ်။")
                await query.edit_message_text(f"⭕ **Tic Tac Toe ပြီးဆုံးပါပြီ!**\n{msg}",parse_mode="Markdown",reply_markup=ttt_keyboard(board,state)); return
            state["turn"]="O" if mark=="X" else "X"
            next_name=state["player_x_name"] if state["turn"]=="X" else state["player_o_name"]
            await query.edit_message_text(f"⭕ **Tic Tac Toe**\n❌ X: {state['player_x_name']}\n⭕ O: {state['player_o_name']}\n\nအလှည့်: {next_name} ({state['turn']})",parse_mode="Markdown",reply_markup=ttt_keyboard(board,state)); return
        board=ud.get("ttt_board")
        if not board or board[idx]: await query.answer("ဂိမ်းအသစ်စပါ။"); return
        board[idx]="X"; result=mini_ttt_result(board)
        if not result:
            free=[i for i,v in enumerate(board) if not v]
            if free:
                move=None
                for i in free:
                    test=board.copy(); test[i]="O"
                    if mini_ttt_result(test)=="O": move=i; break
                if move is None:
                    for i in free:
                        test=board.copy(); test[i]="X"
                        if mini_ttt_result(test)=="X": move=i; break
                if move is None: move=random.choice(free)
                board[move]="O"
            result=mini_ttt_result(board)
        msg={"X":"🎉 သင်အနိုင်ရပါပြီ!","O":"🤖 Bot အနိုင်ရသွားပါတယ်။","draw":"🤝 သရေကျပါတယ်။"}.get(result,"သင်က X၊ Bot က O ဖြစ်ပါတယ်။")
        await query.edit_message_text("⭕ **Tic Tac Toe**\n"+msg,parse_mode="Markdown",reply_markup=ttt_keyboard(board)); return
    if data == "mini_snake":
        ud["snake_score"]=0; ud["snake_pos"]=5
        kb=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️",callback_data="mini_snake_left"),InlineKeyboardButton("⬆️",callback_data="mini_snake_up"),InlineKeyboardButton("➡️",callback_data="mini_snake_right")],[InlineKeyboardButton("⬇️",callback_data="mini_snake_down"),InlineKeyboardButton("🍎 အစာစား",callback_data="mini_snake_food")],[InlineKeyboardButton("🎮 ဂိမ်းမီနူး",callback_data="menu_games")]])
        await query.edit_message_text("🐍 **Snake Mini Game**\nမြွေကို ဦးတည်ချက်ရွှေ့ပြီး 🍎 အစာစားပါ။ အစာစားတိုင်း အမှတ်တိုးပါမယ်။\nအမှတ်: 0",parse_mode="Markdown",reply_markup=kb); return
    if data.startswith("mini_snake_"):
        if "snake_score" not in ud: ud["snake_score"]=0
        if data.endswith("food"): ud["snake_score"]+=1
        elif data.endswith(("left","right","up","down")): ud["snake_score"]+=random.choice([0,0,1])
        kb=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️",callback_data="mini_snake_left"),InlineKeyboardButton("⬆️",callback_data="mini_snake_up"),InlineKeyboardButton("➡️",callback_data="mini_snake_right")],[InlineKeyboardButton("⬇️",callback_data="mini_snake_down"),InlineKeyboardButton("🍎 အစာစား",callback_data="mini_snake_food")],[InlineKeyboardButton("🎮 ဂိမ်းမီနူး",callback_data="menu_games")]])
        await query.edit_message_text(f"🐍 **Snake Mini Game**\nရွှေ့ပြီး အစာစားပါ။\n⭐ အမှတ်: {ud['snake_score']}",parse_mode="Markdown",reply_markup=kb); return
    if data == "mini_treasure":
        ud["treasure_prize"]=random.randrange(9)
        kb=InlineKeyboardMarkup([[InlineKeyboardButton("📦",callback_data=f"mini_treasure_{i}") for i in range(r*3,(r+1)*3)] for r in range(3)]+[[InlineKeyboardButton("🎮 ဂိမ်းမီနူး",callback_data="menu_games")]])
        await query.edit_message_text("💎 **Treasure Hunt**\nသေတ္တာ ၉ လုံးထဲက ရတနာပါတဲ့ သေတ္တာကို ရွေးပါ!",parse_mode="Markdown",reply_markup=kb); return
    if data.startswith("mini_treasure_"):
        try: idx=int(data.rsplit("_",1)[1])
        except ValueError: return
        won=idx==ud.get("treasure_prize",-1)
        await query.edit_message_text("🎉 ရတနာတွေ့ပါပြီ! သင်အနိုင်ရပါတယ်။" if won else "📦 ဒီသေတ္တာထဲမှာ ဘာမှမရှိပါ။ ထပ်ကြိုးစားပါ!",reply_markup=games_menu_keyboard(query.message.chat.type)); return
    if data == "mini_word":
        q,a=random.choice(WORD_PUZZLES); ud["mini_word_answer"]=a
        await query.edit_message_text("🔤 **Word Puzzle**\n"+q+"\n\nအဖြေကို စာနဲ့ ပြန်ပို့ပါ။",parse_mode="Markdown",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎮 ဂိမ်းမီနူး",callback_data="menu_games")]])); return
    if data == "mini_space":
        ud["space_hp"]=3; ud["space_score"]=0
        kb=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 ပစ်ခတ်မည်!",callback_data="mini_space_shoot")],[InlineKeyboardButton("🎮 ဂိမ်းမီနူး",callback_data="menu_games")]])
        await query.edit_message_text("🚀 **Space Shooter**\nဂြိုဟ်သားတွေကို ပစ်ခတ်ပါ။ သင့်အသက် ၃ ခုရှိပါတယ်။\n❤️ 3 | ⭐ 0",parse_mode="Markdown",reply_markup=kb); return
    if data == "mini_space_shoot":
        hp=ud.get("space_hp",0); score=ud.get("space_score",0)
        if hp>0:
            if random.random()<0.72: score+=10; msg="🎯 ပစ်မှတ်ထိပါတယ်! +10 မှတ်"
            else: hp-=1; msg="💥 ရန်သူပြန်တိုက်လို့ အသက်တစ်ခုဆုံးရှုံး!"
            ud["space_hp"]=hp; ud["space_score"]=score
        if hp<=0:
            await query.edit_message_text(f"🚀 Game Over!\n⭐ ရမှတ်: {score}",reply_markup=games_menu_keyboard(query.message.chat.type)); return
        kb=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 ပစ်ခတ်မည်!",callback_data="mini_space_shoot")],[InlineKeyboardButton("🎮 ဂိမ်းမီနူး",callback_data="menu_games")]])
        await query.edit_message_text(f"🚀 **Space Shooter**\n{msg}\n❤️ {hp} | ⭐ {score}",parse_mode="Markdown",reply_markup=kb); return


# ------------------------- ADDITIONAL GAME CENTER (SQLite-backed scores) -------------------------
NEW_GAME_NAMES = {
    "monopoly":"Monopoly", "poker":"Poker", "uno":"UNO", "detective":"Detective",
    "tower":"Tower Defense", "racing":"Car Racing", "football":"Football", "brain":"Brain Battle",
    "mystery":"Mystery Box", "rps":"Rock Paper Scissors", "monster":"Monster Battle", "hidden":"Hidden Object",
    "door":"Choose a Door", "picture":"Picture Quiz", "memory":"Memory Match", "weapon":"Weapon Choice"
}

def record_arcade_score(user, game, points):
    with db_connect() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS arcade_scores (user_id INTEGER NOT NULL, username TEXT NOT NULL, game TEXT NOT NULL, points INTEGER NOT NULL DEFAULT 0, played INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(user_id,game))")
        conn.execute("INSERT INTO arcade_scores(user_id,username,game,points,played) VALUES(?,?,?,?,1) ON CONFLICT(user_id,game) DO UPDATE SET username=excluded.username, points=arcade_scores.points+excluded.points, played=arcade_scores.played+1", (user.id, user.first_name or str(user.id), game, int(points)))

def arcade_kb(game, buttons):
    rows=[[InlineKeyboardButton(label, callback_data=data)] for label,data in buttons]
    rows.append([InlineKeyboardButton("🎮 Game Center", callback_data="menu_games")])
    return InlineKeyboardMarkup(rows)

PICTURE_QUIZ_QUESTIONS = [
    {"emoji":"🍎", "file":"1f34e", "q":"ဒီပုံထဲမှာ ဘယ်အရာကို မြင်ရသလဲ?", "options":["ပန်းသီး", "ငှက်ပျောသီး", "လိမ္မော်သီး"], "answer":0},
    {"emoji":"🚗", "file":"1f697", "q":"ဒီပုံထဲမှာ ဘယ်ယာဉ်ကို မြင်ရသလဲ?", "options":["စက်ဘီး", "ကား", "လေယာဉ်"], "answer":1},
    {"emoji":"🐱", "file":"1f431", "q":"ဒီပုံထဲမှာ ဘယ်တိရစ္ဆာန်လဲ?", "options":["ခွေး", "ကြောင်", "ယုန်"], "answer":1},
    {"emoji":"🏠", "file":"1f3e0", "q":"ဒီပုံက ဘာအဆောက်အအုံလဲ?", "options":["အိမ်", "ကျောင်း", "ဆေးရုံ"], "answer":0},
    {"emoji":"🐟", "file":"1f41f", "q":"ဒီပုံထဲမှာ ဘာကို မြင်ရသလဲ?", "options":["ငါး", "ငှက်", "လိပ်"], "answer":0},
    {"emoji":"🌳", "file":"1f333", "q":"ဒီပုံထဲမှာ ဘာရှိသလဲ?", "options":["ပန်း", "သစ်ပင်", "တောင်"], "answer":1},
    {"emoji":"📚", "file":"1f4da", "q":"ဒီပုံထဲက ပစ္စည်းက ဘာလဲ?", "options":["စာအုပ်များ", "ဖုန်းများ", "ဖိနပ်များ"], "answer":0},
    {"emoji":"⚽", "file":"1f3c8", "q":"ဒီပုံက ဘယ်အားကစားနဲ့ သက်ဆိုင်သလဲ?", "options":["ဘတ်စကက်ဘော", "ဘောလုံး", "တင်းနစ်"], "answer":1},
]

async def send_picture_quiz(query, context):
    """Send a real picture and three answer buttons for a solo picture quiz."""
    q = random.choice(PICTURE_QUIZ_QUESTIONS)
    context.user_data["picture_quiz_answer"] = q["answer"]
    context.user_data["picture_quiz_question"] = q
    context.user_data["picture_quiz_score"] = context.user_data.get("picture_quiz_score", 0)
    image_url = f"https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/{q['file']}.png"
    keyboard = [[InlineKeyboardButton(option, callback_data=f"picq_{i}")] for i, option in enumerate(q["options"])]
    keyboard.append([InlineKeyboardButton("🎮 Game Center", callback_data="menu_games")])
    caption = f"🖼️ **Picture Quiz**\n{q['q']}\n\nအဖြေ ၃ ခုထဲမှ တစ်ခုကို ရွေးပါ။\n⭐ လက်ရှိအမှတ်: {context.user_data['picture_quiz_score']}"
    await query.message.reply_photo(photo=image_url, caption=caption, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def additional_game_callback(query, context, data):
    user=query.from_user; ud=context.user_data
    # Eight additional solo-vs-bot visual/choice mini-games.
    if data.startswith("new_"):
        game=data[4:]
        if game in {"mystery","rps","monster","hidden","door","picture","memory","weapon"}:
            ud["extra_game"]=game
            if game == "mystery":
                prize=random.randrange(6); ud["mystery_prize"]=prize
                kb=InlineKeyboardMarkup([[InlineKeyboardButton(f"🎁 {i+1}",callback_data=f"arcx_mystery_{i}") for i in range(3)], [InlineKeyboardButton(f"🎁 {i+1}",callback_data=f"arcx_mystery_{i}") for i in range(3,6)], [InlineKeyboardButton("🎮 Game Center",callback_data="menu_games")]])
                await query.edit_message_text("🎁 **Mystery Box**\nသေတ္တာ ၆ လုံးထဲက ဆုလက်ဆောင်ပါတဲ့ တစ်လုံးကို ရွေးပါ!",parse_mode="Markdown",reply_markup=kb)
            elif game == "rps":
                kb=InlineKeyboardMarkup([[InlineKeyboardButton(x,callback_data=f"arcx_rps_{v}") for x,v in (("✊ ကျောက်","rock"),("✋ စက္ကူ","paper"),("✌️ ကတ်ကြေး","scissors"))],[InlineKeyboardButton("🎮 Game Center",callback_data="menu_games")]])
                await query.edit_message_text("✊ **Rock Paper Scissors**\nBot ကို ယှဉ်ပြိုင်ဖို့ တစ်ခုရွေးပါ။",parse_mode="Markdown",reply_markup=kb)
            elif game == "monster":
                ud["monster_hp"]=60; ud["monster_enemy_hp"]=55
                kb=InlineKeyboardMarkup([[InlineKeyboardButton("⚔️ တိုက်ခိုက်မည်",callback_data="arcx_monster_attack"),InlineKeyboardButton("🧪 ကုသမည်",callback_data="arcx_monster_heal")],[InlineKeyboardButton("🎮 Game Center",callback_data="menu_games")]])
                await query.edit_message_text("🐉 **Monster Battle**\nသင့် HP: 60 | ဘီလူး HP: 55\nတိုက်ခိုက်ပါ၊ လိုအပ်လျှင် ဆေးသုံးပါ။",parse_mode="Markdown",reply_markup=kb)
            elif game == "hidden":
                items=["🗝️ သော့","💎 စိန်","🪙 ဒင်္ဂါး","🧸 ဝက်ဝံရုပ်","📜 စာလိပ်","⭐ ကြယ်"]
                target=random.randrange(len(items)); ud["hidden_target"]=target
                kb=InlineKeyboardMarkup([[InlineKeyboardButton(items[i],callback_data=f"arcx_hidden_{i}") for i in range(3)],[InlineKeyboardButton(items[i],callback_data=f"arcx_hidden_{i}") for i in range(3,6)],[InlineKeyboardButton("🎮 Game Center",callback_data="menu_games")]])
                await query.edit_message_text("🔎 **Hidden Object**\nပစ္စည်း ၆ မျိုးထဲမှာ ဝှက်ထားတဲ့ ရတနာကို ရှာပါ!",parse_mode="Markdown",reply_markup=kb)
                ud["hidden_items"]=items
            elif game == "door":
                ud["door_safe"]=random.randrange(3)
                kb=InlineKeyboardMarkup([[InlineKeyboardButton(f"🚪 တံခါး {i+1}",callback_data=f"arcx_door_{i}") for i in range(3)],[InlineKeyboardButton("🎮 Game Center",callback_data="menu_games")]])
                await query.edit_message_text("🚪 **Choose a Door**\nတံခါး ၃ ပေါက်ထဲက ဘေးကင်းပြီး ဆုရှိတဲ့ တံခါးကို ရွေးပါ!",parse_mode="Markdown",reply_markup=kb)
            elif game == "picture":
                await send_picture_quiz(query, context)
            elif game == "memory":
                vals=["🍎","🚗","🐱","🌟","🍎","🚗","🐱","🌟"]; random.shuffle(vals); ud["memory_vals"]=vals; ud["memory_open"]=[]; ud["memory_found"]=[]
                kb=InlineKeyboardMarkup([[InlineKeyboardButton("❔",callback_data=f"arcx_memory_{i}") for i in range(4)],[InlineKeyboardButton("❔",callback_data=f"arcx_memory_{i}") for i in range(4,8)],[InlineKeyboardButton("🎮 Game Center",callback_data="menu_games")]])
                await query.edit_message_text("🧠 **Memory Match**\nတူညီတဲ့ ပုံအတွဲ ၄ တွဲကို မှတ်မိအောင် ရှာပါ။ တစ်ကြိမ်လျှင် ကတ် ၂ ချပ်ဖွင့်နိုင်ပါတယ်။",parse_mode="Markdown",reply_markup=kb)
            elif game == "weapon":
                ud["weapon_enemy"]=random.choice(["🛡️ ဒိုင်း","🐉 ဘီလူး","🏹 လေးမြား"])
                kb=InlineKeyboardMarkup([[InlineKeyboardButton(x,callback_data=f"arcx_weapon_{v}")] for x,v in (("⚔️ ဓား","sword"),("🏹 လေးမြား","bow"),("🪄 မန္တန်တုတ်","wand"))]+[[InlineKeyboardButton("🎮 Game Center",callback_data="menu_games")]])
                await query.edit_message_text("⚔️ **Weapon Choice**\nပြိုင်ဘက်ကို အနိုင်ယူနိုင်မယ့် လက်နက်ကို ရွေးချယ်ပါ။",parse_mode="Markdown",reply_markup=kb)
            return
        game=data[4:]
        ud["arcade_game"]=game
        if game=="monopoly":
            ud["mono_cash"]=500; ud["mono_pos"]=0
            await query.edit_message_text("🏠 **Monopoly Mini**\nသင့်မှာ 500 Coins ရှိပါတယ်။ အန်စာတုံးလှိမ့်ပြီး မြေကွက်ဝယ်ပါ။\n\n💰 500 | 📍 Start",parse_mode="Markdown",reply_markup=arcade_kb(game,[("🎲 အန်စာတုံးလှိမ့်မည်","arc_mono_roll")]))
        elif game=="poker":
            # Play-money only; no deposits, withdrawals or real-money wagering.
            cards=[random.randint(2,14) for _ in range(5)]; ud["poker_cards"]=cards
            score=sum(cards); record_arcade_score(user,game,score)
            await query.edit_message_text("🃏 **Poker Draw (အမှတ်ကစား)**\nသင့်ကတ်: "+", ".join(map(str,cards))+f"\n\nစုစုပေါင်းအမှတ်: {score}\nအမြင့်ဆုံးအမှတ်ရအောင် ထပ်ဆော့နိုင်ပါတယ်။",parse_mode="Markdown",reply_markup=arcade_kb(game,[("🃏 ကတ်အသစ်ဆွဲမည်","new_poker")]))
        elif game=="uno":
            colors=["🔴 အနီ","🟢 အစိမ်း","🔵 အပြာ","🟡 အဝါ"]; ud["uno_top"]=(random.choice(colors),random.randint(0,9)); ud["uno_hand"]=[(random.choice(colors),random.randint(0,9)) for _ in range(5)]
            top=ud["uno_top"]; hand=ud["uno_hand"]
            opts=[(f"{c} {n}",f"arc_uno_{i}") for i,(c,n) in enumerate(hand)]
            await query.edit_message_text(f"🎴 **UNO Mini**\nအပေါ်ကတ်: {top[0]} {top[1]}\nသင့်ကတ်များ: "+" | ".join(f"{c} {n}" for c,n in hand)+"\nအရောင်တူ သို့မဟုတ် နံပါတ်တူကတ်ကို ရွေးပါ။",parse_mode="Markdown",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(a,callback_data=b)] for a,b in opts]+[[InlineKeyboardButton("🎮 Game Center",callback_data="menu_games")]]))
        elif game=="detective":
            ud["detective_answer"]="မီးဖိုချောင်ဓား"
            await query.edit_message_text("🕵️ **Detective Case #01**\nအိမ်ရှင်ကို ည ၉ နာရီမှာ စာကြည့်ခန်းထဲ ဒဏ်ရာရလျက်တွေ့ရှိခဲ့သည်။ မီးဖိုချောင်မှာ ဓားတစ်ချောင်းပျောက်နေပြီး ပြတင်းပေါက်မှာ အပြင်မှဝင်ရာ ခြေရာမရှိပါ။ သဲလွန်စအရ ဘယ်ပစ္စည်းက အရေးကြီးဆုံးလဲ?",parse_mode="Markdown",reply_markup=arcade_kb(game,[("🔪 မီးဖိုချောင်ဓား","arc_detective_right"),("🪟 ပြတင်းပေါက်","arc_detective_wrong"),("📚 စာအုပ်","arc_detective_wrong")]))
        elif game=="tower":
            ud["tower_wave"]=1; ud["tower_gold"]=100; ud["tower_level"]=1
            await query.edit_message_text("🏰 **Tower Defense**\nလှိုင်း ၁ စတင်ပါပြီ။ ရွှေ 100၊ Tower Lv.1\nရန်သူကို တားဆီးဖို့ Tower မြှင့်ပါ။",parse_mode="Markdown",reply_markup=arcade_kb(game,[("⬆️ Tower မြှင့် (30 Gold)","arc_tower_upgrade"),("⚔️ Wave ကို တိုက်မည်","arc_tower_wave")]))
        elif game=="racing":
            ud["race_distance"]=0; ud["race_fuel"]=5
            await query.edit_message_text("🏎️ **Car Racing**\nပြိုင်ပွဲစပါပြီ။ အရှိန်မြှင့်ပြီး Finish Line ကို အရင်ရောက်အောင်လုပ်ပါ။\nလောင်စာ 5",parse_mode="Markdown",reply_markup=arcade_kb(game,[("🚀 အရှိန်မြှင့်မည်","arc_race_go"),("🛞 Nitro သုံးမည်","arc_race_nitro")]))
        elif game=="football":
            ud["football_goals"]=0; ud["football_shots"]=0
            await query.edit_message_text("⚽ **Penalty Shootout**\nဘယ်၊ အလယ်၊ ညာ ထဲက တစ်နေရာရွေးပြီး ကန်ပါ။ ကန်ခွင့် ၅ ကြိမ်ရှိပါတယ်။",parse_mode="Markdown",reply_markup=arcade_kb(game,[("⬅️ ဘယ်ဘက်","arc_football_left"),("⬆️ အလယ်","arc_football_center"),("➡️ ညာဘက်","arc_football_right")]))
        elif game=="brain":
            ud["brain_answer"]=3
            await query.edit_message_text("🧠 **Brain Battle**\n၂, ၄, ၆, ၈, ?\nနောက်ထပ်ကိန်းဂဏန်းက ဘာလဲ?",parse_mode="Markdown",reply_markup=arcade_kb(game,[("၉","arc_brain_9"),("၁၀","arc_brain_10"),("၁၂","arc_brain_12")]))
        return
    if data.startswith("arcx_"):
        parts=data.split("_"); game=parts[1]; choice="_".join(parts[2:])
        if game == "mystery":
            win=int(choice)==ud.get("mystery_prize",-1); record_arcade_score(user,"mystery",20 if win else 0)
            await query.edit_message_text("🎉 ဆုလက်ဆောင်ရရှိပါပြီ! +20 မှတ်" if win else f"📦 ဗလာသေတ္တာပါ။ ဆုရှိတဲ့သေတ္တာက နံပါတ် {ud.get('mystery_prize',0)+1} ပါ။",reply_markup=arcade_kb("mystery",[("🔄 ထပ်ကစားမည်","new_mystery")]))
        elif game == "rps":
            bot=random.choice(["rock","paper","scissors"]); beats={"rock":"scissors","paper":"rock","scissors":"paper"}; names={"rock":"✊ ကျောက်","paper":"✋ စက္ကူ","scissors":"✌️ ကတ်ကြေး"}
            result="သရေကျပါတယ်။" if choice==bot else ("🎉 သင်နိုင်ပါတယ်! +10 မှတ်" if beats[choice]==bot else "🤖 Bot နိုင်ပါတယ်။")
            if beats[choice]==bot: record_arcade_score(user,"rps",10)
            await query.edit_message_text(f"✊ သင်: {names[choice]}\n🤖 Bot: {names[bot]}\n{result}",reply_markup=arcade_kb("rps",[("🔄 ထပ်ကစားမည်","new_rps")]))
        elif game == "monster":
            hp=ud.get("monster_hp",0); ehp=ud.get("monster_enemy_hp",0)
            if choice=="heal": hp=min(60,hp+15); note="🧪 HP ၁၅ ပြန်တိုးပါတယ်။"
            else: damage=random.randint(12,22); ehp=max(0,ehp-damage); note=f"⚔️ ဘီလူးကို {damage} ထိခိုက်စေပါတယ်။"
            if ehp>0: hit=random.randint(7,14); hp=max(0,hp-hit); note+=f"\n🐉 ဘီလူးက ပြန်တိုက်လို့ {hit} HP ဆုံးရှုံးပါတယ်။"
            ud["monster_hp"]=hp; ud["monster_enemy_hp"]=ehp
            if hp<=0 or ehp<=0:
                won=ehp<=0; record_arcade_score(user,"monster",30 if won else 0)
                await query.edit_message_text(("🏆 ဘီလူးကို အနိုင်ယူနိုင်ပါပြီ! +30 မှတ်" if won else "💀 သင်ရှုံးနိမ့်သွားပါတယ်။")+f"\nသင့် HP {hp} | ဘီလူး HP {ehp}",reply_markup=arcade_kb("monster",[("🔄 ပြန်စမည်","new_monster")]))
            else:
                kb=InlineKeyboardMarkup([[InlineKeyboardButton("⚔️ တိုက်ခိုက်မည်",callback_data="arcx_monster_attack"),InlineKeyboardButton("🧪 ကုသမည်",callback_data="arcx_monster_heal")],[InlineKeyboardButton("🎮 Game Center",callback_data="menu_games")]])
                await query.edit_message_text(f"🐉 Monster Battle\n{note}\n❤️ သင့် HP: {hp} | ဘီလူး HP: {ehp}",reply_markup=kb)
        elif game == "hidden":
            i=int(choice); items=ud.get("hidden_items",[]); win=i==ud.get("hidden_target",-1); record_arcade_score(user,"hidden",15 if win else 0)
            await query.edit_message_text((f"🎉 {items[i]} ကို ရှာတွေ့ပါပြီ!" if win else f"❌ မတွေ့သေးပါ။ ဝှက်ထားတာက {items[ud['hidden_target']]} ဖြစ်ပါတယ်။"),reply_markup=arcade_kb("hidden",[("🔄 ထပ်ရှာမည်","new_hidden")]))
        elif game == "door":
            win=int(choice)==ud.get("door_safe",-1); record_arcade_score(user,"door",15 if win else 0)
            await query.edit_message_text("🏆 တံခါးမှန်ကို ရွေးမိပါတယ်! ဆုရရှိပါပြီ။" if win else f"💥 မှားသွားပါတယ်။ ဘေးကင်းတဲ့တံခါးက {ud.get('door_safe',0)+1} ဖြစ်ပါတယ်။",reply_markup=arcade_kb("door",[("🔄 ထပ်ရွေးမည်","new_door")]))
        elif game == "picture":
            win=int(choice)==ud.get("picture_answer",-1); record_arcade_score(user,"picture",15 if win else 0)
            await query.edit_message_text("🎉 အဖြေမှန်ပါတယ်! +15 မှတ်" if win else "❌ အဖြေမှားပါတယ်။",reply_markup=arcade_kb("picture",[("🖼️ မေးခွန်းအသစ်","new_picture")]))
        elif game == "memory":
            i=int(choice); vals=ud.get("memory_vals",[]); opened=ud.get("memory_open",[]); found=ud.get("memory_found",[])
            if i in found or i in opened: await query.answer("ဒီကတ်ကို ဖွင့်ပြီးပါပြီ။"); return
            opened.append(i)
            if len(opened)==2:
                if vals[opened[0]]==vals[opened[1]]: found.extend(opened); note="🎉 ပုံတူအတွဲ မှန်ပါတယ်!"
                else: note="မတူပါဘူး။ နောက်တစ်ကြိမ် မှတ်မိအောင်ကြိုးစားပါ။"
                opened.clear()
            else: note="ကတ်တစ်ချပ် ဖွင့်ပြီးပါပြီ။ နောက်တစ်ချပ်ရွေးပါ။"
            ud["memory_open"]=opened; ud["memory_found"]=found
            rows=[]
            for r in range(2):
                row=[]
                for j in range(r*4,r*4+4): row.append(InlineKeyboardButton(vals[j] if j in found or j in opened else "❔",callback_data=f"arcx_memory_{j}" if j not in found else "arcx_memory_done"))
                rows.append(row)
            rows.append([InlineKeyboardButton("🎮 Game Center",callback_data="menu_games")])
            if len(found)==8:
                record_arcade_score(user,"memory",40); await query.edit_message_text("🏆 ပုံအတွဲအားလုံးကို ရှာတွေ့ပါပြီ! +40 မှတ်",reply_markup=arcade_kb("memory",[("🔄 ပြန်ကစားမည်","new_memory")]))
            else: await query.edit_message_text(f"🧠 Memory Match\n{note}\nတွေ့ပြီး: {len(found)//2}/4 အတွဲ",reply_markup=InlineKeyboardMarkup(rows))
        elif game == "weapon":
            enemy=ud.get("weapon_enemy"); win=(choice=="sword" and enemy=="🐉 ဘီလူး") or (choice=="bow" and enemy=="🛡️ ဒိုင်း") or (choice=="wand" and enemy=="🏹 လေးမြား")
            record_arcade_score(user,"weapon",20 if win else 0)
            await query.edit_message_text(f"⚔️ သင်ရွေးသောလက်နက်: {choice}\nပြိုင်ဘက်: {enemy}\n"+("🏆 အနိုင်ရပါတယ်! +20 မှတ်" if win else "🤖 ဒီတစ်ကြိမ်တော့ မနိုင်ပါဘူး။"),reply_markup=arcade_kb("weapon",[("🔄 ထပ်ကစားမည်","new_weapon")]))
        return
    if data=="arc_mono_roll":
        roll=random.randint(1,6); cash=ud.get("mono_cash",500); pos=ud.get("mono_pos",0)+roll
        if pos%4==0: cash+=100; event="ပိုင်ဆိုင်မှုအငှား +100 Coins"
        elif pos%3==0 and cash>=80: cash-=80; event="မြေကွက်ဝယ်ယူ -80 Coins"
        else: event="ဘာမှမဖြစ်ပါ။"
        ud["mono_cash"]=cash; ud["mono_pos"]=pos; record_arcade_score(user,"monopoly",max(0,roll*5))
        await query.edit_message_text(f"🏠 Monopoly\n🎲 {roll} လှိမ့်ရရှိ\n📍 နေရာ {pos}\n💰 {cash} Coins\n{event}",reply_markup=arcade_kb("monopoly",[("🎲 ထပ်လှိမ့်မည်","arc_mono_roll")]))
    elif data.startswith("arc_uno_"):
        i=int(data.rsplit("_",1)[1]); hand=ud.get("uno_hand",[]); top=ud.get("uno_top")
        if i>=len(hand): return
        card=hand[i]
        if card[0]==top[0] or card[1]==top[1]:
            hand.pop(i); ud["uno_top"]=card; record_arcade_score(user,"uno",10)
            msg="🎉 ကတ်ချနိုင်ပါပြီ!" + (" UNO အနိုင်ရပါပြီ!" if not hand else f" ကျန်ကတ် {len(hand)} ချပ်")
        else: msg="❌ အရောင်/နံပါတ် မတူပါ။ ထပ်ရွေးပါ။"
        opts=[(f"{c} {n}",f"arc_uno_{j}") for j,(c,n) in enumerate(hand)]
        await query.edit_message_text(f"🎴 UNO\nအပေါ်ကတ်: {ud['uno_top'][0]} {ud['uno_top'][1]}\n{msg}",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(a,callback_data=b)] for a,b in opts]+[[InlineKeyboardButton("ကတ်အသစ်",callback_data="new_uno")],[InlineKeyboardButton("🎮 Game Center",callback_data="menu_games")]]))
    elif data.startswith("arc_detective_"):
        ok=data.endswith("right"); record_arcade_score(user,"detective",20 if ok else 0)
        await query.edit_message_text("🎉 အမှုမှန်ကို ဖော်ထုတ်နိုင်ပါပြီ!" if ok else "❌ သဲလွန်စကို မှားယွင်းရွေးချယ်ခဲ့ပါတယ်။",reply_markup=arcade_kb("detective",[("🔎 Case အသစ်","new_detective")]))
    elif data=="arc_tower_upgrade":
        gold=ud.get("tower_gold",0)
        if gold>=30: ud["tower_gold"]=gold-30; ud["tower_level"]+=1; msg="Tower အဆင့်မြှင့်ပြီးပါပြီ။"
        else: msg="ရွှေမလောက်ပါ။ Wave တိုက်ပြီး ရွှေရှာပါ။"
        await query.edit_message_text(f"🏰 Tower Lv.{ud['tower_level']} | Gold {ud['tower_gold']}\n{msg}",reply_markup=arcade_kb("tower",[("⬆️ Tower မြှင့် (30 Gold)","arc_tower_upgrade"),("⚔️ Wave တိုက်မည်","arc_tower_wave")]))
    elif data=="arc_tower_wave":
        power=ud.get("tower_level",1)*random.randint(8,15); enemy=random.randint(8,35); win=power>=enemy
        ud["tower_wave"]+=1; ud["tower_gold"]+=25 if win else 5; record_arcade_score(user,"tower",20 if win else 5)
        await query.edit_message_text(f"🏰 Wave {ud['tower_wave']}\n{'🏆 အောင်မြင်စွာ ကာကွယ်နိုင်ပါပြီ!' if win else '💥 ရန်သူအချို့ ဖြတ်ကျော်သွားပါတယ်။'}\nGold: {ud['tower_gold']}",reply_markup=arcade_kb("tower",[("⬆️ Tower မြှင့်","arc_tower_upgrade"),("⚔️ နောက် Wave","arc_tower_wave")]))
    elif data in ("arc_race_go","arc_race_nitro"):
        fuel=ud.get("race_fuel",0); dist=ud.get("race_distance",0)
        if fuel<=0: await query.edit_message_text(f"🏁 ပြိုင်ပွဲပြီးပါပြီ။ အကွာအဝေး {dist} m",reply_markup=arcade_kb("racing",[("🔄 ထပ်ပြိုင်မည်","new_racing")])); return
        step=random.randint(15,30)*(2 if data.endswith("nitro") else 1); dist+=step; fuel-=1
        ud["race_distance"]=dist; ud["race_fuel"]=fuel; record_arcade_score(user,"racing",step)
        won=dist>=100
        await query.edit_message_text(f"🏎️ အကွာအဝေး {dist} m / 100 m\nလောင်စာ {fuel}\n{'🏆 သင်အနိုင်ရပါပြီ!' if won else 'ဆက်မောင်းပါ!'}",reply_markup=arcade_kb("racing",[("🚀 အရှိန်မြှင့်","arc_race_go"),("🛞 Nitro","arc_race_nitro"),("🔄 ပြန်စမည်","new_racing")]))
    elif data.startswith("arc_football_"):
        shots=ud.get("football_shots",0)+1; goals=ud.get("football_goals",0); kick=data.rsplit("_",1)[1]; keeper=random.choice(["left","center","right"])
        if kick!=keeper: goals+=1
        ud["football_shots"]=shots; ud["football_goals"]=goals
        if shots>=5: record_arcade_score(user,"football",goals*20); await query.edit_message_text(f"⚽ ပွဲပြီးပါပြီ! ဂိုး {goals}/5",reply_markup=arcade_kb("football",[("🔄 ထပ်ကစားမည်","new_football")]))
        else: await query.edit_message_text(f"⚽ ဂိုး {goals} | ကန်ပြီး {shots}/5\nနောက်တစ်ကြိမ် ကန်ပါ။",reply_markup=arcade_kb("football",[("⬅️ ဘယ်","arc_football_left"),("⬆️ အလယ်","arc_football_center"),("➡️ ညာ","arc_football_right")]))
    elif data.startswith("arc_brain_"):
        ok=data.endswith("10"); record_arcade_score(user,"brain",30 if ok else 0)
        await query.edit_message_text("🎉 မှန်ပါတယ်! +30 Points" if ok else "❌ အဖြေမှန်က ၁၀ ဖြစ်ပါတယ်။",reply_markup=arcade_kb("brain",[("🧠 မေးခွန်းအသစ်","new_brain")]))


# ------------------------- MLBB ENGLISH HERO VOICE GUESS -------------------------
MLBB_WIKI = "https://mobile-legends.fandom.com"
MLBB_CATEGORY_URL = MLBB_WIKI + "/wiki/Category:Hero_audio"
# ------------------------- MLBB HERO IMAGE GUESS -------------------------
MLBB_WIKI = "https://mobile-legends.fandom.com"
MLBB_IMAGE_CACHE = os.path.join(os.path.dirname(os.path.abspath(DB_PATH)) or ".", "mlbb_hero_images")


def _mlbb_image_candidates_sync():
    """Read hero page thumbnails through MediaWiki API; no audio scraping."""
    names=[]; cont={}
    # The wiki category can change; try the main hero category and a common alternate.
    categories = ["Category:Heroes", "Category:Hero"]
    for category in categories:
        names=[]; cont={}
        for _ in range(8):
            params={"action":"query","list":"categorymembers","cmtitle":category,"cmtype":"page","cmlimit":"500",**cont}
            url=MLBB_WIKI+"/api.php?"+urllib.parse.urlencode({"format":"json",**params})
            data=_fetch_json(url)
            names.extend(x.get("title","") for x in data.get("query",{}).get("categorymembers",[]))
            cont=data.get("continue")
            if not cont: break
        if names:
            break
    names=[n for n in names if n and not n.startswith(("Category:","User:"))]
    if not names: raise RuntimeError("MLBB hero categories returned no pages")
    random.shuffle(names)
    for title in names[:100]:
        params={"action":"query","titles":title,"prop":"pageimages","piprop":"thumbnail","pithumbsize":"700"}
        url=MLBB_WIKI+"/api.php?"+urllib.parse.urlencode({"format":"json",**params})
        data=_fetch_json(url)
        for page in data.get("query",{}).get("pages",{}).values():
            thumb=page.get("thumbnail",{}).get("source")
            if thumb: yield title,thumb


def _mlbb_cache_image_sync(hero, url):
    os.makedirs(MLBB_IMAGE_CACHE,exist_ok=True)
    safe=re.sub(r"[^A-Za-z0-9._-]","_",hero)+".jpg"
    path=os.path.join(MLBB_IMAGE_CACHE,safe)
    if not os.path.isfile(path) or os.path.getsize(path)<1000:
        req=urllib.request.Request(url,headers={"User-Agent":"CKBotMLBBImageQuiz/1.0"})
        with urllib.request.urlopen(req,timeout=20) as response: data=response.read(8*1024*1024+1)
        if not data or len(data)>8*1024*1024: raise ValueError("Invalid or oversized image")
        with open(path,"wb") as f: f.write(data)
    return path


def mlbbi_random_cached():
    with db_connect() as conn:
        rows=conn.execute("SELECT * FROM mlbb_hero_images ORDER BY RANDOM() LIMIT 1").fetchone()
        return dict(rows) if rows else None


async def mlbbi_discover():
    cached=mlbbi_random_cached()
    try:
        candidates=await asyncio.to_thread(lambda: list(_mlbb_image_candidates_sync()))
        random.shuffle(candidates)
        for hero,url in candidates[:12]:
            try:
                path=await asyncio.to_thread(_mlbb_cache_image_sync,hero,url)
                with db_connect() as conn:
                    conn.execute("INSERT OR REPLACE INTO mlbb_hero_images(hero,image_path,source_url,created_at) VALUES(?,?,?,?)",(hero,path,url,int(time.time())))
                    conn.commit()
                return {"hero":hero,"image_path":path,"source_url":url}
            except Exception: logger.exception("Could not cache MLBB hero image: %s",hero)
    except Exception:
        logger.exception("MLBB image discovery failed; check Railway outbound network and MediaWiki API access")
    if cached and os.path.isfile(cached["image_path"]): return cached
    return None


async def mlbbi_start(message):
    status=await message.reply_text("🖼️ MLBB Hero ပုံတွေ ရှာဖွေနေပါတယ်။ ခဏစောင့်ပါ…")
    item=await mlbbi_discover()
    if not item:
        await status.edit_text("⚠️ MLBB Hero ပုံရင်းမြစ်ကို လောလောဆယ် မရယူနိုင်သေးပါ။ Railway Logs နဲ့ Network ကို စစ်ဆေးပြီး ပြန်စမ်းပါ။")
        return
    chat_id=message.chat_id
    with db_connect() as conn:
        old=conn.execute("SELECT round_no FROM mlbb_image_sessions WHERE chat_id=?",(chat_id,)).fetchone()
        rnd=(old[0]+1) if old else 1
        conn.execute("INSERT INTO mlbb_image_sessions(chat_id,hero,status,round_no,hint_used,started_at) VALUES(?,?,'active',?,0,?) ON CONFLICT(chat_id) DO UPDATE SET hero=excluded.hero,status='active',round_no=excluded.round_no,hint_used=0,started_at=excluded.started_at",(chat_id,item["hero"],rnd,int(time.time())))
        conn.commit()
    try:
        with open(item["image_path"],"rb") as photo:
            await message.reply_photo(photo=photo,caption=f"🗡️ **MLBB HERO IMAGE GUESS**\nRound {rnd}\n\nဒီပုံထဲက Hero ကို English နာမည်နဲ့ ခန့်မှန်းပါ။\nလက်နက်/ဝတ်စုံ/ပုံစံကို သေချာကြည့်ပါ။",parse_mode="Markdown")
        await status.delete()
    except Exception:
        logger.exception("Could not send MLBB hero image")
        await status.edit_text("⚠️ Hero ပုံကို Telegram သို့ မပို့နိုင်ပါ။ နောက်တစ်ကြိမ် ပြန်စမ်းပါ။")
        return
    await message.reply_text("အဖြေကို Chat ထဲမှာ ရိုက်ပို့ပါ။ Group မှာ အရင်ဆုံးမှန်သူ +10 Points ရပါမယ်။",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💡 Hint",callback_data="mlbbi_hint"),InlineKeyboardButton("⏭️ Skip",callback_data="mlbbi_skip")],[InlineKeyboardButton("🔄 ပုံအသစ်",callback_data="mlbbi_start"),InlineKeyboardButton("🏆 Ranking",callback_data="mlbbi_rank")]]))


async def mlbbi_callback(query,data):
    chat_id=query.message.chat_id
    if data=="mlbbi_start": await mlbbi_start(query.message); return
    with db_connect() as conn: row=conn.execute("SELECT * FROM mlbb_image_sessions WHERE chat_id=? AND status='active'",(chat_id,)).fetchone()
    if data=="mlbbi_rank":
        with db_connect() as conn: rows=conn.execute("SELECT username,points,wins FROM mlbb_image_scores ORDER BY points DESC,wins DESC LIMIT 10").fetchall()
        await query.message.reply_text("🏆 **MLBB Hero Quiz Ranking**\n\n"+("\n".join(f"{i+1}. {r['username']} — {r['points']} pts" for i,r in enumerate(rows)) if rows else "ရမှတ်မရှိသေးပါ။"),parse_mode="Markdown"); return
    if not row: await query.message.reply_text("လက်ရှိ Round မရှိပါ။ ပုံအသစ်စပါ။"); return
    if data=="mlbbi_hint":
        hint=row["hero"][0]+"… (စာလုံး "+str(len(row["hero"]))+" လုံး)"
        with db_connect() as conn: conn.execute("UPDATE mlbb_image_sessions SET hint_used=1 WHERE chat_id=?",(chat_id,)); conn.commit()
        await query.message.reply_text("💡 Hint: "+hint); return
    if data=="mlbbi_skip":
        with db_connect() as conn: conn.execute("UPDATE mlbb_image_sessions SET status='finished' WHERE chat_id=?",(chat_id,)); conn.commit()
        await query.message.reply_text(f"⏭️ အဖြေမှန်က **{row['hero']}** ပါ။",parse_mode="Markdown",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 နောက်တစ် Round",callback_data="mlbbi_start")]]))


async def mlbbi_check_guess(update,raw_text):
    chat=update.effective_chat
    with db_connect() as conn: row=conn.execute("SELECT * FROM mlbb_image_sessions WHERE chat_id=? AND status='active'",(chat.id,)).fetchone()
    if not row: return False
    guess=re.sub(r"[^a-z0-9]","",raw_text.lower()); answer=re.sub(r"[^a-z0-9]","",row["hero"].lower())
    if guess!=answer:
        await update.message.reply_text("❌ မမှန်သေးပါ။ ထပ်ခန့်မှန်းကြည့်ပါ။"); return True
    user=update.effective_user
    with db_connect() as conn:
        cur=conn.execute("UPDATE mlbb_image_sessions SET status='finished' WHERE chat_id=? AND status='active'",(chat.id,))
        if cur.rowcount:
            conn.execute("INSERT INTO mlbb_image_scores(user_id,username,points,wins) VALUES(?,?,10,1) ON CONFLICT(user_id) DO UPDATE SET username=excluded.username,points=points+10,wins=wins+1",(user.id,user.first_name or str(user.id)))
            conn.commit()
        else: conn.rollback()
    if cur.rowcount:
        await update.message.reply_text(f"🎉 မှန်ပါတယ်! Hero က **{row['hero']}** ပါ။ +10 Points ရရှိပါတယ်။",parse_mode="Markdown",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 နောက်တစ် Round",callback_data="mlbbi_start")],[InlineKeyboardButton("🏆 Ranking",callback_data="mlbbi_rank")]]))
    else: await update.message.reply_text("ဒီ Round ကို အခြားသူက အရင်ဖြေပြီးပါပြီ။")
    return True


# ------------------------- MLBB HERO GUIDE & SEASON META -------------------------
MLBB_GUIDE_API = MLBB_WIKI + "/api.php"
MLBB_META_URL = "https://mlbbhub.com/tier-list"
MLBB_GUIDE_HEADERS = {"User-Agent": "CKBot/1.0 (MLBB guide; informational bot)"}

# Role-based starter builds are fallback guidance, not live in-game presets.
MLBB_ROLE_BUILDS = {
    "tank": {"role":"Tank / Roam", "items":["Tough Boots / Warrior Boots", "Dominance Ice", "Athena's Shield", "Antique Cuirass", "Immortality", "Radiant Armor"], "emblem":"Tank Emblem — Vitality, Tenacity, Concussive Blast", "spell":"Flicker (သို့) Vengeance"},
    "fighter": {"role":"Fighter / EXP", "items":["Tough Boots", "War Axe", "Queen's Wings", "Brute Force Breastplate", "Malefic Roar", "Immortality"], "emblem":"Fighter Emblem — Firmness, Festival of Blood, Brave Smite", "spell":"Vengeance / Execute / Flicker"},
    "assassin": {"role":"Assassin / Jungle", "items":["Tough Boots (Ice Retribution)", "Hunter Strike", "Blade of the Heptaseas", "Malefic Roar", "Blade of Despair", "Immortality"], "emblem":"Assassin Emblem — Rupture, Seasoned Hunter, Killing Spree", "spell":"Retribution (Jungle)"},
    "mage": {"role":"Mage / Mid", "items":["Arcane Boots", "Genius Wand", "Glowing Wand", "Divine Glaive", "Holy Crystal", "Blood Wings"], "emblem":"Mage Emblem — Inspire, Bargain Hunter, Lethal Ignition", "spell":"Flicker (သို့) Flameshot"},
    "marksman": {"role":"Marksman / Gold", "items":["Swift Boots", "Corrosion Scythe", "Demon Hunter Sword", "Golden Staff", "Malefic Gun", "Wind of Nature"], "emblem":"Marksman Emblem — Fatal, Weapon Master, Quantum Charge", "spell":"Inspire (သို့) Flicker"},
    "support": {"role":"Support / Roam", "items":["Tough Boots (Roam Blessing)", "Flask of the Oasis", "Dominance Ice", "Athena's Shield", "Immortality", "Oracle"], "emblem":"Support Emblem — Agility, Pull Yourself Together, Focusing Mark", "spell":"Flicker / Revitalize"},
}

MLBB_HERO_ROLES = {
    "masha":"fighter", "argus":"fighter", "aulus":"fighter", "sun":"fighter", "gloo":"tank", "khufra":"tank", "minotaur":"tank", "carmilla":"support", "rafaela":"support", "floryn":"support", "estes":"support", "valir":"mage", "gord":"mage", "eudora":"mage", "kagura":"mage", "kadita":"mage", "ling":"assassin", "saber":"assassin", "nolan":"assassin", "fanny":"assassin", "hanabi":"marksman", "bruno":"marksman", "obsidia":"marksman", "irithel":"marksman", "popol and kupa":"marksman", "popol":"marksman"
}

MLBB_COMBO_PRESETS = [
    ("Masha + Minotaur + Valir + Obsidia + Rafaela", "Masha EXP/Jungle က ရှေ့တန်းဖိအားပေး၊ Minotaur engage၊ Valir zone control၊ Obsidia damage နဲ့ Rafaela sustain ပေါင်းစပ်မှု။"),
    ("Gloo + Ling + Valir + Bruno + Floryn", "Gloo ရဲ့ frontline၊ Ling ရဲ့ backline dive၊ Valir ရဲ့ zoning၊ Bruno ရဲ့ Gold Lane damage နဲ့ Floryn heal။"),
    ("Khufra + Aulus + Gord + Hanabi + Estes", "Khufra engage နဲ့ Aulus follow-up၊ Gord poke၊ Hanabi team-fight damage၊ Estes sustain။")
]

def _mlbb_get_json_sync(params):
    url = MLBB_GUIDE_API + "?" + urllib.parse.urlencode({"format":"json", **params})
    return _fetch_json(url, timeout=18)


def _mlbb_hero_extract_sync(hero_name):
    data = _mlbb_get_json_sync({"action":"query", "generator":"search", "gsrsearch":hero_name + "", "gsrnamespace":0, "gsrlimit":5, "prop":"extracts|info", "exintro":1, "explaintext":1, "inprop":"url"})
    pages = data.get("query", {}).get("pages", {})
    if not pages:
        # Retry direct title lookup for common exact page names.
        data = _mlbb_get_json_sync({"action":"query", "titles":hero_name, "prop":"extracts|info", "exintro":1, "explaintext":1, "inprop":"url"})
        pages = data.get("query", {}).get("pages", {})
    candidates = [x for x in pages.values() if not x.get("missing")]
    if not candidates:
        return None
    # Prefer title matching the requested hero name.
    page = next((x for x in candidates if x.get("title", "").casefold() == hero_name.casefold()), candidates[0])
    return {"title":page.get("title", hero_name), "extract":page.get("extract", ""), "url":page.get("fullurl", MLBB_WIKI + "/wiki/" + urllib.parse.quote(page.get("title", hero_name).replace(" ", "_")))}


async def mlbb_hero_guide(update, context, hero_name, section="all"):
    msg = await update.effective_message.reply_text("🔎 MLBB Hero အချက်အလက်ကို Online မှ ရှာဖွေနေပါတယ်…")
    try:
        info = await asyncio.to_thread(_mlbb_hero_extract_sync, hero_name)
    except Exception:
        logger.exception("MLBB hero guide lookup failed")
        info = None
    if not info:
        await msg.edit_text("⚠️ Hero အချက်အလက် မတွေ့ပါ။ Hero နာမည်ကို English ဖြင့် စစ်ပြီး ပြန်စမ်းပါ။ ဥပမာ /hero Gusion")
        return
    title = info["title"]
    role_key = MLBB_HERO_ROLES.get(title.casefold())
    if not role_key:
        # infer only from explicit role text in the fetched wiki extract
        low = info["extract"].lower()
        role_key = next((r for r in ("tank","fighter","assassin","mage","marksman","support") if r in low), "fighter")
    build = MLBB_ROLE_BUILDS[role_key]
    lore = re.sub(r"\s+", " ", info["extract"]).strip()
    if not lore:
        lore = "ဒီ Hero အတွက် Wiki မှာ အကျဉ်းချုပ် Lore မရရှိသေးပါ။ မူရင်းစာမျက်နှာကို ဖွင့်ကြည့်ပါ။"
    lore = lore[:1800]
    if section == "lore":
        answer = f"📖 **{title} — Hero ဇာတ်လမ်း**\n\n{lore}\n\n🔗 {info['url']}"
    elif section == "build":
        answer = f"🛠️ **{title} — အကြံပြု Build**\nRole ခန့်မှန်းချက်: {build['role']}\n\n**Items (အခြေအနေအလိုက် ပြောင်းပါ):**\n" + "\n".join(f"{i+1}. {x}" for i,x in enumerate(build["items"])) + f"\n\n**Emblem:** {build['emblem']}\n\n**Battle Spell:** {build['spell']}\n\nမှတ်ချက်: ဒီ Build က Role အခြေပြု starter suggestion ဖြစ်ပြီး တိကျတဲ့ live pro build မဟုတ်ပါ။"
    else:
        answer = f"🦸 **{title} — MLBB Hero Guide**\n━━━━━━━━━━━━━━━━━━\n**Role ခန့်မှန်းချက်:** {build['role']}\n\n**📖 Lore:**\n{lore}\n\n**🛠️ Item Build (Starter):**\n" + "\n".join(f"{i+1}. {x}" for i,x in enumerate(build["items"])) + f"\n\n**🎖️ Emblem:** {build['emblem']}\n\n**✨ Battle Spell:** {build['spell']}\n\n**🎮 ကစားနည်း:** Skill combo ကို training mode မှာ စမ်းသပ်ပါ။ Enemy composition အလိုက် defense/anti-heal item ကို ပြောင်းလဲပါ.\n\n🔗 အချက်အလက်ရင်းမြစ်: {info['url']}"
    await msg.edit_text(answer, parse_mode="Markdown", disable_web_page_preview=True)


async def mlbb_combo_command(update, context):
    # Read the current public tier-list page; preset team compositions are suggestions, not guaranteed win rates.
    status = await update.effective_message.reply_text("📊 Season Meta ကို Online မှ စစ်ဆေးနေပါတယ်…")
    try:
        req = urllib.request.Request(MLBB_META_URL, headers=MLBB_GUIDE_HEADERS)
        def fetch_meta():
            with urllib.request.urlopen(req, timeout=15) as response:
                return response.read(2_000_000).decode("utf-8", "ignore")
        html = await asyncio.to_thread(fetch_meta)
        plain = re.sub(r"<[^>]+>", " ", html)
        plain = unescape(re.sub(r"\s+", " ", plain))
        season_match = re.search(r"Season\s+\d+", plain, re.I)
        patch_match = re.search(r"Patch\s+[0-9.]+[a-z]?", plain, re.I)
        season = season_match.group(0) if season_match else "လက်ရှိ Season (အတည်မပြုနိုင်)"
        patch = patch_match.group(0) if patch_match else "Patch မသိရသေး"
        head = f"📊 **MLBB {season} — Hero Combo အကြံပြုချက်**\n{patch}\n\n"
    except Exception:
        logger.exception("MLBB meta page unavailable")
        head = "📊 **MLBB Season Hero Combo အကြံပြုချက်**\nOnline Meta ကို ယခုမရနိုင်သဖြင့် ကြိုတင်သတ်မှတ်ထားသော Role synergy ကို ပြထားသည်။\n\n"
    body = "\n\n".join(f"**{i+1}. {name}**\n{desc}" for i,(name,desc) in enumerate(MLBB_COMBO_PRESETS))
    body += "\n\n⚠️ Combo များသည် Role synergy အခြေပြု အကြံပြုချက်များသာဖြစ်ပြီး လက်ရှိ patch အနိုင်ရနှုန်းအာမခံချက် မဟုတ်ပါ။ Draft၊ Rank နဲ့ အသင်းဖော်ကျွမ်းကျင်မှုအလိုက် ပြောင်းလဲပါ။\n🔗 Meta ရင်းမြစ်: " + MLBB_META_URL
    await status.edit_text(head + body, parse_mode="Markdown", disable_web_page_preview=True)


async def mlbb_meta_command(update, context):
    await mlbb_combo_command(update, context)


async def mlbb_hero_command(update, context):
    if not update.message: return
    if not context.args:
        context.user_data["mlbb_waiting_hero"] = "all"
        await update.message.reply_text("Hero နာမည်ကို English ဖြင့် ရိုက်ပို့ပါ။ ဥပမာ Gusion, Miya, Masha")
        return
    await mlbb_hero_guide(update, context, " ".join(context.args))


async def mlbb_build_command(update, context):
    if not update.message: return
    if not context.args:
        context.user_data["mlbb_waiting_hero"] = "build"
        await update.message.reply_text("Build ကြည့်လိုတဲ့ Hero နာမည်ကို English ဖြင့် ရိုက်ပို့ပါ။")
        return
    await mlbb_hero_guide(update, context, " ".join(context.args), "build")


async def mlbb_lore_command(update, context):
    if not update.message: return
    if not context.args:
        context.user_data["mlbb_waiting_hero"] = "lore"
        await update.message.reply_text("Lore ကြည့်လိုတဲ့ Hero နာမည်ကို English ဖြင့် ရိုက်ပို့ပါ။")
        return
    await mlbb_hero_guide(update, context, " ".join(context.args), "lore")


async def mlbb_duo_command(update, context):
    if not update.message: return
    hero = " ".join(context.args).strip()
    if not hero:
        await update.message.reply_text("ဥပမာ /duo Gusion — Hero နာမည်နဲ့ ပို့ပါ။")
        return
    partners = {"gusion":"Angela / Khufra / Atlas", "ling":"Angela / Khufra", "masha":"Minotaur / Rafaela", "obsidia":"Minotaur / Rafaela", "bruno":"Tigreal / Angela", "valir":"Khufra / Minotaur", "aulus":"Rafaela / Minotaur"}
    await update.message.reply_text(f"🤝 **{hero} နဲ့ လိုက်ဖက်နိုင်တဲ့ Hero များ**\n{partners.get(hero.casefold(), 'Minotaur / Khufra / Rafaela')}\n\nဒီအတွဲတွေက Skill synergy အခြေပြု အကြံပြုချက်သာဖြစ်ပြီး patch အလိုက် စမ်းသပ်ပြင်ဆင်ပါ။", parse_mode="Markdown")


# ------------------------- EXISTING BOT HANDLERS -------------------------

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Beginner-friendly Burmese command guide."""
    if not update.effective_message:
        return
    help_text = (
        "📖 **CK BOT အသုံးပြုနည်း လမ်းညွှန်**\n\n"
        "စတင်အသုံးပြုရန် `/start` ကိုနှိပ်ပါ။ အောက်ပါ command များကို Bot chat ထဲတွင် ရိုက်ပို့နိုင်ပါတယ်။\n\n"
        "🔮 **ဗေဒင်နှင့် တားရော့**\n"
        "• `/start` — ပင်မမီနူးဖွင့်ရန်\n"
        "• မီနူးမှ ရာသီခွင်၊ မနက်ဖြန်ဟောကိန်း၊ တားရော့ကို ရွေးချယ်ပါ။\n\n"
        "🌐 **Internet Search & Send (Private Chat)**\n"
        "• `/appsearch အမည်` — App / APK Official Release ရှာရန်\n"
        "• `/gamesearch အမည်` — Game Official Release ရှာရန်\n"
        "• `/book အမည်` — Public-domain စာအုပ်ရှာရန်\n"
        "• `/moviesearch အမည်` — အသုံးပြုခွင့်ရှိသော Movie ရှာရန်\n"
        "• `/wallpaper အကြောင်းအရာ` — Wallpaper / ပုံရှာရန်\n"
        "• `/videosearch အကြောင်းအရာ` — Video ရှာရန်\n"
        "• `/education အကြောင်းအရာ` — ပညာရေးစာတမ်းရှာရန်\n"
        "• `/audiosearch အမည်` — Podcast / Audio ရှာရန်\n"
        "• `/docsearch အကြောင်းအရာ` — Document / Template ရှာရန်\n"
        "• `/fontsearch အမည်` — Font / Icon ရှာရန်\n"
        "မှတ်ချက် — မူပိုင်ခွင့်/လိုင်စင်ခွင့်ပြုထားသော ရင်းမြစ်များကိုသာ ရှာဖွေပြီး အချို့ရလဒ်များကို Download Link အဖြစ်ပေးပါမည်။\n\n"
        "🎮 **ဂိမ်းနှင့် RPG**\n"
        "• `/game` — ဂိမ်းမီနူး\n"
        "• `/rpg` — Adventure RPG စတင်ရန်\n"
        "• `/pvp` — အခြားကစားသူနှင့် ယှဉ်ပြိုင်ရန်\n"
        "• `/addq မေးခွန်း / ရွေးချယ်စရာ၁ / ရွေးချယ်စရာ၂ / ရွေးချယ်စရာ၃ / ရွေးချယ်စရာ၄ / အဖြေနံပါတ်` — Quiz မေးခွန်းထည့်ရန် (အဖြေနံပါတ် 0–3)\n\n"
        "⚔️ **MLBB Hero Guide**\n"
        "• `/hero Gusion` — Hero အကြောင်းနှင့် အကြံပြုချက်\n"
        "• `/build Gusion` — Item / Emblem / Spell အကြံပြုချက်\n"
        "• `/lore Gusion` — Hero ဇာတ်ကြောင်း\n"
        "• `/duo Gusion` — Duo တွဲဖက် Hero အကြံပြုချက်\n"
        "• `/combo` သို့မဟုတ် `/meta` — Team combo အကြံပြုချက်\n"
        "• `/mlbbhero` — MLBB Hero ပုံခန့်မှန်းဂိမ်း\n"
        "Hero နာမည်ကို English လိုရေးပါ။ ဥပမာ `Gusion`, `Miya`, `Tigreal`။\n\n"
        "⏰ **သတိပေးချက် (Reminder)**\n"
        "• `/remind 10m စာသား` — ၁၀ မိနစ်အကြာ သတိပေးရန်\n"
        "• `/remind 2h စာသား` — ၂ နာရီအကြာ သတိပေးရန်\n"
        "• `/remind 1d စာသား` — ၁ ရက်အကြာ သတိပေးရန်\n"
        "• `/reminders` — သတိပေးချက်စာရင်းကြည့်ရန်\n"
        "• `/delreminder ID` — သတိပေးချက်ဖျက်ရန်\n\n"
        "💰 **အသုံးစရိတ်နှင့် Budget**\n"
        "• `/expense 5000 ထမင်း` — အသုံးစရိတ်မှတ်တမ်းတင်ရန်\n"
        "• `/expenses` — အသုံးစရိတ်စာရင်း\n"
        "• `/budget 200000` — Budget သတ်မှတ်ရန်\n"
        "• `/budgetstatus` — Budget အခြေအနေကြည့်ရန်\n\n"
        "💬 **အမည်မဖော်ဘဲ စကားပြောခြင်း**\n"
        "• `/chat` — တစ်ဖက်လူနှင့် ချိတ်ဆက်ရန်\n"
        "• `/next` — နောက်တစ်ယောက်နှင့် ချိတ်ဆက်ရန်\n"
        "• `/stop` — စကားပြောခြင်းရပ်ရန်\n"
        "• `/report` — မသင့်လျော်သော အသုံးပြုသူကို တိုင်ကြားရန်\n\n"
        "🌈 **Relax & Fun / နေ့စဉ်အသုံးဝင်ကိရိယာများ**\n"
        "• `/life` — Relax & Fun Center ဖွင့်ရန်\n\n"
        "╭━━━━━━━━━━━━━━━━━━━━╮\n"
        "   🎬 **TIKTOK VIDEO & PHOTO DOWNLOADER**\n"
        "╰━━━━━━━━━━━━━━━━━━━━╯\n"
        "✨ TikTok Video နှင့် Photo များကို CK BOT မှတစ်ဆင့် ရယူနိုင်ပါသည်။\n"
        "• `/tiktok LINK` — Video/Photo ကို အလိုအလျောက် ခွဲခြားရယူရန်\n"
        "• Private Chat တွင် TikTok Link ကို တိုက်ရိုက်ပို့၍လည်း ရယူနိုင်ပါသည်။\n"
        "💠 မူရင်းရင်းမြစ်မှ Watermark မပါသော ဖိုင်ရရှိပါက ထိုဖိုင်ကို ပို့ပေးပါမည်။\n"
        "⚠️ ဗီဒီယိုတိုင်းတွင် Logo ဖယ်ရှားနိုင်မည်ဟု အာမမခံနိုင်ပါ။ Watermark ပါပြီးသား ဗီဒီယိုကို Bot က အမြဲတမ်း ဖျောက်ပေးနိုင်ခြင်း မရှိပါ။\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🛡️ **Group ဆဲဆိုမှုထိန်းချုပ်ရေး (ခွင့်ပြုထားသူများသာ)**\n"
        "• Bot ပိုင်ရှင်က ခွင့်ပြုလိုသူ၏ စာကို Reply လုပ်ပြီး `/permission` ပို့ပါ။\n"
        "• ခွင့်ပြုချက်ပယ်ဖျက်ရန် Reply လုပ်ပြီး `/unpermission` ပို့ပါ။\n"
        "• ခွင့်ပြုထားသူက Bot ကို Group ထဲထည့်ရုံနဲ့ မလုံလောက်ပါ — Bot ကို အဲဒီ Group မှာ Admin ခန့်ထားပြီး Restrict Members ခွင့်ပေးရပါမယ်။\n"
        "• ဆဲဆိုမှုတွေ့ရှိပါက ၁၀ မိနစ် Mute လုပ်ပြီး Bot က သတိပေးစာပြန်ပို့ပါမယ်။\n\n"
        "❓ **အကူအညီလိုပါက**\n"
        "Command တစ်ခုခုကို မသိပါက `/help` ကို ထပ်ရိုက်ပို့နိုင်ပါတယ်။ Command သုံးရာတွင် ဥပမာထဲက စာသားနှင့် နံပါတ်များကို ကိုယ့်အချက်အလက်ဖြင့် အစားထိုးပါ။"
    )
    await update.effective_message.reply_text(help_text, parse_mode="Markdown")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args and context.args[0].startswith("ref_"):
        await ck_handle_referral(update, context)
    if not await require_group_bot_admin(update, context): return
    if update.effective_chat and update.effective_chat.type == "private" and update.effective_user:
        with db_connect() as conn:
            conn.execute("INSERT INTO ck_ad_users(user_id,active,updated_at) VALUES(?,1,?) ON CONFLICT(user_id) DO UPDATE SET active=1,updated_at=excluded.updated_at", (update.effective_user.id, int(time.time())))
            conn.commit()
    keyboard = [
        [InlineKeyboardButton("🌟 ရာသီခွင် အသေးစိတ်ဟောကိန်း", callback_data="mode_zodiac")],
        [InlineKeyboardButton("📅 မနက်ဖြန် ဖြစ်ပျက်မည့်ဟောကိန်း", callback_data="mode_tomorrow")],
        [InlineKeyboardButton("🃏 တားရော့ (၃) ကတ် ဟောရန်", callback_data="mode_tarot")],
        [InlineKeyboardButton("🎮 ဂိမ်းများ ဆော့ကစားရန် (/game)", callback_data="menu_games")],
        [InlineKeyboardButton("🛡️ Adventure RPG (/rpg)", callback_data="rpg_open")],
        [InlineKeyboardButton("🌈 Relax & Fun Center", callback_data="life_open")],
    ]
    await update.message.reply_text(
        "မင်္ဂလာပါရှင့်/ခဗျာ 🙏\n\n"
        "ဤဘော့တ်မှတဆင့် ဗေဒင်၊ တားရော့နှင့် ဂိမ်းများ ဆော့ကစားနိုင်ပါသည်။\n"
        "မေးခွန်းအသစ်ထည့်ရန် `/addq` ကို အသုံးပြုပါ။\n"
        "Adventure RPG အတွက် `/rpg` ကို အသုံးပြုပါ။\n"
        "အသုံးပြုနည်းအပြည့်အစုံကြည့်ရန် `/help` ကိုနှိပ်ပါ။",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

async def game_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_group_bot_admin(update, context): return
    await update.message.reply_text(
        "🎮 **CK BOT GAME CENTER** 🎮\nဂိမ်းအမျိုးအစားကို ရွေးချယ်ပါ။",
        reply_markup=games_menu_keyboard(update.effective_chat.type), parse_mode="Markdown",
    )

async def add_question_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text or ""
    text = raw.split(maxsplit=1)[1].strip() if len(raw.split(maxsplit=1)) > 1 else ""
    parts = [p.strip() for p in text.split("/")]
    if len(parts) < 6:
        await update.message.reply_text(
            "⚠️ ပုံစံမမှန်ပါ။ ဤကဲ့သို့ ပို့ပေးပါ:\n\n"
            "`/addq မေးခွန်းစာသား / ဖြေစရာကွက် ၁ / ဖြေစရာကွက် ၂ / ဖြေစရာကွက် ၃ / ဖြေစရာကွက် ၄ / အမှန်အဖြေနံပါတ်(0,1,2,3)`",
            parse_mode="Markdown",
        )
        return
    q_text, options = parts[0], parts[1:5]
    try:
        ans_idx = int(parts[5])
        if not 0 <= ans_idx <= 3:
            raise ValueError
    except ValueError:
        await update.message.reply_text("⚠️ အမှန်အဖြေနံပါတ်သည် 0 မှ 3 အတွင်းသာ ဖြစ်ရပါမည်။")
        return
    SAVED_TRIVIA_QUESTIONS.append({"q": q_text, "options": options, "answer": ans_idx})
    await update.message.reply_text(
        f"✅ **အောင်မြင်သည်!** မေးခွန်းအသစ်ကို မှတ်သားလိုက်ပါပြီ။ စုစုပေါင်း: {len(SAVED_TRIVIA_QUESTIONS)} ခု",
        parse_mode="Markdown",
    )

ROOM_GAMES = {
    "monopoly":"Monopoly", "poker":"Poker", "uno":"UNO", "detective":"Detective",
    "tower":"Tower Defense", "racing":"Car Racing", "football":"Football", "brain":"Brain Battle",
    "mystery":"Mystery Box", "rps":"Rock Paper Scissors", "monster":"Monster Battle", "hidden":"Hidden Object",
    "door":"Choose a Door", "picture":"Picture Quiz", "memory":"Memory Match", "weapon":"Weapon Choice"
}
ROOM_ACTIONS = {
    "monopoly":[("🎲 အန်စာတုံးလှိမ့်","roll"),("🏠 မြေကွက်ဝယ်","buy")],
    "poker":[("🃏 ကတ်ဆွဲ","draw"),("✋ ရပ်မည်","stand")],
    "uno":[("🔴 အနီ","red"),("🟢 အစိမ်း","green"),("🔵 အပြာ","blue"),("🟡 အဝါ","yellow")],
    "detective":[("🔎 သဲလွန်စ A","clue_a"),("🔎 သဲလွန်စ B","clue_b"),("🔎 သဲလွန်စ C","clue_c")],
    "tower":[("⬆️ Tower မြှင့်","upgrade"),("⚔️ တိုက်ခိုက်","attack")],
    "racing":[("🚀 အရှိန်မြှင့်","boost"),("🛞 Nitro","nitro")],
    "football":[("⬅️ ဘယ်","left"),("⬆️ အလယ်","center"),("➡️ ညာ","right")],
    "brain":[("8️⃣ ၈","8"),("🔟 ၁၀","10"),("1️⃣2️⃣ ၁၂","12")],
    "mystery":[("🎁 သေတ္တာ A","a"),("🎁 သေတ္တာ B","b")], "rps":[("✊ ကျောက်","rock"),("✋ စက္ကူ","paper")],
    "monster":[("⚔️ တိုက်ခိုက်","attack"),("🛡️ ကာကွယ်","defend")], "hidden":[("🔎 ရှာဖွေ A","a"),("🔎 ရှာဖွေ B","b")],
    "door":[("🚪 တံခါး ၁","one"),("🚪 တံခါး ၂","two")], "picture":[("🖼️ ပုံ A","a"),("🖼️ ပုံ B","b")],
    "memory":[("🧠 ကတ် A","a"),("🧠 ကတ် B","b")], "weapon":[("⚔️ ဓား","sword"),("🏹 လေး","bow")],
}

def room_keyboard(room, waiting=False):
    rid=room['id']
    if waiting:
        return InlineKeyboardMarkup([[InlineKeyboardButton("🙋 Join လုပ်မည်",callback_data=f"room_join_{rid}")],
                                     [InlineKeyboardButton("🎮 Game Center",callback_data="menu_games")]])
    game=room['game']; actions=ROOM_ACTIONS[game]
    rows=[[InlineKeyboardButton(label,callback_data=f"room_act_{rid}_{action}") for label,action in actions[i:i+2]] for i in range(0,len(actions),2)]
    rows.append([InlineKeyboardButton("🎮 Game Center",callback_data="menu_games")])
    return InlineKeyboardMarkup(rows)

def get_room(rid):
    with db_connect() as conn:
        row=conn.execute("SELECT * FROM game_rooms WHERE id=?",(rid,)).fetchone()
        return dict(row) if row else None

async def room_callback(query, context, data):
    chat=query.message.chat; user=query.from_user
    if chat.type != "private" and not await group_bot_is_admin(chat,context):
        await query.answer("Bot ကို Group Admin ပေးထားရန်လိုပါတယ်။",show_alert=True); return
    if data.startswith("room_create_"):
        game=data.replace("room_create_", "",1)
        if game not in ROOM_GAMES: return
        if chat.type == "private":
            # In private chat these games use their existing solo-vs-game/bot implementations.
            await additional_game_callback(query, context, "new_" + game)
            return
        with db_connect() as conn:
            conn.execute("UPDATE game_rooms SET status='cancelled' WHERE chat_id=? AND host_id=? AND status='waiting'",(chat.id,user.id))
            cur=conn.execute("INSERT INTO game_rooms(chat_id,game,host_id,host_name,status,created_at) VALUES(?,?,?,?, 'waiting',?)",
                             (chat.id,game,user.id,user.first_name or str(user.id),int(time.time())))
            rid=cur.lastrowid; conn.commit()
        room=get_room(rid)
        await query.edit_message_text(f"🎮 **{ROOM_GAMES[game]} — ၂ ယောက်ကစားခန်း**\n\nဖန်တီးသူ: {room['host_name']}\nဒုတိယကစားသမားကို Join လုပ်ဖို့ စောင့်နေပါတယ်။\n\nဒီခလုတ်ကို အခြားကစားသမားတစ်ယောက် နှိပ်ပါ။",parse_mode="Markdown",reply_markup=room_keyboard(room,True)); return
    if data.startswith("room_join_"):
        rid=int(data.rsplit("_",1)[1]); room=get_room(rid)
        if not room or room['status']!='waiting':
            await query.answer("ဒီအခန်း မရှိတော့ပါ။",show_alert=True); return
        if room['host_id']==user.id:
            await query.answer("ကိုယ်ဖန်တီးထားတဲ့အခန်းကို ကိုယ်တိုင် Join လုပ်လို့မရပါ။",show_alert=True); return
        with db_connect() as conn:
            conn.execute("UPDATE game_rooms SET guest_id=?,guest_name=?,status='playing' WHERE id=? AND status='waiting'",
                         (user.id,user.first_name or str(user.id),rid)); conn.commit()
        room=get_room(rid)
        await query.edit_message_text(f"🎮 **{ROOM_GAMES[room['game']]} စတင်ပါပြီ!**\n\n🔵 {room['host_name']} — {room['score_host']} မှတ်\n🔴 {room['guest_name']} — {room['score_guest']} မှတ်\n\n{room['host_name']} ရဲ့ အလှည့်ပါ။ ရွေးချယ်ပါ။",parse_mode="Markdown",reply_markup=room_keyboard(room)); return
    if data.startswith("room_act_"):
        parts=data.split("_"); rid=int(parts[2]); action="_".join(parts[3:]); room=get_room(rid)
        if not room or room['status']!='playing':
            await query.answer("ဒီပွဲ မကစားနိုင်တော့ပါ။",show_alert=True); return
        if user.id not in (room['host_id'],room['guest_id']):
            await query.answer("ဒီပွဲမှာ ပါဝင်ထားသူသာ ကစားနိုင်ပါတယ်။",show_alert=True); return
        expected=room['host_id'] if room['turn']%2==0 else room['guest_id']
        if user.id!=expected:
            await query.answer("အခု သင့်အလှည့် မဟုတ်သေးပါ။",show_alert=True); return
        game=room['game']; valid={a for _,a in ROOM_ACTIONS[game]}
        if action not in valid: return
        # Each valid turn earns game-specific points; the game ends after 5 turns per player.
        points=0; note=""
        if game=="monopoly": points=random.randint(2,12)*2 if action=="roll" else random.randint(5,15)
        elif game=="poker": points=random.randint(1,20) if action=="draw" else random.randint(0,8)
        elif game=="uno": points=random.randint(4,15); note=f"{action.upper()} ကတ် ရွေးချယ်ခဲ့သည်။"
        elif game=="detective": points=15 if action=="clue_b" else random.randint(2,8)
        elif game=="tower": points=random.randint(3,10) if action=="upgrade" else random.randint(6,16)
        elif game=="racing": points=random.randint(5,12) if action=="boost" else random.randint(3,18)
        elif game=="football": points=10 if random.choice([True,False]) else 0; note="ဂိုးဝင်!" if points else "ဂိုးမဝင်ပါ။"
        elif game=="brain": points=12 if action=="10" else 0; note="အဖြေမှန်!" if points else "အဖြေမှား!"
        else:
            points=random.randint(4,15)
            note=f"{ROOM_GAMES[game]} ရွေးချယ်မှု: {action}"
        host_turn=(user.id==room['host_id'])
        sh=room['score_host']+(points if host_turn else 0); sg=room['score_guest']+(points if not host_turn else 0)
        turn=room['turn']+1; round_no=turn//2
        finished=turn>=10
        with db_connect() as conn:
            conn.execute("UPDATE game_rooms SET score_host=?,score_guest=?,turn=?,round_no=?,status=? WHERE id=?",
                         (sh,sg,turn,round_no,'finished' if finished else 'playing',rid)); conn.commit()
        room=get_room(rid)
        if finished:
            winner=room['host_name'] if sh>sg else room['guest_name'] if sg>sh else None
            result=f"🏁 **ပွဲပြီးဆုံးပါပြီ!**\n\n🔵 {room['host_name']}: {sh} မှတ်\n🔴 {room['guest_name']}: {sg} မှတ်\n\n"+(f"🏆 အနိုင်ရသူ: {winner}" if winner else "🤝 သရေကျပါတယ်။")
            await query.edit_message_text(result,parse_mode="Markdown",reply_markup=games_menu_keyboard(query.message.chat.type)); return
        next_name=room['host_name'] if turn%2==0 else room['guest_name']
        await query.edit_message_text(f"🎮 **{ROOM_GAMES[game]}**\n\n🔵 {room['host_name']}: {sh} မှတ်\n🔴 {room['guest_name']}: {sg} မှတ်\n\n{note}\n⭐ ဒီအလှည့်ရမှတ်: +{points}\nအလှည့်: {next_name}\nပွဲစဉ်: {turn}/10",parse_mode="Markdown",reply_markup=room_keyboard(room)); return


# ------------------------- 50 ADDITIONAL ARCADE GAMES -------------------------
# Data-driven quick-play games. Each has its own title/theme and uses 5 rounds
# of multiple-choice challenges. Group rooms support 2-3 human players.
ARCADE50_GAMES = [
    "🧠 ဉာဏ်စမ်းပြိုင်ပွဲ", "🔢 သင်္ချာအမြန်တွက်", "🔤 စကားလုံးရှာဖွေ", "🧩 ပဟေဠိဖြေရှင်း",
    "🌍 ကမ္ဘာ့ဗဟုသုတ", "🇲🇲 မြန်မာ့ဗဟုသုတ", "🐾 တိရစ္ဆာန်ကမ္ဘာ", "🌿 သဘာဝပတ်ဝန်းကျင်",
    "🚀 အာကာသစူးစမ်း", "🏛️ သမိုင်းခရီး", "🍎 အစားအသောက်ဗဟုသုတ", "⚽ အားကစားဗဟုသုတ",
    "🎬 ရုပ်ရှင်ပဟေဠိ", "🎵 ဂီတပဟေဠိ", "📚 စာပေဗဟုသုတ", "💻 နည်းပညာစိန်ခေါ်မှု",
    "🔬 သိပ္ပံစမ်းသပ်ခန်း", "🧮 နံပါတ်ခန့်မှန်း", "🕵️ စုံထောက်ဉာဏ်စမ်း", "🗺️ နေရာခန့်မှန်း",
    "🚦 လမ်းစည်းကမ်းစမ်းသပ်", "🧑‍🍳 မီးဖိုချောင်စိန်ခေါ်", "💎 ရတနာခန့်မှန်း", "🎨 အရောင်မှတ်မိ",
    "🧠 မှတ်ဉာဏ်စမ်းသပ်", "⚡ အမြန်ဆုံးဖြေ", "🧭 လမ်းကြောင်းရွေးချယ်", "🐉 နဂါးစိန်ခေါ်မှု",
    "🏰 ရဲတိုက်ကာကွယ်ရေး", "🛡️ သူရဲကောင်းရွေးချယ်", "🧪 ဆေးပညာဗဟုသုတ", "🌦️ ရာသီဥတုဗဟုသုတ",
    "🪐 ဂြိုဟ်စနစ်ပဟေဠိ", "🦖 ဒိုင်နိုဆောကမ္ဘာ", "🐠 ပင်လယ်ရေအောက်", "🌋 ကမ္ဘာမြေစူးစမ်း",
    "🚗 ယာဉ်အမျိုးအစား", "✈️ လေကြောင်းဗဟုသုတ", "🏅 အိုလံပစ်စိန်ခေါ်", "🎲 ကံနှင့်ဉာဏ်ပြိုင်ပွဲ",
    "🔐 လျှို့ဝှက်ကုဒ်ဖော်", "🧱 ပုံစံဆက်စပ်မှု", "🧸 ကလေးဉာဏ်စမ်း", "🧑‍🚀 အာကာသယာဉ်မှူး",
    "🦁 တောရိုင်းတိရစ္ဆာန်", "🌸 ပန်းမျိုးစုံခွဲခြား", "📱 App ဗဟုသုတ", "🪙 ငွေကြေးဗဟုသုတ",
    "🏙️ မြို့တော်ခန့်မှန်း", "🏆 အထွေထွေချန်ပီယံ"
]
ARCADE50_QUESTIONS = [
    {"q":"မြန်မာနိုင်ငံ၏ အမြင့်ဆုံးတောင်မှာ ဘာလဲ?","o":["ခါကာဘိုရာဇီ","ပုပ္ပားတောင်","ဇွဲကပင်တောင်"],"a":0},
    {"q":"တစ်ပတ်မှာ ရက်ဘယ်နှရက်ရှိသလဲ?","o":["၅ ရက်","၇ ရက်","၈ ရက်"],"a":1},
    {"q":"နေအဖွဲ့အစည်းမှာ အကြီးဆုံးဂြိုဟ်က ဘာလဲ?","o":["ကမ္ဘာ","အင်္ဂါ","ဂျူပီတာ"],"a":2},
    {"q":"ရေ၏ ဓာတုသင်္ကေတက ဘာလဲ?","o":["H₂O","CO₂","O₂"],"a":0},
    {"q":"ကမ္ဘာပေါ်မှာ အမြန်ဆုံးပြေးနိုင်တဲ့ ကုန်းနေတိရစ္ဆာန်က ဘာလဲ?","o":["ခြင်္သေ့","ကျားသစ်","ဆင်"],"a":1},
    {"q":"၁၂ × ၈ = ဘယ်လောက်လဲ?","o":["၈၆","၉၆","၁၀၈"],"a":1},
    {"q":"ဂျပန်နိုင်ငံ၏ မြို့တော်က ဘာလဲ?","o":["တိုကျို","အိုဆာကာ","ကျိုတို"],"a":0},
    {"q":"အပင်များ အစာချက်လုပ်ရာတွင် အဓိကလိုအပ်တာ ဘာလဲ?","o":["နေရောင်ခြည်","သဲ","ဆား"],"a":0},
    {"q":"လူ့ခန္ဓာကိုယ်မှာ သွေးကို ညှစ်ပို့ပေးတဲ့ အင်္ဂါက ဘာလဲ?","o":["အဆုတ်","နှလုံး","အသည်း"],"a":1},
    {"q":"တစ်နာရီမှာ မိနစ်ဘယ်နှမိနစ်ရှိသလဲ?","o":["၃၀","၆၀","၁၀၀"],"a":1},
    {"q":"အနီနဲ့ အဝါရောလိုက်ရင် ဘယ်အရောင်ရမလဲ?","o":["အစိမ်း","ခရမ်း","လိမ္မော်"],"a":2},
    {"q":"ကမ္ဘာ့အကြီးဆုံးသမုဒ္ဒရာက ဘာလဲ?","o":["ပစိဖိတ်","အတ္တလန္တိတ်","အိန္ဒိယ"],"a":0},
    {"q":"မြန်မာနိုင်ငံ၏ ငွေကြေးယူနစ်က ဘာလဲ?","o":["ဘတ်","ကျပ်","ယန်း"],"a":1},
    {"q":"အောက်ဆီဂျင်၏ သင်္ကေတက ဘာလဲ?","o":["O","H","N"],"a":0},
    {"q":"ဘယ်တိရစ္ဆာန်က ဥဥသလဲ?","o":["ကြောင်","ကြက်","ခွေး"],"a":1},
    {"q":"၅၀ ကို ၅ နဲ့စားရင် ဘယ်လောက်လဲ?","o":["၅","၁၀","၁၅"],"a":1},
    {"q":"ကမ္ဘာကို အလင်းနဲ့ အပူပေးတဲ့ ကြယ်က ဘာလဲ?","o":["လ","နေ","စီးရီးယပ်စ်"],"a":1},
    {"q":"အင်တာနက်စာမျက်နှာကြည့်ရန် အသုံးများတဲ့ App အမျိုးအစားက ဘာလဲ?","o":["Browser","Calculator","Camera"],"a":0},
    {"q":"ရေခဲက ဘယ်အခြေအနေဖြစ်သလဲ?","o":["အရည်","အစိုင်အခဲ","ဓာတ်ငွေ့"],"a":1},
    {"q":"ဘယ်ဂြိုဟ်ကို အနီရောင်ဂြိုဟ်လို့ ခေါ်သလဲ?","o":["အင်္ဂါ","သောကြာ","စနေ"],"a":0},
    {"q":"မြန်မာ့ရိုးရာနှစ်သစ်ကူးပွဲတော်က ဘာလဲ?","o":["သင်္ကြန်","သီတင်းကျွတ်","တန်ဆောင်တိုင်"],"a":0},
    {"q":"၃၆ ÷ ၆ = ဘယ်လောက်လဲ?","o":["၅","၆","၇"],"a":1},
    {"q":"ပင်လယ်ရေမှာ ဘာအရသာရှိသလဲ?","o":["ချို","ငန်","ခါး"],"a":1},
    {"q":"ဘယ်ကိရိယာနဲ့ အပူချိန်တိုင်းသလဲ?","o":["သာမိုမီတာ","ကွန်ပတ်စ်","နာရီ"],"a":0},
    {"q":"စာအုပ်ဖတ်ရာမှာ အဓိကအသုံးပြုတဲ့ အာရုံခံအင်္ဂါက ဘာလဲ?","o":["နား","မျက်စိ","နှာခေါင်း"],"a":1},
    {"q":"ကမ္ဘာ့အကြီးဆုံး နို့တိုက်သတ္တဝါက ဘာလဲ?","o":["ဆင်","ဝေလငါးပြာ","သစ်ကုလားအုတ်"],"a":1},
    {"q":"၁၀၀ စင်တီမီတာက ဘယ်လောက်နဲ့ညီသလဲ?","o":["၁ မီတာ","၁၀ မီတာ","၁ ကီလိုမီတာ"],"a":0},
    {"q":"ဘယ်အရာက သံလိုက်ကို ဆွဲဆောင်နိုင်သလဲ?","o":["သစ်သား","သံ","ပလတ်စတစ်"],"a":1},
    {"q":"တစ်နှစ်မှာ လဘယ်နှလရှိသလဲ?","o":["၁၀","၁၁","၁၂"],"a":2},
    {"q":"ဘယ်တိရစ္ဆာန်ကို သဲကန္တာရသင်္ဘောလို့ ခေါ်သလဲ?","o":["ကုလားအုတ်","မြင်း","မြည်း"],"a":0},
]

def arcade50_menu(page=0, chat_type="private"):
    start=page*10
    rows=[]
    for i in range(start,min(start+10,50),2):
        pair=[]
        for j in range(i,min(i+2,50)):
            pair.append(InlineKeyboardButton(f"{j+1}. {ARCADE50_GAMES[j]}",callback_data=f"a50_pick_{j}"))
        rows.append(pair)
    nav=[]
    if page>0: nav.append(InlineKeyboardButton("⬅️ နောက်ပြန်",callback_data=f"a50_page_{page-1}"))
    if page<4: nav.append(InlineKeyboardButton("နောက်စာမျက်နှာ ➡️",callback_data=f"a50_page_{page+1}"))
    if nav: rows.append(nav)
    rows.append([InlineKeyboardButton("🎮 Game Center",callback_data="menu_games")])
    return InlineKeyboardMarkup(rows)

def arcade50_question(game_id, round_no):
    # Shuffle the challenge bank per session; every round has a three-choice answer.
    q=ARCADE50_QUESTIONS[(game_id*3+round_no*7+random.randrange(len(ARCADE50_QUESTIONS)))%len(ARCADE50_QUESTIONS)].copy()
    return q

def arcade50_keyboard(session, waiting=False):
    sid=session["id"]
    if waiting:
        players=json.loads(session["players_json"])
        rows=[[InlineKeyboardButton("🙋 ဝင်ကစားမည်",callback_data=f"a50_join_{sid}")]]
        if len(players)>=2:
            rows.append([InlineKeyboardButton("▶️ ဂိမ်းစမည်",callback_data=f"a50_start_{sid}")])
        rows.append([InlineKeyboardButton("🎮 Game Center",callback_data="menu_games")])
        return InlineKeyboardMarkup(rows)
    q=json.loads(session["question_json"])
    rows=[[InlineKeyboardButton(f"{i+1}. {opt}",callback_data=f"a50_ans_{sid}_{i}")] for i,opt in enumerate(q["o"])]
    rows.append([InlineKeyboardButton("🎮 Game Center",callback_data="menu_games")])
    return InlineKeyboardMarkup(rows)

def arcade50_get(sid):
    with db_connect() as conn:
        row=conn.execute("SELECT * FROM arcade50_sessions WHERE id=?",(sid,)).fetchone()
        return dict(row) if row else None

async def arcade50_callback(query, context, data):
    chat=query.message.chat; user=query.from_user
    if data.startswith("a50_page_"):
        page=int(data.rsplit("_",1)[1])
        await query.edit_message_text("🕹️ **ဂိမ်းအသစ် ၅၀ မျိုး**\nစာမျက်နှာကို ရွေးချယ်ပါ။",parse_mode="Markdown",reply_markup=arcade50_menu(page,chat.type)); return
    if data.startswith("a50_pick_"):
        gid=int(data.rsplit("_",1)[1])
        if chat.type=="private":
            q=arcade50_question(gid,0)
            context.user_data["a50_solo"]={"gid":gid,"round":0,"score":0,"question":q}
            kb=InlineKeyboardMarkup([[InlineKeyboardButton(f"{i+1}. {o}",callback_data=f"a50_solo_{i}")] for i,o in enumerate(q["o"])] + [[InlineKeyboardButton("🎮 ဂိမ်းမီနူး",callback_data="menu_games")]])
            await query.edit_message_text(f"{ARCADE50_GAMES[gid]}\n\n🤖 Bot နဲ့ ယှဉ်ပြိုင်ပါ။\nမေးခွန်း ၅ ခု ဖြေဆိုပါ။\n\n❓ {q['q']}",reply_markup=kb); return
        with db_connect() as conn:
            conn.execute("UPDATE arcade50_sessions SET status='finished' WHERE chat_id=? AND status IN ('waiting','playing')",(chat.id,))
            cur=conn.execute("INSERT INTO arcade50_sessions(chat_id,game_id,game_name,host_id,players_json,scores_json,created_at) VALUES(?,?,?,?,?,?,?)",
                (chat.id,gid,ARCADE50_GAMES[gid],user.id,json.dumps([{"id":user.id,"name":user.first_name or str(user.id)}],ensure_ascii=False),json.dumps({str(user.id):0}),int(time.time())))
            sid=cur.lastrowid; conn.commit()
        session=arcade50_get(sid)
        await query.edit_message_text(f"🎮 **{ARCADE50_GAMES[gid]}**\n\nအခန်းဖွင့်သူ: {user.first_name}\nကစားသမား ၂ ယောက်မှ ၃ ယောက်အထိ ဝင်နိုင်ပါတယ်။\nအနည်းဆုံး ၂ ယောက်ပြည့်လျှင် Start နှိပ်ပါ။",parse_mode="Markdown",reply_markup=arcade50_keyboard(session,True)); return
    if data.startswith("a50_join_"):
        sid=int(data.rsplit("_",1)[1]); session=arcade50_get(sid)
        if not session or session["status"]!="waiting": await query.answer("ဒီအခန်း မရနိုင်တော့ပါ။",show_alert=True); return
        players=json.loads(session["players_json"])
        if any(p["id"]==user.id for p in players): await query.answer("သင် အခန်းထဲမှာ ပါပြီးပါပြီ။"); return
        if len(players)>=3: await query.answer("ကစားသမား ၃ ယောက်ပြည့်ပါပြီ။",show_alert=True); return
        players.append({"id":user.id,"name":user.first_name or str(user.id)})
        scores=json.loads(session["scores_json"]); scores[str(user.id)]=0
        with db_connect() as conn:
            conn.execute("UPDATE arcade50_sessions SET players_json=?,scores_json=? WHERE id=? AND status='waiting'",(json.dumps(players,ensure_ascii=False),json.dumps(scores),sid)); conn.commit()
        session=arcade50_get(sid)
        await query.edit_message_text(f"🎮 **{session['game_name']}**\n\nကစားသမားများ:\n"+"\n".join(f"{i+1}. {p['name']}" for i,p in enumerate(players))+"\n\n▶️ အနည်းဆုံး ၂ ယောက်ပြည့်ပါပြီ။ Host က Start နှိပ်နိုင်ပါပြီ။",parse_mode="Markdown",reply_markup=arcade50_keyboard(session,True)); return
    if data.startswith("a50_start_"):
        sid=int(data.rsplit("_",1)[1]); session=arcade50_get(sid)
        if not session or session["status"]!="waiting": await query.answer("ဒီအခန်း မစနိုင်တော့ပါ။",show_alert=True); return
        if user.id!=session["host_id"]: await query.answer("အခန်းဖွင့်သူသာ စတင်နိုင်ပါတယ်။",show_alert=True); return
        players=json.loads(session["players_json"])
        if len(players)<2: await query.answer("အနည်းဆုံး လူ ၂ ယောက်လိုပါတယ်။",show_alert=True); return
        q=arcade50_question(session["game_id"],0)
        with db_connect() as conn:
            conn.execute("UPDATE arcade50_sessions SET status='playing',question_json=? WHERE id=?",(json.dumps(q,ensure_ascii=False),sid)); conn.commit()
        session=arcade50_get(sid)
        await query.edit_message_text(f"🎮 **{session['game_name']}**\nပွဲစဉ် ၁/၅\nကစားသမား: "+", ".join(p['name'] for p in players)+f"\n\n❓ {q['q']}\n\nတစ်ယောက်ချင်းစီ အဖြေရွေးပါ။",parse_mode="Markdown",reply_markup=arcade50_keyboard(session)); return
    if data.startswith("a50_ans_"):
        _,_,sid_s,idx_s=data.split("_"); sid=int(sid_s); idx=int(idx_s); session=arcade50_get(sid)
        if not session or session["status"]!="playing": await query.answer("ဒီမေးခွန်း ပြီးဆုံးသွားပါပြီ။"); return
        players=json.loads(session["players_json"]); ids=[p["id"] for p in players]
        if user.id not in ids: await query.answer("ဒီပွဲမှာ ပါဝင်ထားသူသာ ဖြေနိုင်ပါတယ်။",show_alert=True); return
        answered=json.loads(session["answered_json"])
        if user.id in answered: await query.answer("ဒီအလှည့် ဖြေပြီးပါပြီ။"); return
        q=json.loads(session["question_json"]); scores=json.loads(session["scores_json"])
        if idx==q["a"]: scores[str(user.id)]=scores.get(str(user.id),0)+10
        answered.append(user.id)
        if len(answered)<len(players):
            with db_connect() as conn:
                conn.execute("UPDATE arcade50_sessions SET answered_json=?,scores_json=? WHERE id=?",(json.dumps(answered),json.dumps(scores),sid)); conn.commit()
            await query.answer("အဖြေမှန်! +10" if idx==q['a'] else "အဖြေမှားပါပြီ။",show_alert=True)
            return
        round_no=session["round_no"]+1
        if round_no>=5:
            with db_connect() as conn:
                conn.execute("UPDATE arcade50_sessions SET status='finished',answered_json=?,scores_json=?,round_no=? WHERE id=?",(json.dumps(answered),json.dumps(scores),round_no,sid)); conn.commit()
            ranking=sorted(players,key=lambda p:scores.get(str(p['id']),0),reverse=True)
            result="\n".join(f"{i+1}. {p['name']} — {scores.get(str(p['id']),0)} မှတ်" for i,p in enumerate(ranking))
            await query.edit_message_text(f"🏁 **ပွဲပြီးပါပြီ — {session['game_name']}**\n\n{result}\n\n🏆 အနိုင်ရသူ: {ranking[0]['name']}",parse_mode="Markdown",reply_markup=games_menu_keyboard(chat.type)); return
        nq=arcade50_question(session["game_id"],round_no)
        with db_connect() as conn:
            conn.execute("UPDATE arcade50_sessions SET answered_json='[]',scores_json=?,round_no=?,question_json=? WHERE id=?",(json.dumps(scores),round_no,json.dumps(nq,ensure_ascii=False),sid)); conn.commit()
        await query.edit_message_text(f"🎮 **{session['game_name']}**\nပွဲစဉ် {round_no+1}/5\n\n❓ {nq['q']}\n\n⭐ ရမှတ်: "+" | ".join(f"{p['name']} {scores.get(str(p['id']),0)}" for p in players),parse_mode="Markdown",reply_markup=arcade50_keyboard(arcade50_get(sid))); return
    if data.startswith("a50_solo_"):
        idx=int(data.rsplit("_",1)[1]); st=context.user_data.get("a50_solo")
        if not st: await query.answer("ဂိမ်းအသစ်စပါ။"); return
        q=st["question"]; right=idx==q["a"]; bot_idx=random.randrange(3); st["score"]+=10 if right else 0
        bot_score=st.get("bot_score",0)+(10 if bot_idx==q["a"] else 0); st["bot_score"]=bot_score
        st["round"]+=1
        if st["round"]>=5:
            winner="သင်" if st["score"]>bot_score else "Bot" if bot_score>st["score"] else "သရေ"
            context.user_data.pop("a50_solo",None)
            await query.edit_message_text(f"🏁 **ပွဲပြီးပါပြီ — {ARCADE50_GAMES[st['gid']]}**\n\nသင်: {st['score']} မှတ်\nBot: {bot_score} မှတ်\n🏆 ရလဒ်: {winner}",parse_mode="Markdown",reply_markup=games_menu_keyboard(chat.type)); return
        nq=arcade50_question(st["gid"],st["round"]); st["question"]=nq
        kb=InlineKeyboardMarkup([[InlineKeyboardButton(f"{i+1}. {o}",callback_data=f"a50_solo_{i}")] for i,o in enumerate(nq["o"])] + [[InlineKeyboardButton("🎮 ဂိမ်းမီနူး",callback_data="menu_games")]])
        await query.edit_message_text(f"🎮 **{ARCADE50_GAMES[st['gid']]}** — {st['round']+1}/5\n\n❓ {nq['q']}\n\nယခင်အဖြေ: {'မှန်' if right else 'မှား'}\nသင်: {st['score']} | Bot: {bot_score}",parse_mode="Markdown",reply_markup=kb); return



# ------------------------- RELAX & FUN CENTER -------------------------
LIFE_MOODS = {
    "happy": ("😊 ပျော်ရွှင်နေတယ်", "ဒီနေ့ရဲ့ ပျော်ရွှင်မှုလေးကို သတိထားခံစားပါ။ ကောင်းတဲ့အရာလေးတွေကို မျှဝေလိုက်ပါ။"),
    "tired": ("😴 ပင်ပန်းနေတယ်", "ခဏနားတာဟာ အရှုံးမဟုတ်ပါဘူး။ ရေတစ်ခွက်သောက်ပြီး ကိုယ့်ကိုယ်ကို အနားပေးပါ။"),
    "sad": ("🌧️ စိတ်မကောင်းဘူး", "ခံစားချက်တွေကို ဖိနှိပ်စရာမလိုပါဘူး။ တစ်ဆင့်ချင်း ဖြည်းဖြည်းချင်း ဖြတ်သန်းလို့ရပါတယ်။"),
    "stressed": ("😵 စိတ်ရှုပ်နေတယ်", "အခုချက်ချင်း အရာအားလုံး ဖြေရှင်းစရာမလိုပါဘူး။ အရေးကြီးဆုံးတစ်ခုကိုပဲ အရင်ရွေးပါ။"),
    "calm": ("🌿 အေးချမ်းနေတယ်", "ဒီအေးချမ်းမှုလေးကို ခဏခံစားပါ။ အသက်ကို ဖြည်းဖြည်းရှူပြီး ဖြည်းဖြည်းထုတ်ပါ။"),
}
FUNNY_LINES = [
    "အလုပ်မလုပ်ချင်တဲ့အခါ ကွန်ပျူတာကို Restart လုပ်လိုက်တယ်။ ကွန်ပျူတာကတော့ ပြန်စတယ်၊ ကိုယ်ကတော့ မစသေးဘူး 😂",
    "ပိုက်ဆံက စကားမပြောဘူး။ ဒါပေမဲ့ မရှိတဲ့အခါ အရာအားလုံးကို ပြောပြနေသလိုပဲ 💸",
    "ဒီနေ့ အားကစားလုပ်မယ်လို့ ဆုံးဖြတ်ထားတယ်။ ဆုံးဖြတ်ချက်ချပြီးတာနဲ့ ပင်ပန်းသွားလို့ အနားယူလိုက်တယ် 😆",
    "နာရီက အချိန်ကို ပြတယ်။ လစာကတော့ အချိန်ဘယ်လောက်မြန်မြန်ကုန်သွားလဲ ပြတယ် 😅",
]
RELAX_STORIES = [
    "ညနေခင်းလေးမှာ မိုးဖွဲဖွဲကျနေတယ်။ ပြတင်းပေါက်နားက လက်ဖက်ရည်ပူပူလေးကို ကိုင်ရင်း ဒီနေ့ကြုံခဲ့တာတွေကို ခဏလွှတ်ချလိုက်တယ်။ မနက်ဖြန်ဟာ စာမျက်နှာအသစ်တစ်ရွက်ပါ။",
    "တောအုပ်လေးထဲမှာ လေညင်းက သစ်ရွက်တွေကို တိုးတိုးလေး လှုပ်ခတ်စေတယ်။ ဘယ်သူမှ အလျင်မလိုတဲ့ အဲဒီနေရာမှာ ခဏရပ်ပြီး အသက်ရှူလိုက်ပါ။",
    "ပင်လယ်ကမ်းခြေမှာ လှိုင်းလေးတွေ တစ်လှိုင်းပြီးတစ်လှိုင်း ရောက်လာတယ်။ စိတ်ပင်ပန်းမှုတွေကိုလည်း လှိုင်းနဲ့အတူ ပြန်လွှတ်လိုက်ပါ။",
]
CREATIVE_PROMPTS = [
    "ဒီနေ့ကို အရောင်တစ်ရောင်နဲ့ ဖော်ပြမယ်ဆို ဘယ်အရောင်ဖြစ်မလဲ။ ဘာကြောင့်လဲ?",
    "စကားလုံး ၃ လုံးနဲ့ ပျော်ရွှင်စရာ ဇာတ်လမ်းတိုလေး ရေးပါ။",
    "သင့်ရဲ့ အနာဂတ်ကို အားပေးမယ့် စာကြောင်းတစ်ကြောင်း ရေးပါ။",
    "မိုးရွာတဲ့နေ့အတွက် ကဗျာတိုလေး ၂ ကြောင်း ရေးကြည့်ပါ။",
]
PERSONALITY_QUESTIONS = [
    ("အားလပ်ရက်ရရင် ဘာလုပ်ချင်လဲ?", [("သူငယ်ချင်းတွေနဲ့ ခရီးသွားမယ်", 2), ("စာအုပ်ဖတ်ပြီး အေးအေးဆေးဆေးနေမယ်", 0), ("အသစ်တစ်ခု စမ်းလုပ်မယ်", 1)]),
    ("အခက်အခဲကြုံရင် ဘယ်လိုလုပ်မလဲ?", [("အရင်ဆုံး အစီအစဉ်ချမယ်", 0), ("သူငယ်ချင်းနဲ့ တိုင်ပင်မယ်", 2), ("နည်းလမ်းအသစ် စမ်းကြည့်မယ်", 1)]),
    ("သင့်အတွက် အရေးကြီးဆုံးက ဘာလဲ?", [("တည်ငြိမ်မှု", 0), ("မိတ်ဆွေများ", 2), ("စွန့်စားမှု", 1)]),
]


def load_life_camp(chat_id):
    """Load a Friendship Camp room from SQLite so Railway restarts do not erase it."""
    with db_connect() as conn:
        row = conn.execute("SELECT state_json FROM leisure_camps WHERE chat_id=?", (chat_id,)).fetchone()
    if not row:
        return None
    try:
        return json.loads(row["state_json"])
    except (TypeError, json.JSONDecodeError):
        logger.exception("Invalid Friendship Camp state for chat %s", chat_id)
        return None


def save_life_camp(chat_id, camp):
    with db_connect() as conn:
        if camp is None:
            conn.execute("DELETE FROM leisure_camps WHERE chat_id=?", (chat_id,))
        else:
            conn.execute("""INSERT INTO leisure_camps(chat_id,state_json,updated_at) VALUES(?,?,?)
                ON CONFLICT(chat_id) DO UPDATE SET state_json=excluded.state_json, updated_at=excluded.updated_at""",
                (chat_id, json.dumps(camp, ensure_ascii=False), int(time.time())))
        conn.commit()


def life_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🐱 Virtual Pet", callback_data="life_pet"), InlineKeyboardButton("🌻 Dream Garden", callback_data="life_garden")],
        [InlineKeyboardButton("🌅 Mood Relax Room", callback_data="life_mood"), InlineKeyboardButton("🔥 Friendship Camp", callback_data="life_camp")],
        [InlineKeyboardButton("🎁 Daily Reward", callback_data="life_daily"), InlineKeyboardButton("😂 Funny Zone", callback_data="life_funny")],
        [InlineKeyboardButton("🌧️ Relax Sound & Story", callback_data="life_story"), InlineKeyboardButton("💝 Personality Quiz", callback_data="life_quiz")],
        [InlineKeyboardButton("🎨 Creative Challenge", callback_data="life_creative"), InlineKeyboardButton("🍀 Daily Fortune", callback_data="life_fortune")],
        [InlineKeyboardButton("🌍 လူမှုဘဝစနစ် ၅၀", callback_data="life50_home_0")],
        [InlineKeyboardButton("🎮 Game Center", callback_data="menu_games"), InlineKeyboardButton("🏠 ပင်မမီနူး", callback_data="menu_start")],
    ])


# ------------------------- LIFE & COMMUNITY: 50 PRACTICAL TOOLS -------------------------
LIFE50_GROUPS = [
    ("🧠 Mind & Relax", [
        ("Stress Relief Guide","စိတ်ဖိစီးမှုဖြစ်စေတဲ့အကြောင်းရင်းနဲ့ လုပ်ကြည့်ချင်တဲ့ အနားယူနည်းကို မှတ်တမ်းတင်ပါ။"),
        ("Breathing Trainer","၄ စက္ကန့်ရှူ၊ ၄ စက္ကန့်ရပ်၊ ၆ စက္ကန့်ထုတ် လေ့ကျင့်မှုကို ပြီးရင် ခံစားချက်ရေးပါ။"),
        ("Sleep Assistant","ဒီည အိပ်ချိန်ရည်မှန်းချက်နဲ့ အိပ်မတိုင်ခင် လုပ်မယ့်အရာကို ရေးပါ။"),
        ("Gratitude Journal","ဒီနေ့ ကျေးဇူးတင်မိတဲ့ အရာ ၃ ခုကို ရေးပါ။"),
        ("Daily Motivation","ဒီနေ့ အောင်မြင်ချင်တဲ့ သေးငယ်တဲ့အရာတစ်ခုကို ရေးပါ။"),
        ("Positive Thinking","အခက်အခဲတစ်ခုကို အပြုသဘောနဲ့ ပြန်မြင်နိုင်မယ့် နည်းလမ်းရေးပါ။"),
        ("Mindfulness Challenge","လက်ရှိမြင်၊ ကြား၊ ခံစားနေရတာတွေထဲက တစ်ခုစီကို သတိထားရေးပါ။"),
        ("Worry Box","စိတ်ပူစရာကို ရေးပြီး ကိုယ်ထိန်းချုပ်နိုင်တဲ့ အဆင့်တစ်ခုကို ဖော်ပြပါ။"),
        ("Self-Care Planner","ဒီနေ့ ကိုယ့်ကိုယ်ကို ဂရုစိုက်ဖို့ လုပ်မယ့်အရာတစ်ခု ရေးပါ။"),
        ("Relax Sound Library","အနားယူဖို့ ကြိုက်တဲ့အသံ/ပတ်ဝန်းကျင်နဲ့ အချိန်ကို မှတ်တမ်းတင်ပါ။"),
    ]),
    ("🤝 Social & Friends", [
        ("Anonymous Confession","အမည်၊ ဖုန်း၊ လိပ်စာ မထည့်ဘဲ မျှဝေချင်တဲ့ ရင်ဖွင့်စာကို ရေးပါ။"),
        ("Friendship Finder","မိတ်ဆွေအသစ်နဲ့ မျှဝေချင်တဲ့ ဝါသနာ/စိတ်ဝင်စားမှုကို ရေးပါ။"),
        ("Random Chat","စကားစဖို့ မေးခွန်း သို့မဟုတ် မိတ်ဆက်စာကို ရေးပါ။"),
        ("Group Question","Group ထဲ မေးချင်တဲ့ မေးခွန်းတစ်ခုကို ရေးပါ။"),
        ("Friendship Quiz","သူငယ်ချင်းနဲ့ မေးဖြေချင်တဲ့ မေးခွန်းတစ်ခု ရေးပါ။"),
        ("Compliment Box","တစ်ယောက်ယောက်ကို ပေးချင်တဲ့ ချီးကျူးစကားကို ရေးပါ။"),
        ("Secret Message","အမည်မဖော်ဘဲ မျှဝေမယ့် ယဉ်ကျေးတဲ့စာတိုကို ရေးပါ။"),
        ("Birthday Reminder","မွေးနေ့အမည်နဲ့ ရက်စွဲကို ရေးပါ။ ကိုယ်ရေးကိုယ်တာအချက်အလက် မထည့်ပါနှင့်။"),
        ("Group Event Planner","ပွဲအမည်၊ ရက်စွဲ၊ နေရာ/အွန်လိုင်းလင့်ခ်၊ လိုအပ်ချက် ရေးပါ။"),
        ("Social Challenge","ဒီနေ့ လုပ်မယ့် ကောင်းမွန်တဲ့ လူမှုဆက်ဆံရေးလုပ်ဆောင်ချက်ကို ရေးပါ။"),
    ]),
    ("📚 Learning & Growth", [
        ("English Daily Lesson","ဒီနေ့ လေ့လာမယ့် English စကားလုံး/ဝါကျကို ရေးပါ။"),
        ("Vocabulary Trainer","စကားလုံး၊ အဓိပ္ပာယ်၊ ဥပမာဝါကျကို ရေးပါ။"),
        ("Typing Speed Test","စမ်းသပ်ခဲ့တဲ့ WPM ရလဒ်နဲ့ နောက်ပစ်မှတ်ကို ရေးပါ။"),
        ("General Knowledge","သိချင်တဲ့ ဗဟုသုတမေးခွန်းကို ရေးပါ။"),
        ("Brain Training","ဖြေရှင်းချင်တဲ့ ဉာဏ်စမ်း/ပဟေဠိကို ရေးပါ။"),
        ("Memory Training","မှတ်မိအောင် လေ့ကျင့်မယ့် အကြောင်းအရာကို ရေးပါ။"),
        ("Study Planner","ဘာသာရပ်၊ လေ့လာချိန်နဲ့ ရည်မှန်းချက်ကို ရေးပါ။"),
        ("Goal Tracker","ရည်မှန်းချက်၊ ပြီးမြောက်ရမယ့်ရက်နဲ့ ပထမခြေလှမ်းကို ရေးပါ။"),
        ("Habit Tracker","တည်ဆောက်ချင်တဲ့ အလေ့အကျင့်နဲ့ နေ့စဉ်ပစ်မှတ်ကို ရေးပါ။"),
        ("Daily Reading","ဖတ်မယ့်စာအုပ်/ဆောင်းပါးနဲ့ ဖတ်ပြီးမှတ်ချက်ကို ရေးပါ။"),
    ]),
    ("💼 Daily Life Tools", [
        ("Expense Tracker","အသုံးစရိတ်ပမာဏ၊ အမျိုးအစားနဲ့ မှတ်ချက်ကို ရေးပါ။ ဥပမာ 2500, စားစရိတ်, နေ့လယ်စာ"),
        ("Saving Challenge","စုမယ့်ပမာဏ၊ ရည်မှန်းချက်နဲ့ စတင်ရက်ကို ရေးပါ။"),
        ("To-do List","လုပ်စရာတစ်ခုနဲ့ ပြီးစီးရမယ့်အချိန်ကို ရေးပါ။"),
        ("Smart Reminder","သတိပေးချင်တဲ့အကြောင်းအရာနဲ့ အချိန်ကို ရေးပါ။ (ဒီမှတ်တမ်းက push notification မပို့သေးပါ)"),
        ("Daily Schedule","အချိန်နဲ့ လုပ်ဆောင်ချက်ကို ရေးပါ။"),
        ("Water Reminder","ဒီနေ့ ရေသောက်ဖို့ ကိုယ်ပိုင်ပန်းတိုင်ကို ရေးပါ။"),
        ("Exercise Planner","လေ့ကျင့်ခန်းအမျိုးအစား၊ ကြာချိန်နဲ့ ပန်းတိုင်ကို ရေးပါ။"),
        ("Meal Planner","မနက်/နေ့လယ်/ည စားမယ့်အစားအစာကို ရေးပါ။"),
        ("Shopping List","ဝယ်ရန်ပစ္စည်းနဲ့ အရေအတွက်ကို ရေးပါ။"),
        ("Emergency Contact Card","အရေးပေါ်အချိန် အသုံးပြုမယ့် အများပြည်သူဆိုင်ရာ ဝန်ဆောင်မှု/ဆက်သွယ်ရန်ကို မှတ်သားပါ။ ကိုယ်ရေးကိုယ်တာနံပါတ် မထည့်ပါနှင့်။"),
    ]),
    ("🎨 Creative & Entertainment", [
        ("Story Generator","ဇာတ်လမ်းအကြောင်းအရာ၊ ဇာတ်ကောင်နဲ့ အမျိုးအစားကို ရေးပါ။"),
        ("Poetry Creator","ကဗျာရေးချင်တဲ့ အကြောင်းအရာနဲ့ ခံစားချက်ကို ရေးပါ။"),
        ("Caption Maker","ဓာတ်ပုံ/ပို့စ်အတွက် Caption ရေးချင်တဲ့ အကြောင်းအရာကို ရေးပါ။"),
        ("Meme Challenge","Meme စိတ်ကူး သို့မဟုတ် စာသားကို ရေးပါ။"),
        ("Drawing Challenge","ဒီနေ့ ဆွဲမယ့်ပုံအကြောင်းအရာကို ရေးပါ။"),
        ("Photo Guessing","ခန့်မှန်းဂိမ်းအတွက် ပုံအကြောင်းအရာ/မေးခွန်းကို ရေးပါ။"),
        ("Would You Rather","ရွေးချယ်စရာ A နဲ့ B ကို ရေးပါ။"),
        ("Truth or Dare","လုံခြုံပြီး ယဉ်ကျေးတဲ့ Truth သို့မဟုတ် Dare တစ်ခု ရေးပါ။"),
        ("Community Poll","မဲပေးမေးခွန်းနဲ့ ရွေးချယ်စရာတွေကို ရေးပါ။"),
        ("Talent Showcase","မျှဝေချင်တဲ့ အရည်အချင်း/ဖန်တီးမှုအကြောင်းကို ရေးပါ။"),
    ]),
]
LIFE50_ITEMS=[]
for _gi,(_group,_items) in enumerate(LIFE50_GROUPS):
    for _name,_desc in _items:
        LIFE50_ITEMS.append((len(LIFE50_ITEMS)+1,_name,_desc,_gi))


def life50_keyboard(page=0):
    page=max(0,min(4,int(page)))
    items=LIFE50_ITEMS[page*10:(page+1)*10]
    rows=[]
    for j in range(0,len(items),2):
        a=items[j]; row=[InlineKeyboardButton(f"{a[0]}. {a[1]}",callback_data=f"life50_{a[0]}")]
        if j+1<len(items):
            b=items[j+1]; row.append(InlineKeyboardButton(f"{b[0]}. {b[1]}",callback_data=f"life50_{b[0]}"))
        rows.append(row)
    nav=[]
    if page>0: nav.append(InlineKeyboardButton("⬅️ ယခင်",callback_data=f"life50_home_{page-1}"))
    if page<4: nav.append(InlineKeyboardButton("နောက် ➡️",callback_data=f"life50_home_{page+1}"))
    if nav: rows.append(nav)
    rows.append([InlineKeyboardButton("🌈 Relax & Fun",callback_data="life_open"),InlineKeyboardButton("🏠 ပင်မ",callback_data="menu_start")])
    return InlineKeyboardMarkup(rows)


async def life50_callback(query,data,context):
    if data.startswith("life50_home_"):
        page=int(data.rsplit("_",1)[1])
        if page < 0 or page >= len(LIFE50_GROUPS):
            await query.answer("စာမျက်နှာ မမှန်ကန်ပါ", show_alert=True)
            return
        group=LIFE50_GROUPS[page][0]
        await query.edit_message_text(f"🌍 **Life & Community Center**\n{group}\n\nဒီစာမျက်နှာမှာ စနစ် {page*10+1} မှ {page*10+10} အထိ ပါဝင်ပါတယ်။\nစနစ်တစ်ခုကို ရွေးပြီး မှတ်တမ်း/အကြောင်းအရာ ထည့်နိုင်ပါတယ်။",parse_mode="Markdown",reply_markup=life50_keyboard(page)); return
    tool_id=int(data.split("_",1)[1]); item=next((x for x in LIFE50_ITEMS if x[0]==tool_id),None)
    if not item: await query.answer("ဒီစနစ် မတွေ့ပါ",show_alert=True); return
    _,name,desc,group_idx=item
    context.user_data["life50_pending"]=tool_id
    await query.message.reply_text(f"📝 **{name}**\n\n{desc}\n\nသင့်မှတ်တမ်းကို စာသားအဖြစ် ပို့ပါ။",parse_mode="Markdown",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📚 မှတ်တမ်းကြည့်ရန်",callback_data=f"life50_list_{tool_id}")],[InlineKeyboardButton("⬅️ စာရင်း",callback_data=f"life50_home_{group_idx}")]]))


async def life50_show_entries(query,tool_id):
    item=next((x for x in LIFE50_ITEMS if x[0]==tool_id),None)
    if not item: return
    with db_connect() as conn:
        rows=conn.execute("SELECT entry,created_at FROM life50_entries WHERE user_id=? AND tool_id=? ORDER BY id DESC LIMIT 10",(query.from_user.id,tool_id)).fetchall()
    if rows:
        body="\\n\\n".join("• " + escape_markdown(r["entry"][:500], version=1) for r in rows)
    else: body="မှတ်တမ်းမရှိသေးပါ။"
    await query.message.reply_text(f"📚 **{item[1]} — နောက်ဆုံးမှတ်တမ်းများ**\n\n{body}",parse_mode="Markdown")


def get_pet(uid):
    with db_connect() as conn:
        conn.execute("INSERT OR IGNORE INTO leisure_pets(user_id,updated_at) VALUES(?,?)", (uid, int(time.time())))
        row=conn.execute("SELECT * FROM leisure_pets WHERE user_id=?", (uid,)).fetchone()
        return dict(row)


def get_garden(uid):
    now=int(time.time())
    with db_connect() as conn:
        conn.execute("INSERT OR IGNORE INTO leisure_gardens(user_id) VALUES(?)", (uid,))
        row=conn.execute("SELECT * FROM leisure_gardens WHERE user_id=?", (uid,)).fetchone()
        if now-int(row["updated_at"] or 0) >= 86400:
            conn.execute("UPDATE leisure_gardens SET water=3,updated_at=? WHERE user_id=?", (now,uid))
            row=conn.execute("SELECT * FROM leisure_gardens WHERE user_id=?", (uid,)).fetchone()
        return dict(row)


def pet_text(p):
    return (f"🐱 **{p['pet_name']} ရဲ့ အိမ်လေး**\n\n"
            f"🍚 အစာ: {p['food']}/100\n😊 ပျော်ရွှင်မှု: {p['joy']}/100\n🧼 သန့်ရှင်းမှု: {p['clean']}/100\n⭐ Level: {p['level']}\n\n"
            "အောက်က ခလုတ်တွေနဲ့ အစာကျွေး၊ ကစားပေး၊ သန့်ရှင်းရေးလုပ်ပေးပါ။")


def garden_text(g):
    return (f"🌻 **သင့်ရဲ့ Dream Garden**\n\n🌱 မျိုးစေ့: {g['seeds']}\n💧 ရေလောင်းခွင့်: {g['water']}\n🌼 ပွင့်ပြီးပန်း: {g['flowers']}\n\n"
            "ရေလောင်းပြီး ပန်းပွင့်အောင် စိုက်ပျိုးပါ။")


def pet_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🍚 အစာကျွေး",callback_data="life_pet_feed"),InlineKeyboardButton("🎾 ကစားပေး",callback_data="life_pet_play")],
        [InlineKeyboardButton("🧼 သန့်ရှင်းရေး",callback_data="life_pet_clean"),InlineKeyboardButton("🌈 မီနူး",callback_data="life_open")]])


def garden_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("💧 ရေလောင်း",callback_data="life_garden_water"),InlineKeyboardButton("🌱 မျိုးစေ့ဝယ်",callback_data="life_garden_seed")],
        [InlineKeyboardButton("🌼 ပန်းခူး",callback_data="life_garden_harvest"),InlineKeyboardButton("🌈 မီနူး",callback_data="life_open")]])


async def send_relax_audio(query, kind):
    """Generate a short, gentle synthetic ambience WAV using Python's standard library."""
    import os, random, wave, struct, math, tempfile
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    rate, seconds = 16000, 6
    rng=random.Random(int(time.time())//30 + len(kind))
    try:
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(rate)
            frames=[]
            for i in range(rate*seconds):
                t=i/rate
                if kind == "rain":
                    value=(rng.random()*2-1)*0.12 + math.sin(2*math.pi*95*t)*0.025
                elif kind == "forest":
                    chirp=max(0,math.sin(2*math.pi*3.2*t))*math.sin(2*math.pi*(950+220*math.sin(t))*t)*0.10
                    value=(rng.random()*2-1)*0.025+chirp
                else:
                    wave_amp=0.045+0.055*(0.5+0.5*math.sin(2*math.pi*0.18*t))
                    value=(rng.random()*2-1)*wave_amp+math.sin(2*math.pi*70*t)*0.025
                sample=max(-1,min(1,value))
                frames.append(struct.pack("<h",int(sample*32767)))
            wf.writeframes(b"".join(frames))
        title={"rain":"မိုးဖွဲသံ","forest":"တောအုပ်ငှက်သံ","ocean":"ပင်လယ်လှိုင်းသံ"}[kind]
        with open(path, "rb") as audio_file:
            await query.message.reply_audio(audio=audio_file,title=title,performer="CK BOT Relax")
    finally:
        try: os.remove(path)
        except OSError: pass


async def leisure_callback(query, context, data):
    user=query.from_user; uid=user.id; chat=query.message.chat
    if data == "life_open":
        await query.edit_message_text("🌈 **CK BOT — Relax & Fun Center**\nပင်ပန်းတဲ့နေ့လေးမှာ ခဏအနားယူပြီး ပျော်ရွှင်စရာလေးတွေ လုပ်ကြရအောင်။",parse_mode="Markdown",reply_markup=life_menu()); return
    if data == "life_pet":
        await query.edit_message_text(pet_text(get_pet(uid)),parse_mode="Markdown",reply_markup=pet_keyboard()); return
    if data.startswith("life_pet_"):
        action=data.rsplit("_",1)[1]; get_pet(uid)
        changes={"feed":("food",25,"🍚 အစာကျွေးပြီးပါပြီ!"),"play":("joy",20,"🎾 အတူကစားပြီး ပျော်ရွှင်မှုတိုးလာပါတယ်!"),"clean":("clean",25,"🧼 သန့်ရှင်းရေးလုပ်ပြီးပါပြီ!")}
        if action in changes:
            col,amount,msg=changes[action]
            with db_connect() as conn:
                level_expr = "level+CASE WHEN joy < 100 AND joy+? >= 100 THEN 1 ELSE 0 END" if col == "joy" else "level"
            params = (amount, amount, int(time.time()), uid) if col == "joy" else (amount, int(time.time()), uid)
            conn.execute(f"UPDATE leisure_pets SET {col}=MIN(100,{col}+?), level={level_expr}, updated_at=? WHERE user_id=?", params)
            await query.edit_message_text(msg+"\n\n"+pet_text(get_pet(uid)),parse_mode="Markdown",reply_markup=pet_keyboard()); return
    if data == "life_garden":
        await query.edit_message_text(garden_text(get_garden(uid)),parse_mode="Markdown",reply_markup=garden_keyboard()); return
    if data.startswith("life_garden_"):
        action=data.rsplit("_",1)[1]; g=get_garden(uid); msg=""
        with db_connect() as conn:
            if action=="seed":
                if g["seeds"]>=10: msg="🌱 မျိုးစေ့ ၁၀ ခု ပြည့်နေပါပြီ။"
                else: conn.execute("UPDATE leisure_gardens SET seeds=seeds+1 WHERE user_id=?",(uid,)); msg="🌱 မျိုးစေ့တစ်ခု ထည့်ပေးလိုက်ပါပြီ။"
            elif action=="water":
                if g["water"]<=0: msg="💧 ရေလောင်းခွင့် မကျန်တော့ပါ။ မနက်ဖြန် ပြန်ရပါမယ်။"
                elif g["seeds"]<=0: msg="🌱 အရင်ဆုံး မျိုးစေ့ဝယ်ပါ။"
                else:
                    conn.execute("UPDATE leisure_gardens SET water=water-1,seeds=seeds-1,flowers=flowers+1 WHERE user_id=?",(uid,)); msg="🌼 ပန်းတစ်ပွင့် ပွင့်လာပါပြီ!"
            elif action=="harvest":
                if g["flowers"]<=0: msg="🌼 ခူးစရာပန်း မရှိသေးပါ။"
                else: conn.execute("UPDATE leisure_gardens SET flowers=flowers-1,seeds=seeds+1 WHERE user_id=?",(uid,)); msg="🌷 ပန်းတစ်ပွင့် ခူးပြီး မျိုးစေ့တစ်ခု ပြန်ရပါပြီ။"
        await query.edit_message_text(msg+"\n\n"+garden_text(get_garden(uid)),parse_mode="Markdown",reply_markup=garden_keyboard()); return
    if data == "life_mood":
        kb=InlineKeyboardMarkup([[InlineKeyboardButton(v[0],callback_data=f"life_mood_{k}")] for k,v in LIFE_MOODS.items()]+[[InlineKeyboardButton("🌈 မီနူး",callback_data="life_open")]])
        await query.edit_message_text("🌅 **ဒီနေ့ ဘယ်လိုခံစားနေရလဲ?**\nကိုယ့်ခံစားချက်နဲ့ အနီးစပ်ဆုံးတစ်ခုကို ရွေးပါ။",parse_mode="Markdown",reply_markup=kb); return
    if data.startswith("life_mood_"):
        key=data.rsplit("_",1)[1]; item=LIFE_MOODS.get(key)
        if item:
            await query.edit_message_text(f"🌅 **{item[0]}**\n\n{item[1]}\n\nအသက်ကို ၄ စက္ကန့်ရှူသွင်း၊ ၄ စက္ကန့်ခဏရပ်၊ ၆ စက္ကန့်ဖြည်းဖြည်းထုတ်ကြည့်ပါ။",parse_mode="Markdown",reply_markup=life_menu()); return
    if data == "life_camp":
        if chat.type=="private":
            await query.edit_message_text("🔥 Friendship Camp ကို Group Chat ထဲမှာ သူငယ်ချင်းတွေနဲ့ ကစားနိုင်ပါတယ်။",reply_markup=life_menu()); return
        camp=load_life_camp(chat.id)
        if not camp or camp.get("status")=="finished":
            camp={"host":uid,"players":[{"id":uid,"name":user.first_name or str(uid)}],"status":"waiting","answers":{}}
            save_life_camp(chat.id, camp)
        names="\n".join(f"{i+1}. {p['name']}" for i,p in enumerate(camp["players"]))
        kb=InlineKeyboardMarkup([[InlineKeyboardButton("🙋 Join",callback_data="life_camp_join"),InlineKeyboardButton("▶️ Start",callback_data="life_camp_start")],[InlineKeyboardButton("🌈 မီနူး",callback_data="life_open")]])
        await query.edit_message_text("🔥 **Friendship Camp**\nကစားသမား ၂ ယောက်မှ ၃ ယောက်အထိ ပါဝင်နိုင်ပါတယ်။\n\n"+names+"\n\nJoin လုပ်ပြီး Start နှိပ်ပါ။",parse_mode="Markdown",reply_markup=kb); return
    if data == "life_camp_join":
        camp=load_life_camp(chat.id)
        if not camp or camp.get("status")!="waiting": return
        if any(p["id"]==uid for p in camp["players"]): return
        if len(camp["players"])>=3: return
        camp["players"].append({"id":uid,"name":user.first_name or str(uid)})
        save_life_camp(chat.id, camp)
        names="\n".join(f"{i+1}. {p['name']}" for i,p in enumerate(camp["players"]))
        await query.edit_message_text("🔥 **Friendship Camp**\n\n"+names+"\n\n၂ ယောက်ပြည့်ပါပြီ။ Host က Start နှိပ်နိုင်ပါပြီ။",parse_mode="Markdown",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🙋 Join",callback_data="life_camp_join"),InlineKeyboardButton("▶️ Start",callback_data="life_camp_start")]])); return
    if data == "life_camp_start":
        camp=load_life_camp(chat.id)
        if not camp or camp.get("status")!="waiting" or uid!=camp["host"]: return
        if len(camp["players"])<2: return
        camp["status"]="playing"; camp["answers"]={}
        prompt=random.choice(["ဒီအဖွဲ့ထဲမှာ အရယ်ရဆုံးသူ ဘယ်သူလဲ?","အတူခရီးသွားချင်ဆုံးသူ ဘယ်သူလဲ?","အကူအညီတောင်းရင် အမြန်ဆုံးကူညီမယ့်သူ ဘယ်သူလဲ?"])
        camp["prompt"]=prompt
        save_life_camp(chat.id, camp)
        kb=InlineKeyboardMarkup([[InlineKeyboardButton(p["name"],callback_data=f"life_camp_vote_{i}")] for i,p in enumerate(camp["players"])])
        await query.edit_message_text("🔥 **Friendship Camp — Round 1**\n\n"+prompt+"\n\nတစ်ယောက်ချင်းစီ ရွေးပါ။",parse_mode="Markdown",reply_markup=kb); return
    if data.startswith("life_camp_vote_"):
        camp=load_life_camp(chat.id)
        if not camp or camp.get("status")!="playing": return
        if uid not in [p["id"] for p in camp["players"]]: return
        ix=int(data.rsplit("_",1)[1])
        if ix < 0 or ix >= len(camp["players"]): return
        camp["answers"][str(uid)]=camp["players"][ix]["name"]
        save_life_camp(chat.id, camp)
        if len(camp["answers"])<len(camp["players"]): return
        counts={}
        for v in camp["answers"].values(): counts[v]=counts.get(v,0)+1
        camp["status"]="finished"; save_life_camp(chat.id, camp); result="\n".join(f"• {k}: {v} မဲ" for k,v in counts.items())
        await query.edit_message_text("🔥 **Friendship Camp ပြီးပါပြီ!**\n\n"+camp["prompt"]+"\n\n"+result+"\n\nအတူတူရယ်မောပြီး ခင်မင်မှုတိုးပါစေ!",parse_mode="Markdown",reply_markup=life_menu()); return
    if data == "life_daily":
        today=(datetime.now(timezone.utc)+timedelta(hours=6,minutes=30)).strftime("%Y-%m-%d")
        with db_connect() as conn:
            conn.execute("INSERT OR IGNORE INTO leisure_daily(user_id) VALUES(?)",(uid,))
            row=conn.execute("SELECT * FROM leisure_daily WHERE user_id=?",(uid,)).fetchone()
            reward=0
            if row["claim_day"]==today: msg=f"🎁 ဒီနေ့ ဆုယူပြီးပါပြီ။ Streak {row['streak']} ရက် | စုစုပေါင်း {row['coins']} Coins"
            else:
                yesterday=(datetime.now(timezone.utc)+timedelta(hours=6,minutes=30)-timedelta(days=1)).strftime("%Y-%m-%d")
                streak=row["streak"]+1 if row["claim_day"]==yesterday else 1
                reward=50+min(streak,7)*10
                conn.execute("UPDATE leisure_daily SET claim_day=?,streak=?,coins=coins+? WHERE user_id=?",(today,streak,reward,uid))
                msg=f"🎉 ဒီနေ့ဆု +{reward} Coins ရပါပြီ!\n🔥 Streak: {streak} ရက်"
        if reward:
            player=rpg_player(user)
            rpg_update(uid, coins=player["coins"]+reward)
        await query.edit_message_text(msg,reply_markup=life_menu()); return
    if data == "life_funny":
        await query.edit_message_text("😂 **Funny Zone**\n\n"+random.choice(FUNNY_LINES),reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🤣 နောက်တစ်ခု",callback_data="life_funny")],[InlineKeyboardButton("🌈 မီနူး",callback_data="life_open")]])); return
    if data == "life_story":
        kb=InlineKeyboardMarkup([[InlineKeyboardButton("🌧️ မိုးဖွဲသံ",callback_data="life_sound_rain"),InlineKeyboardButton("🐦 တောအုပ်သံ",callback_data="life_sound_forest")],[InlineKeyboardButton("🌊 ပင်လယ်လှိုင်းသံ",callback_data="life_sound_ocean")],[InlineKeyboardButton("📖 ပုံပြင်အသစ်",callback_data="life_story_text")],[InlineKeyboardButton("🌈 မီနူး",callback_data="life_open")]])
        await query.edit_message_text("🌧️ **Relax Sound & Story**\n\nအသံအေးအေးလေး နားထောင်နိုင်သလို ပုံပြင်တိုလေးလည်း ဖတ်နိုင်ပါတယ်။",parse_mode="Markdown",reply_markup=kb); return
    if data.startswith("life_sound_"):
        await send_relax_audio(query,data.rsplit("_",1)[1]); return
    if data == "life_story_text":
        await query.edit_message_text("📖 **အနားယူချိန် ပုံပြင်တို**\n\n"+random.choice(RELAX_STORIES),reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔊 အသံနဲ့အနားယူမယ်",callback_data="life_story")],[InlineKeyboardButton("🌈 မီနူး",callback_data="life_open")]])); return
    if data == "life_quiz":
        context.user_data["life_quiz"]={"step":0,"score":0}
        q,opts=PERSONALITY_QUESTIONS[0]
        kb=InlineKeyboardMarkup([[InlineKeyboardButton(x,callback_data=f"life_quiz_{i}")] for i,(x,_) in enumerate(opts)])
        await query.edit_message_text("💝 **ပျော်စရာ Personality Quiz (၁/၃)**\n\n"+q,parse_mode="Markdown",reply_markup=kb); return
    if data.startswith("life_quiz_"):
        st=context.user_data.get("life_quiz")
        if not st: return
        ix=int(data.rsplit("_",1)[1]); step=st["step"]
        if ix not in range(3): return
        st["score"]+=PERSONALITY_QUESTIONS[step][1][ix][1]; st["step"]+=1
        if st["step"]>=3:
            score=st["score"]; context.user_data.pop("life_quiz",None)
            result="🌿 တည်ငြိမ်စဉ်းစားတတ်သူ" if score<=1 else "💛 ခင်မင်နွေးထွေးသူ" if score>=4 else "🚀 စူးစမ်းတီထွင်သူ"
            await query.edit_message_text("💝 **သင့်ရဲ့ ပျော်စရာ Quiz ရလဒ်**\n\n"+result+"\n\nဒီရလဒ်ဟာ ဖျော်ဖြေရေးသဘောသာ ဖြစ်ပြီး သိပ္ပံနည်းကျ ကိုယ်ရည်ကိုယ်သွေးစစ်ဆေးမှု မဟုတ်ပါ။",parse_mode="Markdown",reply_markup=life_menu()); return
        q,opts=PERSONALITY_QUESTIONS[st["step"]]
        kb=InlineKeyboardMarkup([[InlineKeyboardButton(x,callback_data=f"life_quiz_{i}")] for i,(x,_) in enumerate(opts)])
        await query.edit_message_text(f"💝 **ပျော်စရာ Personality Quiz ({st['step']+1}/3)**\n\n"+q,parse_mode="Markdown",reply_markup=kb); return
    if data == "life_creative":
        prompt=random.choice(CREATIVE_PROMPTS); context.user_data["creative_prompt"]=prompt
        await query.edit_message_text("🎨 **Creative Challenge**\n\n"+prompt+"\n\nသင့်အဖြေကို Chat ထဲမှာ စာသားအဖြစ် ပို့ပေးပါ။",parse_mode="Markdown",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🌈 မီနူး",callback_data="life_open")]])); return
    if data == "life_fortune":
        fortunes=["ဒီနေ့ သေးငယ်တဲ့ အခွင့်အရေးတစ်ခုက ပျော်ရွှင်မှုကြီးတစ်ခု ဖြစ်လာနိုင်ပါတယ်။","မိတ်ဆွေတစ်ယောက်ဆီက သတင်းကောင်းကြားရနိုင်တဲ့နေ့ပါ။","အလုပ်တွေကို တစ်ခုချင်းစီလုပ်ပါ။ အလျင်မလိုရင် ပိုကောင်းတဲ့ရလဒ်ရနိုင်ပါတယ်။","ကိုယ့်ကိုယ်ကို ယုံကြည်ပြီး စတင်လိုက်ပါ။ ပထမခြေလှမ်းက အရေးကြီးဆုံးပါ။"]
        await query.edit_message_text("🍀 **ဒီနေ့အတွက် ကံကောင်းစေမယ့် စကားလေး**\n\n"+random.choice(fortunes)+"\n\nဖျော်ဖြေရေးသဘောသာ ယူဆပါ။",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 နောက်တစ်ခု",callback_data="life_fortune")],[InlineKeyboardButton("🌈 မီနူး",callback_data="life_open")]])); return

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""

    if data.startswith(("ckg:", "ckc:")):
        try:
            await group_channel_button_callback(query, context, data)
        except Exception:
            logger.exception("Group/Channel settings callback failed: %s", data)
            try: await query.answer("လုပ်ဆောင်မှု မအောင်မြင်ပါ။ ပြန်စမ်းပါ။", show_alert=True)
            except Exception: pass
        return

    if data.startswith("ckt:"):
        try:
            await tools_button_callback(query, context, data)
        except Exception:
            logger.exception("Toolbox callback failed: %s", data)
            try: await query.answer("Tool လုပ်ဆောင်မှု မအောင်မြင်ပါ။", show_alert=True)
            except Exception: pass
        return

    if data.startswith("mlbbi_"):
        await query.answer()
        try: await mlbbi_callback(query,data)
        except Exception:
            logger.exception("MLBB image callback failed: %r",data)
            try: await query.message.reply_text("⚠️ MLBB ပုံခန့်မှန်းစနစ်မှာ အမှားဖြစ်နေပါတယ်။ ပြန်စမ်းပါ။")
            except Exception: pass
        return

    if data.startswith("rpg_"):
        await query.answer()
        if not await require_group_bot_admin(query, context): return
        try:
            await rpg_callback(query, context, data)
        except Exception:
            logger.exception("RPG callback failed for %r", data)
            try:
                await query.edit_message_text("⚠️ RPG ဂိမ်းတွင် အမှားတစ်ခု ဖြစ်နေပါတယ်။ /rpg ကို ပြန်ပို့ပြီး ထပ်စမ်းပါ။")
            except Exception:
                logger.exception("Could not display RPG error message")
        return

    if data.startswith("life50_"):
        await query.answer()
        try:
            if data.startswith("life50_list_"):
                await life50_show_entries(query,int(data.rsplit("_",1)[1]))
            else:
                await life50_callback(query,data,context)
        except Exception:
            logger.exception("Life50 callback failed: %r",data)
            await query.message.reply_text("⚠️ ဒီစနစ်မှာ အမှားဖြစ်နေပါတယ်။ ပြန်စမ်းပါ။")
        return

    if data.startswith("life_"):
        await query.answer()
        if not await require_group_bot_admin(query, context): return
        try:
            await leisure_callback(query, context, data)
        except Exception:
            logger.exception("Relax & Fun callback failed for %r", data)
            try: await query.message.reply_text("⚠️ ဒီစနစ်မှာ ခဏတာအမှားဖြစ်နေပါတယ်။ ပြန်စမ်းကြည့်ပါ။")
            except Exception: pass
        return

    if data.startswith("a50_"):
        await query.answer()
        try:
            await arcade50_callback(query, context, data)
        except Exception:
            logger.exception("Arcade50 callback failed: %r", data)
            try: await query.edit_message_text("⚠️ ဂိမ်းမှာ အမှားဖြစ်နေပါတယ်။ /game ကို ပြန်စမ်းပါ။")
            except Exception: pass
        return

    if data.startswith("room_"):
        await query.answer()
        try:
            await room_callback(query, context, data)
        except Exception:
            logger.exception("Multiplayer room callback failed: %r", data)
            try:
                await query.edit_message_text("⚠️ Multiplayer ဂိမ်းခန်းမှာ အမှားဖြစ်နေပါတယ်။ /game ကို ပြန်စမ်းပါ။", reply_markup=games_menu_keyboard(query.message.chat.type))
            except Exception:
                logger.exception("Could not display multiplayer room error")
        return

    await query.answer()
    if not await require_group_bot_admin(query, context): return

    if data.startswith("mini_"):
        try:
            await mini_game_callback(query, context, data)
        except Exception:
            logger.exception("Mini game callback failed for %r", data)
            await query.edit_message_text("⚠️ ဂိမ်းတွင် အမှားတစ်ခုဖြစ်နေပါတယ်။ /game ကို ပြန်စမ်းပါ။", reply_markup=games_menu_keyboard(query.message.chat.type))
        return

    if data == "picq_next":
        await send_picture_quiz(query, context)
        return

    if data.startswith("picq_"):
        try:
            selected = int(data.split("_")[1])
            q = context.user_data.get("picture_quiz_question")
            if not q:
                return
            correct = selected == q["answer"]
            if correct:
                score = context.user_data.get("picture_quiz_score", 0) + 10
                context.user_data["picture_quiz_score"] = score
                result = f"🎉 အဖြေမှန်ပါတယ်။ +10 မှတ်\n⭐ စုစုပေါင်း: {score} မှတ်"
            else:
                result = f"❌ အဖြေမှားပါတယ်။ အဖြေမှန်က **{q['options'][q['answer']]}** ဖြစ်ပါတယ်။\n⭐ စုစုပေါင်း: {context.user_data.get('picture_quiz_score', 0)} မှတ်"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("➡️ နောက်မေးခွန်း", callback_data="picq_next")], [InlineKeyboardButton("🎮 Game Center", callback_data="menu_games")]])
            await query.edit_message_caption(caption=f"🖼️ **Picture Quiz**\n{q['q']}\n\n{result}", parse_mode="Markdown", reply_markup=kb)
        except Exception:
            logger.exception("Picture quiz answer failed")
            logger.exception("Picture quiz callback could not update message")
        return

    if data == "arcx_memory_done":
        await query.answer("ဒီအတွဲကို ရှာတွေ့ပြီးပါပြီ။")
        return

    if data.startswith("new_") or data.startswith("arc_") or data.startswith("arcx_"):
        try:
            await additional_game_callback(query, context, data)
        except Exception:
            logger.exception("Additional game callback failed for %r", data)
            await query.edit_message_text("⚠️ ဂိမ်းတွင် အမှားဖြစ်နေပါတယ်။ /game ဖြင့် ပြန်စတင်ပါ။", reply_markup=games_menu_keyboard(query.message.chat.type))
        return

    if data.startswith("ans_"):
        _, selected_idx, correct_idx = data.split("_")
        if selected_idx == correct_idx:
            result_text = "🎉 **ဂုဏ်ယူပါတယ်!** အဖွဲ့သားများ စုပေါင်းဖြေဆိုချက်မှာ **မှန်ကန်ပါသည်**။ 🏆\n\nထပ်မံဆော့ရန် `/game` ဟု ရိုက်ပါ။"
        else:
            result_text = "❌ **မှားယွင်းနေပါတယ်!** နောက်တစ်ကြိမ် ထပ်မံကြိုးစားကြည့်ပါ။\n\nထပ်မံဆော့ရန် `/game` ဟု ရိုက်ပါ။"
        await query.edit_message_text(result_text, parse_mode="Markdown")
        return

    if data == "thief_start":
        keyboard = [
            [InlineKeyboardButton("🚪 အိမ်နောက်ဖေး တံခါးပေါက်မှ ခိုးဝင်မည်", callback_data="thief_backdoor")],
            [InlineKeyboardButton("🪟 ဒုတိယထပ် ပြတင်းပေါက်ကို တက်မည်", callback_data="thief_window")],
            [InlineKeyboardButton("🏠 ပင်မတံခါးကို သော့ဖျက်ဝင်မည်", callback_data="thief_frontdoor")],
        ]
        text = (
            "🦹 **သူခိုးဂိမ်း: လန်ဘား၏ ညဉ့်နက်သန်းခေါင် စွန့်စားခန်း** 🦹\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "ညဉ့်နက်သန်းခေါင်ယံအချိန်... နာမည်ကျော်သူခိုး **'လန်ဘား'** ဟာ မြို့စွန်က စီးပွားရေးလုပ်ငန်းရှင်ကြီးတစ်ယောက်ရဲ့ ဇိမ်ခံအိမ်ကြီးရှေ့ကို ရောက်ရှိလာပါပြီ။\n\n"
            "🏡 အိမ်ကြီးရဲ့ လုံခြုံရေးက တော်တော်တင်းကျပ်ပါတယ်။ လန်ဘား ဘယ်လိုနည်းလမ်းနဲ့ အိမ်ထဲကို ဝင်ရောက်မှာလဲ?"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data == "thief_backdoor":
        keyboard = [
            [InlineKeyboardButton("💎 ဧည့်ခန်းထဲက ရွှေပန်းအိုးကို ခိုးမည်", callback_data="thief_livingroom")],
            [InlineKeyboardButton("🛏️ အပေါ်ထပ် အိပ်ခန်းထဲက စိန်လက်စွပ်ကို ရှာမည်", callback_data="thief_bedroom")],
        ]
        await query.edit_message_text(
            "🚪 **အနောက်ဖေး တံခါးပေါက်**\n━━━━━━━━━━━━━━━━━━━\n"
            "လန်ဘားဟာ သော့တံကို ကျွမ်းကျင်ပိုင်နိုင်စွာ သုံးပြီး အနောက်ဖေးတံခါးကို အောင်မြင်စွာ ဖွင့်ဝင်လာနိုင်ခဲ့ပါပြီ။ အခု အိမ်ထဲကို ရောက်ပါပြီ။ ဘယ်နေရာကို ဆက်သွားမလဲ?",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard),
        )
    elif data in ("thief_window", "thief_frontdoor", "thief_livingroom", "thief_lose"):
        stories = {
            "thief_window": "🪟 **ပြတင်းပေါက်မှ တက်စဉ် မတော်တဆဖြစ်ခြင်း!** ❌\nလုံခြုံရေးခွေးကြီးက အသံကြားပြီး အော်ဟောက်လိုက်သဖြင့် လန်ဘား ဖမ်းမိသွားပါပြီ။",
            "thief_frontdoor": "🏠 **ပင်မတံခါးမှ ဝင်ရောက်ခြင်း** ❌\nAlarm မြည်သွားပြီး ရဲတွေ ရောက်လာပါတော့တယ်။",
            "thief_livingroom": "💎 **ရွှေပန်းအိုး ခိုးယူခြင်း** ❌\nအလေးချိန်အာရုံခံစနစ် ပွင့်သွားပြီး လုံခြုံရေးတွေ ဝိုင်းဖမ်းလိုက်ပါပြီ။",
            "thief_lose": "🚗 **ထွက်ပြေးစဉ် မိသွားခြင်း** ❌\nအောက်ထပ်မှာ လုံခြုံရေးတွေ စောင့်နေတာကြောင့် လန်ဘား မိသွားပါပြီ။",
        }
        keyboard = [
            [InlineKeyboardButton("🔄 ထပ်မံ ကြိုးစားမည်", callback_data="thief_start")],
            [InlineKeyboardButton("🎮 ဂိမ်းမီနူးသို့", callback_data="menu_games")],
        ]
        await query.edit_message_text(stories[data] + "\n\n💥 **Game Over**", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data == "thief_bedroom":
        keyboard = [
            [InlineKeyboardButton("🚁 အမိုးပေါ်ကနေ ရဟတ်ယာဉ်နဲ့ ထွက်ပြေးမည်", callback_data="thief_win")],
            [InlineKeyboardButton("🚗 အောက်ထပ်ကနေ အမြန်ယာဉ်နဲ့ ထွက်မည်", callback_data="thief_lose")],
        ]
        await query.edit_message_text(
            "🛏️ **အိပ်ခန်းထဲသို့ အောင်မြင်စွာ ရောက်ရှိခြင်း** ✨\n"
            "လန်ဘားဟာ စိန်လက်စွပ်နဲ့ ငွေစက္ကူအထုပ်တွေကို ရယူနိုင်ခဲ့ပါပြီ။ ဘယ်လိုထွက်ပြေးမှာလဲ?",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard),
        )
    elif data == "thief_win":
        keyboard = [
            [InlineKeyboardButton("🎮 အခြားဂိမ်းများ ဆော့မည်", callback_data="menu_games")],
            [InlineKeyboardButton("🏠 ပင်မမီနူးသို့", callback_data="menu_start")],
        ]
        await query.edit_message_text(
            "🎉 **ဂုဏ်ယူပါတယ်! လန်ဘား အောင်မြင်သွားပါပြီ!** 🏆\n"
            "လန်ဘားဟာ ခိုးထားတဲ့ပစ္စည်းတွေနဲ့အတူ အမိုးပေါ်ကနေ အောင်မြင်စွာ လွတ်မြောက်သွားပါတယ်။",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard),
        )
    elif data == "menu_games":
        await query.edit_message_text(
            "🎮 **CK BOT GAME CENTER** 🎮\nဂိမ်းအမျိုးအစားကို ရွေးချယ်ပါ။",
            parse_mode="Markdown", reply_markup=games_menu_keyboard(query.message.chat.type),
        )
    elif data == "game_trivia":
        if not SAVED_TRIVIA_QUESTIONS:
            await query.edit_message_text("⚠️ မေးခွန်းမရှိသေးပါ။ `/addq` ဖြင့် အရင်ထည့်ပါ。")
            return
        q_data = random.choice(SAVED_TRIVIA_QUESTIONS)
        keyboard = [[InlineKeyboardButton(opt, callback_data=f"ans_{idx}_{q_data['answer']}")] for idx, opt in enumerate(q_data["options"])]
        game_intro = (
            "🎮 **ဉာဏ်စမ်း အဖွဲ့လိုက်ဂိမ်း စတင်ပါပြီ** 🎮\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ *စည်းမျဉ်း:* ဤဂိမ်းတွင် ပါဝင်ရန် **အဖွဲ့သား (၃) ယောက်** လိုအပ်ပါသည်။\n\n"
            f"❓ **မေးခွန်း:** {q_data['q']}"
        )
        await query.edit_message_text(game_intro, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data == "game_lucky":
        prize = random.choice(LUCKY_PRIZES)
        keyboard = [
            [InlineKeyboardButton("🎲 ထပ်မံ ကံစမ်းမည်", callback_data="game_lucky")],
            [InlineKeyboardButton("🎮 ဂိမ်းမီနူးသို့", callback_data="menu_games")],
            [InlineKeyboardButton("🏠 ပင်မမီနူးသို့", callback_data="menu_start")],
        ]
        await query.edit_message_text(
            f"🎁 **ကံစမ်းမဲ ကံကောင်းခြင်းဂိမ်း** 🎁\n━━━━━━━━━━━━━━━━━━━\n\n{prize}",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard),
        )
    elif data == "mode_zodiac":
        context.user_data.setdefault("fortune_modes", {})[str(query.message.chat_id)] = "zodiac"
        await query.edit_message_text("✨ **ရာသီခွင် အသေးစိတ် မေးမြန်းရန်**\n\nသင့်ရဲ့ ရာသီခွင်အမည်ကို Chat ထဲမှာ ပို့ပေးပါ။", parse_mode="Markdown")
    elif data == "mode_tomorrow":
        context.user_data.setdefault("fortune_modes", {})[str(query.message.chat_id)] = "tomorrow"
        await query.edit_message_text("📅 **မနက်ဖြန် ဖြစ်ပျက်မည့်ဟောကိန်း မေးမြန်းရန်**\n\nသင့်ရဲ့ ရာသီခွင်အမည်ကို Chat ထဲမှာ ပို့ပေးပါ။", parse_mode="Markdown")
    elif data == "mode_tarot":
        cards = random.sample(TAROT_DECK, 3)
        response = "✨ **တားရော့ (၃) ကတ် ဟောကိန်း** ✨\n━━━━━━━━━━━━━━━━━━━\n\n" + "\n\n".join(
            f"• **{card['name']}**: {card['vibe']}" for card in cards
        )
        keyboard = [
            [InlineKeyboardButton("🔄 ထပ်မံ မဲကြည့်မည်", callback_data="mode_tarot")],
            [InlineKeyboardButton("🏠 ပင်မမီနူးသို့", callback_data="menu_start")],
        ]
        await query.edit_message_text(response, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data == "menu_start":
        keyboard = [
            [InlineKeyboardButton("🌟 ရာသီခွင် အသေးစိတ်ဟောကိန်း", callback_data="mode_zodiac")],
            [InlineKeyboardButton("📅 မနက်ဖြန် ဖြစ်ပျက်မည့်ဟောကိန်း", callback_data="mode_tomorrow")],
            [InlineKeyboardButton("🃏 တားရော့ (၃) ကတ် ဟောရန်", callback_data="mode_tarot")],
            [InlineKeyboardButton("🎮 ဂိမ်းများ ဆော့ကစားရန် (/game)", callback_data="menu_games")],
            [InlineKeyboardButton("🛡️ Adventure RPG (/rpg)", callback_data="rpg_open")],
            [InlineKeyboardButton("🌈 Relax & Fun Center", callback_data="life_open")],
            [InlineKeyboardButton("🌍 လူမှုဘဝစနစ် ၅၀", callback_data="life50_home_0")],
        ]
        await query.edit_message_text("ကျေးဇူးပြု၍ အောက်ပါတို့မှ ရွေးချယ်ပါ -", reply_markup=InlineKeyboardMarkup(keyboard))


# ------------------------- RESTRICTED GROUP LANGUAGE MODERATION -------------------------
# Conservative detection: avoid very short/common fragments that can trigger false positives.
# Burmese phrases are normalized for zero-width characters and spacing variants.
PROFANITY_TERMS_MY = (
    "ခွေးမသား", "ခွေးသား", "မအေလိုး", "အမေလိုး", "စောက်ဖုတ်",
    "စောက်ခွက်", "စောက်ကျင့်", "သောက်ကျင့်", "လိုးမသား",
    "လီးစုပ်", "ဖင်ခံ", "ဖာသည်မ", "ခွေးလိုး",
)
PROFANITY_TERMS_EN = (
    "motherfucker", "motherfuckers", "fucking", "fuck", "shit",
    "bitch", "bastard", "asshole", "dickhead", "cunt",
)
_ZERO_WIDTH_RE = re.compile(r"[\u200b-\u200f\u2060\ufeff]")
_NONWORD_RE = re.compile(r"[^a-z0-9]+")

def _normalize_moderation_text(value):
    value = _ZERO_WIDTH_RE.sub("", (value or "").casefold())
    # Collapse repeated whitespace, preserve Burmese characters.
    return re.sub(r"\s+", " ", value).strip()

def contains_profanity(text):
    value = _normalize_moderation_text(text)
    if not value:
        return False
    # English terms require alphabetic boundaries, so e.g. "class" won't match "ass".
    for term in PROFANITY_TERMS_EN:
        if re.search(r"(?<![a-z])" + re.escape(term) + r"(?![a-z])", value):
            return True
    # Burmese profanity entries are intentionally full abusive expressions, not short fragments.
    compact = re.sub(r"\s+", "", value)
    return any(term in compact for term in PROFANITY_TERMS_MY)

def has_profanity_permission(user_id):
    with db_connect() as conn:
        return conn.execute(
            "SELECT 1 FROM profanity_permissions WHERE user_id=?", (user_id,)
        ).fetchone() is not None

async def _is_group_admin(chat_id, user_id, context):
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        logger.exception("Could not verify group member status chat=%s user=%s", chat_id, user_id)
        return False

async def permission_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, user = update.effective_message, update.effective_user
    if not msg or not user:
        return
    if not BOT_OWNER_ID or user.id != BOT_OWNER_ID:
        await msg.reply_text(
            "⛔ Bot ပိုင်ရှင်အဖြစ် အတည်မပြုနိုင်ပါ။\n"
            f"သင့် Telegram ID: `{user.id}`\n"
            "Railway → Variables ထဲက `BOT_OWNER_ID` ကို ဒီ ID နဲ့ အတိအကျတူအောင် ထည့်ပြီး Redeploy လုပ်ပါ။",
            parse_mode="Markdown",
        )
        return
    if not msg.reply_to_message or not msg.reply_to_message.from_user:
        await msg.reply_text("အသုံးပြုပုံ — ခွင့်ပြုလိုသူရဲ့ စာကို Reply လုပ်ပြီး /permission ပို့ပါ။")
        return
    target = msg.reply_to_message.from_user
    if target.is_bot or target.id == BOT_OWNER_ID:
        await msg.reply_text("ဒီအကောင့်ကို ခွင့်ပြုစာရင်းထဲ ထည့်ရန် မလိုအပ်ပါ။")
        return
    with db_connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO profanity_permissions(user_id,granted_by,granted_at) VALUES(?,?,?)",
            (target.id, user.id, int(time.time())),
        )
        conn.commit()
    await msg.reply_text(
        f"✅ {target.first_name} ကို Group ဆဲဆိုမှုထိန်းချုပ်ရေးစနစ် စတင်အသုံးပြုခွင့်ပေးပြီးပါပြီ။\n\n"
        "အသုံးပြုရန် — သူ/သူမက Group ထဲဝင်ပြီး Group Admin ဖြစ်ရပါမယ်။ "
        "အဲဒီ Group မှာ Bot ကိုလည်း Admin ခန့်ပြီး Delete Messages နှင့် Restrict Members "
        "ခွင့်နှစ်ခုလုံးပေးထားရပါမယ်။ ထို့နောက် ခွင့်ပြုထားသူက Group ထဲ စာတစ်ကြောင်းပို့ပါ။"
    )

async def unpermission_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, user = update.effective_message, update.effective_user
    if not msg or not user:
        return
    if not BOT_OWNER_ID or user.id != BOT_OWNER_ID:
        await msg.reply_text("⛔ ဒီ command ကို Bot ပိုင်ရှင်တစ်ဦးတည်းသာ အသုံးပြုနိုင်ပါတယ်။")
        return
    if not msg.reply_to_message or not msg.reply_to_message.from_user:
        await msg.reply_text("ခွင့်ပြုချက်ပယ်ဖျက်လိုသူရဲ့ စာကို Reply လုပ်ပြီး /unpermission ပို့ပါ။")
        return
    target = msg.reply_to_message.from_user
    with db_connect() as conn:
        conn.execute("DELETE FROM profanity_permissions WHERE user_id=?", (target.id,))
        conn.execute("DELETE FROM profanity_settings WHERE activated_by=?", (target.id,))
        conn.commit()
    await msg.reply_text(f"✅ {target.first_name} ရဲ့ အသုံးပြုခွင့်ကို ပယ်ဖျက်ပြီးပါပြီ။")

async def profanity_moderation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, chat, sender = update.effective_message, update.effective_chat, update.effective_user
    if not msg or not chat or chat.type == "private" or not sender or sender.is_bot:
        return False
    # Only ordinary text messages are checked. Commands, captions, media and edits are excluded.
    text = msg.text or ""
    if not text or text.startswith("/"):
        return False
    if not await group_bot_is_admin(chat, context):
        return False

    # An authorized operator must ALSO be a group admin to activate this group.
    if has_profanity_permission(sender.id) and await _is_group_admin(chat.id, sender.id, context):
        with db_connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO profanity_settings(chat_id,enabled,activated_by) VALUES(?,1,?)",
                (chat.id, sender.id),
            )
            conn.commit()

    with db_connect() as conn:
        enabled = conn.execute(
            "SELECT enabled,activated_by FROM profanity_settings WHERE chat_id=?", (chat.id,)
        ).fetchone()
    if not enabled or not enabled["enabled"]:
        return False
    # Stop automatically if the authorized operator was revoked or is no longer a group admin.
    activator_id = enabled["activated_by"]
    if not activator_id or not has_profanity_permission(activator_id) or not await _is_group_admin(chat.id, activator_id, context):
        with db_connect() as conn:
            conn.execute("DELETE FROM profanity_settings WHERE chat_id=?", (chat.id,))
            conn.commit()
        return False

    # Never automatically punish group admins, the bot owner, or the authorized operator.
    if sender.id == BOT_OWNER_ID or has_profanity_permission(sender.id):
        return False
    if await _is_group_admin(chat.id, sender.id, context):
        return False
    if not contains_profanity(text):
        return False

    try:
        # Delete the offending message first when the bot has the required permission.
        try:
            await msg.delete()
        except Exception:
            logger.warning("Could not delete abusive message chat=%s message=%s", chat.id, msg.message_id)

        from telegram import ChatPermissions
        await context.bot.restrict_chat_member(
            chat_id=chat.id,
            user_id=sender.id,
            permissions=ChatPermissions(can_send_messages=False),
        )
        await context.bot.send_message(
            chat_id=chat.id,
            text=(
                f"🛡️ {sender.first_name} — သင့်စာထဲမှာ စော်ကားဆဲဆိုတဲ့ အသုံးအနှုန်း ပါဝင်နေကြောင်း "
                "စနစ်က တွေ့ရှိခဲ့ပါတယ်။\n\n"
                "📌 အရေးယူမှု — စာကို ဖယ်ရှားပြီး Admin / Owner က /unmute လုပ်ပေးသည်အထိ စာပို့ခွင့် ပိတ်ထားပါတယ်။\n\n"
                "အမြင်မတူတာ၊ စိတ်ဆိုးတာကို ပြောနိုင်ပါတယ်။ ဒါပေမဲ့ လူကိုမစော်ကားဘဲ "
                "ပြဿနာနဲ့ အကြောင်းအရာကိုသာ ပြောဆိုပါ။ စနစ်က စကားလုံးစာရင်းကို အခြေခံတာဖြစ်လို့ "
                "မှားယွင်းဖမ်းမိခဲ့ပါက Group Admin ကို ဆက်သွယ်ပြီး ပြန်လည်စစ်ဆေးခိုင်းနိုင်ပါတယ်။"
            ),
        )
    except Exception:
        logger.exception("Profanity moderation failed chat=%s user=%s", chat.id, sender.id)
        try:
            await context.bot.send_message(
                chat_id=chat.id,
                text="⚠️ ဆဲဆိုမှုဖြစ်နိုင်တဲ့ စာကို တွေ့ရှိခဲ့ပေမဲ့ Mute လုပ်မှု မအောင်မြင်ပါ။ "
                     "Bot Admin ရဲ့ Delete Messages / Restrict Members ခွင့်ကို စစ်ဆေးပါ။",
            )
        except Exception:
            logger.exception("Could not send moderation failure notice chat=%s", chat.id)
    return True

async def reply_roast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Permissioned group admins can request a firm 12-line verbal rebuttal by replying 'ရိုက်'."""
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not msg or not chat or not user or chat.type == "private":
        return False

    trigger = re.sub(r"\s+", "", (msg.text or "").strip())
    if trigger not in ("ရိုက်", "@ရိုက်"):
        return False

    if not msg.reply_to_message or not msg.reply_to_message.from_user:
        await msg.reply_text("ပြင်းပြင်းထန်ထန် တုံ့ပြန်စာရေးစေချင်တဲ့သူရဲ့ စာကို Reply လုပ်ပြီး 'ရိုက်' လို့ပို့ပါ။")
        return True

    if user.id != BOT_OWNER_ID and not has_profanity_permission(user.id):
        await msg.reply_text("⛔ ဒီစနစ်ကို အသုံးပြုခွင့်မရှိသေးပါ။ Bot ပိုင်ရှင်ထံမှ /permission ခွင့်ပြုချက်ရယူပါ။")
        return True
    if not await _is_group_admin(chat.id, user.id, context):
        await msg.reply_text("⛔ ဒီ Group ရဲ့ Admin ဖြစ်သူသာ အသုံးပြုနိုင်ပါတယ်။")
        return True
    if not await group_bot_is_admin(chat, context):
        await msg.reply_text("⚠️ Bot ကို ဒီ Group မှာ Admin ခန့်ပေးပါ။")
        return True

    target_msg = msg.reply_to_message
    target = target_msg.from_user
    if target.is_bot:
        await msg.reply_text("Bot အကောင့်ကို ပစ်မှတ်ထားတဲ့ တုံ့ပြန်စာ မရေးပေးပါဘူး။")
        return True
    if target.id == user.id:
        await msg.reply_text("ကိုယ့်စာကိုယ် Reply လုပ်ထားတာဖြစ်လို့ တခြားသူကို ရည်ညွှန်းတဲ့ တုံ့ပြန်စာ မရေးနိုင်ပါဘူး။")
        return True

    name = (target.first_name or "မိတ်ဆွေ").replace("\n", " ")[:40]
    quoted = (target_msg.text or target_msg.caption or "").strip()
    quoted = re.sub(r"\s+", " ", quoted)[:100]
    if quoted:
        opening = f"မင်းရေးထားတဲ့စာက — ‘{quoted}’ ပါ။ ဒီလိုပြောဆိုပုံကို အောက်ပါအတိုင်း ပြန်တုံ့ပြန်နိုင်တယ်။"
    else:
        opening = "မင်းရဲ့အပြောအဆိုကို အကြောင်းအရာအပေါ် အခြေခံပြီး တိုက်ရိုက်တုံ့ပြန်မယ်။"

    lines = [
        f"{name} ရေ၊ မင်းရဲ့အပြောအဆိုကို ဒီတစ်ခါတော့ ပြတ်ပြတ်သားသား ပြန်ပြောမယ်။",
        opening,
        "အကြောင်းပြချက်မရှိဘဲ စော်ကားတာက မင်းဘက်က အနိုင်ရတာ မဟုတ်ဘူး။",
        "ပြောစရာအချက်မရှိလို့ အသံကျယ်ကျယ်နဲ့ ဖုံးကွယ်နေတာလား။",
        "စကားတစ်ခွန်းပြောတိုင်း ကိုယ့်အဆင့်အတန်းကို ကိုယ်တိုင်ဖော်ပြနေတယ်။",
        "တစ်ဖက်လူကို လေးစားမှုမပေးနိုင်ရင် အနည်းဆုံး ကိုယ့်စကားကိုယ် တာဝန်ယူပါ။",
        "မင်းရဲ့စကားမှာ အချက်အလက်ထက် စော်ကားချင်စိတ်က ပိုများနေတယ်။",
        "အမြင်မတူတာကို ဆွေးနွေးလို့ရတယ်၊ လူကိုပစ်မှတ်ထားပြီး စော်ကားတာကတော့ အဖြေမဟုတ်ဘူး။",
        "ကိုယ့်စကားကို ပြန်ဖတ်ကြည့်ပါ—အဲဒီစကားက မင်းကိုပဲ ပိုပြီးဖော်ပြနေတယ်။",
        "တကယ်ပြောနိုင်စွမ်းရှိရင် အကြောင်းအရာနဲ့ သက်သေပြပါ၊ အဆဲနဲ့ မဖုံးပါနဲ့။",
        "ဒီလိုအပြောအဆိုမျိုးနဲ့ ဆက်သွားရင် ဆွေးနွေးမှုကို မင်းကိုယ်တိုင် အဓိပ္ပာယ်မဲ့အောင် လုပ်နေတာပဲ။",
        "နောက်တစ်ခါ ပြန်ပြောမယ်ဆိုရင် စော်ကားစကားမဟုတ်ဘဲ အချက်အလက်နဲ့ ပြောပါ။ ဒီလောက်ပါပဲ။",
    ]
    await msg.reply_text("\n".join(lines), reply_to_message_id=target_msg.message_id)
    return True


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user and update.effective_chat and update.effective_message and update.effective_message.text:
        ck_record_activity(update.effective_user, update.effective_chat.id)
    # Group conversations stay quiet: never reply to ordinary messages just because
    # the bot lacks admin rights. Group-only moderation runs only when permissions allow.
    if not update.message or not update.message.text:
        return
    if await reply_roast_command(update, context):
        return
    if await profanity_moderation(update, context):
        return
    raw_text = update.message.text.strip()
    text = raw_text.lower()
    pending_tool = context.user_data.pop("tool_waiting_key", None)
    if pending_tool:
        try:
            result=str(_tool_run(pending_tool, raw_text))
            if len(result)>3900: result=result[:3900]+"\n… (စာသားရှည်လွန်း၍ ဖြတ်ထားသည်)"
            await update.message.reply_text("🧰 ရလဒ်\n"+result)
        except Exception as exc:
            logger.info("Tool %s input rejected: %s",pending_tool,exc)
            await update.message.reply_text("⚠️ ထည့်သွင်းမှုကို စစ်ဆေးပါ။\n"+str(exc)[:500])
        return
    if update.effective_chat.type == "private":
        tiktok_url = extract_tiktok_url(raw_text)
        if tiktok_url:
            await download_tiktok_video(update.message, tiktok_url)
            return
    if update.effective_chat.type != "private":
        if await random_chat_relay(update, context):
            return
        return
    if await random_chat_relay(update, context):
        return
    if await mlbbi_check_guess(update, raw_text):
        return
    mlbb_mode = context.user_data.pop("mlbb_waiting_hero", None)
    if mlbb_mode:
        await mlbb_hero_guide(update, context, raw_text, mlbb_mode)
        return
    life50_pending=context.user_data.pop("life50_pending",None)
    if life50_pending:
        if not raw_text:
            await update.message.reply_text("စာသားအလွတ် မသိမ်းနိုင်ပါ။ ပြန်ပို့ပေးပါ။")
            context.user_data["life50_pending"] = life50_pending
            return
        with db_connect() as conn:
            conn.execute("INSERT INTO life50_entries(user_id,tool_id,entry,created_at) VALUES(?,?,?,?)",(update.effective_user.id,int(life50_pending),raw_text[:3000],int(time.time())))
            conn.commit()
        tool=next((x for x in LIFE50_ITEMS if x[0]==int(life50_pending)),None)
        await update.message.reply_text(f"✅ {tool[1] if tool else 'မှတ်တမ်း'} ကို သိမ်းဆည်းပြီးပါပြီ။",reply_markup=life50_keyboard((int(life50_pending)-1)//10))
        return
    creative_prompt = context.user_data.pop("creative_prompt", None)
    if creative_prompt:
        with db_connect() as conn:
            conn.execute("INSERT INTO creative_entries(user_id,username,prompt,entry,created_at) VALUES(?,?,?,?,?)",
                         (update.effective_user.id, update.effective_user.first_name or str(update.effective_user.id), creative_prompt, raw_text[:2000], int(time.time())))
        await update.message.reply_text("🎨 သင့်ဖန်တီးမှုကို သိမ်းဆည်းပြီးပါပြီ။ မျှဝေပေးတဲ့အတွက် ကျေးဇူးပါ!", reply_markup=life_menu())
        return
    word_answer = context.user_data.pop("mini_word_answer", None)
    if word_answer is not None:
        if raw_text.strip() == word_answer:
            await update.message.reply_text("🎉 အဖြေမှန်ပါတယ်! Word Puzzle အနိုင်ရပါပြီ။", reply_markup=games_menu_keyboard(update.effective_chat.type))
        else:
            await update.message.reply_text(f"❌ မမှန်ပါ။ အဖြေမှန်က '{word_answer}' ဖြစ်ပါတယ်။", reply_markup=games_menu_keyboard(update.effective_chat.type))
        return
    # Fortune mode is isolated by chat: private chat, each group, and each supergroup
    # keep their own selection instead of overwriting one another.
    fortune_modes = context.user_data.get("fortune_modes", {})
    current_mode = fortune_modes.get(str(update.effective_chat.id), "zodiac")
    chat_label = "Group ဟောကိန်း" if update.effective_chat.type != "private" else "Private ဟောကိန်း"
    matched_key = next(
        (key for key in ZODIAC_NAMES
         if re.search(r"(?<![a-z])" + re.escape(key) + r"(?![a-z])", text)),
        None,
    )
    if not matched_key:
        return
    zodiac_title = ZODIAC_NAMES[matched_key]
    if current_mode == "tomorrow":
        response = (
            f"📅 **{chat_label} — မနက်ဖြန်အတွက် ဟောကိန်းအထူး**\n━━━━━━━━━━━━━━━━━━━\n"
            f"✨ **ရာသီခွင်:** {zodiac_title}\n\n"
            f"🌟 **ဖြစ်ပျက်မည့်အခြေအနေ:**\n{random.choice(TOMORROW_EVENTS)}\n\n"
            f"⚠️ **သတိပြုရှောင်ရှားရမည့်အချက်:**\n{random.choice(TOMORROW_AVOIDS)}"
        )
    else:
        response = (
            f"🔮 **{chat_label} — ရာသီခွင် အသေးစိတ်ဟောကိန်း**\n━━━━━━━━━━━━━━━━━━━\n"
            f"✨ **ရာသီခွင်:** {zodiac_title}\n\n"
            f"🧠 **စိတ်နေစိတ်ထား:**\n{random.choice(TRAITS_POOL)}\n\n"
            f"❤️ **အချစ်ရေး:**\n{random.choice(LOVE_POOL)}\n\n"
            f"💼 **လုပ်ငန်းခွင်နှင့် စီးပွားရေး:**\n{random.choice(CAREER_POOL)}"
        )
    keyboard = [
        [InlineKeyboardButton("🔄 အခြားတစ်ခု ထပ်မံမေးမည်", callback_data="menu_start")],
        [InlineKeyboardButton("🏠 ပင်မမီနူးသို့", callback_data="menu_start")],
    ]
    await update.message.reply_text(
        response, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard),
        reply_to_message_id=update.message.message_id if update.effective_chat.type != "private" else None,
    )



async def group_horoscope_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, chat = update.effective_message, update.effective_chat
    if not msg or not chat or chat.type == "private":
        return
    if not await require_group_bot_admin(update, context):
        return
    key = (msg.text or "").split()[0].split("@", 1)[0].lstrip("/").lower()
    if key not in ZODIAC_NAMES:
        return
    response = (
        f"🔮 **Group ဟောကိန်း — {ZODIAC_NAMES[key]}**\n━━━━━━━━━━━━━━━━━━━\n"
        f"🧠 **စိတ်နေစိတ်ထား:**\n{random.choice(TRAITS_POOL)}\n\n"
        f"❤️ **အချစ်ရေး:**\n{random.choice(LOVE_POOL)}\n\n"
        f"💼 **လုပ်ငန်းခွင်နှင့် စီးပွားရေး:**\n{random.choice(CAREER_POOL)}\n\n"
        "ဖျော်ဖြေရေးသဘောဖြင့်သာ ယူဆပါ။"
    )
    await msg.reply_text(response, parse_mode="Markdown", reply_to_message_id=msg.message_id)


async def group_tomorrow_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, chat = update.effective_message, update.effective_chat
    if not msg or not chat or chat.type == "private":
        return
    if not await require_group_bot_admin(update, context):
        return
    key = context.args[0].lower() if context.args else ""
    if key not in ZODIAC_NAMES:
        await msg.reply_text("အသုံးပြုပုံ — /tomorrow aries")
        return
    response = (
        f"📅 **Group ဟောကိန်း — {ZODIAC_NAMES[key]} (မနက်ဖြန်)**\n"
        f"🌟 **ဖြစ်ပျက်နိုင်သည့်အခြေအနေ:**\n{random.choice(TOMORROW_EVENTS)}\n\n"
        f"⚠️ **သတိပြုရန်:**\n{random.choice(TOMORROW_AVOIDS)}"
    )
    await msg.reply_text(response, parse_mode="Markdown", reply_to_message_id=msg.message_id)


async def group_tarot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, chat = update.effective_message, update.effective_chat
    if not msg or not chat or chat.type == "private":
        return
    if not await require_group_bot_admin(update, context):
        return
    cards = random.sample(TAROT_DECK, k=min(3, len(TAROT_DECK)))
    body = "🃏 **Group တားရော့ — ၃ ကတ်**\n━━━━━━━━━━━━━━━━━━━\n"
    body += "\n\n".join(f"**{i}. {c['name']}**\n{c['vibe']}" for i, c in enumerate(cards, 1))
    body += "\n\nဖျော်ဖြေရေးသဘောဖြင့်သာ ယူဆပါ။"
    await msg.reply_text(body, parse_mode="Markdown", reply_to_message_id=msg.message_id)


TIKTOK_URL_RE = re.compile(
    r"https?://(?:(?:www|m|vm|vt)\.)?tiktok\.com/[^\s<>]+",
    re.IGNORECASE,
)


def extract_tiktok_url(text):
    """Extract a TikTok URL and remove common trailing punctuation."""
    match = TIKTOK_URL_RE.search(text or "")
    if not match:
        return None
    return match.group(0).rstrip(".,!?;:)]}>")


async def _download_tiktok_video_file(url, tmp):
    """Try yt-dlp first. Return a video path, or None for photo-only posts."""
    import yt_dlp

    options = {
        "outtmpl": os.path.join(tmp, "video.%(ext)s"),
        "format": "best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "max_filesize": 49 * 1024 * 1024,
        "socket_timeout": 30,
        "retries": 2,
    }

    def download():
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.extract_info(url, download=True)

    await asyncio.to_thread(download)
    video_exts = {".mp4", ".m4v", ".mov", ".webm", ".mkv"}
    candidates = []
    for root, _, files in os.walk(tmp):
        for name in files:
            path = os.path.join(root, name)
            if os.path.splitext(name)[1].lower() in video_exts:
                candidates.append(path)
    if not candidates:
        return None
    return max(candidates, key=os.path.getsize)


async def _download_tiktok_photos(url, tmp):
    """Use gallery-dl for TikTok photo/slideshow posts."""
    cmd = [sys.executable, "-m", "gallery_dl", "-D", tmp, url]

    def download():
        return subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, timeout=180, check=False,
        )

    result = await asyncio.to_thread(download)
    image_exts = {".jpg", ".jpeg", ".png", ".webp"}
    images = []
    for root, _, files in os.walk(tmp):
        for name in files:
            path = os.path.join(root, name)
            if os.path.splitext(name)[1].lower() in image_exts:
                images.append(path)
    images.sort()
    if not images:
        detail = (result.stderr or result.stdout or "No images returned")[-1200:]
        raise RuntimeError(f"gallery-dl could not retrieve TikTok photos: {detail}")
    return images


async def download_tiktok_video(msg, url):
    """Automatically send TikTok video as video, or photo posts as photos."""
    status = await msg.reply_text("⏳ TikTok Link ကို စစ်ဆေးပြီး မီဒီယာရယူနေပါတယ်…")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            video_path = None
            video_error = None
            try:
                video_path = await _download_tiktok_video_file(url, tmp)
            except ImportError:
                raise
            except Exception as exc:
                # Photo posts commonly fail in yt-dlp; try the photo extractor next.
                video_error = exc
                logger.info("TikTok video extraction did not return a video; trying photos: %s", exc)

            if video_path:
                if os.path.getsize(video_path) > 49 * 1024 * 1024:
                    raise RuntimeError("Video exceeds Telegram upload limit")
                with open(video_path, "rb") as video:
                    await msg.reply_video(
                        video=video,
                        caption="✅ TikTok Video ရရှိပါပြီ။\nWatermark မပါ/ပါ အခြေအနေသည် မူရင်းရင်းမြစ်မှ ရရှိသောဖိုင်ပေါ် မူတည်ပါတယ်။",
                    )
                await status.delete()
                return

            # No video stream: treat the post as a photo/slideshow.
            images = await _download_tiktok_photos(url, tmp)
            sent_any = False
            for offset in range(0, len(images), 10):
                batch = images[offset:offset + 10]
                media = []
                opened = []
                try:
                    for index, path in enumerate(batch):
                        if os.path.getsize(path) > 10 * 1024 * 1024:
                            logger.warning("Skipping oversized TikTok image: %s", path)
                            continue
                        fh = open(path, "rb")
                        opened.append(fh)
                        from telegram import InputMediaPhoto
                        media.append(InputMediaPhoto(
                            media=fh,
                            caption="✅ TikTok Photo ရရှိပါပြီ။" if not sent_any and not media else None,
                        ))
                    if not media:
                        continue
                    if len(media) == 1:
                        await msg.reply_photo(photo=media[0].media, caption="✅ TikTok Photo ရရှိပါပြီ။")
                    else:
                        await msg.reply_media_group(media=media)
                    sent_any = True
                finally:
                    for fh in opened:
                        fh.close()
            if not sent_any:
                raise RuntimeError("No Telegram-compatible photo files found")
        await status.delete()
    except ImportError as exc:
        missing = "gallery-dl" if "gallery_dl" in str(exc) else "yt-dlp"
        await status.edit_text(
            f"⚠️ {missing} မတပ်ဆင်ရသေးပါ။ requirements.txt ထဲတွင် ထည့်ပြီး Railway ကို Redeploy လုပ်ပါ။"
        )
    except Exception:
        logger.exception("TikTok media download failed")
        await status.edit_text(
            "⚠️ ဒီ TikTok Link မှ Video/Photo ကို ရယူမရပါ။ Public Link ဖြစ်/မဖြစ်၊ "
            "Railway Logs နဲ့ package version များကို စစ်ဆေးပါ။"
        )


async def tiktok_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, chat = update.effective_message, update.effective_chat
    if not msg:
        return
    url = extract_tiktok_url(" ".join(context.args))
    if not url:
        await msg.reply_text("အသုံးပြုပုံ — /tiktok https://vt.tiktok.com/...")
        return
    if chat.type != "private" and not await require_group_bot_admin(update, context):
        return
    await download_tiktok_video(msg, url)


async def telegram_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Unhandled Telegram update error", exc_info=context.error)


async def mlbb_image_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    await mlbbi_start(update.message)


async def life50_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text("🌍 Life & Community Center — စနစ် ၅၀",reply_markup=life50_keyboard(0))




# ------------------------- AUTOMATED LIFE TOOLS -------------------------
MYANMAR_TZ = ZoneInfo("Asia/Yangon")


def _safe_float(value):
    try:
        amount = float(value.replace(",", ""))
        if not math.isfinite(amount) or amount <= 0 or amount > 1_000_000_000_000:
            return None
        return amount
    except (TypeError, ValueError):
        return None


def _money(value):
    return f"{value:,.0f}" if float(value).is_integer() else f"{value:,.2f}"


async def reminder_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ /remind HH:MM message (daily) OR /remind YYYY-MM-DD HH:MM message """
    msg = update.effective_message
    if not msg:
        return
    args = context.args or []
    if len(args) < 2:
        await msg.reply_text(
            "⏰ Reminder အသုံးပြုပုံ\n"
            "နေ့စဉ်: `/remind 08:30 မနက်စာစားရန်`\n"
            "တစ်ကြိမ်: `/remind 2026-11-05 18:30 အစည်းအဝေး`\n"
            "စာရင်း: `/reminders`\n"
            "ဖျက်ရန်: `/delreminder ID`\n\n"
            "အချိန်ကို Myanmar Time (UTC+6:30) ဖြင့် သတ်မှတ်ပါ။",
            parse_mode="Markdown")
        return
    now = datetime.now(MYANMAR_TZ)
    repeat_daily = False
    try:
        if re.fullmatch(r"\d{2}:\d{2}", args[0]):
            hour, minute = map(int, args[0].split(":"))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError
            due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if due <= now:
                due += timedelta(days=1)
            repeat_daily = True
            reminder_text = " ".join(args[1:]).strip()
        elif len(args) >= 3:
            due = datetime.strptime(args[0] + " " + args[1], "%Y-%m-%d %H:%M").replace(tzinfo=MYANMAR_TZ)
            reminder_text = " ".join(args[2:]).strip()
            if due <= now:
                await msg.reply_text("အတိတ်အချိန်ကို Reminder မသတ်မှတ်နိုင်ပါ။")
                return
        else:
            raise ValueError
        if not reminder_text:
            raise ValueError
    except ValueError:
        await msg.reply_text("ရက်စွဲ/အချိန် မမှန်ပါ။ `/remind 08:30 အလုပ်သွားရန်` ပုံစံနဲ့ ပြန်ပို့ပါ။", parse_mode="Markdown")
        return
    with db_connect() as conn:
        cur = conn.execute(
            "INSERT INTO user_reminders(user_id,chat_id,remind_at,message,repeat_daily,status,created_at) VALUES(?,?,?,?,?,'active',?)",
            (update.effective_user.id, update.effective_chat.id, int(due.timestamp()),
             reminder_text[:500], int(repeat_daily), int(time.time())))
        reminder_id = cur.lastrowid
        conn.commit()
    label = "နေ့စဉ်" if repeat_daily else "တစ်ကြိမ်"
    await msg.reply_text(f"✅ Reminder #{reminder_id} သတ်မှတ်ပြီးပါပြီ။\n⏰ {due.strftime('%Y-%m-%d %H:%M')} (မြန်မာစံတော်ချိန်)\n🔁 {label}\n📝 {reminder_text[:300]}")


async def reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with db_connect() as conn:
        rows = conn.execute("SELECT id,remind_at,message,repeat_daily FROM user_reminders WHERE user_id=? AND status='active' ORDER BY remind_at LIMIT 30",
                            (update.effective_user.id,)).fetchall()
    if not rows:
        await update.effective_message.reply_text("📭 လက်ရှိ Reminder မရှိသေးပါ။ `/remind` ဖြင့် ထည့်နိုင်ပါတယ်။")
        return
    lines = ["⏰ **သင့် Reminder စာရင်း**"]
    for row in rows:
        dt = datetime.fromtimestamp(row["remind_at"], MYANMAR_TZ)
        lines.append(f"#{row['id']} · {dt:%Y-%m-%d %H:%M} · {'နေ့စဉ်' if row['repeat_daily'] else 'တစ်ကြိမ်'}\n{row['message'][:120]}")
    await update.effective_message.reply_text("\n\n".join(lines), parse_mode="Markdown")


async def delete_reminder_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].isdigit():
        await update.effective_message.reply_text("ဖျက်ရန် `/delreminder ID` ဥပမာ `/delreminder 3`", parse_mode="Markdown")
        return
    with db_connect() as conn:
        cur = conn.execute("UPDATE user_reminders SET status='cancelled' WHERE id=? AND user_id=? AND status='active'",
                           (int(context.args[0]), update.effective_user.id))
        conn.commit()
    await update.effective_message.reply_text("🗑️ Reminder ဖျက်ပြီးပါပြီ။" if cur.rowcount else "အဲဒီ ID နဲ့ အသက်ဝင်နေတဲ့ Reminder မတွေ့ပါ။")


async def reminder_scheduler(app):
    """Persistent DB-backed scheduler; survives process restarts."""
    while True:
        now_ts = int(time.time())
        due_rows = []
        try:
            with db_connect() as conn:
                due_rows = conn.execute(
                    "SELECT * FROM user_reminders WHERE status='active' AND remind_at<=? ORDER BY remind_at LIMIT 100",
                    (now_ts,)).fetchall()
                for row in due_rows:
                    if row["repeat_daily"]:
                        next_at = row["remind_at"] + 86400
                        while next_at <= now_ts:
                            next_at += 86400
                        conn.execute("UPDATE user_reminders SET remind_at=? WHERE id=?", (next_at, row["id"]))
                    else:
                        conn.execute("UPDATE user_reminders SET status='sent' WHERE id=?", (row["id"],))
                conn.commit()
            for row in due_rows:
                try:
                    await app.bot.send_message(
                        chat_id=row["chat_id"],
                        text=f"⏰ သတိပေးချက်\n\n{row['message']}")
                except Exception:
                    logger.exception("Reminder delivery failed id=%s", row["id"])
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Reminder scheduler cycle failed")
        await asyncio.sleep(20)


async def expense_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ /expense 2500 အစားအသောက် မုန့်ဝယ် """
    args = context.args or []
    if len(args) < 2:
        await update.effective_message.reply_text(
            "💰 အသုံးစရိတ်မှတ်တမ်း\n"
            "`/expense 2500 အစားအသောက် မုန့်ဝယ်`\n"
            "`/expenses` — ယခုလစာရင်း\n"
            "`/expenses all` — စုစုပေါင်းစာရင်း\n"
            "`/budget 150000` — လစဉ်ဘတ်ဂျက်သတ်မှတ်\n"
            "`/budgetstatus` — ဘတ်ဂျက်အခြေအနေ",
            parse_mode="Markdown")
        return
    amount = _safe_float(args[0])
    if amount is None:
        await update.effective_message.reply_text("ငွေပမာဏ မှန်ကန်စွာထည့်ပါ။ ဥပမာ `/expense 2500 အစားအသောက်`", parse_mode="Markdown")
        return
    category = args[1][:60]
    note = " ".join(args[2:])[:250]
    with db_connect() as conn:
        conn.execute("INSERT INTO user_expenses(user_id,amount,category,note,created_at) VALUES(?,?,?,?,?)",
                     (update.effective_user.id, amount, category, note, int(time.time())))
        conn.commit()
    await update.effective_message.reply_text(f"✅ အသုံးစရိတ် သိမ်းပြီးပါပြီ။\n💸 {_money(amount)} ကျပ်\n🏷️ {category}\n📝 {note or 'မှတ်ချက်မရှိ'}")


async def expenses_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if context.args and context.args[0].lower() == "all":
        start_ts = 0
        heading = "စုစုပေါင်း"
    else:
        now = datetime.now(MYANMAR_TZ)
        start_ts = int(now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp())
        heading = now.strftime("%Y-%m")
    with db_connect() as conn:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS total, COUNT(*) AS n FROM user_expenses WHERE user_id=? AND created_at>=? GROUP BY category ORDER BY total DESC",
            (user_id, start_ts)).fetchall()
        total = conn.execute("SELECT COALESCE(SUM(amount),0) FROM user_expenses WHERE user_id=? AND created_at>=?",
                             (user_id, start_ts)).fetchone()[0]
        recent = conn.execute("SELECT id,amount,category,note,created_at FROM user_expenses WHERE user_id=? AND created_at>=? ORDER BY created_at DESC LIMIT 8",
                              (user_id, start_ts)).fetchall()
    if not rows:
        await update.effective_message.reply_text(f"📭 {heading} အတွက် အသုံးစရိတ်မရှိသေးပါ။")
        return
    lines = [f"💰 **အသုံးစရိတ်အစီရင်ခံစာ — {heading}**", f"စုစုပေါင်း: **{_money(total)} ကျပ်**", "", "အမျိုးအစားအလိုက်:"]
    lines += [f"• {r['category']}: {_money(r['total'])} ကျပ် ({r['n']} ကြိမ်)" for r in rows]
    lines += ["", "နောက်ဆုံးမှတ်တမ်းများ:"]
    lines += [f"#{r['id']} · {_money(r['amount'])} ကျပ် · {r['category']} · {datetime.fromtimestamp(r['created_at'], MYANMAR_TZ):%m-%d}" for r in recent]
    await update.effective_message.reply_text("\n".join(lines), parse_mode="Markdown")


async def budget_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.effective_message.reply_text("လစဉ်ဘတ်ဂျက်သတ်မှတ်ရန် `/budget 150000`", parse_mode="Markdown")
        return
    amount = _safe_float(context.args[0])
    if amount is None:
        await update.effective_message.reply_text("ဘတ်ဂျက်ပမာဏ မှန်ကန်စွာထည့်ပါ။")
        return
    with db_connect() as conn:
        conn.execute("INSERT INTO user_budgets(user_id,monthly_limit,updated_at) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET monthly_limit=excluded.monthly_limit,updated_at=excluded.updated_at",
                     (update.effective_user.id, amount, int(time.time())))
        conn.commit()
    await update.effective_message.reply_text(f"✅ လစဉ်ဘတ်ဂျက်ကို {_money(amount)} ကျပ် သတ်မှတ်ပြီးပါပြီ။")


async def budget_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    now = datetime.now(MYANMAR_TZ)
    start_ts = int(now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp())
    with db_connect() as conn:
        budget = conn.execute("SELECT monthly_limit FROM user_budgets WHERE user_id=?", (uid,)).fetchone()
        spent = conn.execute("SELECT COALESCE(SUM(amount),0) FROM user_expenses WHERE user_id=? AND created_at>=?", (uid, start_ts)).fetchone()[0]
    if not budget:
        await update.effective_message.reply_text("ဘတ်ဂျက် မသတ်မှတ်ရသေးပါ။ `/budget 150000` ကို အသုံးပြုပါ။", parse_mode="Markdown")
        return
    limit = float(budget["monthly_limit"])
    remaining = limit - spent
    percent = spent / limit * 100 if limit else 0
    status = "⚠️ ဘတ်ဂျက်ကျော်လွန်နေပါပြီ။" if remaining < 0 else "✅ ဘတ်ဂျက်အတွင်း ရှိနေပါတယ်။"
    await update.effective_message.reply_text(
        f"📊 **လစဉ်ဘတ်ဂျက်အခြေအနေ**\nသတ်မှတ်ငွေ: {_money(limit)} ကျပ်\nသုံးပြီး: {_money(spent)} ကျပ်\nကျန်ငွေ: {_money(remaining)} ကျပ်\nအသုံးပြုမှု: {percent:.1f}%\n{status}",
        parse_mode="Markdown")


# ------------------------- OPT-IN ANONYMOUS RANDOM CHAT -------------------------
async def chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        await update.effective_message.reply_text("🔒 Random Chat ကို Bot Private Chat ထဲမှာပဲ စတင်နိုင်ပါတယ်။")
        return
    uid = update.effective_user.id
    with db_connect() as conn:
        existing = conn.execute("SELECT partner_id FROM random_chat_pairs WHERE user_id=?", (uid,)).fetchone()
        if existing:
            await update.effective_message.reply_text("သင်က Chat တစ်ခုထဲမှာ ရှိနေပါပြီ။ /stop ဖြင့် ရပ်နိုင်ပါတယ်။")
            return
        # Remove stale self-queue row and find an eligible waiting partner.
        conn.execute("DELETE FROM random_chat_queue WHERE queued_at<?", (int(time.time()) - 600,))
        conn.execute("DELETE FROM random_chat_queue WHERE user_id=?", (uid,))
        candidates = conn.execute(
            """SELECT q.user_id,q.chat_id,q.display_name FROM random_chat_queue q
               WHERE q.user_id<>? AND NOT EXISTS (
                 SELECT 1 FROM random_chat_blocks b WHERE b.user_id=? AND b.blocked_id=q.user_id
               ) AND NOT EXISTS (
                 SELECT 1 FROM random_chat_blocks b WHERE b.user_id=q.user_id AND b.blocked_id=?
               ) ORDER BY q.queued_at LIMIT 1""", (uid, uid, uid)).fetchone()
        if candidates:
            partner_id = candidates["user_id"]
            now_ts = int(time.time())
            conn.execute("DELETE FROM random_chat_queue WHERE user_id IN (?,?)", (uid, partner_id))
            conn.execute("INSERT OR REPLACE INTO random_chat_pairs(user_id,partner_id,created_at) VALUES(?,?,?)",
                         (uid, partner_id, now_ts))
            conn.execute("INSERT OR REPLACE INTO random_chat_pairs(user_id,partner_id,created_at) VALUES(?,?,?)",
                         (partner_id, uid, now_ts))
            conn.commit()
        else:
            conn.execute("INSERT OR REPLACE INTO random_chat_queue(user_id,chat_id,display_name,queued_at) VALUES(?,?,?,?)",
                         (uid, update.effective_chat.id, update.effective_user.first_name[:80], int(time.time())))
            conn.commit()
            partner_id = None
    if partner_id:
        await update.effective_message.reply_text("🎉 မိတ်ဆွေတစ်ယောက်နဲ့ ချိတ်ဆက်ပြီးပါပြီ။ စာပို့နိုင်ပါပြီ။\nရပ်ရန် /stop · နောက်တစ်ယောက် /next")
        try:
            await context.bot.send_message(partner_id, "🎉 မိတ်ဆွေတစ်ယောက်နဲ့ ချိတ်ဆက်ပြီးပါပြီ။ စာပို့နိုင်ပါပြီ။\nရပ်ရန် /stop · နောက်တစ်ယောက် /next")
        except Exception:
            logger.exception("Could not notify random chat partner")
    else:
        await update.effective_message.reply_text("🔎 မိတ်ဆွေရှာနေပါတယ်။ တွေ့တာနဲ့ အလိုအလျောက် ချိတ်ဆက်ပေးပါမယ်။\nရပ်ရန် /stop")


async def stop_chat(update: Update, context: ContextTypes.DEFAULT_TYPE, notify=True):
    uid = update.effective_user.id
    with db_connect() as conn:
        pair = conn.execute("SELECT partner_id FROM random_chat_pairs WHERE user_id=?", (uid,)).fetchone()
        conn.execute("DELETE FROM random_chat_queue WHERE user_id=?", (uid,))
        conn.execute("DELETE FROM random_chat_pairs WHERE user_id=?", (uid,))
        if pair:
            conn.execute("DELETE FROM random_chat_pairs WHERE user_id=?", (pair["partner_id"],))
        conn.commit()
    if pair and notify:
        try:
            await context.bot.send_message(pair["partner_id"], "ℹ️ တစ်ဖက်မိတ်ဆွေက စကားပြောခြင်းကို ရပ်လိုက်ပါပြီ။ /chat ဖြင့် မိတ်ဆွေအသစ်ရှာနိုင်ပါတယ်။")
        except Exception:
            pass
    await update.effective_message.reply_text("🛑 Random Chat ရပ်လိုက်ပါပြီ။" if pair else "🔎 ရှာဖွေမှုကို ရပ်လိုက်ပါပြီ။")


async def next_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await stop_chat(update, context, notify=True)
    await chat_command(update, context)


async def report_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    with db_connect() as conn:
        pair = conn.execute("SELECT partner_id FROM random_chat_pairs WHERE user_id=?", (uid,)).fetchone()
        if not pair:
            await update.effective_message.reply_text("Report လုပ်ရန် Chat Partner မရှိပါ။")
            return
        partner = pair["partner_id"]
        conn.execute("INSERT OR IGNORE INTO random_chat_blocks(user_id,blocked_id,created_at) VALUES(?,?,?)",
                     (uid, partner, int(time.time())))
        conn.execute("DELETE FROM random_chat_pairs WHERE user_id IN (?,?)", (uid, partner))
        conn.commit()
    await update.effective_message.reply_text("🚩 Report/Block လုပ်ပြီး Chat ကို ရပ်လိုက်ပါပြီ။")
    try:
        await context.bot.send_message(partner, "ℹ️ ဒီ Chat ကို အဆုံးသတ်လိုက်ပါပြီ။")
    except Exception:
        pass


async def random_chat_relay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Relay private text messages without exposing Telegram IDs/usernames."""
    msg = update.effective_message
    if not msg or update.effective_chat.type != "private" or not update.effective_user:
        return False
    uid = update.effective_user.id
    with db_connect() as conn:
        pair = conn.execute("SELECT partner_id FROM random_chat_pairs WHERE user_id=?", (uid,)).fetchone()
    if not pair:
        return False
    try:
        await context.bot.send_message(pair["partner_id"], f"💬 {msg.text[:3500]}")
    except Exception:
        logger.exception("Random chat relay failed for user=%s", uid)
        await msg.reply_text("⚠️ တစ်ဖက်သူထံ စာပို့မရပါ။ /next ဖြင့် ပြန်ချိတ်ဆက်ပါ။")
    return True



async def random_chat_media_relay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or update.effective_chat.type != "private" or not update.effective_user:
        return
    with db_connect() as conn:
        pair = conn.execute("SELECT partner_id FROM random_chat_pairs WHERE user_id=?",
                            (update.effective_user.id,)).fetchone()
    if not pair:
        return
    try:
        await context.bot.copy_message(
            chat_id=pair["partner_id"],
            from_chat_id=update.effective_chat.id,
            message_id=msg.message_id)
    except Exception:
        logger.exception("Random chat media relay failed for user=%s", update.effective_user.id)
        await msg.reply_text("⚠️ ဒီဖိုင်/မီဒီယာကို ပို့မရပါ။ စာသားနဲ့ ပြန်ပို့ကြည့်ပါ။")



# ------------------------- GROUP / CHANNEL SET COMMANDS -------------------------
CHANNEL_MODULE_TITLES = [
    "Post စီမံခန့်ခွဲမှု", "Auto Pin", "Post အချိန်ဇယား", "Welcome & Intro", "Announcement",
    "Link စစ်ဆေးမှု", "Forward ထိန်းချုပ်မှု", "Media စီမံမှု", "Caption စစ်ဆေးမှု", "Hashtag စနစ်",
    "Mention စနစ်", "Comment စီမံမှု", "Reaction စနစ်", "Poll စနစ်", "Quiz စနစ်",
    "File စီမံမှု", "Photo စီမံမှု", "Video စီမံမှု", "Audio စီမံမှု", "Document စီမံမှု",
    "Admin မှတ်တမ်း", "Post စာရင်း", "အကြောင်းကြားချက်", "အချိန်ကန့်သတ်မှု", "Content စစ်ဆေးမှု",
    "Spam ကာကွယ်မှု", "Scam သတိပေးမှု", "Privacy စနစ်", "Backup စာရင်း", "Report စနစ်",
    "Member ချိတ်ဆက်မှု", "Discussion ချိတ်ဆက်မှု", "Channel အချက်အလက်", "Description စီမံမှု", "Invite စနစ်",
    "Statistics", "အကြံပြုချက်", "Event ကြေညာမှု", "FAQ စနစ်", "အကူအညီစနစ်",
    "အရေးပေါ်ကြေညာချက်", "စီမံခန့်ခွဲသူတာဝန်", "ပူးပေါင်း Channel", "အကြောင်းအရာစုစည်းမှု", "Archive စနစ်",
    "Post Template", "Language စနစ်", "Schedule သတိပေးမှု", "Audit စနစ်", "အထွေထွေ Setting",
]
CHANNEL_CONTROL_NAMES = [
    "Link စစ်ဆေးရန်", "Invite Link စစ်ရန်", "Forward Post စစ်ရန်", "Photo Post စစ်ရန်",
    "Video Post စစ်ရန်", "Audio Post စစ်ရန်", "Voice Post စစ်ရန်", "Document စစ်ရန်",
    "Sticker စစ်ရန်", "Animation စစ်ရန်", "Contact စစ်ရန်", "Location စစ်ရန်",
    "Poll စစ်ရန်", "Bot Post စစ်ရန်", "Hashtag စစ်ရန်", "Mention စစ်ရန်",
    "ထပ်နေသော Post စစ်ရန်", "စာအရှည်စစ်ရန်", "စာလုံးအကြီးများစစ်ရန်", "Post မှတ်တမ်းထားရန်",
]

async def _resolve_channel(context, raw_id):
    value = raw_id.strip()
    if value.startswith("@"): value = value
    elif value.lstrip("-").isdigit(): value = int(value)
    chat = await context.bot.get_chat(value)
    if chat.type != "channel":
        raise ValueError("ပေးထားသော ID သည် Channel မဟုတ်ပါ။")
    return chat

async def _channel_admin_check(context, channel_id, user_id):
    member = await context.bot.get_chat_member(channel_id, user_id)
    return member.status in ("administrator", "creator")

async def groupset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, chat, user = update.effective_message, update.effective_chat, update.effective_user
    if not msg or not chat or not user: return
    if chat.type not in ("group", "supergroup"):
        return await msg.reply_text("ဒီ Command ကို Group ထဲမှာ အသုံးပြုပါ။")
    if len(context.args) != 2 or not context.args[0].isdigit() or context.args[1].lower() not in ("on", "off"):
        return await msg.reply_text("အသုံးပြုပုံ: /groupset Module_ID on\nဥပမာ: /groupset 12 off\nModule စာရင်း: /groupmenu")
    if not await _is_group_admin(chat.id, user.id, context):
        return await msg.reply_text("⛔ Group Admin သာ Setting ပြောင်းနိုင်ပါတယ်။")
    module_id = int(context.args[0])
    if not 1 <= module_id <= len(GROUP_MODULES):
        return await msg.reply_text(f"Module ID သည် 1 မှ {len(GROUP_MODULES)} အတွင်း ဖြစ်ရပါမယ်။")
    enabled = int(context.args[1].lower() == "on")
    with db_connect() as conn:
        conn.execute("""INSERT INTO ck_group_module_settings(chat_id,module_id,enabled,updated_by,updated_at)
            VALUES(?,?,?,?,?) ON CONFLICT(chat_id,module_id) DO UPDATE SET
            enabled=excluded.enabled,updated_by=excluded.updated_by,updated_at=excluded.updated_at""",
            (chat.id,module_id,enabled,user.id,int(time.time())))
        conn.commit()
    item = GROUP_MODULES[module_id-1]
    await msg.reply_text(f"{'🟢 ဖွင့်' if enabled else '⚪ ပိတ်'} ပြီးပါပြီ။\n{module_id}. {item['title']}\n{item['desc']}")

async def channelmenu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, user = update.effective_message, update.effective_user
    if not msg or not user: return
    if not context.args:
        return await msg.reply_text("အသုံးပြုပုံ: /channelmenu @channelname\nသို့မဟုတ် /channelmenu -1001234567890\nChannel ID ရယူရန် Bot ကို Channel Admin ထည့်ပြီး Forward လုပ်ထားသော Post ကို စစ်ဆေးပါ။")
    try:
        channel = await _resolve_channel(context, context.args[0])
        if not await _channel_admin_check(context, channel.id, user.id):
            return await msg.reply_text("⛔ အဲဒီ Channel ရဲ့ Admin ဖြစ်မှ Menu ကြည့်နိုင်ပါတယ်။")
    except ValueError as exc:
        return await msg.reply_text(str(exc))
    except Exception:
        logger.exception("Channel menu access check failed")
        return await msg.reply_text("Channel ကို ရှာမတွေ့ပါ၊ သို့မဟုတ် Admin ခွင့်ပြုချက် စစ်မရပါ။ Bot ကို Channel Admin ထည့်ပြီး ပြန်စမ်းပါ။")
    await msg.reply_text(
        f"📢 {channel.title} — CHANNEL MENU\\nModule ၅၀ × Control ၂၀ = Setting ၁,၀၀၀\\nModule ကို ခလုတ်ဖြင့် ရွေးပါ။",
        reply_markup=channel_modules_keyboard(channel.id, 1)
    )

async def channelset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, user = update.effective_message, update.effective_user
    if not msg or not user: return
    if len(context.args) != 3 or not context.args[1].isdigit() or context.args[2].lower() not in ("on", "off"):
        return await msg.reply_text("အသုံးပြုပုံ: /channelset @channelname Setting_ID on\nဥပမာ: /channelset @mychannel 25 off")
    try:
        channel = await _resolve_channel(context, context.args[0])
        if not await _channel_admin_check(context, channel.id, user.id):
            return await msg.reply_text("⛔ Channel Admin သာ Setting ပြောင်းနိုင်ပါတယ်။")
    except Exception:
        logger.exception("Channel setting permission check failed")
        return await msg.reply_text("Channel ကို ရှာမတွေ့ပါ၊ သို့မဟုတ် သင့် Admin ခွင့်ပြုချက်ကို စစ်မရပါ။")
    setting_id = int(context.args[1])
    if not 1 <= setting_id <= 1000:
        return await msg.reply_text("Setting ID သည် 1 မှ 1000 အတွင်း ဖြစ်ရပါမယ်။ /channelmenu ကိုကြည့်ပါ။")
    enabled = int(context.args[2].lower() == "on")
    with db_connect() as conn:
        conn.execute("""INSERT INTO ck_channel_settings(channel_id,setting_id,enabled,updated_by,updated_at)
            VALUES(?,?,?,?,?) ON CONFLICT(channel_id,setting_id) DO UPDATE SET
            enabled=excluded.enabled,updated_by=excluded.updated_by,updated_at=excluded.updated_at""",
            (channel.id,setting_id,enabled,user.id,int(time.time())))
        conn.commit()
    module_no = (setting_id-1)//20 + 1
    control_no = (setting_id-1)%20 + 1
    await msg.reply_text(f"{'🟢 ဖွင့်' if enabled else '⚪ ပိတ်'} ပြီးပါပြီ။\nChannel: {channel.title}\nModule: {module_no} — {CHANNEL_MODULE_TITLES[module_no-1]}\nControl: {control_no} — {CHANNEL_CONTROL_NAMES[control_no-1]}\nမှတ်ချက်: Setting ကို သိမ်းဆည်းထားခြင်းဖြစ်ပြီး အလိုအလျောက်လုပ်ဆောင်မှုချိတ်ဆက်ထားသော စနစ်များသာ အကျိုးသက်ရောက်ပါမယ်။")


# Button UI: Group 300 modules => 12 blocks x 25; Channel 1000 settings => 40 blocks x 25.
def _group_setting(chat_id, module_id):
    with db_connect() as conn:
        row=conn.execute("SELECT enabled FROM ck_group_module_settings WHERE chat_id=? AND module_id=?",(chat_id,module_id)).fetchone()
    return bool(row["enabled"]) if row else False

def _save_group_setting(chat_id,module_id,enabled,user_id):
    with db_connect() as conn:
        conn.execute("""INSERT INTO ck_group_module_settings(chat_id,module_id,enabled,updated_by,updated_at)
        VALUES(?,?,?,?,?) ON CONFLICT(chat_id,module_id) DO UPDATE SET enabled=excluded.enabled,
        updated_by=excluded.updated_by,updated_at=excluded.updated_at""",(chat_id,module_id,int(enabled),user_id,int(time.time())))
        conn.commit()

def group_modules_keyboard(chat_id, page=1):
    # Show two group folders side-by-side on each row.
    rows=[]
    buttons=[]
    for block in range(1,13):
        first=(block-1)*25+1; last=min(block*25,len(GROUP_MODULES))
        enabled=sum(_group_setting(chat_id,mid) for mid in range(first,last+1))
        buttons.append(InlineKeyboardButton(
            f"📁 အုပ်စု {block:02d}\n{first}-{last} ({enabled}/25)",
            callback_data=f"ckg:b:{block}"
        ))
        if len(buttons)==2:
            rows.append(buttons)
            buttons=[]
    if buttons:
        rows.append(buttons)
    return InlineKeyboardMarkup(rows)

def group_block_modules_keyboard(chat_id, block):
    block=max(1,min(12,int(block))); start=(block-1)*25; rows=[]
    for mid,item in enumerate(GROUP_MODULES[start:start+25],start+1):
        icon="🟢" if _group_setting(chat_id,mid) else "⚪"
        rows.append([InlineKeyboardButton(f"{icon} {mid:03d}. {item['title'][:40]}",callback_data=f"ckg:m:{mid}:{block}")])
    rows.append([InlineKeyboardButton("⬅️ အုပ်စု ၁၂ ခုသို့ ပြန်သွားရန်",callback_data="ckg:home")])
    return InlineKeyboardMarkup(rows)

def group_module_detail_keyboard(mid,block):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 ဖွင့်ရန်",callback_data=f"ckg:t:{mid}:1:{block}"),
         InlineKeyboardButton("⚪ ပိတ်ရန်",callback_data=f"ckg:t:{mid}:0:{block}")],
        [InlineKeyboardButton("⬅️ စနစ် ၂၅ ခုသို့ ပြန်သွားရန်",callback_data=f"ckg:b:{block}")]
    ])


def group_module_help_text(mid, item, state):
    return (
        f"📁 GROUP စနစ် {mid:03d} — {item['title']}\n"
        f"📝 ရှင်းပြချက်: {item['desc']}\n"
        f"📌 လက်ရှိအခြေအနေ: {state}\n\n"
        "🟢 ဖွင့်ရန် — ဒီစနစ်အတွက် ဖွင့်/ပိတ် Setting ကို ON အဖြစ် သိမ်းမယ်။\n"
        "⚪ ပိတ်ရန် — ဒီစနစ်အတွက် Setting ကို OFF အဖြစ် သိမ်းမယ်။\n\n"
        "ℹ️ သတိပြုရန် — Setting ဖွင့်ထားခြင်းတစ်ခုတည်းနဲ့ အလိုအလျောက်အလုပ်လုပ်မည် မဟုတ်ပါ။ "
        "သက်ဆိုင်ရာ လုပ်ဆောင်ချက်ကို Bot ထဲမှာ ချိတ်ဆက်ထားမှ အကျိုးသက်ရောက်ပါမယ်။"
    )

def _channel_setting(cid,sid):
    with db_connect() as conn:
        row=conn.execute("SELECT enabled FROM ck_channel_settings WHERE channel_id=? AND setting_id=?",(cid,sid)).fetchone()
    return bool(row["enabled"]) if row else False

def _save_channel_setting(cid,sid,enabled,uid):
    with db_connect() as conn:
        conn.execute("""INSERT INTO ck_channel_settings(channel_id,setting_id,enabled,updated_by,updated_at)
        VALUES(?,?,?,?,?) ON CONFLICT(channel_id,setting_id) DO UPDATE SET enabled=excluded.enabled,
        updated_by=excluded.updated_by,updated_at=excluded.updated_at""",(cid,sid,int(enabled),uid,int(time.time())))
        conn.commit()

def channel_modules_keyboard(cid,page=1):
    # Show two group folders side-by-side on each row (10 folders per page).
    # Existing Channel catalogue contains 50 modules x 20 controls = 1000 settings.
    page=max(1,min(4,int(page))); rows=[]; buttons=[]
    for block in range((page-1)*10+1,min(page*10,40)+1):
        first=(block-1)*25+1; last=block*25
        count=sum(_channel_setting(cid,sid) for sid in range(first,last+1))
        buttons.append(InlineKeyboardButton(
            f"📁 အုပ်စု {block:02d}\n{first}-{last} ({count}/25)",
            callback_data=f"ckc:b:{cid}:{block}:{page}"
        ))
        if len(buttons)==2:
            rows.append(buttons)
            buttons=[]
    if buttons:
        rows.append(buttons)
    nav=[]
    if page>1: nav.append(InlineKeyboardButton("⬅️",callback_data=f"ckc:p:{cid}:{page-1}"))
    nav.append(InlineKeyboardButton(f"{page}/4",callback_data="ckg:noop"))
    if page<4: nav.append(InlineKeyboardButton("➡️",callback_data=f"ckc:p:{cid}:{page+1}"))
    rows.append(nav)
    return InlineKeyboardMarkup(rows)

CHANNEL_CONTROL_DESCRIPTIONS = [
    "Post ထဲတွင် ပါလာသော Website Link များကို စစ်ဆေးရန် ရည်ရွယ်ထားသည်။",
    "Channel Invite Link များကို စစ်ဆေးရန် ရည်ရွယ်ထားသည်။",
    "အခြားနေရာမှ Forward လုပ်ထားသော Post များကို စစ်ဆေးရန် ရည်ရွယ်ထားသည်။",
    "Photo ပါဝင်သော Post များကို စစ်ဆေးရန် ရည်ရွယ်ထားသည်။",
    "Video ပါဝင်သော Post များကို စစ်ဆေးရန် ရည်ရွယ်ထားသည်။",
    "Audio ဖိုင်ပါဝင်သော Post များကို စစ်ဆေးရန် ရည်ရွယ်ထားသည်။",
    "Voice Message ပါဝင်သော Post များကို စစ်ဆေးရန် ရည်ရွယ်ထားသည်။",
    "Document ဖိုင်များပါဝင်သော Post များကို စစ်ဆေးရန် ရည်ရွယ်ထားသည်။",
    "Sticker ပါဝင်သော Post များကို စစ်ဆေးရန် ရည်ရွယ်ထားသည်။",
    "GIF သို့မဟုတ် Animation ပါဝင်သော Post များကို စစ်ဆေးရန် ရည်ရွယ်ထားသည်။",
    "Contact အချက်အလက်မျှဝေထားသော Post များကို စစ်ဆေးရန် ရည်ရွယ်ထားသည်။",
    "Location တည်နေရာမျှဝေထားသော Post များကို စစ်ဆေးရန် ရည်ရွယ်ထားသည်။",
    "Poll မဲပေးမှု Post များကို စစ်ဆေးရန် ရည်ရွယ်ထားသည်။",
    "Bot မှ ပေးပို့သော Post များကို စစ်ဆေးရန် ရည်ရွယ်ထားသည်။",
    "Hashtag အသုံးပြုထားမှုကို စစ်ဆေးရန် ရည်ရွယ်ထားသည်။",
    "အသုံးပြုသူများကို Mention ခေါ်ထားမှုကို စစ်ဆေးရန် ရည်ရွယ်ထားသည်။",
    "အကြောင်းအရာတူပြီး ထပ်ခါထပ်ခါ တင်ထားသော Post များကို စစ်ဆေးရန် ရည်ရွယ်ထားသည်။",
    "Post စာသား၏ အရှည်ကို သတ်မှတ်ချက်နှင့် နှိုင်းယှဉ်စစ်ဆေးရန် ရည်ရွယ်ထားသည်။",
    "စာလုံးအကြီးများ အလွန်အကျွံအသုံးပြုထားမှုကို စစ်ဆေးရန် ရည်ရွယ်ထားသည်။",
    "Post တစ်ခုချင်းစီ၏ မှတ်တမ်းကို သိမ်းဆည်းရန် ရည်ရွယ်ထားသည်။",
]


def channel_control_detail_keyboard(cid,sid,block,page):
    enabled=_channel_setting(cid,sid)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 ဖွင့်ရန်",callback_data=f"ckc:t:{cid}:{sid}:1:{block}:{page}"),
         InlineKeyboardButton("⚪ ပိတ်ရန်",callback_data=f"ckc:t:{cid}:{sid}:0:{block}:{page}")],
        [InlineKeyboardButton("⬅️ Setting ၂၅ ခုသို့ ပြန်သွားရန်",callback_data=f"ckc:b:{cid}:{block}:{page}")]
    ])


def channel_control_help_text(cid,sid):
    module_no=(sid-1)//20+1
    control_no=(sid-1)%20
    enabled=_channel_setting(cid,sid)
    state="ဖွင့်ထားသည် 🟢" if enabled else "ပိတ်ထားသည် ⚪"
    return (
        f"📢 CHANNEL SETTING {sid:03d}\n"
        f"Module: {module_no} — {CHANNEL_MODULE_TITLES[module_no-1]}\n"
        f"Setting: {control_no+1} — {CHANNEL_CONTROL_NAMES[control_no]}\n"
        f"📝 ရှင်းပြချက်: {CHANNEL_CONTROL_DESCRIPTIONS[control_no]}\n"
        f"📌 လက်ရှိအခြေအနေ: {state}\n\n"
        "🟢 ဖွင့်ရန် — ဒီ Setting ကို ON အဖြစ် သိမ်းမယ်။\n"
        "⚪ ပိတ်ရန် — ဒီ Setting ကို OFF အဖြစ် သိမ်းမယ်။\n\n"
        "ℹ️ သတိပြုရန် — Setting ဖွင့်ထားခြင်းတစ်ခုတည်းနဲ့ Post ကို အလိုအလျောက် စစ်ဆေး/ဖျက်/တားဆီးမည် မဟုတ်ပါ။ "
        "သက်ဆိုင်ရာ လုပ်ဆောင်ချက်ကို Bot ထဲမှာ ချိတ်ဆက်ထားမှ အကျိုးသက်ရောက်ပါမယ်။"
    )


def channel_controls_keyboard(cid,block,page):
    block=max(1,min(40,int(block))); rows=[]
    first=(block-1)*25+1
    for sid in range(first,first+25):
        enabled=_channel_setting(cid,sid); icon="🟢" if enabled else "⚪"
        module_no=(sid-1)//20+1; control_no=(sid-1)%20
        label=f"{CHANNEL_MODULE_TITLES[module_no-1]} / {CHANNEL_CONTROL_NAMES[control_no]}"
        rows.append([InlineKeyboardButton(f"{icon} {sid:03d}. {label[:42]}",callback_data=f"ckc:d:{cid}:{sid}:{block}:{page}")])
    rows.append([InlineKeyboardButton("⬅️ အုပ်စုစာရင်းသို့ ပြန်သွားရန်",callback_data=f"ckc:p:{cid}:{page}")])
    return InlineKeyboardMarkup(rows)

async def group_channel_button_callback(query,context,data):
    p=data.split(":"); uid=query.from_user.id; chat=query.message.chat
    if data in ("ckg:noop",):
        await query.answer(); return
    if p[0]=="ckg":
        if chat.type not in ("group","supergroup") or not await _is_group_admin(chat.id,uid,context):
            await query.answer("Group Admin သာ အသုံးပြုနိုင်ပါတယ်။",show_alert=True); return
        if p[1] in ("home","p"):
            await query.answer()
            await query.edit_message_text("🧰 CK GROUP MENU — စနစ် ၃၀၀ ခု / အုပ်စု ၁၂ ခု / တစ်အုပ်စု ၂၅ ခု",reply_markup=group_modules_keyboard(chat.id)); return
        if p[1]=="b":
            block=int(p[2]); start=(block-1)*25
            lines=[f"🧰 GROUP အုပ်စု {block}/12 — စနစ် ၂၅ ခု", "စနစ်တစ်ခုကို နှိပ်ပါ။ ရှင်းပြချက်နဲ့ ဖွင့်/ပိတ်ခလုတ် ပေါ်လာပါမယ်။", ""]
            for mid,item in enumerate(GROUP_MODULES[start:start+25],start+1):
                lines.append(f"{mid:03d}. {item['title']} — {item['desc']}")
            await query.answer()
            await query.edit_message_text("\n".join(lines),reply_markup=group_block_modules_keyboard(chat.id,block)); return
        if p[1]=="m":
            mid,block=int(p[2]),int(p[3]); item=GROUP_MODULES[mid-1]
            state="ဖွင့်ထားသည် 🟢" if _group_setting(chat.id,mid) else "ပိတ်ထားသည် ⚪"
            await query.answer()
            await query.edit_message_text(group_module_help_text(mid,item,state),reply_markup=group_module_detail_keyboard(mid,block)); return
        if p[1]=="t":
            mid,on,block=int(p[2]),bool(int(p[3])),int(p[4]); _save_group_setting(chat.id,mid,on,uid)
            item=GROUP_MODULES[mid-1]; state="ဖွင့်ထားသည် 🟢" if on else "ပိတ်ထားသည် ⚪"
            await query.answer("ဖွင့်ပြီးပါပြီ။" if on else "ပိတ်ပြီးပါပြီ။")
            await query.edit_message_text(group_module_help_text(mid,item,state),reply_markup=group_module_detail_keyboard(mid,block)); return
    if p[0]=="ckc":
        cid=int(p[2])
        try:
            member=await context.bot.get_chat_member(cid,uid)
            if member.status not in ("administrator","creator"): raise PermissionError()
        except Exception:
            await query.answer("Channel Admin ဖြစ်မှ အသုံးပြုနိုင်ပါတယ်။",show_alert=True); return
        channel=await context.bot.get_chat(cid)
        if p[1]=="p":
            page=int(p[3]); await query.answer()
            await query.edit_message_text(f"📢 {channel.title} — CHANNEL MENU / Setting ၁,၀၀၀ ခု / အုပ်စု ၄၀ ခု",reply_markup=channel_modules_keyboard(cid,page)); return
        if p[1]=="b":
            block,page=int(p[3]),int(p[4]); await query.answer()
            await query.edit_message_text(f"📢 {channel.title}\nအုပ်စု {block}/40 — Setting ၂၅ ခု",reply_markup=channel_controls_keyboard(cid,block,page)); return
        if p[1]=="d":
            sid,block,page=map(int,p[3:6]); await query.answer()
            await query.edit_message_text(f"📢 {channel.title}\n\n"+channel_control_help_text(cid,sid),reply_markup=channel_control_detail_keyboard(cid,sid,block,page)); return
        if p[1]=="t":
            sid,on,block,page=map(int,p[3:7]); _save_channel_setting(cid,sid,bool(on),uid)
            await query.answer("ဖွင့်ပြီးပါပြီ။" if on else "ပိတ်ပြီးပါပြီ။")
            await query.edit_message_text(f"📢 {channel.title}\n\n"+channel_control_help_text(cid,sid),reply_markup=channel_control_detail_keyboard(cid,sid,block,page)); return
        # Compatibility for older inline keyboards already sent before this update.
        if p[1]=="m":
            mid,page=int(p[3]),int(p[4]); block=max(1,min(40,((mid-1)*20)//25+1)); await query.answer()
            await query.edit_message_text(f"📢 {channel.title}\nModule {mid}: {CHANNEL_MODULE_TITLES[mid-1]}",reply_markup=channel_controls_keyboard(cid,block,page)); return

async def sethelp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg: return
    await msg.reply_text(
        "📚 CK BOT — SET COMMAND အသုံးပြုနည်း\n\n"
        "👥 GROUP\n/groupmenu — Group Module စာရင်း\n"
        "/groupset 12 on — Module 12 ဖွင့်ရန်\n/groupset 12 off — Module 12 ပိတ်ရန်\n"
        "Group Admin သာ ပြောင်းလဲနိုင်ပါတယ်။\n\n"
        "📢 CHANNEL\n/channelmenu @channelname — Channel Menu\n"
        "/channelset @channelname 25 on — Setting 25 ဖွင့်ရန်\n"
        "/channelset @channelname 25 off — Setting 25 ပိတ်ရန်\n"
        "Channel Admin သာ ပြောင်းလဲနိုင်ပါတယ်။ Bot ကိုလည်း Channel Admin ထည့်ထားရပါမယ်။\n\n"
        "ℹ️ Setting တွေကို Group/Channel တစ်ခုချင်းစီအလိုက် Database မှာ သီးခြားသိမ်းပါတယ်။ Toggle လုပ်ထားခြင်းဟာ သက်ဆိုင်ရာ feature handler ချိတ်ဆက်ထားမှသာ အလိုအလျောက်အကျိုးသက်ရောက်ပါမယ်။"
    )


async def setup_telegram_command_menus(app):
    """Publish supported Telegram slash commands without removing existing commands."""
    # Telegram command menus are scoped separately for private chats and groups.
    # Only commands with registered handlers are published here.
    private_commands = [
        BotCommand("start", "🤖 CK BOT စတင်ရန်"),
        BotCommand("help", "📖 အကူအညီကြည့်ရန်"),
        BotCommand("ckhelp", "🌟 စနစ်များနှင့် အသုံးပြုပုံ"),
        BotCommand("profile", "👤 ကိုယ်ရေးအချက်အလက်"),
        BotCommand("daily", "🎁 နေ့စဉ်ဆုယူရန်"),
        BotCommand("points", "⭐ ရမှတ်ကြည့်ရန်"),
        BotCommand("leaderboard", "🏆 ထိပ်ဆုံးအသုံးပြုသူများ"),
        BotCommand("mission", "🎯 နေ့စဉ်လုပ်ဆောင်ချက်များ"),
        BotCommand("game", "🎮 ဂိမ်းကစားရန်"),
        BotCommand("rpg", "⚔️ RPG စွန့်စားခန်း"),
        BotCommand("pvp", "⚔️ ကစားသမားချင်းယှဉ်ပြိုင်ရန်"),
        BotCommand("mlbbhero", "🗡️ MLBB Hero ပုံခန့်မှန်း"),
        BotCommand("hero", "🦸 MLBB Hero အချက်အလက်"),
        BotCommand("build", "🛠️ Hero Build ကြည့်ရန်"),
        BotCommand("lore", "📜 Hero နောက်ခံဇာတ်လမ်း"),
        BotCommand("combo", "⚡ Hero Combo ကြည့်ရန်"),
        BotCommand("meta", "📊 MLBB Meta ကြည့်ရန်"),
        BotCommand("duo", "🤝 Duo အကြံပြုချက်"),
        BotCommand("tools", "🧰 အသုံးဝင် Tools များ"),
        BotCommand("tool", "🧮 Tool တစ်ခု အသုံးပြုရန်"),
        BotCommand("toolhelp", "📚 Tool အသုံးပြုနည်း"),
        BotCommand("life", "🌱 နေ့စဉ်ဘဝအကူအညီ"),
        BotCommand("remind", "⏰ သတိပေးချက်ထားရန်"),
        BotCommand("reminders", "🗓️ သတိပေးချက်များကြည့်ရန်"),
        BotCommand("delreminder", "🗑️ သတိပေးချက်ဖျက်ရန်"),
        BotCommand("expense", "💰 အသုံးစရိတ်မှတ်ရန်"),
        BotCommand("expenses", "🧾 အသုံးစရိတ်စာရင်း"),
        BotCommand("budget", "📊 ဘတ်ဂျက်စီမံရန်"),
        BotCommand("budgetstatus", "📈 ဘတ်ဂျက်အခြေအနေ"),
        BotCommand("chat", "👥 အမည်မဖော် Chat စရန်"),
        BotCommand("next", "➡️ Chat မိတ်ဖက်ပြောင်းရန်"),
        BotCommand("stop", "⏹️ Chat ရပ်ရန်"),
        BotCommand("report", "🚩 Chat တိုင်ကြားရန်"),
        BotCommand("movie", "🎬 Movie ရှာရန်"),
        BotCommand("movies", "🎞️ Movie စာရင်းကြည့်ရန်"),
        BotCommand("tiktok", "📹 TikTok မီဒီယာရယူရန်"),
        BotCommand("channelmenu", "📢 Channel စနစ်များကြည့်ရန်"),
        BotCommand("channelset", "⚙️ Channel Setting ဖွင့်/ပိတ်ရန်"),
        BotCommand("sethelp", "📚 Set Command အသုံးပြုနည်း"),
        BotCommand("settings", "⚙️ Bot ဆက်တင်များ"),
    ]
    group_commands = [
        BotCommand("start", "🤖 CK BOT စတင်ရန်"),
        BotCommand("help", "📖 အကူအညီကြည့်ရန်"),
        BotCommand("ckhelp", "🌟 Bot စနစ်များနှင့် အသုံးပြုပုံ"),
        BotCommand("groupmenu", "🧰 Group စနစ်များနှင့် အသုံးပြုပုံ"),
        BotCommand("groupset", "⚙️ Group စနစ် ဖွင့်/ပိတ်ရန်"),
        BotCommand("channelmenu", "📢 Channel စနစ်များကြည့်ရန်"),
        BotCommand("channelset", "⚙️ Channel Setting ဖွင့်/ပိတ်ရန်"),
        BotCommand("sethelp", "📚 Set Command အသုံးပြုနည်း"),
        BotCommand("group", "👥 Group Community Menu"),
        BotCommand("groupstats", "📊 Group Statistics"),
        BotCommand("rules", "📜 Group Rules ကြည့်ရန်"),
        BotCommand("setrules", "✏️ Group Rules ပြင်ရန် (Admin)"),
        BotCommand("setwelcome", "👋 Welcome စာပြင်ရန် (Admin)"),
        BotCommand("settings", "⚙️ Group ဆက်တင်များ"),
        BotCommand("setlang", "🌐 ဘာသာစကားပြောင်းရန်"),
        BotCommand("notifications", "🔔 အသိပေးချက်ဆက်တင်"),
        BotCommand("poll", "🗳️ Poll ပြုလုပ်ရန်"),
        BotCommand("suggest", "💡 အကြံပြုချက်ပေးရန်"),
        BotCommand("suggestions", "📋 အကြံပြုချက်များကြည့်ရန်"),
        BotCommand("event", "📅 Event အသစ်ပြုလုပ်ရန်"),
        BotCommand("events", "🗓️ Event များကြည့်ရန်"),
        BotCommand("faq", "❓ မေးလေ့ရှိသောမေးခွန်းများ"),
        BotCommand("faqadd", "➕ FAQ အသစ်ထည့်ရန် (Admin)"),
        BotCommand("faqdel", "➖ FAQ ဖျက်ရန် (Admin)"),
        BotCommand("activity", "📈 Group Activity"),
        BotCommand("ban", "⛔ အဖွဲ့ဝင်ပိတ်ရန် (Admin)"),
        BotCommand("unban", "✅ ပိတ်ထားသူပြန်ဖွင့်ရန် (Admin)"),
        BotCommand("kick", "👢 အဖွဲ့ဝင်ထုတ်ရန် (Admin)"),
        BotCommand("mute", "🔇 စာရေးခွင့်ပိတ်ရန် (Admin)"),
        BotCommand("unmute", "🔊 စာရေးခွင့်ပြန်ဖွင့်ရန် (Admin)"),
        BotCommand("warn", "⚠️ သတိပေးရန် (Admin)"),
        BotCommand("warnings", "📋 သတိပေးချက်စာရင်း"),
        BotCommand("purge", "🧹 စာများရှင်းရန် (Admin)"),
        BotCommand("permission", "🔐 ခွင့်ပြုချက်ပေးရန် (Admin)"),
        BotCommand("unpermission", "🔒 ခွင့်ပြုချက်ရုပ်သိမ်းရန် (Admin)"),
        BotCommand("game", "🎮 ဂိမ်းကစားရန်"),
        BotCommand("tomorrow", "🔮 မနက်ဖြန်ဟောကိန်း"),
        BotCommand("tarot", "🃏 တားရော့ဟောကိန်း"),
        BotCommand("tools", "🧰 အသုံးဝင် Tools များ"),
        BotCommand("tool", "🧮 Tool တစ်ခု အသုံးပြုရန်"),
        BotCommand("toolhelp", "📚 Tool အသုံးပြုနည်း"),
    ]
    await app.bot.set_my_commands(private_commands, scope=BotCommandScopeAllPrivateChats())
    await app.bot.set_my_commands(group_commands, scope=BotCommandScopeAllGroupChats())
    logger.info(
        "Telegram command menus configured: %d private commands, %d group commands",
        len(private_commands), len(group_commands),
    )


async def start_background_tasks(app):
    await setup_telegram_command_menus(app)
    app.create_task(reminder_scheduler(app), name="ck-reminder-scheduler")



# ------------------------- CK BOT: 100 NEW OFFLINE TOOLS -------------------------
# These tools are additive: they do not replace or alter existing bot systems.
import base64
import csv
import difflib
import hashlib
import html
import io
import statistics
import textwrap
import uuid
from collections import Counter
from fractions import Fraction
from urllib.parse import quote, unquote

NEW_TOOL_CATALOG = [
    ("စာလုံးရေတွက်", "wordcount", "စာလုံးရေတွက်"), ("အက္ခရာရေတွက်", "charcount", "အက္ခရာရေတွက်"),
    ("စာကြောင်းရေတွက်", "linecount", "စာကြောင်းရေတွက်"), ("စာပြောင်းပြန်", "reverse", "စာသားကို ပြောင်းပြန်ဖော်ပြ"),
    ("စာကြောင်းစီ", "sortlines", "စာကြောင်းများကို အက္ခရာစဉ်စီ"), ("ထပ်နေစာကြောင်းဖယ်", "unique", "ထပ်နေသောစာကြောင်းများ ဖယ်ရှား"),
    ("ဗလာစာကြောင်းဖယ်", "noblank", "ဗလာစာကြောင်းများ ဖယ်ရှား"), ("စာအကြီး", "upper", "စာလုံးအကြီးပြောင်း"),
    ("စာအသေး", "lower", "စာလုံးအသေးပြောင်း"), ("စာလုံးအစအကြီး", "title", "စကားလုံးအစ စာလုံးအကြီးပြောင်း"),
    ("ဝါကျစနစ်", "sentence", "ဝါကျအစ စာလုံးအကြီးပြောင်း"), ("စာလုံးပုံစံလဲ", "swapcase", "စာလုံးအကြီးအသေး ပြောင်းပြန်လဲ"),
    ("သရရေတွက်", "vowels", "အင်္ဂလိပ်သရ ရေတွက်"), ("ဗျည်းရေတွက်", "consonants", "အင်္ဂလိပ်ဗျည်း ရေတွက်"),
    ("ဂဏန်းထုတ်ယူ", "numbers", "စာထဲမှ ဂဏန်းများ ထုတ်ယူ"), ("Email ထုတ်ယူ", "emails", "Email လိပ်စာများ ထုတ်ယူ"),
    ("Link ထုတ်ယူ", "urls", "URL များ ထုတ်ယူ"), ("Hashtag ထုတ်ယူ", "hashtags", "Hashtag များ ထုတ်ယူ"),
    ("Mention ထုတ်ယူ", "mentions", "@Mention များ ထုတ်ယူ"), ("Link ဖယ်ရှား", "nourl", "စာထဲမှ URL များ ဖယ်ရှား"),
    ("Email ဖယ်ရှား", "noemail", "စာထဲမှ Email များ ဖယ်ရှား"), ("Hashtag ဖယ်ရှား", "nohash", "Hashtag များ ဖယ်ရှား"),
    ("Mention ဖယ်ရှား", "nomention", "Mention များ ဖယ်ရှား"), ("Space ပြင်ဆင်", "spaces", "ပိုနေသော Space များ ဖယ်ရှား"),
    ("စာအတိုကောက်", "slug", "စာသားကို URL slug ပုံစံပြောင်း"), ("ROT13", "rot13", "ROT13 စာဝှက်/ပြန်ဖော်"),
    ("Binary Encode", "binenc", "စာသားကို Binary ပြောင်း"), ("Binary Decode", "bindec", "Binary ကို စာသားပြောင်း"),
    ("Hex Encode", "hexenc", "စာသားကို Hex ပြောင်း"), ("Hex Decode", "hexdec", "Hex ကို စာသားပြောင်း"),
    ("Base64 Encode", "b64enc", "Base64 Encode"), ("Base64 Decode", "b64dec", "Base64 Decode"),
    ("URL Encode", "urlenc", "URL Encode"), ("URL Decode", "urldec", "URL Decode"),
    ("HTML Escape", "htmlesc", "HTML special characters Escape"), ("HTML Decode", "htmldec", "HTML entities ပြန်ဖော်"),
    ("JSON အလှပြင်", "jsonpretty", "JSON ကို ဖတ်ရလွယ်အောင်စီ"), ("JSON Minify", "jsonmin", "JSON အရွယ်အစားချုံ့"),
    ("CSV မှ JSON", "csvjson", "CSV ကို JSON ပြောင်း"), ("JSON မှ CSV", "jsoncsv", "JSON ကို CSV ပြောင်း"),
    ("Markdown Code", "mdcode", "စာသားကို Markdown code block ပြောင်း"), ("Quote စာသား", "quote", "စာကြောင်းတိုင်း Quote ထည့်"),
    ("Bullet List", "bullets", "စာကြောင်းများကို Bullet List ပြောင်း"), ("Number List", "numberlist", "စာကြောင်းများကို နံပါတ်စဉ်တပ်"),
    ("Markdown Table", "mdtable", "စာကြောင်းများမှ Markdown Table ပြုလုပ်"), ("စာလုံးအကြိမ်ရေ", "freq", "စကားလုံးအကြိမ်ရေတွက်"),
    ("စာတန်းဖြတ်", "wrap", "စာသားကို သတ်မှတ်အကျယ်ဖြင့် ဖြတ်"), ("စာကြောင်းပေါင်း", "joinlines", "စာကြောင်းများကို တစ်ကြောင်းတည်းပေါင်း"),
    ("စာလုံးဖယ်", "removechar", "သတ်မှတ်ထားသော စာလုံးဖယ်ရှား"), ("စာလုံးအစားထိုး", "replace", "စာလုံး/စကားလုံး အစားထိုး"),
    ("ပေါင်းလဒ်", "sum", "ဂဏန်းများ ပေါင်း"), ("ပျမ်းမျှ", "average", "ဂဏန်းများ၏ ပျမ်းမျှ"),
    ("အလယ်တန်ဖိုး", "median", "ဂဏန်းများ၏ Median"), ("အနည်းဆုံး/အများဆုံး", "minmax", "အနည်းဆုံးနှင့် အများဆုံး"),
    ("ရာခိုင်နှုန်း", "percent", "X သည် Y ၏ ရာခိုင်နှုန်းမည်မျှ"), ("Discount", "discount", "လျှော့ဈေးတွက်ချက်"),
    ("အခွန်တွက်", "tax", "အခွန်ပေါင်းတွက်ချက်"), ("Tip တွက်", "tip", "Tip နှင့် စုစုပေါင်းတွက်ချက်"),
    ("Bill ခွဲ", "splitbill", "ငွေစာရင်းကို လူအရေအတွက်ဖြင့်ခွဲ"), ("ရာခိုင်နှုန်းပြောင်းလဲမှု", "pctchange", "တန်ဖိုးပြောင်းလဲမှုရာခိုင်နှုန်း"),
    ("အချိုးလျှော့", "ratio", "အချိုးကို အနည်းဆုံးပုံစံချုံ့"), ("Fraction Decimal", "fracdec", "Fraction ကို Decimal ပြောင်း"),
    ("Decimal Fraction", "decfrac", "Decimal ကို Fraction ပြောင်း"), ("GCD", "gcd", "အကြီးဆုံးဘုံစားကိန်း"),
    ("LCM", "lcm", "အငယ်ဆုံးဘုံဆတိုးကိန်း"), ("Prime စစ်", "prime", "Prime number ဟုတ်မဟုတ်စစ်"),
    ("Prime Factor", "factors", "Prime factorization"), ("Roman Encode", "roman", "ဂဏန်းကို Roman numeral ပြောင်း"),
    ("Roman Decode", "unroman", "Roman numeral ကို ဂဏန်းပြောင်း"), ("ဂဏန်းပတ်လည်", "round", "Decimal ကို ဒသမနေရာသတ်မှတ်ပတ်"),
    ("အပေါင်း/အနုတ်", "calc", "အခြေခံဂဏန်းတွက်စက်"), ("အသက်တွက်", "age", "မွေးနေ့မှ အသက်တွက်"),
    ("ရက်ကွာခြားချက်", "datediff", "ရက်စွဲနှစ်ခုကြား ရက်တွက်"), ("ရက်ပေါင်းထည့်", "adddays", "ရက်စွဲထဲ ရက်ပေါင်းထည့်"),
    ("နေ့အမည်", "weekday", "ရက်စွဲ၏ နေ့အမည်ရှာ"), ("Unix Timestamp", "unix", "ရက်စွဲမှ Unix timestamp"),
    ("Timestamp ပြန်ဖော်", "fromunix", "Unix timestamp မှ ရက်စွဲ"), ("Leap Year", "leap", "Leap year ဟုတ်မဟုတ်စစ်"),
    ("လရက်အရေအတွက်", "monthdays", "နှစ်/လအလိုက် ရက်အရေအတွက်"), ("Countdown", "countdown", "ရက်စွဲအထိ ကျန်ရက်တွက်"),
    ("အပူချိန်ပြောင်း", "temp", "Celsius/Fahrenheit ပြောင်း"), ("အလျားပြောင်း", "length", "mm/cm/m/km/in/ft ပြောင်း"),
    ("အလေးချိန်ပြောင်း", "weight", "g/kg/lb/oz ပြောင်း"), ("Data Size ပြောင်း", "datasize", "B/KB/MB/GB ပြောင်း"),
    ("အမြန်နှုန်းပြောင်း", "speed", "km/h နှင့် mph ပြောင်း"), ("ဧရိယာတွက်", "area", "စတုဂံ/စတုရန်း ဧရိယာတွက်"),
    ("ထုထည်တွက်", "volume", "အလျား/အနံ/အမြင့်မှ ထုထည်တွက်"), ("ချက်ပြုတ်အပူချိန်", "cooktemp", "ချက်ပြုတ်အပူချိန် C/F ပြောင်း"),
    ("Random Number", "random", "ကျပန်းဂဏန်းထုတ်"), ("Dice", "dice", "အန်စာတုံးလှိမ့်"),
    ("Coin Flip", "coin", "ခေါင်း/ပန်း ကျပန်းရွေး"), ("UUID", "uuid", "UUID အသစ်ထုတ်"),
    ("Password", "passgen", "ကျပန်းလုံခြုံသော Password ထုတ်"), ("SHA256", "sha256", "စာသား SHA-256 checksum"),
    ("MD5 Checksum", "md5", "စာသား MD5 checksum"), ("Morse Encode", "morse", "စာသား Morse code ပြောင်း"),
    ("Morse Decode", "unmorse", "Morse code ပြန်ဖော်"), ("စာသားကွာခြားချက်", "diff", "စာသားနှစ်ခု ကွာခြားချက်ရှာ"),
    ("Palindrome စစ်", "palindrome", "စာသား Palindrome ဟုတ်မဟုတ်စစ်"), ("Anagram စစ်", "anagram", "စကားလုံးနှစ်ခု Anagram ဟုတ်မဟုတ်စစ်"),
]

NEW_TOOL_HELP = (
    "🧰 **CK BOT — TOOLBOX 100**\n"
    "အောက်ပါပုံစံဖြင့် အသုံးပြုပါ။\n"
    "`/tool အမည် စာသား/တန်ဖိုး`\n"
    "ဥပမာ — `/tool wordcount Hello world`\n"
    "စာမျက်နှာကြည့်ရန် `/tools 1` မှ `/tools 5` အထိ သုံးပါ။\n"
    "Tool အမည်အားလုံးကို `/toolhelp` တွင်ကြည့်နိုင်ပါတယ်။"
)


def _tool_num_list(s):
    vals = re.findall(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)", s)
    if not vals:
        raise ValueError("ဂဏန်းအနည်းဆုံးတစ်ခု ထည့်ပါ။")
    return [float(x) for x in vals]


def _tool_date(s):
    return datetime.strptime(s.strip(), "%Y-%m-%d").date()


def _tool_roman(n):
    if not 1 <= n <= 3999: raise ValueError("Roman numeral အတွက် 1 မှ 3999 အတွင်း ထည့်ပါ။")
    pairs=((1000,"M"),(900,"CM"),(500,"D"),(400,"CD"),(100,"C"),(90,"XC"),(50,"L"),(40,"XL"),(10,"X"),(9,"IX"),(5,"V"),(4,"IV"),(1,"I"))
    out=""
    for v,sym in pairs:
        while n>=v: out+=sym; n-=v
    return out


def _tool_run(key, arg):
    s=arg.strip()
    if key=="wordcount": return f"စကားလုံး {len(s.split())} လုံး"
    if key=="charcount": return f"စာလုံး/အက္ခရာ {len(s)} လုံး (Space အပါအဝင်)"
    if key=="linecount": return f"စာကြောင်း {len(s.splitlines())} ကြောင်း"
    if key=="reverse": return s[::-1]
    if key=="sortlines": return "\n".join(sorted(s.splitlines(),key=str.casefold))
    if key=="unique": return "\n".join(dict.fromkeys(s.splitlines()))
    if key=="noblank": return "\n".join(x for x in s.splitlines() if x.strip())
    if key=="upper": return s.upper()
    if key=="lower": return s.lower()
    if key=="title": return s.title()
    if key=="sentence": return re.sub(r"(^|[.!?]\s+)([a-z])",lambda m:m.group(1)+m.group(2).upper(),s.lower())
    if key=="swapcase": return s.swapcase()
    if key=="vowels": return f"သရ {sum(c.lower() in 'aeiou' for c in s)} လုံး"
    if key=="consonants": return f"ဗျည်း {sum(c.isalpha() and c.lower() not in 'aeiou' for c in s)} လုံး"
    if key=="numbers": return "\n".join(re.findall(r"[-+]?\d+(?:\.\d+)?",s)) or "ဂဏန်းမတွေ့ပါ။"
    if key=="emails": return "\n".join(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",s)) or "Email မတွေ့ပါ။"
    if key=="urls": return "\n".join(re.findall(r"https?://[^\s]+",s)) or "URL မတွေ့ပါ။"
    if key=="hashtags": return "\n".join(re.findall(r"(?<!\w)#[\w\u1000-\u109f]+",s)) or "Hashtag မတွေ့ပါ။"
    if key=="mentions": return "\n".join(re.findall(r"(?<!\w)@[A-Za-z0-9_]+",s)) or "Mention မတွေ့ပါ။"
    if key=="nourl": return re.sub(r"https?://\S+", "", s).strip()
    if key=="noemail": return re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "", s).strip()
    if key=="nohash": return re.sub(r"(?<!\w)#[\w\u1000-\u109f]+", "", s).strip()
    if key=="nomention": return re.sub(r"(?<!\w)@[A-Za-z0-9_]+", "", s).strip()
    if key=="spaces": return re.sub(r"\s+", " ", s).strip()
    if key=="slug": return re.sub(r"[^a-z0-9]+","-",s.lower()).strip("-")
    if key=="rot13": return s.translate(str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz","NOPQRSTUVWXYZABCDEFGHIJKLMnopqrstuvwxyzabcdefghijklm"))
    if key=="binenc": return " ".join(format(b,"08b") for b in s.encode("utf-8"))
    if key=="bindec": return bytes(int(x,2) for x in s.split()).decode("utf-8")
    if key=="hexenc": return s.encode().hex()
    if key=="hexdec": return bytes.fromhex(s).decode("utf-8")
    if key=="b64enc": return base64.b64encode(s.encode()).decode()
    if key=="b64dec": return base64.b64decode(s,validate=True).decode("utf-8")
    if key=="urlenc": return quote(s,safe="")
    if key=="urldec": return unquote(s)
    if key=="htmlesc": return html.escape(s)
    if key=="htmldec": return html.unescape(s)
    if key=="jsonpretty": return json.dumps(json.loads(s),ensure_ascii=False,indent=2)
    if key=="jsonmin": return json.dumps(json.loads(s),ensure_ascii=False,separators=(",",":"))
    if key=="csvjson":
        rows=list(csv.DictReader(io.StringIO(s))); return json.dumps(rows,ensure_ascii=False,indent=2)
    if key=="jsoncsv":
        rows=json.loads(s)
        if not isinstance(rows,list) or not rows or not all(isinstance(x,dict) for x in rows): raise ValueError("JSON array of objects ထည့်ပါ။")
        out=io.StringIO(); w=csv.DictWriter(out,fieldnames=list(dict.fromkeys(k for row in rows for k in row))); w.writeheader(); w.writerows(rows); return out.getvalue()
    if key=="mdcode": return "```\n"+s[:3500]+"\n```"
    if key=="quote": return "\n".join("> "+x for x in s.splitlines())
    if key=="bullets": return "\n".join("• "+x for x in s.splitlines() if x.strip())
    if key=="numberlist": return "\n".join(f"{i}. {x}" for i,x in enumerate(s.splitlines(),1) if x.strip())
    if key=="mdtable":
        rows=[x.split(",") for x in s.splitlines() if x.strip()]
        if not rows: raise ValueError("Comma ဖြင့်ခွဲထားသော အချက်အလက်ထည့်ပါ။")
        width=max(map(len,rows)); rows=[r+['']*(width-len(r)) for r in rows]
        return "| "+" | ".join(rows[0])+" |\n| "+" | ".join(["---"]*width)+" |\n"+"\n".join("| "+" | ".join(r)+" |" for r in rows[1:])
    if key=="freq": return "\n".join(f"{w}: {n}" for w,n in Counter(re.findall(r"\w+",s.lower())).most_common(30)) or "စာသားမရှိပါ။"
    if key=="wrap":
        width=int(s.split(None,1)[0]); body=s.split(None,1)[1]
        if not 10<=width<=200: raise ValueError("အကျယ်ကို 10 မှ 200 အတွင်းထည့်ပါ။")
        return textwrap.fill(body,width)
    if key=="joinlines": return " ".join(x.strip() for x in s.splitlines() if x.strip())
    if key=="removechar":
        a,b=s.split("|",1); return b.replace(a,"")
    if key=="replace":
        a,b,c=s.split("|",2); return c.replace(a,b)
    if key in ("sum","average","median","minmax"):
        v=_tool_num_list(s)
        if key=="sum": return f"ပေါင်းလဒ် = {sum(v):g}"
        if key=="average": return f"ပျမ်းမျှ = {statistics.mean(v):g}"
        if key=="median": return f"Median = {statistics.median(v):g}"
        return f"အနည်းဆုံး = {min(v):g}\nအများဆုံး = {max(v):g}"
    if key in ("percent","discount","tax","tip","splitbill","pctchange"):
        v=_tool_num_list(s)
        if key=="percent":
            if len(v)!=2 or v[1]==0: raise ValueError("ပုံစံ: တန်ဖိုး စုစုပေါင်း (ဥပမာ 25 200)")
            return f"{v[0]/v[1]*100:.2f}%"
        if key=="discount":
            if len(v)!=2: raise ValueError("ပုံစံ: မူရင်းဈေး လျှော့ရာခိုင်နှုန်း")
            return f"လျှော့ငွေ {v[0]*v[1]/100:g}\nကျသင့်ငွေ {v[0]*(1-v[1]/100):g}"
        if key=="tax":
            if len(v)!=2: raise ValueError("ပုံစံ: မူရင်းငွေ အခွန်ရာခိုင်နှုန်း")
            return f"အခွန် {v[0]*v[1]/100:g}\nစုစုပေါင်း {v[0]*(1+v[1]/100):g}"
        if key=="tip":
            if len(v)!=2: raise ValueError("ပုံစံ: Bill Tipရာခိုင်နှုန်း")
            return f"Tip {v[0]*v[1]/100:g}\nစုစုပေါင်း {v[0]*(1+v[1]/100):g}"
        if key=="splitbill":
            if len(v)!=2 or v[1]<=0: raise ValueError("ပုံစံ: စုစုပေါင်းငွေ လူဦးရေ")
            return f"တစ်ဦးလျှင် {v[0]/v[1]:,.2f}"
        if len(v)!=2 or v[0]==0: raise ValueError("ပုံစံ: အဟောင်းတန်ဖိုး အသစ်တန်ဖိုး")
        return f"ပြောင်းလဲမှု {(v[1]-v[0])/abs(v[0])*100:+.2f}%"
    if key=="ratio":
        a,b=map(int,re.findall(r"-?\d+",s)); g=math.gcd(a,b); return f"{a//g}:{b//g}"
    if key in ("fracdec","decfrac"):
        if key=="fracdec": return f"{float(Fraction(s)):.10g}"
        return str(Fraction(s).limit_denominator(100000))
    if key in ("gcd","lcm"):
        v=[int(x) for x in _tool_num_list(s)]
        return str(math.gcd(*v) if key=="gcd" else math.lcm(*v))
    if key=="prime":
        n=int(s)
        if n<2: return "Prime မဟုတ်ပါ။"
        return "Prime ဖြစ်ပါတယ်။" if all(n%d for d in range(2,math.isqrt(n)+1)) else "Prime မဟုတ်ပါ။"
    if key=="factors":
        n=abs(int(s));
        if n<2: return "2 နှင့်အထက် ကိန်းထည့်ပါ။"
        out=[]; d=2
        while d*d<=n:
            while n%d==0: out.append(str(d)); n//=d
            d+=1
        if n>1: out.append(str(n))
        return " × ".join(out)
    if key=="roman": return _tool_roman(int(s))
    if key=="unroman":
        vals={"I":1,"V":5,"X":10,"L":50,"C":100,"D":500,"M":1000}; total=0; prev=0
        for c in s.upper()[::-1]:
            if c not in vals: raise ValueError("Roman numeral မှန်ကန်စွာထည့်ပါ။")
            n=vals[c]; total += -n if n<prev else n; prev=max(prev,n)
        if _tool_roman(total)!=s.upper(): raise ValueError("Roman numeral ပုံစံမမှန်ပါ။")
        return str(total)
    if key=="round":
        a=s.split(); return f"{round(float(a[0]),int(a[1]) if len(a)>1 else 0):g}"
    if key=="calc":
        if not re.fullmatch(r"[0-9+*/().% \-]+",s): raise ValueError("ဂဏန်းနှင့် + - * / % ( ) သာသုံးပါ။")
        # Restricted arithmetic parser; no eval.
        import ast as _ast
        node=_ast.parse(s,mode="eval")
        def ev(n):
            if isinstance(n,_ast.Expression): return ev(n.body)
            if isinstance(n,_ast.Constant) and isinstance(n.value,(int,float)): return n.value
            if isinstance(n,_ast.BinOp) and type(n.op) in ( _ast.Add,_ast.Sub,_ast.Mult,_ast.Div,_ast.Mod,_ast.Pow):
                a,b=ev(n.left),ev(n.right)
                if isinstance(n.op,_ast.Add): return a+b
                if isinstance(n.op,_ast.Sub): return a-b
                if isinstance(n.op,_ast.Mult): return a*b
                if isinstance(n.op,_ast.Div): return a/b
                if isinstance(n.op,_ast.Mod): return a%b
                if abs(b)>10: raise ValueError("Exponent အလွန်ကြီးနေပါတယ်။")
                return a**b
            if isinstance(n,_ast.UnaryOp) and isinstance(n.op,(_ast.UAdd,_ast.USub)): return ev(n.operand)*(1 if isinstance(n.op,_ast.UAdd) else -1)
            raise ValueError("တွက်ချက်မှုပုံစံ မမှန်ပါ။")
        return f"အဖြေ = {ev(node):g}"
    if key in ("age","datediff","adddays","weekday","unix","fromunix","leap","monthdays","countdown"):
        if key=="age":
            d=_tool_date(s); today=datetime.now(ZoneInfo("Asia/Yangon")).date(); return f"အသက် {today.year-d.year-((today.month,today.day)<(d.month,d.day))} နှစ်"
        if key=="datediff":
            a,b=[_tool_date(x) for x in s.split()[:2]]; return f"{abs((b-a).days)} ရက်"
        if key=="adddays":
            a,n=s.split()[:2]; return (_tool_date(a)+timedelta(days=int(n))).isoformat()
        if key=="weekday": return _tool_date(s).strftime("%A")
        if key=="unix": return str(int(datetime.combine(_tool_date(s),datetime.min.time(),tzinfo=ZoneInfo("Asia/Yangon")).timestamp()))
        if key=="fromunix": return datetime.fromtimestamp(int(s),ZoneInfo("Asia/Yangon")).strftime("%Y-%m-%d %H:%M:%S (%Z)")
        if key=="leap":
            y=int(s); return "Leap Year ဖြစ်ပါတယ်။" if y%4==0 and (y%100!=0 or y%400==0) else "Leap Year မဟုတ်ပါ။"
        if key=="monthdays":
            import calendar as _cal
            y,m=map(int,s.split()[:2]); return f"{_cal.monthrange(y,m)[1]} ရက်"
        d=_tool_date(s); today=datetime.now(ZoneInfo("Asia/Yangon")).date(); return f"ကျန် { (d-today).days } ရက်"
    if key in ("temp","cooktemp"):
        v=float(re.findall(r"[-+]?\d+(?:\.\d+)?",s)[0]); f=s.lower().endswith("f")
        return f"{(v-32)*5/9 if f else v*9/5+32:.2f} {'°C' if f else '°F'}"
    if key in ("length","weight","datasize","speed"):
        a,u=s.lower().split()[:2]
        val=float(a)
        maps={"length":{"mm":.001,"cm":.01,"m":1,"km":1000,"in":.0254,"ft":.3048},"weight":{"g":1,"kg":1000,"lb":453.59237,"oz":28.349523125},"datasize":{"b":1,"kb":1000,"mb":1e6,"gb":1e9,"kib":1024,"mib":1048576,"gib":1073741824},"speed":{"kmh":1,"mph":1.609344}}
        if u not in maps[key]: raise ValueError("Unit မမှန်ပါ။ Unit ဥပမာ: length km, weight kg, datasize mb, speed kmh")
        base=val*maps[key][u]
        converted=[f"{base/factor:g} {unit}" for unit,factor in maps[key].items()]
        return "\n".join(converted)
    if key=="area":
        a,b=_tool_num_list(s)[:2]; return f"ဧရိယာ = {a*b:g} စတုရန်းယူနစ်"
    if key=="volume":
        a,b,c=_tool_num_list(s)[:3]; return f"ထုထည် = {a*b*c:g} ကုဗယူနစ်"
    if key=="random":
        a,b=map(int,re.findall(r"-?\d+",s));
        if b<a or b-a>10**9: raise ValueError("Range မှန်ကန်စွာထည့်ပါ။")
        return str(random.randint(a,b))
    if key=="dice": return "🎲 "+str(random.randint(1,max(2,min(100,int(s or "6")))))
    if key=="coin": return random.choice(["🪙 ခေါင်း","🪙 ပန်း"])
    if key=="uuid": return str(uuid.uuid4())
    if key=="passgen":
        n=int(s or "16")
        if not 12<=n<=64: raise ValueError("Password အရှည် 12 မှ 64 အတွင်းထားပါ။")
        import secrets as _secrets,string as _string
        alphabet=_string.ascii_letters+_string.digits+"!@#$%*-_"
        return "".join(_secrets.choice(alphabet) for _ in range(n))
    if key=="sha256": return hashlib.sha256(s.encode()).hexdigest()
    if key=="md5": return hashlib.md5(s.encode(),usedforsecurity=False).hexdigest()
    if key=="morse":
        m={c:v for c,v in zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",[".-","-...","-.-.","-..",".","..-.","--.","....","..",".---","-.-",".-..","--","-.","---",".--.","--.-",".-.","...","-","..-","...-",".--","-..-","-.--","--..","-----",".----","..---","...--","....-",".....","-....","--...","---..","----."])}
        return " / ".join(" ".join(m.get(c,"?") for c in word) for word in s.upper().split())
    if key=="unmorse":
        rev={v:c for c,v in zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",[".-","-...","-.-.","-..",".","..-.","--.","....","..",".---","-.-",".-..","--","-.","---",".--.","--.-",".-.","...","-","..-","...-",".--","-..-","-.--","--..","-----",".----","..---","...--","....-",".....","-....","--...","---..","----."])}
        return " ".join("".join(rev.get(c,"?") for c in word.split()) for word in s.split(" / "))
    if key=="diff":
        a,b=s.split("|||",1); return "\n".join(difflib.unified_diff(a.splitlines(),b.splitlines(),fromfile="A",tofile="B",lineterm=""))[:3500] or "ကွာခြားချက်မရှိပါ။"
    if key=="alphabet": return "".join(sorted((c for c in s.lower() if c.isalpha())))
    if key=="stopwords":
        stop={"a","an","the","and","or","but","is","are","was","were","to","of","in","on","for","with","this","that"}
        return " ".join(w for w in s.split() if w.lower() not in stop)
    if key=="palindrome":
        t="".join(c.lower() for c in s if c.isalnum()); return "Palindrome ဖြစ်ပါတယ်။" if t==t[::-1] else "Palindrome မဟုတ်ပါ။"
    if key=="anagram":
        a,b=s.split("|",1); norm=lambda x:sorted(c.lower() for c in x if c.isalnum()); return "Anagram ဖြစ်ပါတယ်။" if norm(a)==norm(b) else "Anagram မဟုတ်ပါ။"
    raise ValueError("Tool အမည်မတွေ့ပါ။ `/tools` ကိုကြည့်ပါ။")


def tools_group_keyboard():
    rows=[]
    for group in range(4):
        start=group*25+1
        rows.append([
            InlineKeyboardButton(f"🧰 အုပ်စု {group+1:02d} ({start}-{start+24})", callback_data=f"ckt:g:{group}")
        ])
    return InlineKeyboardMarkup(rows)


def tools_items_keyboard(group):
    rows=[]
    start=group*25
    items=NEW_TOOL_CATALOG[start:start+25]
    for i in range(0,len(items),2):
        row=[]
        for name,key,desc in items[i:i+2]:
            num=start+i+len(row)+1
            row.append(InlineKeyboardButton(f"{num:03d}. {name[:18]}", callback_data=f"ckt:t:{key}:{group}"))
        rows.append(row)
    rows.append([InlineKeyboardButton("⬅️ အုပ်စုစာရင်း",callback_data="ckt:home")])
    return InlineKeyboardMarkup(rows)


async def tools_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "🧰 **CK BOT TOOLBOX — Tool စနစ် ၁၀၀**\n\n"
        "အုပ်စုတစ်ခုစီတွင် Tool ၂၅ ခုစီ ပါဝင်ပါတယ်။ အုပ်စုကိုရွေးပြီး Tool တစ်ခုကိုနှိပ်ပါ။\n"
        "Tool တစ်ခုချင်းစီမှာ မြန်မာလို ရှင်းပြချက်နဲ့ အသုံးပြုနည်း ပြပေးပါမယ်။",
        parse_mode="Markdown", reply_markup=tools_group_keyboard())


async def tools_button_callback(query, context, data):
    await query.answer()
    parts=data.split(":")
    if data=="ckt:home":
        await query.edit_message_text(
            "🧰 **CK BOT TOOLBOX — Tool စနစ် ၁၀၀**\n\nအုပ်စုတစ်ခုစီတွင် Tool ၂၅ ခုစီ ပါဝင်ပါတယ်။",
            parse_mode="Markdown", reply_markup=tools_group_keyboard())
        return
    if len(parts)>=3 and parts[1]=="g":
        group=max(0,min(3,int(parts[2])))
        start=group*25+1
        await query.edit_message_text(
            f"🧰 **Tool အုပ်စု {group+1:02d}**\n\nစနစ် {start} မှ {start+24} အထိ ပါဝင်ပါတယ်။\nTool တစ်ခုကိုနှိပ်ပြီး ရှင်းပြချက်ကြည့်ပါ။",
            parse_mode="Markdown", reply_markup=tools_items_keyboard(group))
        return
    if len(parts)>=4 and parts[1]=="t":
        key=parts[2]
        group=max(0,min(3,int(parts[3])))
        item=next((x for x in NEW_TOOL_CATALOG if x[1]==key),None)
        if not item:
            await query.answer("Tool မတွေ့ပါ။",show_alert=True); return
        name,_,desc=item
        usage=f"/tool {key} တန်ဖိုး"
        if key in ("coin","uuid"): usage=f"/tool {key}"
        await query.edit_message_text(
            f"🧰 **{name}**\n\n📖 **ဘာလုပ်ပေးသလဲ**\n{desc}\n\n📝 **အသုံးပြုနည်း**\n`{usage}`\n\nအသုံးပြုရန် ခလုတ်ကိုနှိပ်ပါ။",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("▶️ Tool အသုံးပြုရန်",callback_data=f"ckt:run:{key}:{group}")],
                [InlineKeyboardButton("⬅️ Tool စာရင်း",callback_data=f"ckt:g:{group}")]
            ]))
        return
    if len(parts)>=4 and parts[1]=="run":
        key=parts[2]
        group=max(0,min(3,int(parts[3])))
        if key in ("coin","uuid"):
            try:
                result=str(_tool_run(key,""))
                await query.message.reply_text("🧰 ရလဒ်\n"+result)
            except Exception as exc:
                await query.message.reply_text("⚠️ Tool အမှား: "+str(exc)[:300])
        else:
            context.user_data["tool_waiting_key"]=key
            context.user_data["tool_waiting_group"]=group
            item=next((x for x in NEW_TOOL_CATALOG if x[1]==key),None)
            await query.message.reply_text(
                f"📝 **{item[0] if item else key}** အတွက် အသုံးပြုမည့် စာသား/တန်ဖိုးကို ပို့ပေးပါ။\n"
                f"ဥပမာ — `/tool {key} တန်ဖိုး`",
                parse_mode="Markdown")
        return


async def tool_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines=["🧰 **Tool အသုံးပြုနည်း**", "`/tool အမည် တန်ဖိုး`", ""]
    lines += [f"`{key}` — {name}" for name,key,_ in NEW_TOOL_CATALOG]
    lines += ["", "အထူးပုံစံများ:", "• `/tool replace ရှာရန်|အစားထိုးရန်|စာသား`", "• `/tool removechar ဖယ်မည့်စာလုံး|စာသား`", "• `/tool diff စာသားA|||စာသားB`", "• `/tool datediff 2026-01-01 2026-02-01`", "• `/tool temp 25C` သို့ `/tool temp 77F`", "• `/tool length 5 km`၊ `/tool weight 2 kg`၊ `/tool datasize 10 mb`"]
    await update.effective_message.reply_text("\n".join(lines),parse_mode="Markdown")


async def tool_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args)<1:
        await update.effective_message.reply_text("အသုံးပြုပုံ: `/tool အမည် တန်ဖိုး`\nဥပမာ: `/tool wordcount Hello world`",parse_mode="Markdown"); return
    key=context.args[0].lower().lstrip("/")
    known={x[1] for x in NEW_TOOL_CATALOG}
    if key not in known:
        await update.effective_message.reply_text("ဒီ Tool အမည် မတွေ့ပါ။ `/tools` ကိုကြည့်ပါ။",parse_mode="Markdown"); return
    arg=" ".join(context.args[1:])
    if not arg and key not in ("coin","uuid"):
        await update.effective_message.reply_text(f"`/tool {key} တန်ဖိုး` ပုံစံဖြင့် ထည့်ပါ။",parse_mode="Markdown"); return
    try:
        result=str(_tool_run(key,arg))
        if len(result)>3900: result=result[:3900]+"\n… (စာသားရှည်လွန်း၍ ဖြတ်ထားသည်)"
        await update.effective_message.reply_text("🧰 ရလဒ်\n"+result)
    except Exception as exc:
        logger.info("Tool %s input rejected: %s",key,exc)
        await update.effective_message.reply_text("⚠️ ထည့်သွင်းမှုကို စစ်ဆေးပါ။\n"+str(exc)[:500])




# ------------------------- CK COMMUNITY HUB: FREE SOCIAL SYSTEMS -------------------------
# These systems use SQLite and Telegram Bot API only. No paid API or subscription is required.
CK_DAILY_REWARDS = (15, 20, 25, 30, 35, 45, 60)
CK_LEVEL_STEP = 250
CK_BADGE_DEFS = {
    "first_steps": ("🌱", "စတင်သူ", "CK BOT ကို စတင်အသုံးပြုသူ"),
    "daily_7": ("🔥", "၇ ရက်ဆက်တိုက်", "နေ့စဉ်ဆု ၇ ရက်ဆက်တိုက်ရယူသူ"),
    "chat_100": ("💬", "စကားပြောသူ", "စာတို ၁၀၀ ပို့ထားသူ"),
    "points_500": ("💎", "စုဆောင်းသူ", "အမှတ် ၅၀၀ ရရှိသူ"),
    "level_5": ("🏆", "အဆင့်မြင့်", "Level 5 ရောက်ရှိသူ"),
    "helper": ("🤝", "ကူညီသူ", "Community အတွက် အကြံပြုချက်ပေးသူ"),
}


def ck_today():
    return datetime.now(ZoneInfo("Asia/Yangon")).date().isoformat()


def ck_profile(user):
    """Create or refresh a profile, returning a plain dictionary."""
    now = int(time.time())
    display = (user.full_name or user.username or "CK User")[:80]
    username = (user.username or "")[:64]
    with db_connect() as conn:
        conn.execute("""INSERT OR IGNORE INTO ck_profiles
            (user_id,username,display_name,joined_at,last_seen)
            VALUES(?,?,?,?,?)""", (user.id, username, display, now, now))
        conn.execute("""UPDATE ck_profiles SET username=?,display_name=?,last_seen=?
            WHERE user_id=?""", (username, display, now, user.id))
        conn.commit()
        row = conn.execute("SELECT * FROM ck_profiles WHERE user_id=?", (user.id,)).fetchone()
        return dict(row)


def ck_award(user_id, points=0, xp=0):
    """Award non-transferable bot points and XP; returns updated profile."""
    with db_connect() as conn:
        conn.execute("""INSERT OR IGNORE INTO ck_profiles
            (user_id,joined_at,last_seen) VALUES(?,?,?)""", (user_id, int(time.time()), int(time.time())))
        row = conn.execute("SELECT xp,points FROM ck_profiles WHERE user_id=?", (user_id,)).fetchone()
        total_xp = max(0, int(row["xp"]) + int(xp))
        level = 1 + total_xp // CK_LEVEL_STEP
        conn.execute("""UPDATE ck_profiles SET points=MAX(0,points+?),xp=?,level=?
            WHERE user_id=?""", (int(points), total_xp, level, user_id))
        conn.commit()
        return dict(conn.execute("SELECT * FROM ck_profiles WHERE user_id=?", (user_id,)).fetchone())


def ck_badge(user_id, badge_key):
    if badge_key not in CK_BADGE_DEFS:
        return False
    with db_connect() as conn:
        cur = conn.execute("INSERT OR IGNORE INTO ck_badges(user_id,badge_key,earned_at) VALUES(?,?,?)",
                           (user_id, badge_key, int(time.time())))
        conn.commit()
        return cur.rowcount > 0


def ck_record_activity(user, chat_id):
    """Record daily activity with a strict per-user daily message cap for XP."""
    if not user or user.is_bot:
        return
    today = ck_today()
    profile = ck_profile(user)
    with db_connect() as conn:
        conn.execute("""INSERT INTO ck_user_message_daily(user_id,day,messages)
            VALUES(?,?,1) ON CONFLICT(user_id,day) DO UPDATE SET messages=messages+1""",
            (user.id, today))
        row = conn.execute("SELECT messages FROM ck_user_message_daily WHERE user_id=? AND day=?",
                           (user.id, today)).fetchone()
        count = int(row["messages"])
        conn.execute("""INSERT INTO ck_group_stats(chat_id,messages,members_seen,updated_at)
            VALUES(?,1,1,?) ON CONFLICT(chat_id) DO UPDATE SET messages=messages+1,updated_at=excluded.updated_at""",
            (chat_id, int(time.time())))
        conn.commit()
    # Only the first 20 ordinary messages per day earn a tiny amount; commands are excluded.
    if count <= 20:
        ck_award(user.id, points=1, xp=2)
    if count >= 1:
        ck_badge(user.id, "first_steps")
    if count >= 100:
        ck_badge(user.id, "chat_100")
    fresh = ck_profile(user)
    if fresh["points"] >= 500:
        ck_badge(user.id, "points_500")
    if fresh["level"] >= 5:
        ck_badge(user.id, "level_5")


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    p = ck_profile(user)
    with db_connect() as conn:
        badges = conn.execute("SELECT badge_key FROM ck_badges WHERE user_id=? ORDER BY earned_at",
                              (user.id,)).fetchall()
        today_row = conn.execute("SELECT messages FROM ck_user_message_daily WHERE user_id=? AND day=?",
                                 (user.id, ck_today())).fetchone()
    badge_text = "၊ ".join(CK_BADGE_DEFS[x["badge_key"]][0] + CK_BADGE_DEFS[x["badge_key"]][1]
                           for x in badges) or "မရရှိသေးပါ"
    messages = today_row["messages"] if today_row else 0
    next_xp = p["level"] * CK_LEVEL_STEP
    await update.effective_message.reply_text(
        f"👤 **သင့် CK Profile**\n\n"
        f"အမည်: {p['display_name']}\n"
        f"⭐ Level: {p['level']}\n"
        f"✨ XP: {p['xp']}/{next_xp}\n"
        f"💎 Points: {p['points']}\n"
        f"💬 ယနေ့စာတို: {messages}\n"
        f"🏅 Badge: {badge_text}\n\n"
        f"နေ့စဉ်အသုံးပြုမှုနဲ့ Quiz/Game များမှ အမှတ်များ စုဆောင်းနိုင်ပါတယ်။",
        )


async def daily_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    p = ck_profile(user)
    today = ck_today()
    with db_connect() as conn:
        if conn.execute("SELECT 1 FROM ck_daily_claims WHERE user_id=? AND claim_day=?",
                        (user.id, today)).fetchone():
            await update.effective_message.reply_text("🎁 ယနေ့ Daily Reward ကို ရယူပြီးပါပြီ။ မနက်ဖြန် ပြန်လာခဲ့ပါ။")
            return
        yesterday = (datetime.now(ZoneInfo("Asia/Yangon")).date() - timedelta(days=1)).isoformat()
        streak = p["streak"] + 1 if p["last_daily"] == yesterday else 1
        reward = CK_DAILY_REWARDS[min(streak - 1, len(CK_DAILY_REWARDS) - 1)]
        conn.execute("INSERT INTO ck_daily_claims(user_id,claim_day,reward) VALUES(?,?,?)",
                     (user.id, today, reward))
        conn.execute("UPDATE ck_profiles SET streak=?,last_daily=? WHERE user_id=?",
                     (streak, today, user.id))
        conn.commit()
    fresh = ck_award(user.id, points=reward, xp=20)
    if streak >= 7:
        ck_badge(user.id, "daily_7")
    await update.effective_message.reply_text(
        f"🎉 **Daily Reward ရရှိပါပြီ!**\n\n"
        f"💎 +{reward} Points\n✨ +20 XP\n🔥 Streak: {streak} ရက်\n"
        f"⭐ Level: {fresh['level']}\n💰 စုစုပေါင်း Points: {fresh['points']}\n\n"
        f"မနက်ဖြန်လည်း ပြန်လာပြီး ဆုယူပါ။", parse_mode="Markdown")


async def points_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p = ck_profile(update.effective_user)
    await update.effective_message.reply_text(
        f"💎 သင့် Points: **{p['points']}**\n✨ XP: **{p['xp']}** · Level **{p['level']}**\n"
        "Points သည် Bot အတွင်းရှိ ဂိမ်း/ဆုစနစ်အတွက်သာဖြစ်ပြီး ငွေသားအဖြစ် လဲလှယ်၍မရပါ။",
        parse_mode="Markdown")


async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with db_connect() as conn:
        rows = conn.execute("SELECT user_id,display_name,points,level,xp FROM ck_profiles "
                            "ORDER BY points DESC,xp DESC LIMIT 10").fetchall()
    if not rows:
        await update.effective_message.reply_text("Leaderboard မရှိသေးပါ။ /daily ဖြင့် စတင်ပါ။")
        return
    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 **CK BOT Leaderboard — Top 10**", ""]
    for i, row in enumerate(rows, 1):
        prefix = medals[i-1] if i <= 3 else f"{i}."
        name = (row["display_name"] or "User")[:24]
        lines.append(f"{prefix} {name} · 💎 {row['points']} · Lv.{row['level']}")
    await update.effective_message.reply_text("\n".join(lines))


async def mission_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    today = ck_today()
    with db_connect() as conn:
        row = conn.execute("SELECT messages FROM ck_user_message_daily WHERE user_id=? AND day=?",
                           (user.id, today)).fetchone()
    count = row["messages"] if row else 0
    done = count >= 5
    await update.effective_message.reply_text(
        "🎯 **ယနေ့ Mission**\n\n"
        f"{'✅' if done else '▫️'} Community မှာ စာတို ၅ ကြိမ် ပို့ပါ ({min(count,5)}/5)\n"
        "▫️ /daily ဖြင့် Daily Reward ရယူပါ\n"
        "▫️ Quiz သို့မဟုတ် Game တစ်ခု ကစားပါ\n\n"
        "မှတ်ချက်: စာတိုပို့ခြင်းမှ XP ရရှိမှုကို တစ်နေ့ ၂၀ ကြိမ်အထိသာတွက်ပါတယ်။",
        parse_mode="Markdown")


async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.effective_message.text or ""
    message = raw.partition(" ")[2].strip()
    if len(message) < 5:
        await update.effective_message.reply_text("အကြံပြုချက်ပို့ရန်: `/feedback Bot မှာ မြန်မာစာ Quiz ထပ်ထည့်ပေးပါ`", parse_mode="Markdown")
        return
    if len(message) > 1000:
        await update.effective_message.reply_text("စာသားကို စာလုံး ၁၀၀၀ အတွင်း ထည့်ပေးပါ။")
        return
    u = update.effective_user
    with db_connect() as conn:
        conn.execute("INSERT INTO ck_feedback(user_id,username,message,created_at) VALUES(?,?,?,?)",
                     (u.id, u.username or u.full_name[:64], message, int(time.time())))
        conn.commit()
    ck_badge(u.id, "helper")
    await update.effective_message.reply_text("🙏 အကြံပြုချက်ကို လက်ခံရရှိပါပြီ။ CK BOT တိုးတက်ရေးအတွက် အသုံးပြုပါမယ်။")
    if BOT_OWNER_ID:
        try:
            await context.bot.send_message(BOT_OWNER_ID,
                f"📩 CK BOT Feedback #{u.id}\nUser: {u.username or u.full_name}\n{message[:1000]}")
        except Exception:
            logger.exception("Could not forward feedback to bot owner")


async def save_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.effective_message.text or ""
    body = raw.partition(" ")[2].strip()
    if not body:
        await update.effective_message.reply_text("သိမ်းရန်: `/save ခေါင်းစဉ် | မှတ်သားလိုသောစာသား`", parse_mode="Markdown")
        return
    title, sep, content = body.partition("|")
    if not sep:
        title, content = "မှတ်စု", body
    title, content = title.strip()[:100], content.strip()[:2000]
    with db_connect() as conn:
        cur = conn.execute("INSERT INTO ck_saved_items(user_id,title,body,created_at) VALUES(?,?,?,?)",
                           (update.effective_user.id, title or "မှတ်စု", content, int(time.time())))
        conn.commit()
    await update.effective_message.reply_text(f"📌 သိမ်းပြီးပါပြီ။ ID: {cur.lastrowid}\nခေါင်းစဉ်: {title}")


async def saved_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with db_connect() as conn:
        rows = conn.execute("SELECT id,title,body FROM ck_saved_items WHERE user_id=? ORDER BY id DESC LIMIT 15",
                            (update.effective_user.id,)).fetchall()
    if not rows:
        await update.effective_message.reply_text("သိမ်းထားသောစာ မရှိသေးပါ။ /save ဖြင့် သိမ်းနိုင်ပါတယ်။")
        return
    lines = ["📚 **သင့်သိမ်းဆည်းထားသောစာများ**"]
    for row in rows:
        lines.append(f"\n#{row['id']} · **{row['title']}**\n{row['body'][:180]}")
    await update.effective_message.reply_text("\n".join(lines), parse_mode="Markdown")


async def delete_saved_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].isdigit():
        await update.effective_message.reply_text("ဖျက်ရန်: `/delsave ID`", parse_mode="Markdown")
        return
    with db_connect() as conn:
        cur = conn.execute("DELETE FROM ck_saved_items WHERE id=? AND user_id=?",
                           (int(context.args[0]), update.effective_user.id))
        conn.commit()
    await update.effective_message.reply_text("🗑️ ဖျက်ပြီးပါပြီ။" if cur.rowcount else "သင့်အကောင့်တွင် အဲဒီ ID မရှိပါ။")


async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    with db_connect() as conn:
        row = conn.execute("SELECT rules FROM ck_group_rules WHERE chat_id=?", (chat.id,)).fetchone()
    await update.effective_message.reply_text("📜 Group Rules\n\n" + (row["rules"] if row else "စည်းမျဉ်း မသတ်မှတ်ရသေးပါ။"))


async def setrules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat, user = update.effective_chat, update.effective_user
    if chat.type == "private":
        await update.effective_message.reply_text("ဒီ command ကို Group ထဲမှာသာ သုံးနိုင်ပါတယ်။")
        return
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status not in ("administrator", "creator"):
            await update.effective_message.reply_text("Group Admin များသာ Rules သတ်မှတ်နိုင်ပါတယ်။")
            return
    except Exception:
        await update.effective_message.reply_text("Admin အခွင့်အရေးကို စစ်ဆေးမရပါ။")
        return
    rules = (update.effective_message.text or "").partition(" ")[2].strip()
    if not rules or len(rules) > 3000:
        await update.effective_message.reply_text("အသုံးပြုပုံ: `/setrules Group စည်းမျဉ်းများ...` (အများဆုံး ၃၀၀၀ စာလုံး)", parse_mode="Markdown")
        return
    with db_connect() as conn:
        conn.execute("INSERT INTO ck_group_rules(chat_id,rules,updated_by,updated_at) VALUES(?,?,?,?) "
                     "ON CONFLICT(chat_id) DO UPDATE SET rules=excluded.rules,updated_by=excluded.updated_by,updated_at=excluded.updated_at",
                     (chat.id, rules, user.id, int(time.time())))
        conn.commit()
    await update.effective_message.reply_text("✅ Group Rules ကို သိမ်းပြီးပါပြီ။ /rules ဖြင့် ကြည့်နိုင်ပါတယ်။")


async def setwelcome_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat, user = update.effective_chat, update.effective_user
    if chat.type == "private":
        await update.effective_message.reply_text("ဒီ command ကို Group ထဲမှာသာ သုံးနိုင်ပါတယ်။")
        return
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status not in ("administrator", "creator"):
            await update.effective_message.reply_text("Group Admin များသာ Welcome သတ်မှတ်နိုင်ပါတယ်။")
            return
    except Exception:
        await update.effective_message.reply_text("Admin အခွင့်အရေးကို စစ်ဆေးမရပါ။")
        return
    welcome = (update.effective_message.text or "").partition(" ")[2].strip()
    if not welcome or len(welcome) > 1000:
        await update.effective_message.reply_text("အသုံးပြုပုံ: `/setwelcome မင်္ဂလာပါ {name}!`", parse_mode="Markdown")
        return
    with db_connect() as conn:
        conn.execute("INSERT INTO ck_group_welcome(chat_id,welcome,updated_by,updated_at) VALUES(?,?,?,?) "
                     "ON CONFLICT(chat_id) DO UPDATE SET welcome=excluded.welcome,updated_by=excluded.updated_by,updated_at=excluded.updated_at",
                     (chat.id, welcome, user.id, int(time.time())))
        conn.commit()
    await update.effective_message.reply_text("✅ Welcome Message သိမ်းပြီးပါပြီ။")


async def groupstats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type == "private":
        await update.effective_message.reply_text("ဒီ command ကို Group ထဲမှာ သုံးပါ။")
        return
    with db_connect() as conn:
        row = conn.execute("SELECT messages,members_seen FROM ck_group_stats WHERE chat_id=?", (chat.id,)).fetchone()
    if not row:
        await update.effective_message.reply_text("📊 စာရင်းစုဆောင်းနေဆဲပါ။")
        return
    await update.effective_message.reply_text(
        f"📊 **{chat.title or 'Group'} Stats**\n💬 Bot စတင်မှတ်တမ်းတင်ထားသော စာတို: {row['messages']}\n"
        f"👥 မှတ်တမ်းဝင်အသုံးပြုသူ: {row['members_seen']}\n\nမှတ်ချက်: Telegram Privacy Mode ကြောင့် Bot မမြင်ရသောစာတိုများ မပါနိုင်ပါ။",
        parse_mode="Markdown")


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    with db_connect() as conn:
        row = conn.execute("SELECT language,notifications,privacy FROM ck_user_settings WHERE user_id=?", (user.id,)).fetchone()
    if not row:
        await update.effective_message.reply_text(
            "⚙️ **CK BOT Settings**\nဘာသာစကား: မြန်မာ (Default)\nNotification: ဖွင့်ထားသည်\nPrivacy: ပုံမှန်\n\n"
            "ပြောင်းရန်: `/setlang my` သို့ `/setlang en` ၊ `/notifications on` သို့ `/notifications off`",
            parse_mode="Markdown")
    else:
        await update.effective_message.reply_text(
            f"⚙️ **CK BOT Settings**\nLanguage: {row['language']}\nNotifications: {'On' if row['notifications'] else 'Off'}\nPrivacy: {row['privacy']}",
            parse_mode="Markdown")


async def setlang_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.args[0].lower() if context.args else ""
    if lang not in ("my", "en"):
        await update.effective_message.reply_text("အသုံးပြုပုံ: `/setlang my` သို့ `/setlang en`", parse_mode="Markdown")
        return
    with db_connect() as conn:
        conn.execute("INSERT INTO ck_user_settings(user_id,language) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET language=excluded.language",
                     (update.effective_user.id, lang))
        conn.commit()
    await update.effective_message.reply_text("ဘာသာစကားကို မြန်မာအဖြစ် သတ်မှတ်ပြီးပါပြီ။" if lang == "my" else "Language set to English.")


async def notifications_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = context.args[0].lower() if context.args else ""
    if value not in ("on", "off"):
        await update.effective_message.reply_text("အသုံးပြုပုံ: `/notifications on` သို့ `/notifications off`", parse_mode="Markdown")
        return
    enabled = int(value == "on")
    with db_connect() as conn:
        conn.execute("INSERT INTO ck_user_settings(user_id,notifications) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET notifications=excluded.notifications",
                     (update.effective_user.id, enabled))
        conn.commit()
    await update.effective_message.reply_text("🔔 Notification ဖွင့်ပြီးပါပြီ။" if enabled else "🔕 Notification ပိတ်ပြီးပါပြီ။")


async def referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    me = await context.bot.get_me()
    link = f"https://t.me/{me.username}?start=ref_{user.id}"
    with db_connect() as conn:
        total = conn.execute("SELECT COUNT(*) AS n FROM ck_referrals WHERE inviter_id=?", (user.id,)).fetchone()["n"]
    await update.effective_message.reply_text(
        f"🔗 **သင့် Invite Link**\n\n`{link}`\n\n👥 အောင်မြင်သော Invite: {total}\n"
        "မိတ်ဆွေက Link ဖြင့် ပထမဆုံး /start လုပ်မှသာ မှတ်တမ်းဝင်ပါမယ်။",
        parse_mode="Markdown")


async def ck_help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "🌟 **CK BOT Community Hub**\n\n"
        "🌐 Search: `/appsearch`, `/gamesearch`, `/book`, `/moviesearch`, `/wallpaper`, `/videosearch`, `/education`, `/audiosearch`, `/docsearch`, `/fontsearch`\n"
        "👤 `/profile` — ကိုယ်ပိုင် Profile / Badge\n"
        "🎁 `/daily` — နေ့စဉ် အခမဲ့ဆု\n"
        "💎 `/points` — Points / XP\n"
        "🏆 `/leaderboard` — Top 10\n"
        "🎯 `/mission` — ယနေ့ Mission\n"
        "📩 `/feedback စာသား` — အကြံပြုချက်ပေးရန်\n"
        "📌 `/save ခေါင်းစဉ် | စာသား` — ကိုယ်ပိုင်မှတ်စုသိမ်းရန်\n"
        "📚 `/saved`၊ `/delsave ID` — မှတ်စုကြည့်/ဖျက်ရန်\n"
        "⚙️ `/settings`၊ `/setlang my|en`၊ `/notifications on|off`\n"
        "🔗 `/referral` — Invite Link\n\n"
        "👥 Group Admin: `/setrules စာသား`, `/rules`, `/setwelcome စာသား`, `/groupstats`\n\n"
        "အမှတ်များသည် Bot အတွင်းသုံး Virtual Points သာဖြစ်ပြီး ငွေကြေးတန်ဖိုးမရှိပါ။",
        parse_mode="Markdown")


async def ck_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.new_chat_members:
        return
    with db_connect() as conn:
        row = conn.execute("SELECT welcome FROM ck_group_welcome WHERE chat_id=?", (update.effective_chat.id,)).fetchone()
    # Welcome messages are OFF by default. Only send after a group admin configures one.
    if not row or not row["welcome"]:
        return
    template = row["welcome"]
    for member in msg.new_chat_members[:10]:
        if member.is_bot:
            continue
        safe_name = (member.full_name or "မိတ်ဆွေ")[:80]
        try:
            await msg.reply_text(template.replace("{name}", safe_name)[:1000])
        except Exception:
            logger.exception("Could not send configured welcome message in chat=%s", update.effective_chat.id)


async def ck_handle_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Record referral start payloads without granting repeat/self-referral rewards."""
    user = update.effective_user
    if not user or not context.args:
        return
    payload = context.args[0]
    if not payload.startswith("ref_"):
        return
    try:
        inviter = int(payload[4:])
    except ValueError:
        return
    if inviter == user.id or inviter <= 0:
        return
    with db_connect() as conn:
        cur = conn.execute("INSERT OR IGNORE INTO ck_referrals(invited_id,inviter_id,created_at) VALUES(?,?,?)",
                           (user.id, inviter, int(time.time())))
        conn.commit()
    if cur.rowcount:
        ck_award(inviter, points=25, xp=25)
        try:
            await context.bot.send_message(inviter, "🎉 မိတ်ဆွေတစ်ဦး သင့် Invite Link ဖြင့် CK BOT ကို စတင်အသုံးပြုပါပြီ။ +25 Points ရရှိပါတယ်။")
        except Exception:
            pass



# ------------------------- GROUP MODERATION COMMANDS -------------------------
def _ensure_moderation_tables():
    with db_connect() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS ck_group_warnings (chat_id INTEGER NOT NULL, user_id INTEGER NOT NULL, warned_by INTEGER NOT NULL, reason TEXT NOT NULL DEFAULT '', created_at INTEGER NOT NULL)")
        conn.commit()

async def _moderation_target(update):
    msg = update.effective_message
    if not msg or not msg.reply_to_message or not msg.reply_to_message.from_user:
        if msg:
            await msg.reply_text("အရေးယူလိုသူရဲ့ စာကို Reply လုပ်ပြီး Command ပို့ပါ။")
        return None
    target = msg.reply_to_message.from_user
    if target.is_bot or target.id == (update.effective_user.id if update.effective_user else 0):
        await msg.reply_text("ဒီအကောင့်ကို အရေးယူလို့မရပါ။")
        return None
    return target

async def _moderation_admin_check(update, context):
    msg, chat, user = update.effective_message, update.effective_chat, update.effective_user
    if not msg or not chat or chat.type == "private" or not user:
        if msg: await msg.reply_text("ဒီ Command ကို Group ထဲမှာသာ အသုံးပြုနိုင်ပါတယ်။")
        return False
    if not await _is_group_admin(chat.id, user.id, context):
        await msg.reply_text("⛔ Group Admin / Owner သာ အသုံးပြုနိုင်ပါတယ်။")
        return False
    if not await group_bot_is_admin(chat, context):
        await msg.reply_text("⚠️ Bot ကို Group Admin ခန့်ပြီး Ban Users နဲ့ Restrict Members ခွင့်ပေးပါ။")
        return False
    return True

async def ban_command(update, context):
    if not await _moderation_admin_check(update, context): return
    target = await _moderation_target(update)
    if not target: return
    chat = update.effective_chat
    if await _is_group_admin(chat.id, target.id, context):
        await update.effective_message.reply_text("⛔ Group Admin / Owner ကို Ban မလုပ်နိုင်ပါ။"); return
    try:
        await context.bot.ban_chat_member(chat.id, target.id)
        await update.effective_message.reply_text(f"🚫 {target.full_name} ကို Group မှ Ban လုပ်ပြီးပါပြီ။")
    except Exception as e:
        logger.exception("Ban failed")
        await update.effective_message.reply_text("Ban မအောင်မြင်ပါ။ Bot ရဲ့ Ban Users ခွင့်ကို စစ်ဆေးပါ။")

async def unban_command(update, context):
    if not await _moderation_admin_check(update, context): return
    target = await _moderation_target(update)
    if not target: return
    try:
        await context.bot.unban_chat_member(update.effective_chat.id, target.id, only_if_banned=True)
        await update.effective_message.reply_text(f"✅ {target.full_name} ရဲ့ Ban ကို ဖြုတ်ပြီးပါပြီ။")
    except Exception:
        logger.exception("Unban failed")
        await update.effective_message.reply_text("Unban မအောင်မြင်ပါ။ Bot ရဲ့ Ban Users ခွင့်ကို စစ်ဆေးပါ။")

async def kick_command(update, context):
    if not await _moderation_admin_check(update, context): return
    target = await _moderation_target(update)
    if not target: return
    chat = update.effective_chat
    if await _is_group_admin(chat.id, target.id, context):
        await update.effective_message.reply_text("⛔ Group Admin / Owner ကို Kick မလုပ်နိုင်ပါ။"); return
    try:
        await context.bot.ban_chat_member(chat.id, target.id)
        await context.bot.unban_chat_member(chat.id, target.id, only_if_banned=True)
        await update.effective_message.reply_text(f"👢 {target.full_name} ကို Group မှ ထုတ်ပယ်ပြီးပါပြီ။")
    except Exception:
        logger.exception("Kick failed")
        await update.effective_message.reply_text("Kick မအောင်မြင်ပါ။ Bot ရဲ့ Ban Users ခွင့်ကို စစ်ဆေးပါ။")

async def mute_command(update, context):
    if not await _moderation_admin_check(update, context): return
    target = await _moderation_target(update)
    if not target: return
    chat = update.effective_chat
    if await _is_group_admin(chat.id, target.id, context):
        await update.effective_message.reply_text("⛔ Group Admin / Owner ကို Mute မလုပ်နိုင်ပါ။"); return
    try:
        from telegram import ChatPermissions
        await context.bot.restrict_chat_member(chat.id, target.id, permissions=ChatPermissions(can_send_messages=False))
        await update.effective_message.reply_text(f"🔇 {target.full_name} ကို Mute လုပ်ပြီးပါပြီ။\nAdmin / Owner က /unmute လုပ်ပေးမှသာ စာပြန်ပို့နိုင်ပါမယ်။")
    except Exception:
        logger.exception("Mute failed")
        await update.effective_message.reply_text("Mute မအောင်မြင်ပါ။ Bot ရဲ့ Restrict Members ခွင့်ကို စစ်ဆေးပါ။")

async def unmute_command(update, context):
    if not await _moderation_admin_check(update, context): return
    target = await _moderation_target(update)
    if not target: return
    try:
        from telegram import ChatPermissions
        await context.bot.restrict_chat_member(update.effective_chat.id, target.id, permissions=ChatPermissions(can_send_messages=True, can_send_audios=True, can_send_documents=True, can_send_photos=True, can_send_videos=True, can_send_video_notes=True, can_send_voice_notes=True, can_send_polls=True, can_send_other_messages=True, can_add_web_page_previews=True))
        await update.effective_message.reply_text(f"🔊 {target.full_name} ကို Unmute လုပ်ပြီးပါပြီ။")
    except Exception:
        logger.exception("Unmute failed")
        await update.effective_message.reply_text("Unmute မအောင်မြင်ပါ။ Bot ရဲ့ Restrict Members ခွင့်ကို စစ်ဆေးပါ။")

async def warn_command(update, context):
    if not await _moderation_admin_check(update, context): return
    target = await _moderation_target(update)
    if not target: return
    if await _is_group_admin(update.effective_chat.id, target.id, context):
        await update.effective_message.reply_text("Admin / Owner ကို Warn မလုပ်နိုင်ပါ။"); return
    _ensure_moderation_tables()
    reason = " ".join(context.args).strip()[:300]
    with db_connect() as conn:
        conn.execute("INSERT INTO ck_group_warnings(chat_id,user_id,warned_by,reason,created_at) VALUES(?,?,?,?,?)", (update.effective_chat.id,target.id,update.effective_user.id,reason,int(time.time())))
        count = conn.execute("SELECT COUNT(*) FROM ck_group_warnings WHERE chat_id=? AND user_id=?", (update.effective_chat.id,target.id)).fetchone()[0]
        conn.commit()
    await update.effective_message.reply_text(f"⚠️ {target.full_name} ကို သတိပေးပြီးပါပြီ။ စုစုပေါင်း Warn: {count}" + (f"\nအကြောင်းပြချက်: {reason}" if reason else ""))

async def warnings_command(update, context):
    if not await _moderation_admin_check(update, context): return
    target = await _moderation_target(update)
    if not target: return
    _ensure_moderation_tables()
    with db_connect() as conn:
        rows = conn.execute("SELECT reason,created_at FROM ck_group_warnings WHERE chat_id=? AND user_id=? ORDER BY created_at DESC LIMIT 20", (update.effective_chat.id,target.id)).fetchall()
    if not rows:
        await update.effective_message.reply_text(f"{target.full_name} မှာ Warn မရှိသေးပါ။"); return
    lines = [f"{i}. {r['reason'] or 'အကြောင်းပြချက် မဖော်ပြထားပါ'}" for i,r in enumerate(rows,1)]
    await update.effective_message.reply_text(f"📋 {target.full_name} ရဲ့ Warn စာရင်း ({len(rows)})\n" + "\n".join(lines))

async def purge_command(update, context):
    if not await _moderation_admin_check(update, context): return
    msg = update.effective_message
    if not msg.reply_to_message:
        await msg.reply_text("ဖျက်လိုတဲ့ စာကို Reply လုပ်ပြီး /purge 20 လို့ ပို့ပါ။ (1 မှ 50)"); return
    try: count = int(context.args[0]) if context.args else 1
    except ValueError: count = 0
    if not 1 <= count <= 50:
        await msg.reply_text("အသုံးပြုပုံ: Reply လုပ်ပြီး /purge 1 မှ 50 အထိ"); return
    start_id = msg.reply_to_message.message_id
    deleted = 0
    for mid in range(start_id, start_id-count, -1):
        try:
            await context.bot.delete_message(msg.chat_id, mid); deleted += 1
        except Exception: pass
    try: await msg.delete()
    except Exception: pass
    await context.bot.send_message(msg.chat_id, f"🧹 စာ {deleted} ခု ဖျက်ပြီးပါပြီ။")



# ------------------------- CK SUPER COMMUNITY PACK -------------------------
# Quiet-by-default community features: commands only; no unsolicited chat replies.
def init_super_community_db():
    with db_connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS ck_group_suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL, username TEXT NOT NULL DEFAULT '',
            body TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open', created_at INTEGER NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS ck_group_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER NOT NULL,
            creator_id INTEGER NOT NULL, title TEXT NOT NULL, event_at TEXT NOT NULL DEFAULT '',
            details TEXT NOT NULL DEFAULT '', created_at INTEGER NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS ck_group_faq (
            id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER NOT NULL,
            keyword TEXT NOT NULL, answer TEXT NOT NULL, creator_id INTEGER NOT NULL,
            created_at INTEGER NOT NULL, UNIQUE(chat_id, keyword))""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ck_suggestions_chat ON ck_group_suggestions(chat_id, status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ck_events_chat ON ck_group_events(chat_id, created_at)")
        conn.execute("CREATE TABLE IF NOT EXISTS ck_ad_users (user_id INTEGER PRIMARY KEY, active INTEGER NOT NULL DEFAULT 1, updated_at INTEGER NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS ck_ad_groups (chat_id INTEGER PRIMARY KEY, title TEXT NOT NULL DEFAULT '', opted_in INTEGER NOT NULL DEFAULT 1, updated_at INTEGER NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS ck_ads (id INTEGER PRIMARY KEY AUTOINCREMENT, body TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'draft', created_at INTEGER NOT NULL, started_at INTEGER, source_chat_id INTEGER, source_message_id INTEGER)")
        ad_cols = {r['name'] for r in conn.execute("PRAGMA table_info(ck_ads)").fetchall()}
        if 'source_chat_id' not in ad_cols:
            conn.execute("ALTER TABLE ck_ads ADD COLUMN source_chat_id INTEGER")
        if 'source_message_id' not in ad_cols:
            conn.execute("ALTER TABLE ck_ads ADD COLUMN source_message_id INTEGER")
        # Ads are enabled by default for every group where the bot is present.
        conn.execute("UPDATE ck_ad_groups SET opted_in=1")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ck_ad_groups_enabled ON ck_ad_groups(opted_in)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ck_ad_users_active ON ck_ad_users(active)")
        conn.execute("CREATE TABLE IF NOT EXISTS ck_ad_delivery (ad_id INTEGER NOT NULL, chat_id INTEGER NOT NULL, delivered_at INTEGER NOT NULL, PRIMARY KEY(ad_id,chat_id))")
        conn.execute("CREATE TABLE IF NOT EXISTS ck_movies (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, media_type TEXT NOT NULL, file_id TEXT NOT NULL, added_by INTEGER NOT NULL, created_at INTEGER NOT NULL)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ck_movies_title ON ck_movies(title)")
        conn.commit()

async def _super_group_only(update):
    chat = update.effective_chat
    msg = update.effective_message
    if not chat or chat.type == "private":
        if msg: await msg.reply_text("ဒီစနစ်ကို Group ထဲမှာသာ အသုံးပြုနိုင်ပါတယ်။")
        return False
    return True

async def _super_admin(update, context):
    if not await _super_group_only(update): return False
    if not await _is_group_admin(update.effective_chat.id, update.effective_user.id, context):
        await update.effective_message.reply_text("⛔ Group Admin / Owner သာ အသုံးပြုနိုင်ပါတယ်။")
        return False
    return True

async def group_poll_command(update, context):
    """Create a native Telegram poll. Usage: /poll Question | Option 1 | Option 2"""
    if not await _super_admin(update, context): return
    raw = " ".join(context.args).strip()
    parts = [x.strip() for x in raw.split("|") if x.strip()]
    if len(parts) < 3 or len(parts) > 11:
        await update.effective_message.reply_text("အသုံးပြုပုံ: /poll မေးခွန်း | ရွေးချယ်မှု ၁ | ရွေးချယ်မှု ၂ (အများဆုံး ၁၀ ခု)")
        return
    try:
        await context.bot.send_poll(chat_id=update.effective_chat.id, question=parts[0][:300], options=[x[:100] for x in parts[1:]], is_anonymous=True)
    except Exception as exc:
        logger.warning("Group poll failed: %s", exc)
        await update.effective_message.reply_text("Poll မဖန်တီးနိုင်ပါ။ Bot ရဲ့ Group permission ကို စစ်ဆေးပါ။")

async def group_suggest_command(update, context):
    if not await _super_group_only(update): return
    body = " ".join(context.args).strip()
    if not body:
        await update.effective_message.reply_text("အသုံးပြုပုံ: /suggest Group အတွက် အကြံပြုချက်")
        return
    user = update.effective_user
    with db_connect() as conn:
        cur = conn.execute("INSERT INTO ck_group_suggestions(chat_id,user_id,username,body,created_at) VALUES(?,?,?,?,?)",
            (update.effective_chat.id, user.id, user.full_name[:100], body[:1500], int(time.time())))
        sid = cur.lastrowid
        conn.commit()
    await update.effective_message.reply_text(f"💡 အကြံပြုချက် #{sid} ကို သိမ်းဆည်းပြီးပါပြီ။ Admin များ ပြန်လည်ကြည့်ရှုနိုင်ပါတယ်။")

async def group_suggestions_command(update, context):
    if not await _super_admin(update, context): return
    with db_connect() as conn:
        rows = conn.execute("SELECT id,username,body FROM ck_group_suggestions WHERE chat_id=? AND status='open' ORDER BY id DESC LIMIT 15", (update.effective_chat.id,)).fetchall()
    if not rows:
        await update.effective_message.reply_text("ဖွင့်ထားတဲ့ အကြံပြုချက် မရှိသေးပါ။"); return
    lines = [f"#{r['id']} · {r['username']}: {r['body'][:180]}" for r in rows]
    await update.effective_message.reply_text("💡 Group အကြံပြုချက်များ\n\n" + "\n".join(lines))

async def group_event_command(update, context):
    if not await _super_admin(update, context): return
    raw = " ".join(context.args).strip()
    if not raw or "|" not in raw:
        await update.effective_message.reply_text("အသုံးပြုပုံ: /event အစီအစဉ်အမည် | နေ့ရက်/အချိန် | အသေးစိတ် (အသေးစိတ် optional)")
        return
    parts = [x.strip() for x in raw.split("|", 2)]
    title = parts[0][:120]
    when = parts[1][:100] if len(parts) > 1 else "မသတ်မှတ်ရသေး"
    details = parts[2][:700] if len(parts) > 2 else ""
    with db_connect() as conn:
        cur = conn.execute("INSERT INTO ck_group_events(chat_id,creator_id,title,event_at,details,created_at) VALUES(?,?,?,?,?,?)",
            (update.effective_chat.id, update.effective_user.id, title, when, details, int(time.time())))
        event_id = cur.lastrowid
        conn.commit()
    text = f"📅 Group Event #{event_id}\n🎉 {title}\n🕒 {when}"
    if details: text += f"\n📝 {details}"
    await context.bot.send_message(update.effective_chat.id, text)

async def group_events_command(update, context):
    if not await _super_group_only(update): return
    with db_connect() as conn:
        rows = conn.execute("SELECT id,title,event_at,details FROM ck_group_events WHERE chat_id=? ORDER BY id DESC LIMIT 10", (update.effective_chat.id,)).fetchall()
    if not rows:
        await update.effective_message.reply_text("📅 Group Event မရှိသေးပါ။"); return
    lines = []
    for r in rows:
        line = f"#{r['id']} · {r['title']} — {r['event_at']}"
        if r['details']: line += f"\n  {r['details']}"
        lines.append(line)
    await update.effective_message.reply_text("📅 နောက်ဆုံး Group Events\n\n" + "\n\n".join(lines))

async def group_faq_command(update, context):
    if not await _super_group_only(update): return
    raw = " ".join(context.args).strip()
    if not raw:
        with db_connect() as conn:
            rows = conn.execute("SELECT keyword,answer FROM ck_group_faq WHERE chat_id=? ORDER BY keyword LIMIT 30", (update.effective_chat.id,)).fetchall()
        if not rows:
            await update.effective_message.reply_text("FAQ မရှိသေးပါ။ Admin က /faqadd မေးခွန်းတို | အဖြေ ဖြင့် ထည့်နိုင်ပါတယ်။"); return
        await update.effective_message.reply_text("📚 Group FAQ\n\n" + "\n".join(f"• {r['keyword']} — {r['answer'][:180]}" for r in rows))
        return
    needle = raw.casefold()
    with db_connect() as conn:
        rows = conn.execute("SELECT keyword,answer FROM ck_group_faq WHERE chat_id=?", (update.effective_chat.id,)).fetchall()
    matches = [r for r in rows if r['keyword'].casefold() == needle]
    if not matches:
        await update.effective_message.reply_text("ဒီမေးခွန်းအတွက် FAQ မတွေ့ပါ။ /faq ဖြင့် စာရင်းကြည့်ပါ။"); return
    await update.effective_message.reply_text(matches[0]['answer'][:3000])

async def group_faqadd_command(update, context):
    if not await _super_admin(update, context): return
    raw = " ".join(context.args).strip()
    if "|" not in raw:
        await update.effective_message.reply_text("အသုံးပြုပုံ: /faqadd မေးခွန်းတို | အဖြေ")
        return
    keyword, answer = [x.strip() for x in raw.split("|", 1)]
    if not keyword or not answer:
        await update.effective_message.reply_text("မေးခွန်းနဲ့ အဖြေ နှစ်ခုလုံး ထည့်ပါ။"); return
    with db_connect() as conn:
        conn.execute("INSERT INTO ck_group_faq(chat_id,keyword,answer,creator_id,created_at) VALUES(?,?,?,?,?) ON CONFLICT(chat_id,keyword) DO UPDATE SET answer=excluded.answer,creator_id=excluded.creator_id,created_at=excluded.created_at",
            (update.effective_chat.id, keyword[:100], answer[:2500], update.effective_user.id, int(time.time())))
        conn.commit()
    await update.effective_message.reply_text("✅ FAQ ကို သိမ်းဆည်းပြီးပါပြီ။")

async def group_faqdel_command(update, context):
    if not await _super_admin(update, context): return
    keyword = " ".join(context.args).strip()
    if not keyword:
        await update.effective_message.reply_text("အသုံးပြုပုံ: /faqdel မေးခွန်းတို"); return
    with db_connect() as conn:
        cur = conn.execute("DELETE FROM ck_group_faq WHERE chat_id=? AND keyword=? COLLATE NOCASE", (update.effective_chat.id, keyword))
        conn.commit()
    await update.effective_message.reply_text("🗑️ FAQ ဖျက်ပြီးပါပြီ။" if cur.rowcount else "FAQ မတွေ့ပါ။")

async def group_activity_command(update, context):
    if not await _super_group_only(update): return
    with db_connect() as conn:
        rows = conn.execute("SELECT user_id,SUM(messages) AS total FROM ck_user_message_daily GROUP BY user_id ORDER BY total DESC LIMIT 10", ()).fetchall()
    if not rows:
        await update.effective_message.reply_text("📊 Activity မှတ်တမ်း မရှိသေးပါ။"); return
    await update.effective_message.reply_text("📊 Bot အသုံးပြုမှု Top 10 (မှတ်တမ်းရှိသည့်နေ့များ စုစုပေါင်း)\n\n" + "\n".join(f"{i}. User {r['user_id']} — {r['total']}" for i,r in enumerate(rows,1)))

async def group_hub_command(update, context):
    await update.effective_message.reply_text(
        "🌟 CK BOT Group Hub\n\n"
        "🗳️ /poll မေးခွန်း | ရွေးချယ်မှု ၁ | ရွေးချယ်မှု ၂\n"
        "💡 /suggest အကြံပြုချက်\n"
        "📋 /suggestions — Admin အတွက် အကြံပြုချက်စာရင်း\n"
        "📅 /event အမည် | အချိန် | အသေးစိတ် — Admin\n"
        "🗓️ /events — Event စာရင်း\n"
        "📚 /faq — FAQ စာရင်း\n"
        "🔎 /faq မေးခွန်းတို — FAQ ရှာရန်\n"
        "➕ /faqadd မေးခွန်းတို | အဖြေ — Admin\n"
        "➖ /faqdel မေးခွန်းတို — Admin\n"
        "📊 /activity — Group Activity Top 10\n\n"
        "ဒီစနစ်တွေက Command ခေါ်မှသာ တုံ့ပြန်ပါတယ်။")



async def ad_track_group_membership(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Register every group when the bot is added; never requires /start in groups."""
    member_update = update.my_chat_member
    chat = member_update.chat if member_update else None
    if not chat or chat.type not in ("group", "supergroup"):
        return
    new_status = member_update.new_chat_member.status
    old_status = member_update.old_chat_member.status
    now = int(time.time())
    if new_status in ("member", "administrator"):
        with db_connect() as conn:
            # New groups are enabled automatically. Existing explicit opt-outs stay disabled.
            conn.execute(
                "INSERT OR IGNORE INTO ck_ad_groups(chat_id,title,opted_in,updated_at) VALUES(?,?,1,?)",
                (chat.id, chat.title or "", now),
            )
            conn.execute("UPDATE ck_ad_groups SET title=?,updated_at=? WHERE chat_id=?",
                         (chat.title or "", now, chat.id))
            conn.commit()
        logger.info("Ad audience group registered: %s (%s)", chat.id, chat.title)
    elif old_status in ("member", "administrator", "restricted") and new_status in ("left", "kicked"):
        with db_connect() as conn:
            conn.execute("UPDATE ck_ad_groups SET opted_in=0,updated_at=? WHERE chat_id=?", (now, chat.id))
            conn.commit()
        logger.info("Ad audience group disabled after bot removal: %s", chat.id)


async def ad_track_group_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fallback registration for groups already containing the bot; preserves opt-outs."""
    chat = update.effective_chat
    if not chat or chat.type not in ("group", "supergroup"):
        return
    now = int(time.time())
    try:
        with db_connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO ck_ad_groups(chat_id,title,opted_in,updated_at) VALUES(?,?,1,?)",
                (chat.id, chat.title or "", now),
            )
            conn.execute("UPDATE ck_ad_groups SET title=?,updated_at=? WHERE chat_id=?",
                         (chat.title or "", now, chat.id))
            conn.commit()
    except Exception:
        logger.exception("Could not register ad audience group: %s", chat.id)


# ------------------------- OWNER ADVERTISING SYSTEM -------------------------
def _ad_owner(update):
    return bool(BOT_OWNER_ID and update.effective_user and update.effective_user.id == BOT_OWNER_ID)

async def ad_help_command(update, context):
    if not _ad_owner(update):
        return await update.effective_message.reply_text("⛔ Bot ပိုင်ရှင်သာ အသုံးပြုနိုင်ပါတယ်။")
    await update.effective_message.reply_text(
        "📢 CK BOT ကြော်ငြာစနစ် (Owner Only)\n\n"
        "/adadd စာသား — စာသားကြော်ငြာအသစ်\n"
        "Media post တင်ရန် ဓာတ်ပုံ/ဗီဒီယို/ဖိုင်ကို ပို့ပြီး Caption သို့မဟုတ် စာသားနဲ့ /adadd ကို Reply လုပ်ပါ။\n"
        "/adpreview — နောက်ဆုံးကြော်ငြာ Preview\n/adedit စာသား — စာသားပြင်ရန်\n"
        "/addel — နောက်ဆုံး Draft ဖျက်ရန်\n/adstart — ကြော်ငြာပို့ရန်\n/adstop — ပို့ခြင်းရပ်ရန်\n/adstats — ပို့ဆောင်မှုစာရင်း\n\n"
        "Bot ကို Group ထဲထည့်လိုက်တာနဲ့ Group ကို အလိုအလျောက် မှတ်သားပြီး ကြော်ငြာပို့ပါမယ်။ "
        "Group ကြော်ငြာပိတ်/ဖွင့် Command မရှိပါ။ Private အသုံးပြုသူက /start နှိပ်ထားရပါမယ်။")


async def ad_add_command(update, context):
    if not _ad_owner(update):
        return await update.effective_message.reply_text("⛔ Owner Only")
    msg = update.effective_message
    reply = msg.reply_to_message
    body = " ".join(context.args).strip()
    source_chat_id = source_message_id = None
    if reply:
        # Save the original post by Telegram message reference, preserving media, caption and formatting.
        source_chat_id, source_message_id = reply.chat_id, reply.message_id
        body = (reply.text or reply.caption or "").strip()
    if not body and not source_message_id:
        return await msg.reply_text("အသုံးပြုပုံ: /adadd ကြော်ငြာစာသား (သို့) ကြော်ငြာ Post ကို Reply လုပ်ပြီး /adadd ပို့ပါ။")
    with db_connect() as conn:
        cur = conn.execute(
            "INSERT INTO ck_ads(body,status,created_at,source_chat_id,source_message_id) VALUES(?,'draft',?,?,?)",
            (body[:3500], int(time.time()), source_chat_id, source_message_id),
        )
        aid = cur.lastrowid
        conn.commit()
    await msg.reply_text(f"✅ ကြော်ငြာ #{aid} ကို Draft အဖြစ်သိမ်းပြီးပါပြီ။ /adpreview ဖြင့်စစ်ပြီး /adstart နဲ့ ပို့နိုင်ပါတယ်။")


async def _ad_latest():
    with db_connect() as conn:
        return conn.execute("SELECT * FROM ck_ads ORDER BY id DESC LIMIT 1").fetchone()


async def ad_preview_command(update, context):
    if not _ad_owner(update):
        return await update.effective_message.reply_text("⛔ Owner Only")
    row = await _ad_latest()
    if not row:
        return await update.effective_message.reply_text("ကြော်ငြာမရှိသေးပါ။")
    if row['source_chat_id'] and row['source_message_id']:
        try:
            await context.bot.copy_message(chat_id=update.effective_chat.id, from_chat_id=row['source_chat_id'], message_id=row['source_message_id'])
            return await update.effective_message.reply_text(f"📢 Preview #{row['id']} · {row['status']}")
        except Exception as exc:
            logger.warning("Ad preview copy failed: %s", exc)
    await update.effective_message.reply_text(f"📢 Preview #{row['id']} · {row['status']}\n\n{row['body'] or '[Media post reference unavailable]'}")


async def ad_edit_command(update, context):
    if not _ad_owner(update):
        return await update.effective_message.reply_text("⛔ Owner Only")
    body = " ".join(context.args).strip()
    if not body:
        return await update.effective_message.reply_text("အသုံးပြုပုံ: /adedit ကြော်ငြာစာသားအသစ်")
    with db_connect() as conn:
        row = conn.execute("SELECT id,status FROM ck_ads ORDER BY id DESC LIMIT 1").fetchone()
        if not row:
            return await update.effective_message.reply_text("ကြော်ငြာမရှိသေးပါ။")
        if row['status'] == 'sending':
            return await update.effective_message.reply_text("လက်ရှိပို့နေသော ကြော်ငြာကို မပြင်နိုင်ပါ။ /adstop အရင်လုပ်ပါ။")
        conn.execute("UPDATE ck_ads SET body=?,source_chat_id=NULL,source_message_id=NULL,status='draft' WHERE id=?", (body[:3500], row['id']))
        conn.commit()
    await update.effective_message.reply_text("✅ နောက်ဆုံးကြော်ငြာကို စာသား Draft အဖြစ် ပြင်ဆင်ပြီးပါပြီ။")


async def ad_delete_command(update, context):
    if not _ad_owner(update):
        return await update.effective_message.reply_text("⛔ Owner Only")
    with db_connect() as conn:
        row = conn.execute("SELECT id,status FROM ck_ads ORDER BY id DESC LIMIT 1").fetchone()
        if not row:
            return await update.effective_message.reply_text("ကြော်ငြာမရှိသေးပါ။")
        if row['status'] == 'sending':
            return await update.effective_message.reply_text("ပို့နေဆဲကြော်ငြာကို မဖျက်နိုင်ပါ။ /adstop အရင်လုပ်ပါ။")
        conn.execute("DELETE FROM ck_ad_delivery WHERE ad_id=?", (row['id'],))
        conn.execute("DELETE FROM ck_ads WHERE id=?", (row['id'],))
        conn.commit()
    await update.effective_message.reply_text("🗑️ နောက်ဆုံးကြော်ငြာကို ဖျက်ပြီးပါပြီ။")


async def ad_start_command(update, context):
    if not _ad_owner(update):
        return await update.effective_message.reply_text("⛔ Owner Only")
    # Atomic lock prevents two simultaneous /adstart commands from duplicating a campaign.
    with db_connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        ad = conn.execute("SELECT * FROM ck_ads ORDER BY id DESC LIMIT 1").fetchone()
        if not ad:
            conn.rollback()
            return await update.effective_message.reply_text("ပို့ရန်ကြော်ငြာမရှိသေးပါ။ /adadd ဖြင့်အရင်ထည့်ပါ။")
        if ad['status'] == 'sending':
            conn.rollback()
            return await update.effective_message.reply_text("ဒီကြော်ငြာကို ပို့နေပြီးဖြစ်ပါတယ်။ /adstats နဲ့ အခြေအနေကြည့်ပါ။")
        users = conn.execute("SELECT user_id AS chat_id FROM ck_ad_users").fetchall()
        groups = conn.execute("SELECT chat_id FROM ck_ad_groups").fetchall()
        targets = list(dict.fromkeys(int(x['chat_id']) for x in (users + groups)))
        conn.execute("UPDATE ck_ads SET status='sending',started_at=? WHERE id=?", (int(time.time()), ad['id']))
        conn.commit()
    sent = failed = skipped = 0
    for cid in targets:
        with db_connect() as conn:
            state = conn.execute("SELECT status FROM ck_ads WHERE id=?", (ad['id'],)).fetchone()
            already = conn.execute("SELECT 1 FROM ck_ad_delivery WHERE ad_id=? AND chat_id=?", (ad['id'], cid)).fetchone()
        if not state or state['status'] == 'stopped':
            break
        if already:
            skipped += 1
            continue
        try:
            if ad['source_chat_id'] and ad['source_message_id']:
                await context.bot.copy_message(chat_id=cid, from_chat_id=ad['source_chat_id'], message_id=ad['source_message_id'])
            else:
                await context.bot.send_message(chat_id=cid, text=ad['body'], disable_web_page_preview=True)
            sent += 1
            with db_connect() as conn:
                conn.execute("INSERT OR IGNORE INTO ck_ad_delivery(ad_id,chat_id,delivered_at) VALUES(?,?,?)", (ad['id'], cid, int(time.time())))
                conn.commit()
        except Exception as exc:
            failed += 1
            error_text = str(exc).lower()
            logger.warning("Ad delivery failed chat=%s: %s", cid, exc)
            # A private user who blocked the bot is removed from the active audience.
            if cid > 0 and any(k in error_text for k in ("bot was blocked", "user is deactivated", "chat not found")):
                with db_connect() as conn:
                    conn.execute("UPDATE ck_ad_users SET active=0,updated_at=? WHERE user_id=?", (int(time.time()), cid))
                    conn.commit()
            # Do not silently keep groups where bot was removed or cannot post.
            if cid < 0 and any(k in error_text for k in ("bot was kicked", "chat not found", "not enough rights")):
                with db_connect() as conn:
                    conn.execute("UPDATE ck_ad_groups SET opted_in=0,updated_at=? WHERE chat_id=?", (int(time.time()), cid))
                    conn.commit()
        await asyncio.sleep(0.08)
    with db_connect() as conn:
        state = conn.execute("SELECT status FROM ck_ads WHERE id=?", (ad['id'],)).fetchone()
        if state and state['status'] == 'sending':
            conn.execute("UPDATE ck_ads SET status='sent' WHERE id=?", (ad['id'],))
        conn.commit()
        pending = conn.execute("SELECT COUNT(*) n FROM ck_ad_delivery WHERE ad_id=?", (ad['id'],)).fetchone()['n']
    final_state = state['status'] if state else 'unknown'
    await update.effective_message.reply_text(
        f"📢 ကြော်ငြာ #{ad['id']} အခြေအနေ: {final_state}\n"
        f"ပစ်မှတ်: {len(targets)}\nအောင်မြင်: {sent}\nမအောင်မြင်: {failed}\nပြီးသား/ကျော်သွား: {skipped}\n"
        f"ဒီကြော်ငြာအတွက် စုစုပေါင်းပို့ပြီး: {pending}"
    )


async def ad_stop_command(update, context):
    if not _ad_owner(update):
        return await update.effective_message.reply_text("⛔ Owner Only")
    with db_connect() as conn:
        row = conn.execute("SELECT id FROM ck_ads WHERE status='sending' ORDER BY id DESC LIMIT 1").fetchone()
        if row:
            conn.execute("UPDATE ck_ads SET status='stopped' WHERE id=?", (row['id'],))
            conn.commit()
    await update.effective_message.reply_text("⏹️ ကြော်ငြာပို့ခြင်း ရပ်တန့်ရန် အမိန့်ပေးပြီးပါပြီ။ လက်ရှိပို့နေသော Message တစ်ခု ပြီးဆုံးပြီးနောက် ရပ်ပါမယ်။" if row else "လက်ရှိ ပို့နေသော ကြော်ငြာမရှိပါ။")


async def ad_stats_command(update, context):
    if not _ad_owner(update):
        return await update.effective_message.reply_text("⛔ Owner Only")
    with db_connect() as conn:
        users = conn.execute("SELECT COUNT(*) n FROM ck_ad_users WHERE active=1").fetchone()['n']
        groups = conn.execute("SELECT COUNT(*) n FROM ck_ad_groups WHERE opted_in=1").fetchone()['n']
        ad = conn.execute("SELECT id,status FROM ck_ads ORDER BY id DESC LIMIT 1").fetchone()
        sent = failed = 0
        if ad:
            sent = conn.execute("SELECT COUNT(*) n FROM ck_ad_delivery WHERE ad_id=?", (ad['id'],)).fetchone()['n']
    await update.effective_message.reply_text(
        f"📊 CK BOT ကြော်ငြာစာရင်း\nPrivate လက်ခံသူ: {users}\nBot ရှိသော Group: {groups}\n"
        f"နောက်ဆုံး Ad: {('#'+str(ad['id'])+' · '+ad['status']) if ad else 'မရှိသေးပါ'}\n"
        f"အောင်မြင်ပို့ထား: {sent}\nမအောင်မြင်မှု: သီးခြား log ထဲတွင် စစ်ဆေးပါ။"
    )


async def ad_optin_command(update, context):
    chat = update.effective_chat
    if not chat or chat.type == 'private':
        return await update.effective_message.reply_text("Group ထဲမှာသာ အသုံးပြုနိုင်ပါတယ်။")
    if not await _is_group_admin(chat.id, update.effective_user.id, context):
        return await update.effective_message.reply_text("⛔ Group Admin/Owner သာ ခွင့်ပြုနိုင်ပါတယ်။")
    with db_connect() as conn:
        conn.execute("INSERT INTO ck_ad_groups(chat_id,title,opted_in,updated_at) VALUES(?,?,1,?) ON CONFLICT(chat_id) DO UPDATE SET title=excluded.title,opted_in=1,updated_at=excluded.updated_at", (chat.id, chat.title or '', int(time.time())))
        conn.commit()
    await update.effective_message.reply_text("✅ ဒီ Group မှာ ကြော်ငြာပြန်ဖွင့်ပြီးပါပြီ။")


async def ad_optout_command(update, context):
    chat = update.effective_chat
    if not chat or chat.type == 'private':
        return await update.effective_message.reply_text("Group ထဲမှာသာ အသုံးပြုနိုင်ပါတယ်။")
    if not await _is_group_admin(chat.id, update.effective_user.id, context):
        return await update.effective_message.reply_text("⛔ Group Admin/Owner သာ ခွင့်ပြုနိုင်ပါတယ်။")
    with db_connect() as conn:
        conn.execute("UPDATE ck_ad_groups SET opted_in=0,updated_at=? WHERE chat_id=?", (int(time.time()), chat.id))
        conn.commit()
    await update.effective_message.reply_text("🔕 ဒီ Group မှာ ကြော်ငြာပို့ခြင်း ပိတ်ပြီးပါပြီ။")


async def ad_startgroup_command(update, context):
    await ad_optin_command(update, context)


async def ad_stopgroup_command(update, context):
    await ad_optout_command(update, context)


async def ad_stopme_command(update, context):
    if not update.effective_user or update.effective_chat.type != 'private':
        return await update.effective_message.reply_text("Private Chat ထဲမှာသာ အသုံးပြုပါ။")
    with db_connect() as conn:
        conn.execute("UPDATE ck_ad_users SET active=0,updated_at=? WHERE user_id=?", (int(time.time()), update.effective_user.id))
        conn.commit()
    await update.effective_message.reply_text("🔕 ကြော်ငြာလက်ခံမှု ပိတ်ပြီးပါပြီ။ ပြန်ဖွင့်ရန် /start ကို ထပ်နှိပ်ပါ။")



# ------------------------- INTERNET SEARCH & SEND (LICENSE-AWARE) -------------------------
SEARCH_COMMANDS = {
    "appsearch": ("📱 App", "app_github"),
    "gamesearch": ("🎮 Game", "game_github"),
    "book": ("📚 Public-domain Book", "books"),
    "moviesearch": ("🎬 Movie", "archive_movie"),
    "wallpaper": ("🖼️ Wallpaper", "commons"),
    "videosearch": ("🎞️ Video", "archive_video"),
    "education": ("🎓 Education", "openalex"),
    "audiosearch": ("🎧 Podcast / Audio", "podcast"),
    "docsearch": ("📄 Document / Template", "document_github"),
    "fontsearch": ("🔤 Font / Icon", "font_github"),
}


def _search_json(url, timeout=12):
    """Fetch JSON only from fixed public catalog endpoints."""
    req = urllib.request.Request(url, headers={
        "User-Agent": "CKHelpBot/2.1 (Telegram catalog search)",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"Catalog HTTP {response.status}")
        raw = response.read(1_500_000)
    return json.loads(raw.decode("utf-8", "replace"))


def _api_url(base, params):
    return base + "?" + urllib.parse.urlencode(params, doseq=True)


def _brave_web_search(kind, query, count=8):
    """Search the wider public web through Brave Search API. Results are links, not proof of download rights."""
    if not BRAVE_API_KEY:
        return []
    category_terms = {
        "app_github": "Android app official website download",
        "game_github": "game official website download",
        "books": "book legal ebook library public domain",
        "archive_movie": "movie film official legal watch download",
        "commons": "wallpaper image open license",
        "archive_video": "video open license legal download",
        "openalex": "education learning open educational resources",
        "podcast": "podcast official audio episodes",
        "document_github": "document template official free download",
        "font_github": "font icon official open source license",
    }
    q = (query + " " + category_terms.get(kind, ""))[:400]
    url = _api_url("https://api.search.brave.com/res/v1/web/search", {
        "q": q, "count": min(max(int(count), 1), 20), "safesearch": "strict",
        "country": "ALL", "search_lang": "en",
    })
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "X-Subscription-Token": BRAVE_API_KEY,
        "User-Agent": "CKHelpBot/2.2",
    })
    with urllib.request.urlopen(req, timeout=20) as response:
        if response.status != 200:
            raise RuntimeError(f"Brave Search HTTP {response.status}")
        payload = json.loads(response.read(2_000_000).decode("utf-8", "replace"))
    out = []
    for item in (payload.get("web") or {}).get("results", []):
        link = item.get("url")
        if not link or not link.startswith("https://"):
            continue
        out.append({
            "title": item.get("title") or "Web result",
            "detail": (item.get("description") or "")[:220],
            "url": link,
            "license": "Web search result — check source terms and reuse rights",
            "source": "Brave Web Search",
        })
    return out


def _free_web_search(kind, query, count=8):
    """Search via public SearXNG instances; no API key required.
    Public instances can rate-limit or disable JSON, so rotate through several.
    """
    category_terms = {
        "app_github": "Android application official download",
        "game_github": "video game official download",
        "books": "legal ebook public domain library",
        "archive_movie": "film legal public domain watch",
        "commons": "wallpaper open license image",
        "archive_video": "open licensed video download",
        "openalex": "free educational resources",
        "podcast": "podcast official audio episodes",
        "document_github": "free document template",
        "font_github": "open source font icon",
    }
    q = (query + " " + category_terms.get(kind, ""))[:400]
    # These instances are listed as online by the community instance monitor.
    # They are public community services, not guaranteed uptime endpoints.
    instances = [
        "https://www.isci.si",
        "https://searx.ononoki.org",
        "https://libresearch.space",
        "https://baresearch.org",
        "https://search.pi.vps.pw",
        "https://searxng.site",
        "https://searx.tiekoetter.com",
    ]
    errors = []
    for base in instances:
        try:
            url = _api_url(base.rstrip("/") + "/search", {
                "q": q, "format": "json", "safesearch": 2, "language": "en",
            })
            req = urllib.request.Request(url, headers={
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 (compatible; CKHelpBot/2.3)",
            })
            with urllib.request.urlopen(req, timeout=12) as response:
                if response.status != 200:
                    raise RuntimeError(f"HTTP {response.status}")
                raw = response.read(1_500_000)
            payload = json.loads(raw.decode("utf-8", "replace"))
            out = []
            for item in payload.get("results", [])[:count]:
                link = item.get("url")
                if not link or not link.startswith("https://"):
                    continue
                out.append({
                    "title": item.get("title") or "Web result",
                    "detail": (item.get("content") or "")[:220],
                    "url": link,
                    "license": "Web search result — reuse/download rights must be checked at source",
                    "source": "SearXNG",
                })
            if out:
                return out
        except Exception as exc:
            errors.append(f"{base}: {type(exc).__name__}")
            logger.info("SearXNG instance unavailable %s: %s", base, exc)
    # DuckDuckGo HTML endpoint fallback; it is not a stable public API.
    try:
        url = _api_url("https://html.duckduckgo.com/html/", {"q": q})
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; CKHelpBot/2.3)",
            "Accept": "text/html",
        })
        with urllib.request.urlopen(req, timeout=12) as response:
            html = response.read(1_500_000).decode("utf-8", "replace")
        parser = _DuckDuckGoResultParser()
        parser.feed(html)
        if parser.results:
            return parser.results[:count]
    except Exception as exc:
        logger.info("DuckDuckGo fallback unavailable: %s", exc)
    raise RuntimeError("No free public search endpoint responded: " + "; ".join(errors[-3:]))


class _DuckDuckGoResultParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results = []
        self._anchor = False
        self._href = ""
        self._text = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            attrs = dict(attrs)
            href = attrs.get("href", "")
            if "result__a" in attrs.get("class", "") and href.startswith("http"):
                self._anchor = True
                self._href = href
                self._text = []

    def handle_data(self, data):
        if self._anchor:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._anchor:
            title = " ".join(" ".join(self._text).split())
            if title and self._href:
                self.results.append({
                    "title": title[:180],
                    "detail": "DuckDuckGo search result",
                    "url": self._href,
                    "license": "Web search result — check source reuse/download terms",
                    "source": "DuckDuckGo",
                })
            self._anchor = False
            self._href = ""
            self._text = []


def _internet_catalog_search(kind, query):
    q = query.strip()[:120]
    if kind == "books":
        out = []
        # First try the public-domain Gutenberg catalog for downloadable files.
        try:
            data = _search_json(_api_url("https://gutendex.com/books/", {"search": q}), timeout=18)
            for item in data.get("results", [])[:6]:
                formats = item.get("formats") or {}
                link = (formats.get("application/epub+zip")
                        or formats.get("text/plain; charset=utf-8")
                        or formats.get("text/plain"))
                out.append({
                    "title": item.get("title", "Untitled"),
                    "detail": ", ".join(a.get("name", "") for a in item.get("authors", [])[:2]) or "Project Gutenberg",
                    "url": item.get("url") or "https://www.gutenberg.org/",
                    "file_url": link if link and link.startswith("https://") else None,
                    "license": "Project Gutenberg public-domain catalog; check local copyright status",
                })
        except Exception:
            logger.warning("Gutendex unavailable; trying Open Library", exc_info=True)
        # Metadata fallback means copyrighted titles can still be found without distributing copies.
        if not out:
            data = _search_json(_api_url("https://openlibrary.org/search.json", {
                "q": q, "limit": 8, "fields": "key,title,author_name,first_publish_year,ebook_access,ia"
            }), timeout=18)
            for item in data.get("docs", [])[:8]:
                key = item.get("key")
                if not key:
                    continue
                access = item.get("ebook_access", "no_ebook")
                out.append({
                    "title": item.get("title", "Book"),
                    "detail": ", ".join(item.get("author_name", [])[:2]) + (f" | {item.get('first_publish_year')}" if item.get("first_publish_year") else ""),
                    "url": "https://openlibrary.org" + key,
                    "license": "Catalog information only; availability and reuse rights depend on the publisher/library",
                })
        return out
    if kind in ("archive_movie", "archive_video"):
        # Internet Archive stores both films and other video under mediatype:movies.
        # Use distinct fields to avoid returning the same generic result set.
        if kind == "archive_movie":
            query_expr = f'title:"{q}" AND mediatype:movies'
        else:
            query_expr = f'description:"{q}" AND mediatype:movies'
        data = _search_json(_api_url("https://archive.org/advancedsearch.php", {
            "q": query_expr, "fl[]": ["identifier", "title", "year", "licenseurl", "mediatype"],
            "rows": 8, "page": 1, "output": "json"
        }))
        out=[]
        for item in data.get("response", {}).get("docs", []):
            lic=(item.get("licenseurl") or "").lower()
            # Only show results whose metadata explicitly signals a reuse license/public-domain.
            if "creativecommons.org/publicdomain" not in lic and "creativecommons.org/licenses" not in lic:
                continue
            ident=item.get("identifier")
            if ident:
                out.append({"title":item.get("title", ident), "detail":str(item.get("year", "")), "url":f"https://archive.org/details/{urllib.parse.quote(ident)}", "license":item.get("licenseurl")})
        return out
    if kind == "commons":
        data = _search_json(_api_url("https://commons.wikimedia.org/w/api.php", {
            "action":"query", "generator":"search", "gsrsearch":f'filetype:bitmap {q}',
            "gsrnamespace":6, "gsrlimit":8, "prop":"imageinfo", "iiprop":"url|extmetadata",
            "iiurlwidth":1200, "format":"json", "origin":"*"
        }))
        out=[]
        for item in (data.get("query",{}).get("pages",{}) or {}).values():
            info=(item.get("imageinfo") or [{}])[0]
            meta=info.get("extmetadata") or {}
            lic=(meta.get("LicenseShortName") or {}).get("value", "License details on Wikimedia Commons")
            out.append({"title":item.get("title", "Image"), "detail":f"License: {lic}", "url":item.get("title") and ("https://commons.wikimedia.org/wiki/" + urllib.parse.quote(item.get("title").replace(" ", "_"))), "file_url":info.get("thumburl") or info.get("url"), "license": "Open license; verify attribution/terms on file page"})
        return out
    if kind == "openalex":
        data = _search_json(_api_url("https://api.openalex.org/works", {"search":q, "per-page":8, "select":"id,display_name,publication_year,doi,open_access,biblio"}))
        out=[]
        for item in data.get("results",[]):
            oa=item.get("open_access") or {}
            url=oa.get("oa_url") or item.get("doi") or item.get("id")
            if url:
                out.append({"title":item.get("display_name","Research work"), "detail":f"Year: {item.get('publication_year') or 'n/a'} | Open access: {'Yes' if oa.get('is_oa') else 'Not confirmed'}", "url":url, "license":"Check publisher/repository license before reuse"})
        return out
    if kind == "podcast":
        data = _search_json(_api_url("https://itunes.apple.com/search", {"term":q,"entity":"podcast","limit":8}))
        out=[]
        for item in data.get("results",[]):
            out.append({"title":item.get("collectionName", "Podcast"), "detail":item.get("artistName", ""), "url":item.get("collectionViewUrl"), "license":"Podcast directory listing; use publisher's official episode/download options"})
        return out
    # Separate GitHub search intents so each command returns relevant repositories.
    search_terms = {
        "app_github": f'({q}) (android OR app OR application) in:name,description,readme',
        "game_github": f'({q}) (game OR gaming) in:name,description,readme',
        "document_github": f'({q}) (template OR document OR pdf OR docx) in:name,description,readme',
        "font_github": f'({q}) (font OR icon OR typography) in:name,description,readme',
    }
    topic = search_terms.get(kind)
    if not topic:
        raise ValueError(f"Unknown catalog category: {kind}")
    data = _search_json(_api_url("https://api.github.com/search/repositories", {"q":topic, "sort":"stars", "order":"desc", "per_page":8}))
    out=[]
    for item in data.get("items",[]):
        license_name=((item.get("license") or {}).get("spdx_id") or "License not declared")
        repo_url = item.get("html_url")
        downloadable = ("https://codeload.github.com/" + item.get("full_name", "") + "/zip/refs/heads/" + urllib.parse.quote(item.get("default_branch") or "main")) if license_name not in ("License not declared", "NOASSERTION") else None
        out.append({"title":item.get("full_name", "GitHub project"), "detail":(item.get("description") or "")[:150], "url":repo_url, "file_url":downloadable, "license":license_name})
    return out



# Direct-send policy: only fetch from known catalog hosts and keep uploads small.
DIRECT_SEND_MAX_BYTES = 45 * 1024 * 1024
DIRECT_SEND_HOSTS = {
    "gutendex.com", "www.gutenberg.org", "gutenberg.org",
    "upload.wikimedia.org", "commons.wikimedia.org",
    "archive.org", "www.archive.org", "ia800000.us.archive.org",
    "github.com", "codeload.github.com",
}

def _download_catalog_file(url):
    """Download a small file from an approved catalog host; reject redirects elsewhere."""
    from urllib.parse import urlparse
    parsed = urlparse(url or "")
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not (
        host in DIRECT_SEND_HOSTS or host.endswith(".archive.org") or host.endswith(".gutenberg.org")
    ):
        raise ValueError("Unapproved download host")
    req = urllib.request.Request(url, headers={"User-Agent": "CKHelpBot/2.0"})
    with urllib.request.urlopen(req, timeout=25) as response:
        final_host = (urlparse(response.geturl()).hostname or "").lower()
        if (final_host not in DIRECT_SEND_HOSTS
                and not final_host.endswith(".archive.org")
                and not final_host.endswith(".gutenberg.org")):
            raise ValueError("Download redirected to an unapproved host")
        length = response.headers.get("Content-Length")
        if length and int(length) > DIRECT_SEND_MAX_BYTES:
            raise ValueError("File is larger than Telegram upload limit")
        data = response.read(DIRECT_SEND_MAX_BYTES + 1)
        if len(data) > DIRECT_SEND_MAX_BYTES:
            raise ValueError("File is larger than Telegram upload limit")
        content_type = response.headers.get_content_type()
        disposition = response.headers.get("Content-Disposition", "")
    name_match = re.search(r'filename="?([^";]+)', disposition, re.I)
    filename = urllib.parse.unquote(name_match.group(1)) if name_match else os.path.basename(parsed.path) or "download"
    filename = re.sub(r"[^A-Za-z0-9._() -]", "_", filename)[:100] or "download"
    return data, filename, content_type


async def _send_catalog_result_file(msg, item):
    url = item.get("file_url")
    if not url:
        return False
    data, filename, content_type = await asyncio.to_thread(_download_catalog_file, url)
    allowed_types = {
        "application/epub+zip", "text/plain", "image/jpeg", "image/png",
        "image/webp", "video/mp4", "application/pdf", "application/zip",
        "application/octet-stream",
    }
    if content_type not in allowed_types and not content_type.startswith(("image/", "video/")):
        raise ValueError(f"Unsupported file type: {content_type}")
    suffix = os.path.splitext(filename)[1].lower()
    if not suffix:
        suffix = {
            "application/epub+zip": ".epub",
            "text/plain": ".txt",
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "video/mp4": ".mp4",
            "application/pdf": ".pdf",
            "application/zip": ".zip",
        }.get(content_type, ".bin")
        filename += suffix
    with tempfile.NamedTemporaryFile(prefix="cksend_", suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        path = tmp.name
    try:
        with open(path, "rb") as stream:
            if content_type.startswith("image/"):
                await msg.reply_photo(photo=stream, caption=("📥 " + (item.get("title") or "File"))[:900])
            elif content_type.startswith("video/"):
                await msg.reply_video(video=stream, caption=("📥 " + (item.get("title") or "File"))[:900], supports_streaming=True)
            else:
                await msg.reply_document(document=stream, filename=filename,
                                         caption=("📥 " + (item.get("title") or "File"))[:900])
        return True
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


async def internet_search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg=update.effective_message
    if not msg:
        return
    command=(msg.text or "").split()[0].split("@")[0].lstrip("/").lower()
    config=SEARCH_COMMANDS.get(command)
    if not config:
        return
    if update.effective_chat and update.effective_chat.type != "private":
        return await msg.reply_text("🔒 Search & Send ကို Bot Private Chat ထဲမှာ အသုံးပြုပါ။")
    query=" ".join(context.args).strip()
    if not query:
        return await msg.reply_text(f"အသုံးပြုပုံ: /{command} ရှာလိုသောအမည် သို့မဟုတ် စာသား\nဥပမာ: /{command} nature")
    if len(query)>120:
        return await msg.reply_text("ရှာဖွေစာသားကို စာလုံး ၁၂၀ အောက်ထားပေးပါ။")
    label,kind=config
    status=await msg.reply_text(f"🔎 {label} ကို ရှာဖွေနေပါတယ်…")
    results=[]
    search_errors=[]
    try:
        results.extend(await asyncio.to_thread(_free_web_search, kind, query, 8))
    except Exception as exc:
        search_errors.append(f"Free web search: {exc}")
        logger.warning("Free web search failed (%s): %s", command, exc)
    try:
        catalog_results=await asyncio.to_thread(_internet_catalog_search, kind, query)
        results.extend(catalog_results)
    except Exception as exc:
        search_errors.append(f"Catalog: {exc}")
        logger.warning("Catalog search failed (%s): %s", command, exc)
    # Deduplicate by normalized URL and retain specialized catalog records (which may include licensed files).
    deduped=[]
    seen_urls=set()
    for item in results:
        link=(item.get("url") or "").strip().rstrip("/")
        if not link or link in seen_urls:
            continue
        seen_urls.add(link)
        deduped.append(item)
    results=deduped[:12]
    if not results and search_errors:
        return await status.edit_text(
             "⚠️ အခမဲ့ Search ရင်းမြစ်တွေကို ချိတ်ဆက်မရပါ။ Railway Internet/DNS နဲ့ Logs ကို စစ်ဆေးပါ။"
        )
    if not results:
        return await status.edit_text("😕 ကိုက်ညီတဲ့ရလဒ် မတွေ့ပါ။ အခြားစကားလုံးနဲ့ ထပ်ရှာကြည့်ပါ။")
    # Archive.org item pages are link-only unless a small, explicitly licensed media file is identified.
    if kind in ("archive_movie", "archive_video"):
        for item in results[:6]:
            try:
                ident = item.get("url", "").rstrip("/").split("/")[-1]
                meta = _search_json("https://archive.org/metadata/" + urllib.parse.quote(ident), timeout=15)
                files = meta.get("files") or []
                for f in files:
                    name = f.get("name", "")
                    fmt = (f.get("format") or "").lower()
                    size = int(f.get("size") or 0)
                    ext = os.path.splitext(name)[1].lower()
                    if 0 < size <= DIRECT_SEND_MAX_BYTES and (fmt in ("mpeg4", "h.264", "mp4") or ext == ".mp4"):
                        item["file_url"] = "https://archive.org/download/" + urllib.parse.quote(ident) + "/" + urllib.parse.quote(name)
                        break
            except Exception:
                logger.info("Archive direct file lookup skipped", exc_info=True)
    await status.delete()
    for index,item in enumerate(results[:6],1):
        title=(item.get("title") or "Untitled")[:180]
        detail=(item.get("detail") or "")[:220]
        link=item.get("url")
        license_text=(item.get("license") or "License not confirmed")[:180]
        text_out=f"{label} ရလဒ် {index}\n{title}"
        if detail: text_out += f"\n{detail}"
        text_out += f"\n📜 {license_text}"
        if kind in ("app_github", "game_github") and item.get("file_url"):
            text_out += "\n⚠️ ပို့မည့်ဖိုင်သည် Source ZIP ဖြစ်ပြီး APK Installer မဟုတ်နိုင်ပါ။"
        sent_file = False
        if item.get("file_url"):
            try:
                sent_file = await _send_catalog_result_file(msg, item)
            except Exception as exc:
                logger.info("Direct catalog send unavailable: %s", exc)
        if link:
            button_text = "🔗 ရင်းမြစ် / Download" if sent_file else "🔗 ဖွင့်ရန် / Download"
            keyboard=InlineKeyboardMarkup([[InlineKeyboardButton(button_text, url=link)]])
            if sent_file:
                await msg.reply_text(f"{text_out}\n✅ ဖိုင်ကို Telegram ထဲ တိုက်ရိုက်ပို့ပြီးပါပြီ။", reply_markup=keyboard, disable_web_page_preview=True)
            else:
                await msg.reply_text(f"{text_out}\nℹ️ ရှာဖွေတွေ့ရှိသော မူရင်းရင်းမြစ် Link ဖြစ်ပါတယ်။ Download ခွင့်နှင့် လိုင်စင်ကို Website မှာ စစ်ဆေးပါ။", reply_markup=keyboard, disable_web_page_preview=True)
        else:
            await msg.reply_text(text_out)


async def movie_add_media(update, context):
    """Owner adds authorized movie files with caption: /movieadd Title."""
    msg, user = update.effective_message, update.effective_user
    if not user or user.id != BOT_OWNER_ID:
        return await msg.reply_text("⛔ Movie ဖိုင်ထည့်ခွင့်ကို Bot Owner သာ အသုံးပြုနိုင်ပါတယ်။")
    caption = (msg.caption or "").strip()
    parts = caption.split(maxsplit=1)
    if len(parts) < 2 or parts[0].split("@")[0].lower() != "/movieadd":
        return
    title = parts[1].strip()[:180]
    if msg.video:
        media_type, file_id = "video", msg.video.file_id
    elif msg.document:
        media_type, file_id = "document", msg.document.file_id
    else:
        return await msg.reply_text("ဗီဒီယို သို့မဟုတ် Movie ဖိုင်အဖြစ် ပို့ပါ။")
    with db_connect() as conn:
        cur = conn.execute("INSERT INTO ck_movies(title,media_type,file_id,added_by,created_at) VALUES(?,?,?,?,?)", (title, media_type, file_id, user.id, int(time.time())))
        movie_id = cur.lastrowid
        conn.commit()
    await msg.reply_text(f"✅ Movie သိမ်းပြီးပါပြီ။\nID: {movie_id}\nအမည်: {title}")

def _movie_normalize(value):
    """Normalize titles and queries while preserving Burmese/Unicode letters."""
    value = (value or "").casefold().strip()
    value = re.sub(r"[\W_]+", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def _movie_similarity(query, title):
    """Score exact, phrase, token and character-ngram matches (0..1)."""
    q = _movie_normalize(query)
    t = _movie_normalize(title)
    if not q or not t:
        return 0.0
    if q == t:
        return 1.0
    if q in t or t in q:
        return 0.96

    q_tokens, t_tokens = set(q.split()), set(t.split())
    token_score = len(q_tokens & t_tokens) / max(1, len(q_tokens))

    # Character bigrams also work for Burmese titles that have no spaces.
    qc, tc = q.replace(" ", ""), t.replace(" ", "")
    qgrams = {qc[i:i+2] for i in range(max(1, len(qc)-1))} if qc else set()
    tgrams = {tc[i:i+2] for i in range(max(1, len(tc)-1))} if tc else set()
    gram_score = len(qgrams & tgrams) / max(1, len(qgrams))
    seq_score = difflib.SequenceMatcher(None, qc, tc).ratio()
    return max(token_score * 0.82, gram_score * 0.88, seq_score * 0.78)


async def movie_command(update, context):
    query = " ".join(context.args).strip()
    if not query:
        return await update.effective_message.reply_text(
            "🎬 Movie ရှာရန်: /movie Movie အမည်\n"
            "ဥပမာ: /movie Avengers\nစာရင်းကြည့်ရန်: /movies"
        )
    with db_connect() as conn:
        rows = conn.execute(
            "SELECT id,title,media_type,file_id FROM ck_movies ORDER BY id DESC"
        ).fetchall()

    ranked = sorted(
        (( _movie_similarity(query, row["title"]), row) for row in rows),
        key=lambda item: (item[0], item[1]["id"]), reverse=True
    )
    # Exact and phrase matches always win. For fuzzy matches, require a meaningful
    # overlap so unrelated titles are not returned for arbitrary queries.
    matches = [(score, row) for score, row in ranked if score >= 0.28]
    if not matches:
        return await update.effective_message.reply_text(
            "🔎 ကိုက်ညီတဲ့ Movie မတွေ့ပါ။ Movie အမည်ကို စာလုံးပေါင်းပြန်စစ်ပြီး ရှာကြည့်ပါ။"
        )

    best_score, best = matches[0]
    caption = f"🎬 {best['title']}\nMovie ID: {best['id']}"
    if best_score < 0.95:
        caption += "\n🔎 အနီးစပ်ဆုံး ကိုက်ညီမှုဖြင့် ရှာတွေ့ထားပါတယ်။"
    if best["media_type"] == "video":
        await update.effective_message.reply_video(best["file_id"], caption=caption)
    else:
        await update.effective_message.reply_document(best["file_id"], caption=caption)

    if len(matches) > 1:
        alternatives = "\n".join(
            f"• {row['title']} — /movie {row['title']}"
            for _, row in matches[1:6]
        )
        await update.effective_message.reply_text(
            "🔎 အခြားအနီးစပ်ဆုံး Movie များ:\n" + alternatives
        )

async def movies_command(update, context):
    with db_connect() as conn:
        rows = conn.execute("SELECT id,title FROM ck_movies ORDER BY id DESC LIMIT 30").fetchall()
    if not rows:
        return await update.effective_message.reply_text("Movie မရှိသေးပါ။")
    text = "🎬 **CK BOT Movie Library**\n\n" + "\n".join(f"{r['id']}. {r['title']} — /movie {r['title']}" for r in rows)
    await update.effective_message.reply_text(text, parse_mode="Markdown")

async def movie_delete_command(update, context):
    if not update.effective_user or update.effective_user.id != BOT_OWNER_ID:
        return await update.effective_message.reply_text("⛔ Owner Only")
    if not context.args or not context.args[0].isdigit():
        return await update.effective_message.reply_text("အသုံးပြုပုံ: /moviedel Movie_ID")
    with db_connect() as conn:
        cur = conn.execute("DELETE FROM ck_movies WHERE id=?", (int(context.args[0]),))
        conn.commit()
    await update.effective_message.reply_text("🗑️ ဖျက်ပြီးပါပြီ။" if cur.rowcount else "Movie ID မတွေ့ပါ။")


# ------------------------- 300 ADDITIVE GROUP MODULES -------------------------
# Each module has its own persistent per-group board. Existing handlers are untouched.
GROUP_MODULES = [{'key': 'admin_tasks', 'title': 'Admin Tasks', 'desc': 'Admin တာဝန်စာရင်း', 'category': 'admin'}, {'key': 'admin_roster', 'title': 'Admin Roster', 'desc': 'Admin အဖွဲ့ဝင်စာရင်း', 'category': 'admin'}, {'key': 'admin_shifts', 'title': 'Admin Shifts', 'desc': 'Admin တာဝန်ချိန်', 'category': 'admin'}, {'key': 'admin_notes', 'title': 'Admin Notes', 'desc': 'Admin မှတ်စု', 'category': 'admin'}, {'key': 'admin_decisions', 'title': 'Admin Decisions', 'desc': 'Admin ဆုံးဖြတ်ချက်များ', 'category': 'admin'}, {'key': 'admin_requests', 'title': 'Admin Requests', 'desc': 'Admin တောင်းဆိုချက်များ', 'category': 'admin'}, {'key': 'admin_reports', 'title': 'Admin Reports', 'desc': 'Admin အစီရင်ခံစာ', 'category': 'admin'}, {'key': 'admin_audit', 'title': 'Admin Audit Log', 'desc': 'Admin လုပ်ဆောင်ချက်မှတ်တမ်း', 'category': 'admin'}, {'key': 'admin_contacts', 'title': 'Admin Contacts', 'desc': 'Admin ဆက်သွယ်ရန်', 'category': 'admin'}, {'key': 'admin_calendar', 'title': 'Admin Calendar', 'desc': 'Admin အစီအစဉ်ပြက္ခဒိန်', 'category': 'admin'}, {'key': 'admin_agenda', 'title': 'Meeting Agenda', 'desc': 'အစည်းအဝေးအစီအစဉ်', 'category': 'admin'}, {'key': 'admin_minutes', 'title': 'Meeting Minutes', 'desc': 'အစည်းအဝေးမှတ်တမ်း', 'category': 'admin'}, {'key': 'admin_checklist', 'title': 'Admin Checklist', 'desc': 'Admin စစ်ဆေးရန်စာရင်း', 'category': 'admin'}, {'key': 'admin_handover', 'title': 'Shift Handover', 'desc': 'တာဝန်လွှဲပြောင်းမှတ်တမ်း', 'category': 'admin'}, {'key': 'admin_issues', 'title': 'Admin Issues', 'desc': 'Admin ဖြေရှင်းရန်ကိစ္စ', 'category': 'admin'}, {'key': 'admin_approvals', 'title': 'Approvals', 'desc': 'ခွင့်ပြုချက်တောင်းခံမှု', 'category': 'admin'}, {'key': 'admin_bans', 'title': 'Ban Review', 'desc': 'ပိတ်ပင်မှုစိစစ်စာရင်း', 'category': 'admin'}, {'key': 'admin_appeals', 'title': 'Appeals', 'desc': 'အယူခံစာရင်း', 'category': 'admin'}, {'key': 'admin_partners', 'title': 'Partner List', 'desc': 'မိတ်ဖက်စာရင်း', 'category': 'admin'}, {'key': 'admin_resources', 'title': 'Admin Resources', 'desc': 'Admin အရင်းအမြစ်များ', 'category': 'admin'}, {'key': 'admin_templates', 'title': 'Admin Templates', 'desc': 'အသုံးပြုစာပုံစံများ', 'category': 'admin'}, {'key': 'admin_announcements', 'title': 'Announcements', 'desc': 'ကြေညာချက်များ', 'category': 'admin'}, {'key': 'admin_pins', 'title': 'Pin Queue', 'desc': 'Pin တင်ရန်စာရင်း', 'category': 'admin'}, {'key': 'admin_tasks_done', 'title': 'Completed Tasks', 'desc': 'ပြီးစီးသောတာဝန်များ', 'category': 'admin'}, {'key': 'admin_followups', 'title': 'Follow-ups', 'desc': 'နောက်ဆက်တွဲလုပ်ရန်', 'category': 'admin'}, {'key': 'admin_suggestions', 'title': 'Admin Suggestions', 'desc': 'Admin အကြံပြုချက်များ', 'category': 'admin'}, {'key': 'admin_incidents', 'title': 'Incident Log', 'desc': 'ဖြစ်စဉ်မှတ်တမ်း', 'category': 'admin'}, {'key': 'admin_inventory', 'title': 'Admin Inventory', 'desc': 'Admin ပစ္စည်းစာရင်း', 'category': 'admin'}, {'key': 'admin_training', 'title': 'Admin Training', 'desc': 'Admin လေ့ကျင့်ရေး', 'category': 'admin'}, {'key': 'admin_goals', 'title': 'Admin Goals', 'desc': 'Admin ရည်မှန်းချက်များ', 'category': 'admin'}, {'key': 'safety_watch', 'title': 'Safety Watch', 'desc': 'လုံခြုံရေးစောင့်ကြည့်စာရင်း', 'category': 'safety'}, {'key': 'spam_reports', 'title': 'Spam Reports', 'desc': 'Spam တိုင်ကြားချက်', 'category': 'safety'}, {'key': 'scam_alerts', 'title': 'Scam Alerts', 'desc': 'လိမ်လည်မှုသတိပေးချက်', 'category': 'safety'}, {'key': 'fake_accounts', 'title': 'Fake Account Reports', 'desc': 'အကောင့်အတုတိုင်ကြားချက်', 'category': 'safety'}, {'key': 'suspicious_links', 'title': 'Suspicious Links', 'desc': 'သံသယဖြစ်ဖွယ်လင့်ခ်', 'category': 'safety'}, {'key': 'blocked_words', 'title': 'Blocked Words', 'desc': 'မသုံးရန်စကားလုံး', 'category': 'safety'}, {'key': 'allowed_links', 'title': 'Allowed Links', 'desc': 'ခွင့်ပြုထားသောလင့်ခ်', 'category': 'safety'}, {'key': 'trusted_users', 'title': 'Trusted Users', 'desc': 'ယုံကြည်ရသူစာရင်း', 'category': 'safety'}, {'key': 'restricted_users', 'title': 'Restricted Users', 'desc': 'ကန့်သတ်ထားသူစာရင်း', 'category': 'safety'}, {'key': 'warning_reasons', 'title': 'Warning Reasons', 'desc': 'သတိပေးရသည့်အကြောင်း', 'category': 'safety'}, {'key': 'incident_reports', 'title': 'Incident Reports', 'desc': 'ပြဿနာတိုင်ကြားချက်', 'category': 'safety'}, {'key': 'safety_tips', 'title': 'Safety Tips', 'desc': 'လုံခြုံရေးအကြံပြုချက်', 'category': 'safety'}, {'key': 'privacy_tips', 'title': 'Privacy Tips', 'desc': 'ကိုယ်ရေးလုံခြုံမှုအကြံပြုချက်', 'category': 'safety'}, {'key': 'scam_domains', 'title': 'Scam Domains', 'desc': 'လိမ်လည်ဝက်ဘ်ဆိုက်စာရင်း', 'category': 'safety'}, {'key': 'moderation_queue', 'title': 'Moderation Queue', 'desc': 'စိစစ်ရန်စာရင်း', 'category': 'safety'}, {'key': 'appeal_queue', 'title': 'Appeal Queue', 'desc': 'အယူခံစိစစ်ရန်', 'category': 'safety'}, {'key': 'report_followups', 'title': 'Report Follow-ups', 'desc': 'တိုင်ကြားမှုနောက်ဆက်တွဲ', 'category': 'safety'}, {'key': 'raid_watch', 'title': 'Raid Watch', 'desc': 'အစုလိုက်ဝင်ရောက်မှုစောင့်ကြည့်', 'category': 'safety'}, {'key': 'new_member_checks', 'title': 'New Member Checks', 'desc': 'အဖွဲ့ဝင်အသစ်စစ်ဆေးရန်', 'category': 'safety'}, {'key': 'link_reviews', 'title': 'Link Reviews', 'desc': 'လင့်ခ်စိစစ်ချက်', 'category': 'safety'}, {'key': 'file_reviews', 'title': 'File Reviews', 'desc': 'ဖိုင်စိစစ်ချက်', 'category': 'safety'}, {'key': 'content_flags', 'title': 'Content Flags', 'desc': 'မသင့်လျော်သောအကြောင်းအရာ', 'category': 'safety'}, {'key': 'trusted_domains', 'title': 'Trusted Domains', 'desc': 'ယုံကြည်ရသောဒိုမိန်း', 'category': 'safety'}, {'key': 'security_notices', 'title': 'Security Notices', 'desc': 'လုံခြုံရေးအသိပေးချက်', 'category': 'safety'}, {'key': 'emergency_contacts', 'title': 'Emergency Contacts', 'desc': 'အရေးပေါ်ဆက်သွယ်ရန်', 'category': 'safety'}, {'key': 'safety_faq', 'title': 'Safety FAQ', 'desc': 'လုံခြုံရေးမေးလေ့ရှိသည်များ', 'category': 'safety'}, {'key': 'moderator_notes', 'title': 'Moderator Notes', 'desc': 'Moderator မှတ်စု', 'category': 'safety'}, {'key': 'spam_patterns', 'title': 'Spam Patterns', 'desc': 'Spam ပုံစံမှတ်တမ်း', 'category': 'safety'}, {'key': 'ban_appeal_notes', 'title': 'Ban Appeal Notes', 'desc': 'ပိတ်ပင်မှုအယူခံမှတ်စု', 'category': 'safety'}, {'key': 'community_guidelines', 'title': 'Community Guidelines', 'desc': 'အသိုင်းအဝိုင်းစည်းကမ်း', 'category': 'safety'}, {'key': 'member_directory', 'title': 'Member Directory', 'desc': 'အဖွဲ့ဝင်စာရင်း', 'category': 'members'}, {'key': 'member_birthdays', 'title': 'Birthdays', 'desc': 'မွေးနေ့စာရင်း', 'category': 'members'}, {'key': 'member_interests', 'title': 'Member Interests', 'desc': 'စိတ်ဝင်စားမှုများ', 'category': 'members'}, {'key': 'member_skills', 'title': 'Member Skills', 'desc': 'ကျွမ်းကျင်မှုစာရင်း', 'category': 'members'}, {'key': 'member_languages', 'title': 'Languages', 'desc': 'ဘာသာစကားစာရင်း', 'category': 'members'}, {'key': 'member_intros', 'title': 'Introductions', 'desc': 'မိတ်ဆက်စာရင်း', 'category': 'members'}, {'key': 'member_goals', 'title': 'Member Goals', 'desc': 'အဖွဲ့ဝင်ရည်မှန်းချက်', 'category': 'members'}, {'key': 'member_feedback', 'title': 'Member Feedback', 'desc': 'အဖွဲ့ဝင်အကြံပြုချက်', 'category': 'members'}, {'key': 'member_questions', 'title': 'Member Questions', 'desc': 'အဖွဲ့ဝင်မေးခွန်း', 'category': 'members'}, {'key': 'member_answers', 'title': 'Member Answers', 'desc': 'အဖွဲ့ဝင်အဖြေ', 'category': 'members'}, {'key': 'member_projects', 'title': 'Member Projects', 'desc': 'အဖွဲ့ဝင်စီမံကိန်း', 'category': 'members'}, {'key': 'member_portfolio', 'title': 'Portfolio', 'desc': 'လက်ရာစုစည်းမှု', 'category': 'members'}, {'key': 'member_services', 'title': 'Member Services', 'desc': 'ဝန်ဆောင်မှုစာရင်း', 'category': 'members'}, {'key': 'member_offers', 'title': 'Member Offers', 'desc': 'ကမ်းလှမ်းချက်များ', 'category': 'members'}, {'key': 'member_needs', 'title': 'Member Needs', 'desc': 'လိုအပ်ချက်များ', 'category': 'members'}, {'key': 'member_recommendations', 'title': 'Recommendations', 'desc': 'အကြံပြုစာရင်း', 'category': 'members'}, {'key': 'member_mentors', 'title': 'Mentors', 'desc': 'လမ်းညွှန်ပေးသူများ', 'category': 'members'}, {'key': 'member_learners', 'title': 'Learners', 'desc': 'သင်ယူသူများ', 'category': 'members'}, {'key': 'member_teams', 'title': 'Teams', 'desc': 'အဖွဲ့ခွဲစာရင်း', 'category': 'members'}, {'key': 'member_roles', 'title': 'Member Roles', 'desc': 'အဖွဲ့ဝင်တာဝန်', 'category': 'members'}, {'key': 'member_attendance', 'title': 'Attendance', 'desc': 'တက်ရောက်မှု', 'category': 'members'}, {'key': 'member_checkin', 'title': 'Check-in', 'desc': 'ရောက်ရှိကြောင်းစာရင်း', 'category': 'members'}, {'key': 'member_absence', 'title': 'Absence Notes', 'desc': 'ပျက်ကွက်မှုမှတ်စု', 'category': 'members'}, {'key': 'member_thanks', 'title': 'Thank You Board', 'desc': 'ကျေးဇူးတင်စကား', 'category': 'members'}, {'key': 'member_kudos', 'title': 'Kudos', 'desc': 'ချီးကျူးစကား', 'category': 'members'}, {'key': 'member_welcome_notes', 'title': 'Welcome Notes', 'desc': 'ကြိုဆိုမှတ်စု', 'category': 'members'}, {'key': 'member_anniversaries', 'title': 'Anniversaries', 'desc': 'နှစ်ပတ်လည်နေ့များ', 'category': 'members'}, {'key': 'member_contacts', 'title': 'Member Contacts', 'desc': 'ဆက်သွယ်ရန်စာရင်း', 'category': 'members'}, {'key': 'member_study_buddies', 'title': 'Study Buddies', 'desc': 'စာလေ့လာဖော်', 'category': 'members'}, {'key': 'member_collaborations', 'title': 'Collaborations', 'desc': 'ပူးပေါင်းလုပ်ဆောင်မှု', 'category': 'members'}, {'key': 'community_ideas', 'title': 'Community Ideas', 'desc': 'အသိုင်းအဝိုင်းအကြံဉာဏ်', 'category': 'community'}, {'key': 'community_votes', 'title': 'Community Votes', 'desc': 'အသိုင်းအဝိုင်းမဲပေးမှု', 'category': 'community'}, {'key': 'community_events', 'title': 'Community Events', 'desc': 'ပွဲအစီအစဉ်', 'category': 'community'}, {'key': 'community_meetups', 'title': 'Meetups', 'desc': 'တွေ့ဆုံပွဲများ', 'category': 'community'}, {'key': 'community_challenges', 'title': 'Challenges', 'desc': 'စိန်ခေါ်မှုများ', 'category': 'community'}, {'key': 'community_wins', 'title': 'Community Wins', 'desc': 'အောင်မြင်မှုများ', 'category': 'community'}, {'key': 'community_milestones', 'title': 'Milestones', 'desc': 'မှတ်တိုင်များ', 'category': 'community'}, {'key': 'community_projects', 'title': 'Community Projects', 'desc': 'အသိုင်းအဝိုင်းစီမံကိန်း', 'category': 'community'}, {'key': 'community_faq', 'title': 'Community FAQ', 'desc': 'မေးလေ့ရှိသောမေးခွန်း', 'category': 'community'}, {'key': 'community_glossary', 'title': 'Glossary', 'desc': 'ဝေါဟာရရှင်းလင်းချက်', 'category': 'community'}, {'key': 'community_resources', 'title': 'Resources', 'desc': 'အသုံးဝင်အရင်းအမြစ်', 'category': 'community'}, {'key': 'community_links', 'title': 'Useful Links', 'desc': 'အသုံးဝင်လင့်ခ်များ', 'category': 'community'}, {'key': 'community_books', 'title': 'Book Club', 'desc': 'စာအုပ်အသင်း', 'category': 'community'}, {'key': 'community_movies', 'title': 'Movie Club', 'desc': 'ရုပ်ရှင်အသင်း', 'category': 'community'}, {'key': 'community_music', 'title': 'Music Club', 'desc': 'ဂီတအသင်း', 'category': 'community'}, {'key': 'community_games', 'title': 'Game Night', 'desc': 'ဂိမ်းည', 'category': 'community'}, {'key': 'community_topics', 'title': 'Discussion Topics', 'desc': 'ဆွေးနွေးခေါင်းစဉ်', 'category': 'community'}, {'key': 'community_debates', 'title': 'Debate Topics', 'desc': 'အမြင်ဖလှယ်ခေါင်းစဉ်', 'category': 'community'}, {'key': 'community_quotes', 'title': 'Quotes', 'desc': 'ကိုးကားစကားများ', 'category': 'community'}, {'key': 'community_jokes', 'title': 'Jokes', 'desc': 'ဟာသများ', 'category': 'community'}, {'key': 'community_memes', 'title': 'Memes', 'desc': 'မီမ်စာရင်း', 'category': 'community'}, {'key': 'community_photos', 'title': 'Photo Themes', 'desc': 'ဓာတ်ပုံခေါင်းစဉ်', 'category': 'community'}, {'key': 'community_art', 'title': 'Art Showcase', 'desc': 'အနုပညာပြခန်း', 'category': 'community'}, {'key': 'community_writing', 'title': 'Writing Showcase', 'desc': 'စာရေးလက်ရာ', 'category': 'community'}, {'key': 'community_talents', 'title': 'Talent Showcase', 'desc': 'အရည်အချင်းပြခန်း', 'category': 'community'}, {'key': 'community_poll_ideas', 'title': 'Poll Ideas', 'desc': 'မဲပေးမေးခွန်းအကြံ', 'category': 'community'}, {'key': 'community_contests', 'title': 'Contests', 'desc': 'ပြိုင်ပွဲများ', 'category': 'community'}, {'key': 'community_prizes', 'title': 'Prizes', 'desc': 'ဆုလက်ဆောင်စာရင်း', 'category': 'community'}, {'key': 'community_volunteers', 'title': 'Volunteers', 'desc': 'စေတနာ့ဝန်ထမ်း', 'category': 'community'}, {'key': 'community_partners', 'title': 'Community Partners', 'desc': 'ပူးပေါင်းအဖွဲ့များ', 'category': 'community'}, {'key': 'learning_topics', 'title': 'Study Topics', 'desc': 'လေ့လာရန်ခေါင်းစဉ်', 'category': 'learning'}, {'key': 'learning_questions', 'title': 'Study Questions', 'desc': 'လေ့လာရေးမေးခွန်း', 'category': 'learning'}, {'key': 'learning_answers', 'title': 'Study Answers', 'desc': 'လေ့လာရေးအဖြေ', 'category': 'learning'}, {'key': 'learning_notes', 'title': 'Study Notes', 'desc': 'စာမှတ်စု', 'category': 'learning'}, {'key': 'learning_flashcards', 'title': 'Flashcards', 'desc': 'မှတ်သားကတ်များ', 'category': 'learning'}, {'key': 'learning_vocabulary', 'title': 'Vocabulary', 'desc': 'ဝေါဟာရ', 'category': 'learning'}, {'key': 'learning_phrases', 'title': 'Useful Phrases', 'desc': 'အသုံးဝင်စကားစု', 'category': 'learning'}, {'key': 'learning_resources', 'title': 'Learning Resources', 'desc': 'သင်ယူရေးအရင်းအမြစ်', 'category': 'learning'}, {'key': 'learning_courses', 'title': 'Courses', 'desc': 'သင်တန်းစာရင်း', 'category': 'learning'}, {'key': 'learning_deadlines', 'title': 'Study Deadlines', 'desc': 'စာလေ့လာရက်ချိန်း', 'category': 'learning'}, {'key': 'learning_homework', 'title': 'Homework Board', 'desc': 'အိမ်စာစာရင်း', 'category': 'learning'}, {'key': 'learning_projects', 'title': 'Learning Projects', 'desc': 'လေ့လာရေးစီမံကိန်း', 'category': 'learning'}, {'key': 'learning_exams', 'title': 'Exam Dates', 'desc': 'စာမေးပွဲရက်', 'category': 'learning'}, {'key': 'learning_timetable', 'title': 'Study Timetable', 'desc': 'စာကျက်အချိန်ဇယား', 'category': 'learning'}, {'key': 'learning_goals', 'title': 'Study Goals', 'desc': 'စာလေ့လာရည်မှန်းချက်', 'category': 'learning'}, {'key': 'learning_streaks', 'title': 'Study Streaks', 'desc': 'စာလေ့လာဆက်တိုက်ရက်', 'category': 'learning'}, {'key': 'learning_tips', 'title': 'Study Tips', 'desc': 'စာကျက်နည်း', 'category': 'learning'}, {'key': 'learning_summaries', 'title': 'Summaries', 'desc': 'အကျဉ်းချုပ်', 'category': 'learning'}, {'key': 'learning_reading', 'title': 'Reading List', 'desc': 'ဖတ်ရန်စာရင်း', 'category': 'learning'}, {'key': 'learning_writing', 'title': 'Writing Prompts', 'desc': 'စာရေးလေ့ကျင့်ခေါင်းစဉ်', 'category': 'learning'}, {'key': 'learning_speaking', 'title': 'Speaking Practice', 'desc': 'စကားပြောလေ့ကျင့်', 'category': 'learning'}, {'key': 'learning_quizbank', 'title': 'Quiz Bank', 'desc': 'ဉာဏ်စမ်းမေးခွန်း', 'category': 'learning'}, {'key': 'learning_definitions', 'title': 'Definitions', 'desc': 'အဓိပ္ပာယ်ဖွင့်ဆိုချက်', 'category': 'learning'}, {'key': 'learning_formulas', 'title': 'Formulas', 'desc': 'ဖော်မြူလာများ', 'category': 'learning'}, {'key': 'learning_tutorials', 'title': 'Tutorials', 'desc': 'သင်ခန်းစာများ', 'category': 'learning'}, {'key': 'learning_bookmarks', 'title': 'Study Bookmarks', 'desc': 'စာလေ့လာမှတ်သားချက်', 'category': 'learning'}, {'key': 'learning_peer_help', 'title': 'Peer Help', 'desc': 'အချင်းချင်းကူညီမှု', 'category': 'learning'}, {'key': 'learning_feedback', 'title': 'Study Feedback', 'desc': 'လေ့လာရေးအကြံပြုချက်', 'category': 'learning'}, {'key': 'learning_career', 'title': 'Career Resources', 'desc': 'အလုပ်အကိုင်အရင်းအမြစ်', 'category': 'learning'}, {'key': 'learning_scholarships', 'title': 'Scholarships', 'desc': 'ပညာသင်ဆုစာရင်း', 'category': 'learning'}, {'key': 'plan_tasks', 'title': 'Task Board', 'desc': 'လုပ်စရာစာရင်း', 'category': 'planning'}, {'key': 'plan_todo', 'title': 'To-do List', 'desc': 'လုပ်ရန်စာရင်း', 'category': 'planning'}, {'key': 'plan_weekly', 'title': 'Weekly Plan', 'desc': 'အပတ်စဉ်အစီအစဉ်', 'category': 'planning'}, {'key': 'plan_monthly', 'title': 'Monthly Plan', 'desc': 'လစဉ်အစီအစဉ်', 'category': 'planning'}, {'key': 'plan_deadlines', 'title': 'Deadlines', 'desc': 'နောက်ဆုံးရက်များ', 'category': 'planning'}, {'key': 'plan_milestones', 'title': 'Project Milestones', 'desc': 'စီမံကိန်းမှတ်တိုင်', 'category': 'planning'}, {'key': 'plan_meetings', 'title': 'Meetings', 'desc': 'အစည်းအဝေးများ', 'category': 'planning'}, {'key': 'plan_agenda', 'title': 'Agendas', 'desc': 'အစီအစဉ်များ', 'category': 'planning'}, {'key': 'plan_minutes', 'title': 'Minutes', 'desc': 'အစည်းအဝေးမှတ်တမ်း', 'category': 'planning'}, {'key': 'plan_appointments', 'title': 'Appointments', 'desc': 'ချိန်းဆိုမှုများ', 'category': 'planning'}, {'key': 'plan_trips', 'title': 'Trip Plans', 'desc': 'ခရီးစဉ်အစီအစဉ်', 'category': 'planning'}, {'key': 'plan_packing', 'title': 'Packing List', 'desc': 'ခရီးဆောင်ပစ္စည်းစာရင်း', 'category': 'planning'}, {'key': 'plan_shopping', 'title': 'Shopping List', 'desc': 'ဈေးဝယ်စာရင်း', 'category': 'planning'}, {'key': 'plan_groceries', 'title': 'Groceries', 'desc': 'စားသောက်ကုန်စာရင်း', 'category': 'planning'}, {'key': 'plan_meals', 'title': 'Meal Plan', 'desc': 'စားသောက်အစီအစဉ်', 'category': 'planning'}, {'key': 'plan_recipes', 'title': 'Recipes', 'desc': 'ချက်ပြုတ်နည်း', 'category': 'planning'}, {'key': 'plan_budget', 'title': 'Group Budget', 'desc': 'အဖွဲ့ဘတ်ဂျက်', 'category': 'planning'}, {'key': 'plan_expenses', 'title': 'Shared Expenses', 'desc': 'မျှဝေကုန်ကျစရိတ်', 'category': 'planning'}, {'key': 'plan_contributions', 'title': 'Contributions', 'desc': 'ထည့်ဝင်ငွေစာရင်း', 'category': 'planning'}, {'key': 'plan_maintenance', 'title': 'Maintenance', 'desc': 'ပြုပြင်ထိန်းသိမ်းရန်', 'category': 'planning'}, {'key': 'plan_equipment', 'title': 'Equipment', 'desc': 'ပစ္စည်းစာရင်း', 'category': 'planning'}, {'key': 'plan_bookings', 'title': 'Bookings', 'desc': 'ကြိုတင်စာရင်းသွင်းမှု', 'category': 'planning'}, {'key': 'plan_reservations', 'title': 'Reservations', 'desc': 'နေရာကြိုတင်ယူမှု', 'category': 'planning'}, {'key': 'plan_volunteer_shifts', 'title': 'Volunteer Shifts', 'desc': 'စေတနာ့ဝန်ထမ်းအလှည့်', 'category': 'planning'}, {'key': 'plan_duties', 'title': 'Duties', 'desc': 'တာဝန်စာရင်း', 'category': 'planning'}, {'key': 'plan_checklists', 'title': 'Checklists', 'desc': 'စစ်ဆေးရန်စာရင်း', 'category': 'planning'}, {'key': 'plan_priorities', 'title': 'Priorities', 'desc': 'ဦးစားပေးစာရင်း', 'category': 'planning'}, {'key': 'plan_risks', 'title': 'Risk Register', 'desc': 'အန္တရာယ်စိစစ်စာရင်း', 'category': 'planning'}, {'key': 'plan_decisions', 'title': 'Decision Log', 'desc': 'ဆုံးဖြတ်ချက်မှတ်တမ်း', 'category': 'planning'}, {'key': 'plan_followups', 'title': 'Follow-up List', 'desc': 'နောက်ဆက်တွဲစာရင်း', 'category': 'planning'}, {'key': 'market_items', 'title': 'Marketplace Items', 'desc': 'အရောင်းအဝယ်ပစ္စည်း', 'category': 'market'}, {'key': 'market_services', 'title': 'Services Market', 'desc': 'ဝန်ဆောင်မှုဈေးကွက်', 'category': 'market'}, {'key': 'market_wanted', 'title': 'Wanted Items', 'desc': 'ဝယ်လိုသောပစ္စည်း', 'category': 'market'}, {'key': 'market_for_sale', 'title': 'For Sale', 'desc': 'ရောင်းရန်ပစ္စည်း', 'category': 'market'}, {'key': 'market_freebies', 'title': 'Free Items', 'desc': 'အခမဲ့ပစ္စည်း', 'category': 'market'}, {'key': 'market_swaps', 'title': 'Swap Board', 'desc': 'ပစ္စည်းလဲလှယ်ရန်', 'category': 'market'}, {'key': 'market_prices', 'title': 'Price List', 'desc': 'ဈေးနှုန်းစာရင်း', 'category': 'market'}, {'key': 'market_suppliers', 'title': 'Suppliers', 'desc': 'ပစ္စည်းပေးသွင်းသူ', 'category': 'market'}, {'key': 'market_vendors', 'title': 'Vendors', 'desc': 'ရောင်းချသူ', 'category': 'market'}, {'key': 'market_orders', 'title': 'Orders', 'desc': 'အော်ဒါစာရင်း', 'category': 'market'}, {'key': 'market_deliveries', 'title': 'Deliveries', 'desc': 'ပို့ဆောင်မှုစာရင်း', 'category': 'market'}, {'key': 'market_reviews', 'title': 'Reviews', 'desc': 'သုံးသပ်ချက်များ', 'category': 'market'}, {'key': 'market_ratings', 'title': 'Ratings', 'desc': 'အဆင့်သတ်မှတ်ချက်', 'category': 'market'}, {'key': 'market_coupons', 'title': 'Coupons', 'desc': 'လျှော့ဈေးကူပွန်', 'category': 'market'}, {'key': 'market_promotions', 'title': 'Promotions', 'desc': 'အရောင်းမြှင့်တင်မှု', 'category': 'market'}, {'key': 'market_deals', 'title': 'Deals', 'desc': 'အထူးဈေးနှုန်း', 'category': 'market'}, {'key': 'market_auctions', 'title': 'Auction Items', 'desc': 'လေလံပစ္စည်း', 'category': 'market'}, {'key': 'market_bids', 'title': 'Bids', 'desc': 'လေလံဈေးပြိုင်မှု', 'category': 'market'}, {'key': 'market_stock', 'title': 'Stock List', 'desc': 'ကုန်ပစ္စည်းလက်ကျန်', 'category': 'market'}, {'key': 'market_returns', 'title': 'Returns', 'desc': 'ပြန်အပ်မှု', 'category': 'market'}, {'key': 'market_warranties', 'title': 'Warranties', 'desc': 'အာမခံစာရင်း', 'category': 'market'}, {'key': 'market_repair', 'title': 'Repair Services', 'desc': 'ပြုပြင်ဝန်ဆောင်မှု', 'category': 'market'}, {'key': 'market_rentals', 'title': 'Rentals', 'desc': 'ငှားရမ်းပစ္စည်း', 'category': 'market'}, {'key': 'market_jobs', 'title': 'Job Board', 'desc': 'အလုပ်အကိုင်စာရင်း', 'category': 'market'}, {'key': 'market_gigs', 'title': 'Gigs', 'desc': 'အချိန်ပိုင်းအလုပ်', 'category': 'market'}, {'key': 'market_collabs', 'title': 'Collaboration Offers', 'desc': 'ပူးပေါင်းကမ်းလှမ်းချက်', 'category': 'market'}, {'key': 'market_clients', 'title': 'Clients', 'desc': 'ဖောက်သည်စာရင်း', 'category': 'market'}, {'key': 'market_portfolios', 'title': 'Seller Portfolios', 'desc': 'ရောင်းချသူလက်ရာ', 'category': 'market'}, {'key': 'market_faq', 'title': 'Market FAQ', 'desc': 'ဈေးကွက်မေးခွန်း', 'category': 'market'}, {'key': 'market_disputes', 'title': 'Dispute Notes', 'desc': 'အငြင်းပွားမှုမှတ်စု', 'category': 'market'}, {'key': 'fun_riddles', 'title': 'Riddles', 'desc': 'ဉာဏ်စမ်းပဟေဠိ', 'category': 'entertainment'}, {'key': 'fun_answers', 'title': 'Riddle Answers', 'desc': 'ပဟေဠိအဖြေ', 'category': 'entertainment'}, {'key': 'fun_trivia', 'title': 'Trivia', 'desc': 'ဗဟုသုတမေးခွန်း', 'category': 'entertainment'}, {'key': 'fun_quizzes', 'title': 'Quizzes', 'desc': 'ဉာဏ်စမ်းပွဲ', 'category': 'entertainment'}, {'key': 'fun_dares', 'title': 'Safe Dares', 'desc': 'ပျော်စရာစိန်ခေါ်မှု', 'category': 'entertainment'}, {'key': 'fun_prompts', 'title': 'Creative Prompts', 'desc': 'ဖန်တီးရေးအကြောင်းအရာ', 'category': 'entertainment'}, {'key': 'fun_story_chain', 'title': 'Story Chain', 'desc': 'ဇာတ်လမ်းဆက်ရေး', 'category': 'entertainment'}, {'key': 'fun_word_chain', 'title': 'Word Chain', 'desc': 'စကားလုံးဆက်', 'category': 'entertainment'}, {'key': 'fun_would_you', 'title': 'Would You Rather', 'desc': 'ရွေးချယ်မေးခွန်း', 'category': 'entertainment'}, {'key': 'fun_this_or_that', 'title': 'This or That', 'desc': 'ဒါလား ဒါလား', 'category': 'entertainment'}, {'key': 'fun_daily_topic', 'title': 'Daily Topic', 'desc': 'နေ့စဉ်ခေါင်းစဉ်', 'category': 'entertainment'}, {'key': 'fun_icebreakers', 'title': 'Icebreakers', 'desc': 'ရင်းနှီးစေမေးခွန်း', 'category': 'entertainment'}, {'key': 'fun_charades', 'title': 'Charades', 'desc': 'အမူအရာခန့်မှန်း', 'category': 'entertainment'}, {'key': 'fun_pictionary', 'title': 'Pictionary', 'desc': 'ပုံဆွဲခန့်မှန်း', 'category': 'entertainment'}, {'key': 'fun_bingo', 'title': 'Bingo', 'desc': 'ဘင်ဂို', 'category': 'entertainment'}, {'key': 'fun_scoreboard', 'title': 'Scoreboard', 'desc': 'အမှတ်စာရင်း', 'category': 'entertainment'}, {'key': 'fun_tournament', 'title': 'Tournament', 'desc': 'ပြိုင်ပွဲဇယား', 'category': 'entertainment'}, {'key': 'fun_teams', 'title': 'Game Teams', 'desc': 'ဂိမ်းအသင်းများ', 'category': 'entertainment'}, {'key': 'fun_playlist', 'title': 'Playlist', 'desc': 'သီချင်းစာရင်း', 'category': 'entertainment'}, {'key': 'fun_song_requests', 'title': 'Song Requests', 'desc': 'သီချင်းတောင်းဆိုမှု', 'category': 'entertainment'}, {'key': 'fun_movie_votes', 'title': 'Movie Votes', 'desc': 'ရုပ်ရှင်မဲပေးမှု', 'category': 'entertainment'}, {'key': 'fun_watchlist', 'title': 'Watchlist', 'desc': 'ကြည့်ရန်စာရင်း', 'category': 'entertainment'}, {'key': 'fun_booklist', 'title': 'Book List', 'desc': 'စာအုပ်စာရင်း', 'category': 'entertainment'}, {'key': 'fun_recommendations', 'title': 'Recommendations', 'desc': 'အကြံပြုချက်', 'category': 'entertainment'}, {'key': 'fun_fan_theories', 'title': 'Fan Theories', 'desc': 'ပရိသတ်အယူအဆ', 'category': 'entertainment'}, {'key': 'fun_character_list', 'title': 'Characters', 'desc': 'ဇာတ်ကောင်စာရင်း', 'category': 'entertainment'}, {'key': 'fun_quotes', 'title': 'Famous Quotes', 'desc': 'နာမည်ကြီးစကားများ', 'category': 'entertainment'}, {'key': 'fun_captions', 'title': 'Caption Ideas', 'desc': 'စာတန်းအကြံ', 'category': 'entertainment'}, {'key': 'fun_photo_challenge', 'title': 'Photo Challenge', 'desc': 'ဓာတ်ပုံစိန်ခေါ်မှု', 'category': 'entertainment'}, {'key': 'fun_weekly_winner', 'title': 'Weekly Winners', 'desc': 'အပတ်စဉ်အနိုင်ရသူ', 'category': 'entertainment'}, {'key': 'know_faq', 'title': 'FAQ', 'desc': 'မေးလေ့ရှိသောမေးခွန်း', 'category': 'knowledge'}, {'key': 'know_glossary', 'title': 'Glossary', 'desc': 'ဝေါဟာရ', 'category': 'knowledge'}, {'key': 'know_howto', 'title': 'How-to Guides', 'desc': 'လုပ်နည်းလမ်းညွှန်', 'category': 'knowledge'}, {'key': 'know_tips', 'title': 'Tips', 'desc': 'အကြံပြုချက်', 'category': 'knowledge'}, {'key': 'know_resources', 'title': 'Resources', 'desc': 'အရင်းအမြစ်', 'category': 'knowledge'}, {'key': 'know_links', 'title': 'Reference Links', 'desc': 'ကိုးကားလင့်ခ်', 'category': 'knowledge'}, {'key': 'know_contacts', 'title': 'Useful Contacts', 'desc': 'အသုံးဝင်ဆက်သွယ်ရန်', 'category': 'knowledge'}, {'key': 'know_locations', 'title': 'Locations', 'desc': 'နေရာစာရင်း', 'category': 'knowledge'}, {'key': 'know_services', 'title': 'Local Services', 'desc': 'ဒေသတွင်းဝန်ဆောင်မှု', 'category': 'knowledge'}, {'key': 'know_transport', 'title': 'Transport Info', 'desc': 'သယ်ယူပို့ဆောင်ရေး', 'category': 'knowledge'}, {'key': 'know_emergency', 'title': 'Emergency Info', 'desc': 'အရေးပေါ်အချက်အလက်', 'category': 'knowledge'}, {'key': 'know_health', 'title': 'Wellbeing Info', 'desc': 'ကျန်းမာရေးဗဟုသုတ', 'category': 'knowledge'}, {'key': 'know_tech', 'title': 'Tech Help', 'desc': 'နည်းပညာအကူအညီ', 'category': 'knowledge'}, {'key': 'know_device_help', 'title': 'Device Help', 'desc': 'စက်ပစ္စည်းအကူအညီ', 'category': 'knowledge'}, {'key': 'know_app_help', 'title': 'App Help', 'desc': 'အက်ပ်အကူအညီ', 'category': 'knowledge'}, {'key': 'know_account_help', 'title': 'Account Help', 'desc': 'အကောင့်အကူအညီ', 'category': 'knowledge'}, {'key': 'know_translation', 'title': 'Translation Notes', 'desc': 'ဘာသာပြန်မှတ်စု', 'category': 'knowledge'}, {'key': 'know_language', 'title': 'Language Notes', 'desc': 'ဘာသာစကားမှတ်စု', 'category': 'knowledge'}, {'key': 'know_templates', 'title': 'Templates', 'desc': 'စာပုံစံများ', 'category': 'knowledge'}, {'key': 'know_documents', 'title': 'Documents', 'desc': 'စာရွက်စာတမ်း', 'category': 'knowledge'}, {'key': 'know_forms', 'title': 'Forms', 'desc': 'ဖောင်များ', 'category': 'knowledge'}, {'key': 'know_policies', 'title': 'Policies', 'desc': 'မူဝါဒများ', 'category': 'knowledge'}, {'key': 'know_rules', 'title': 'Rules Reference', 'desc': 'စည်းမျဉ်းကိုးကား', 'category': 'knowledge'}, {'key': 'know_updates', 'title': 'Updates', 'desc': 'ပြောင်းလဲမှုမှတ်တမ်း', 'category': 'knowledge'}, {'key': 'know_changelog', 'title': 'Changelog', 'desc': 'ဗားရှင်းမှတ်တမ်း', 'category': 'knowledge'}, {'key': 'know_fixes', 'title': 'Known Fixes', 'desc': 'ပြင်ဆင်နည်းများ', 'category': 'knowledge'}, {'key': 'know_troubleshooting', 'title': 'Troubleshooting', 'desc': 'ပြဿနာဖြေရှင်းနည်း', 'category': 'knowledge'}, {'key': 'know_ideas', 'title': 'Knowledge Ideas', 'desc': 'ဗဟုသုတအကြံ', 'category': 'knowledge'}, {'key': 'know_case_studies', 'title': 'Case Studies', 'desc': 'ဖြစ်ရပ်လေ့လာချက်', 'category': 'knowledge'}, {'key': 'know_archive', 'title': 'Knowledge Archive', 'desc': 'ဗဟုသုတသိမ်းဆည်းရာ', 'category': 'knowledge'}, {'key': 'event_calendar', 'title': 'Event Calendar', 'desc': 'ပွဲပြက္ခဒိန်', 'category': 'events'}, {'key': 'event_rsvp', 'title': 'RSVP List', 'desc': 'တက်ရောက်မည်စာရင်း', 'category': 'events'}, {'key': 'event_guests', 'title': 'Guest List', 'desc': 'ဧည့်သည်စာရင်း', 'category': 'events'}, {'key': 'event_hosts', 'title': 'Hosts', 'desc': 'ဦးဆောင်သူစာရင်း', 'category': 'events'}, {'key': 'event_speakers', 'title': 'Speakers', 'desc': 'ဟောပြောသူစာရင်း', 'category': 'events'}, {'key': 'event_topics', 'title': 'Event Topics', 'desc': 'ပွဲခေါင်းစဉ်', 'category': 'events'}, {'key': 'event_agenda', 'title': 'Event Agenda', 'desc': 'ပွဲအစီအစဉ်', 'category': 'events'}, {'key': 'event_checkin', 'title': 'Event Check-in', 'desc': 'ပွဲတက်ရောက်မှု', 'category': 'events'}, {'key': 'event_feedback', 'title': 'Event Feedback', 'desc': 'ပွဲအကြံပြုချက်', 'category': 'events'}, {'key': 'event_photos', 'title': 'Event Photos', 'desc': 'ပွဲဓာတ်ပုံ', 'category': 'events'}, {'key': 'event_highlights', 'title': 'Highlights', 'desc': 'ပွဲအမှတ်တရ', 'category': 'events'}, {'key': 'event_sponsors', 'title': 'Sponsors', 'desc': 'ပံ့ပိုးသူများ', 'category': 'events'}, {'key': 'event_prizes', 'title': 'Event Prizes', 'desc': 'ပွဲဆုများ', 'category': 'events'}, {'key': 'event_volunteers', 'title': 'Event Volunteers', 'desc': 'ပွဲကူညီသူ', 'category': 'events'}, {'key': 'event_duties', 'title': 'Event Duties', 'desc': 'ပွဲတာဝန်များ', 'category': 'events'}, {'key': 'event_budget', 'title': 'Event Budget', 'desc': 'ပွဲဘတ်ဂျက်', 'category': 'events'}, {'key': 'event_expenses', 'title': 'Event Expenses', 'desc': 'ပွဲကုန်ကျစရိတ်', 'category': 'events'}, {'key': 'event_venues', 'title': 'Venues', 'desc': 'ပွဲနေရာများ', 'category': 'events'}, {'key': 'event_equipment', 'title': 'Event Equipment', 'desc': 'ပွဲပစ္စည်းများ', 'category': 'events'}, {'key': 'event_food', 'title': 'Food Plan', 'desc': 'အစားအသောက်အစီအစဉ်', 'category': 'events'}, {'key': 'event_transport', 'title': 'Event Transport', 'desc': 'ပွဲသွားလာရေး', 'category': 'events'}, {'key': 'event_reminders', 'title': 'Event Reminders', 'desc': 'ပွဲသတိပေးချက်', 'category': 'events'}, {'key': 'event_deadlines', 'title': 'Event Deadlines', 'desc': 'ပွဲနောက်ဆုံးရက်', 'category': 'events'}, {'key': 'event_tasks', 'title': 'Event Tasks', 'desc': 'ပွဲလုပ်ငန်းတာဝန်', 'category': 'events'}, {'key': 'event_ideas', 'title': 'Event Ideas', 'desc': 'ပွဲအကြံဉာဏ်', 'category': 'events'}, {'key': 'event_votes', 'title': 'Event Votes', 'desc': 'ပွဲမဲပေးမှု', 'category': 'events'}, {'key': 'event_themes', 'title': 'Event Themes', 'desc': 'ပွဲအပြင်အဆင်', 'category': 'events'}, {'key': 'event_awards', 'title': 'Awards', 'desc': 'ဆုချီးမြှင့်မှု', 'category': 'events'}, {'key': 'event_results', 'title': 'Event Results', 'desc': 'ပွဲရလဒ်', 'category': 'events'}, {'key': 'event_archive', 'title': 'Event Archive', 'desc': 'ပွဲမှတ်တမ်း', 'category': 'events'}]
GROUP_MODULE_BY_KEY = {item["key"]: item for item in GROUP_MODULES}
GROUP_MODULE_BY_KEY.update({str(i + 1): item for i, item in enumerate(GROUP_MODULES)})
GROUP_MODULE_PAGE_SIZE = 20

async def groupmenu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Browse 300 persistent group modules or operate an individual module."""
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not msg or not chat or chat.type == "private":
        if msg: await msg.reply_text("ဒီစနစ်ကို Group ထဲမှာ အသုံးပြုပါ။")
        return
    args = list(context.args or [])
    if not args:
        await msg.reply_text("🧰 CK GROUP MENU — စနစ် ၃၀၀ ခု\nအုပ်စု ၁၂ ခုရှိပြီး တစ်အုပ်စုလျှင် စနစ် ၂၅ ခုစီ ပါဝင်ပါတယ်။\nအုပ်စုတစ်ခုကို ရွေးပါ။", reply_markup=group_modules_keyboard(chat.id))
        return
    elif args[0].isdigit() and len(args) == 1:
        block = max(1, min(12, int(args[0])))
        start = (block - 1) * 25
        rows = GROUP_MODULES[start:start + 25]
        lines = [f"🧰 CK GROUP MENU — အုပ်စု {block}/12", "အသုံးပြုရန်: /groupmenu module_name add စာသား", ""]
        for idx, item in enumerate(rows, start + 1):
            lines.append(f"{idx:03d}. {item['key']} — {item['desc']}")
        lines += ["", "လုပ်ဆောင်ချက်: add | list | search | pick | count | del ID | clear", "ဥပမာ: /groupmenu member_birthdays add 17-08 — မွေးနေ့"]
        await msg.reply_text("\n".join(lines), reply_markup=group_block_modules_keyboard(chat.id, block))
        return
    key = args[0].lower().strip()
    item = GROUP_MODULE_BY_KEY.get(key)
    if not item:
        await msg.reply_text("Module မတွေ့ပါ။ /groupmenu ကိုဖွင့်ပြီး အုပ်စု ၁ မှ ၁၂ အတွင်း ရွေးပါ။")
        return
    if len(args) < 2:
        await msg.reply_text(f"📁 {item['title']}\n{item['desc']}\n\nအသုံးပြုပုံ:\n/groupmenu {key} add စာသား\n/groupmenu {key} list\n/groupmenu {key} search စကားလုံး\n/groupmenu {key} pick\n/groupmenu {key} count\n/groupmenu {key} del ID\n/groupmenu {key} clear")
        return
    action = args[1].lower()
    payload = " ".join(args[2:]).strip()
    module_key = item['key']
    is_admin = await _is_group_admin(chat.id, user.id, context)
    if action == "add":
        if not payload:
            await msg.reply_text(f"အသုံးပြုပုံ: /groupmenu {module_key} add စာသား")
            return
        if len(payload) > 3000:
            await msg.reply_text("စာသားအရှည် ၃၀၀၀ လုံးထက် မကျော်ရပါ။")
            return
        with db_connect() as conn:
            cur = conn.execute("INSERT INTO ck_group_modules(chat_id,module_key,title,body,created_by,created_at) VALUES(?,?,?,?,?,?)",
                               (chat.id,module_key,item['title'],payload,user.id,int(time.time())))
            new_id = cur.lastrowid
            conn.commit()
        await msg.reply_text(f"✅ {item['title']} ထဲ ထည့်ပြီးပါပြီ။ ID: {new_id}")
        return
    if action in ("list", "show"):
        with db_connect() as conn:
            rows = conn.execute("SELECT id,body,created_by,created_at FROM ck_group_modules WHERE chat_id=? AND module_key=? ORDER BY id DESC LIMIT 30", (chat.id,module_key)).fetchall()
        if not rows:
            await msg.reply_text("စာရင်းမရှိသေးပါ။ add နဲ့ ထည့်နိုင်ပါတယ်။")
            return
        lines = [f"📋 {item['title']} — နောက်ဆုံး {len(rows)} ခု"]
        for row in rows:
            body = row['body'].replace("\n", " ")
            lines.append(f"#{row['id']} · {body[:180]}")
        await msg.reply_text("\n".join(lines))
        return
    if action == "search":
        if not payload:
            await msg.reply_text(f"အသုံးပြုပုံ: /groupmenu {module_key} search စကားလုံး")
            return
        with db_connect() as conn:
            rows = conn.execute("SELECT id,body FROM ck_group_modules WHERE chat_id=? AND module_key=? AND body LIKE ? ORDER BY id DESC LIMIT 20", (chat.id,module_key,f"%{payload[:100]}%")).fetchall()
        await msg.reply_text("\n".join([f"#{r['id']} · {r['body'][:180]}" for r in rows]) if rows else "ကိုက်ညီတဲ့အချက်အလက် မတွေ့ပါ။")
        return
    if action == "pick":
        with db_connect() as conn:
            row = conn.execute("SELECT id,body FROM ck_group_modules WHERE chat_id=? AND module_key=? ORDER BY RANDOM() LIMIT 1", (chat.id,module_key)).fetchone()
        await msg.reply_text(f"🎲 ရွေးချယ်မှု #{row['id']}\n{row['body']}" if row else "ရွေးချယ်ရန် စာရင်းမရှိသေးပါ။")
        return
    if action == "count":
        with db_connect() as conn:
            count = conn.execute("SELECT COUNT(*) FROM ck_group_modules WHERE chat_id=? AND module_key=?", (chat.id,module_key)).fetchone()[0]
        await msg.reply_text(f"📊 {item['title']} ထဲမှာ စုစုပေါင်း {count} ခု ရှိပါတယ်။")
        return
    if action == "del":
        if not payload.isdigit():
            await msg.reply_text(f"အသုံးပြုပုံ: /groupmenu {module_key} del ID")
            return
        entry_id = int(payload)
        with db_connect() as conn:
            row = conn.execute("SELECT created_by FROM ck_group_modules WHERE id=? AND chat_id=? AND module_key=?", (entry_id,chat.id,module_key)).fetchone()
            if not row:
                await msg.reply_text("အဲဒီ ID မတွေ့ပါ။")
                return
            if row['created_by'] != user.id and not is_admin:
                await msg.reply_text("ကိုယ်တိုင်ထည့်ထားတဲ့စာ သို့မဟုတ် Admin ဖြစ်မှ ဖျက်နိုင်ပါတယ်။")
                return
            conn.execute("DELETE FROM ck_group_modules WHERE id=?", (entry_id,))
            conn.commit()
        await msg.reply_text(f"🗑️ ID {entry_id} ကို ဖျက်ပြီးပါပြီ။")
        return
    if action == "clear":
        if not is_admin:
            await msg.reply_text("⛔ ဒီစာရင်းတစ်ခုလုံးရှင်းရန် Group Admin သာ ခွင့်ပြုပါတယ်။")
            return
        with db_connect() as conn:
            cur = conn.execute("DELETE FROM ck_group_modules WHERE chat_id=? AND module_key=?", (chat.id,module_key))
            deleted = cur.rowcount
            conn.commit()
        await msg.reply_text(f"🧹 {item['title']} ထဲက {deleted} ခုကို ရှင်းပြီးပါပြီ။")
        return
    await msg.reply_text("လုပ်ဆောင်ချက်မမှန်ပါ။ add/list/search/pick/count/del/clear ကို သုံးပါ။")


def main():
    if not TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN environment variable is missing.")
    init_db()
    init_super_community_db()
    logger.info("SQLite database initialized at %s", os.path.abspath(DB_PATH))
    if os.path.abspath(DB_PATH).startswith("/data/") and not os.path.isdir("/data"):
        logger.warning("/data volume is not mounted; configure a Railway Volume at /data to keep data across redeploys.")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).concurrent_updates(16).post_init(start_background_tasks).build()
    app.add_handler(ChatMemberHandler(ad_track_group_membership, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS, ad_track_group_activity), group=-1)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("groupmenu", groupmenu_command))
    app.add_handler(CommandHandler("groupset", groupset_command))
    app.add_handler(CommandHandler("channelmenu", channelmenu_command))
    app.add_handler(CommandHandler("channelset", channelset_command))
    app.add_handler(CommandHandler("sethelp", sethelp_command))
    app.add_handler(CommandHandler("appsearch", internet_search_command))
    app.add_handler(CommandHandler("gamesearch", internet_search_command))
    app.add_handler(CommandHandler("book", internet_search_command))
    app.add_handler(CommandHandler("moviesearch", internet_search_command))
    app.add_handler(CommandHandler("wallpaper", internet_search_command))
    app.add_handler(CommandHandler("videosearch", internet_search_command))
    app.add_handler(CommandHandler("education", internet_search_command))
    app.add_handler(CommandHandler("audiosearch", internet_search_command))
    app.add_handler(CommandHandler("docsearch", internet_search_command))
    app.add_handler(CommandHandler("fontsearch", internet_search_command))
    app.add_handler(CommandHandler("movie", movie_command))
    app.add_handler(CommandHandler("movies", movies_command))
    app.add_handler(CommandHandler("moviedel", movie_delete_command))
    app.add_handler(MessageHandler((filters.VIDEO | filters.Document.ALL) & filters.CaptionRegex(r"^/movieadd(?:\s|$)"), movie_add_media), group=0)
    app.add_handler(CommandHandler("adhelp", ad_help_command))
    app.add_handler(CommandHandler("adadd", ad_add_command))
    app.add_handler(CommandHandler("adpreview", ad_preview_command))
    app.add_handler(CommandHandler("adedit", ad_edit_command))
    app.add_handler(CommandHandler("addel", ad_delete_command))
    app.add_handler(CommandHandler("adstart", ad_start_command))
    app.add_handler(CommandHandler("adstop", ad_stop_command))
    app.add_handler(CommandHandler("adstats", ad_stats_command))
    app.add_handler(CommandHandler("tools", tools_menu))
    app.add_handler(CommandHandler("toolhelp", tool_help))
    app.add_handler(CommandHandler("tool", tool_command))
    app.add_handler(CommandHandler("ckhelp", ck_help_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("daily", daily_command))
    app.add_handler(CommandHandler("points", points_command))
    app.add_handler(CommandHandler("leaderboard", leaderboard_command))
    app.add_handler(CommandHandler("mission", mission_command))
    app.add_handler(CommandHandler("feedback", feedback_command))
    app.add_handler(CommandHandler("save", save_command))
    app.add_handler(CommandHandler("saved", saved_command))
    app.add_handler(CommandHandler("delsave", delete_saved_command))
    app.add_handler(CommandHandler("rules", rules_command))
    app.add_handler(CommandHandler("setrules", setrules_command))
    app.add_handler(CommandHandler("setwelcome", setwelcome_command))
    app.add_handler(CommandHandler("groupstats", groupstats_command))
    app.add_handler(CommandHandler("group", group_hub_command))
    app.add_handler(CommandHandler("poll", group_poll_command))
    app.add_handler(CommandHandler("suggest", group_suggest_command))
    app.add_handler(CommandHandler("suggestions", group_suggestions_command))
    app.add_handler(CommandHandler("event", group_event_command))
    app.add_handler(CommandHandler("events", group_events_command))
    app.add_handler(CommandHandler("faq", group_faq_command))
    app.add_handler(CommandHandler("faqadd", group_faqadd_command))
    app.add_handler(CommandHandler("faqdel", group_faqdel_command))
    app.add_handler(CommandHandler("activity", group_activity_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("setlang", setlang_command))
    app.add_handler(CommandHandler("notifications", notifications_command))
    app.add_handler(CommandHandler("referral", referral_command))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, ck_new_member))
    app.add_handler(CommandHandler("ban", ban_command))
    app.add_handler(CommandHandler("unban", unban_command))
    app.add_handler(CommandHandler("kick", kick_command))
    app.add_handler(CommandHandler("mute", mute_command))
    app.add_handler(CommandHandler("unmute", unmute_command))
    app.add_handler(CommandHandler("warn", warn_command))
    app.add_handler(CommandHandler("warnings", warnings_command))
    app.add_handler(CommandHandler("purge", purge_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("tiktok", tiktok_command))
    app.add_handler(CommandHandler("tomorrow", group_tomorrow_command))
    app.add_handler(CommandHandler("tarot", group_tarot_command))
    for zodiac_command in ZODIAC_NAMES:
        app.add_handler(CommandHandler(zodiac_command, group_horoscope_command))
    app.add_handler(CommandHandler("permission", permission_command))
    app.add_handler(CommandHandler("unpermission", unpermission_command))
    app.add_handler(CommandHandler("game", game_command))
    app.add_handler(CommandHandler("addq", add_question_command))
    app.add_handler(CommandHandler("rpg", rpg_command))
    app.add_handler(CommandHandler("pvp", rpg_pvp_command))
    app.add_handler(CommandHandler("mlbbhero", mlbb_image_command))
    app.add_handler(CommandHandler("hero", mlbb_hero_command))
    app.add_handler(CommandHandler("build", mlbb_build_command))
    app.add_handler(CommandHandler("lore", mlbb_lore_command))
    app.add_handler(CommandHandler("combo", mlbb_combo_command))
    app.add_handler(CommandHandler("meta", mlbb_meta_command))
    app.add_handler(CommandHandler("duo", mlbb_duo_command))
    app.add_handler(CommandHandler("life", life50_command))
    app.add_handler(CommandHandler("remind", reminder_command))
    app.add_handler(CommandHandler("reminders", reminders_command))
    app.add_handler(CommandHandler("delreminder", delete_reminder_command))
    app.add_handler(CommandHandler("expense", expense_command))
    app.add_handler(CommandHandler("expenses", expenses_command))
    app.add_handler(CommandHandler("budget", budget_command))
    app.add_handler(CommandHandler("budgetstatus", budget_status_command))
    app.add_handler(CommandHandler("chat", chat_command))
    app.add_handler(CommandHandler("next", next_chat))
    app.add_handler(CommandHandler("stop", stop_chat))
    app.add_handler(CommandHandler("report", report_chat))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & (filters.PHOTO | filters.VIDEO | filters.VOICE | filters.AUDIO | filters.Sticker.ALL), random_chat_media_relay))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.add_error_handler(telegram_error_handler)
    logger.info("CK BOT started: existing systems + Group/Channel setting commands + Community Hub.")
    app.run_polling()


if __name__ == "__main__":
    main()
