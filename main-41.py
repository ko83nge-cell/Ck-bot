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
    await update.effective_message.reply_text(rpg_status_text(update.effective_user), parse_mode="Markdown", reply_markup=rpg_keyboard())


async def rpg_pvp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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


# ------------------------- EXISTING BOT HANDLERS -------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    keyboard = [
        [InlineKeyboardButton("🧠 အဖွဲ့လိုက် ဉာဏ်စမ်းဂိမ်း (Trivia)", callback_data="game_trivia")],
        [InlineKeyboardButton("🎁 ကံစမ်းမဲ ကံကောင်းခြင်းဂိမ်း", callback_data="game_lucky")],
        [InlineKeyboardButton("🦹 သူခိုးဂိမ်း: 'လန်ဘား' ၏ အိမ်ခိုးမှု", callback_data="thief_start")],
        [InlineKeyboardButton("🛡️ Adventure RPG", callback_data="rpg_open")],
        [InlineKeyboardButton("🏠 ပင်မမီနူးသို့", callback_data="menu_start")],
    ]
    await update.message.reply_text(
        "🎮 **ဂိမ်းကစားရန် ရွေးချယ်စရာများ** 🎮\n━━━━━━━━━━━━━━━━━━━\n"
        "ကျေးဇူးပြု၍ အောက်ပါတို့မှ ကြိုက်နှစ်သက်ရာ ဂိမ်းအမျိုးအစားကို ရွေးချယ်ပါ -",
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown",
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

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""

    if data.startswith("rpg_"):
        await query.answer()
        try:
            await rpg_callback(query, context, data)
        except Exception:
            logger.exception("RPG callback failed for %r", data)
            try:
                await query.edit_message_text("⚠️ RPG ဂိမ်းတွင် အမှားတစ်ခု ဖြစ်နေပါတယ်။ /rpg ကို ပြန်ပို့ပြီး ထပ်စမ်းပါ။")
            except Exception:
                logger.exception("Could not display RPG error message")
        return

    await query.answer()

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
        keyboard = [
            [InlineKeyboardButton("🧠 အဖွဲ့လိုက် ဉာဏ်စမ်းဂိမ်း (Trivia)", callback_data="game_trivia")],
            [InlineKeyboardButton("🎁 ကံစမ်းမဲ ကံကောင်းခြင်းဂိမ်း", callback_data="game_lucky")],
            [InlineKeyboardButton("🦹 သူခိုးဂိမ်း: 'လန်ဘား' ၏ အိမ်ခိုးမှု", callback_data="thief_start")],
            [InlineKeyboardButton("🛡️ Adventure RPG", callback_data="rpg_open")],
            [InlineKeyboardButton("🏠 ပင်မမီနူးသို့", callback_data="menu_start")],
        ]
        await query.edit_message_text(
            "🎮 **ဂိမ်းကစားရန် ရွေးချယ်စရာများ** 🎮\n━━━━━━━━━━━━━━━━━━━\nရွေးချယ်ပါ -",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard),
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
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip().lower()
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
