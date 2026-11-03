import os
import json
import time
import random
import logging
import sqlite3
from datetime import datetime, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.helpers import escape_markdown
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
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
        [InlineKeyboardButton("🧠 Trivia", callback_data="game_trivia"), InlineKeyboardButton("🎁 Lucky", callback_data="game_lucky")],
        [InlineKeyboardButton("🦹 Thief", callback_data="thief_start"), InlineKeyboardButton("🏠 ပင်မမီနူး", callback_data="menu_start")],
        [InlineKeyboardButton("🕹️ ဂိမ်းအသစ် ၅၀ မျိုး ကြည့်ရန်", callback_data="a50_page_0")],
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

# ------------------------- EXISTING BOT HANDLERS -------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_group_bot_admin(update, context): return
    keyboard = [
        [InlineKeyboardButton("🌟 ရာသီခွင် အသေးစိတ်ဟောကိန်း", callback_data="mode_zodiac")],
        [InlineKeyboardButton("📅 မနက်ဖြန် ဖြစ်ပျက်မည့်ဟောကိန်း", callback_data="mode_tomorrow")],
        [InlineKeyboardButton("🃏 တားရော့ (၃) ကတ် ဟောရန်", callback_data="mode_tarot")],
        [InlineKeyboardButton("🎮 ဂိမ်းများ ဆော့ကစားရန် (/game)", callback_data="menu_games")],
        [InlineKeyboardButton("🛡️ Adventure RPG (/rpg)", callback_data="rpg_open")],
    ]
    await update.message.reply_text(
        "မင်္ဂလာပါရှင့်/ခဗျာ 🙏\n\n"
        "ဤဘော့တ်မှတဆင့် ဗေဒင်၊ တားရော့နှင့် ဂိမ်းများ ဆော့ကစားနိုင်ပါသည်။\n"
        "မေးခွန်းအသစ်ထည့်ရန် `/addq` ကို အသုံးပြုပါ။\n"
        "Adventure RPG အတွက် `/rpg` ကို အသုံးပြုပါ။",
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


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""

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
        context.user_data["mode"] = "zodiac"
        await query.edit_message_text("✨ **ရာသီခွင် အသေးစိတ် မေးမြန်းရန်**\n\nသင့်ရဲ့ ရာသီခွင်အမည်ကို Chat ထဲမှာ ပို့ပေးပါ။", parse_mode="Markdown")
    elif data == "mode_tomorrow":
        context.user_data["mode"] = "tomorrow"
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
        ]
        await query.edit_message_text("ကျေးဇူးပြု၍ အောက်ပါတို့မှ ရွေးချယ်ပါ -", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat and not await group_bot_is_admin(update.effective_chat, context):
        await require_group_bot_admin(update, context)
        return
    if not update.message or not update.message.text:
        return
    raw_text = update.message.text.strip()
    text = raw_text.lower()
    word_answer = context.user_data.pop("mini_word_answer", None)
    if word_answer is not None:
        if raw_text.strip() == word_answer:
            await update.message.reply_text("🎉 အဖြေမှန်ပါတယ်! Word Puzzle အနိုင်ရပါပြီ။", reply_markup=games_menu_keyboard(query.message.chat.type))
        else:
            await update.message.reply_text(f"❌ မမှန်ပါ။ အဖြေမှန်က '{word_answer}' ဖြစ်ပါတယ်။", reply_markup=games_menu_keyboard(query.message.chat.type))
        return
    current_mode = context.user_data.get("mode", "zodiac")
    matched_key = next((key for key in ZODIAC_NAMES if key in text), None)
    if not matched_key:
        await update.message.reply_text(
            "ရာသီခွင်အမည်ကို English ဖြင့် ပို့ပေးပါ။ ဥပမာ Aries, Taurus, Gemini စသည်ဖြင့်။\n"
            "ဂိမ်းများအတွက် /game၊ Adventure RPG အတွက် /rpg ကို အသုံးပြုပါ။"
        )
        return
    zodiac_title = ZODIAC_NAMES[matched_key]
    if current_mode == "tomorrow":
        response = (
            f"📅 **မနက်ဖြန်အတွက် သင့်ရဲ့ ဟောကိန်းအထူး**\n━━━━━━━━━━━━━━━━━━━\n"
            f"✨ **ရာသီခွင်:** {zodiac_title}\n\n"
            f"🌟 **ဖြစ်ပျက်မည့်အခြေအနေ:**\n{random.choice(TOMORROW_EVENTS)}\n\n"
            f"⚠️ **သတိပြုရှောင်ရှားရမည့်အချက်:**\n{random.choice(TOMORROW_AVOIDS)}"
        )
    else:
        response = (
            f"🔮 **ရာသီခွင် အသေးစိတ်ဟောကိန်း**\n━━━━━━━━━━━━━━━━━━━\n"
            f"✨ **ရာသီခွင်:** {zodiac_title}\n\n"
            f"🧠 **စိတ်နေစိတ်ထား:**\n{random.choice(TRAITS_POOL)}\n\n"
            f"❤️ **အချစ်ရေး:**\n{random.choice(LOVE_POOL)}\n\n"
            f"💼 **လုပ်ငန်းခွင်နှင့် စီးပွားရေး:**\n{random.choice(CAREER_POOL)}"
        )
    keyboard = [
        [InlineKeyboardButton("🔄 အခြားတစ်ခု ထပ်မံမေးမည်", callback_data="menu_start")],
        [InlineKeyboardButton("🏠 ပင်မမီနူးသို့", callback_data="menu_start")],
    ]
    await update.message.reply_text(response, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def telegram_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Unhandled Telegram update error: %s", context.error, exc_info=context.error)


def main():
    if not TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN environment variable is missing.")
    init_db()
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("game", game_command))
    app.add_handler(CommandHandler("addq", add_question_command))
    app.add_handler(CommandHandler("rpg", rpg_command))
    app.add_handler(CommandHandler("pvp", rpg_pvp_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.add_error_handler(telegram_error_handler)
    logger.info("Astrology, existing games and SQLite Adventure RPG bot is running.")
    app.run_polling()


if __name__ == "__main__":
    main()
