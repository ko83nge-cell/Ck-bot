import os
import json
import time
import random
import logging
import sqlite3
from datetime import datetime, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DB_PATH = os.getenv("DB_PATH", "farming_bot.db")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("astrology_farming_bot")

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
    "aquarius": "ကုမ်ရာသီ (Capricorn)",
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

CROPS = {
    "rice": {"name": "စပါး", "seed_price": 12, "sell_price": 32, "seconds": 180, "xp": 5, "yield": (2, 4)},
    "corn": {"name": "ပြောင်း", "seed_price": 18, "sell_price": 48, "seconds": 240, "xp": 7, "yield": (2, 4)},
    "bean": {"name": "ပဲ", "seed_price": 15, "sell_price": 42, "seconds": 210, "xp": 6, "yield": (2, 5)},
    "tomato": {"name": "ခရမ်းချဉ်", "seed_price": 25, "sell_price": 70, "seconds": 300, "xp": 9, "yield": (2, 4)},
    "pumpkin": {"name": "ဖရုံ", "seed_price": 35, "sell_price": 105, "seconds": 420, "xp": 12, "yield": (2, 3)},
}
ANIMALS = {
    "chicken": {"name": "ကြက်", "price": 180, "product": "egg", "product_name": "ကြက်ဥ", "product_value": 22, "interval": 3600},
    "cow": {"name": "နွား", "price": 650, "product": "milk", "product_name": "နို့", "product_value": 75, "interval": 7200},
    "pig": {"name": "ဝက်", "price": 450, "product": "pork", "product_name": "ဝက်ထွက်ကုန်", "product_value": 58, "interval": 5400},
}
STARTING_COINS = 250
STARTING_PLOTS = 2
MAX_PLOTS = 12
LEVEL_XP = 100

def db_connect():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    parent = os.path.dirname(DB_PATH)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with db_connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS farms (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                coins INTEGER NOT NULL DEFAULT 250,
                level INTEGER NOT NULL DEFAULT 1,
                xp INTEGER NOT NULL DEFAULT 0,
                plots_count INTEGER NOT NULL DEFAULT 2,
                seeds TEXT NOT NULL DEFAULT '{}',
                harvest TEXT NOT NULL DEFAULT '{}',
                animals TEXT NOT NULL DEFAULT '{}',
                animal_collected_at INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS farm_plots (
                user_id INTEGER NOT NULL,
                plot_no INTEGER NOT NULL,
                crop TEXT,
                planted_at INTEGER,
                watered INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, plot_no)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_farm_coins ON farms(coins DESC)")
        conn.commit()

def get_farm(user_id, username=None):
    with db_connect() as conn:
        row = conn.execute("SELECT * FROM farms WHERE user_id=?", (user_id,)).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO farms(user_id, username, coins, created_at) VALUES(?,?,?,?)",
                (user_id, username or "", STARTING_COINS, int(time.time())),
            )
            conn.executemany(
                "INSERT INTO farm_plots(user_id, plot_no) VALUES(?,?)",
                [(user_id, n) for n in range(1, STARTING_PLOTS + 1)],
            )
            conn.commit()
            row = conn.execute("SELECT * FROM farms WHERE user_id=?", (user_id,)).fetchone()
        elif username and row["username"] != username:
            conn.execute("UPDATE farms SET username=? WHERE user_id=?", (username, user_id))
            conn.commit()
            row = conn.execute("SELECT * FROM farms WHERE user_id=?", (user_id,)).fetchone()
    return dict(row)

def save_farm_value(user_id, field, value):
    allowed = {"coins", "level", "xp", "plots_count", "seeds", "harvest", "animals", "animal_collected_at"}
    if field not in allowed:
        raise ValueError("Invalid farm field")
    if field in {"seeds", "harvest", "animals"}:
        value = json.dumps(value, ensure_ascii=False)
    with db_connect() as conn:
        conn.execute(f"UPDATE farms SET {field}=? WHERE user_id=?", (value, user_id))
        conn.commit()

def get_plots(user_id):
    with db_connect() as conn:
        rows = conn.execute(
            "SELECT * FROM farm_plots WHERE user_id=? ORDER BY plot_no", (user_id,)
        ).fetchall()
    return [dict(row) for row in rows]

def set_plot(user_id, plot_no, crop=None, planted_at=None, watered=0):
    with db_connect() as conn:
        conn.execute(
            "UPDATE farm_plots SET crop=?, planted_at=?, watered=? WHERE user_id=? AND plot_no=?",
            (crop, planted_at, watered, user_id, plot_no),
        )
        conn.commit()

def add_xp(farm, amount):
    xp = farm["xp"] + amount
    level = farm["level"]
    while xp >= LEVEL_XP * level:
        xp -= LEVEL_XP * level
        level += 1
    save_farm_value(farm["user_id"], "xp", xp)
    save_farm_value(farm["user_id"], "level", level)
    return level > farm["level"]

def fmt_time(seconds):
    seconds = max(0, int(seconds))
    if seconds >= 3600:
        return f"{seconds // 3600} နာရီ {(seconds % 3600) // 60} မိနစ်"
    if seconds >= 60:
        return f"{seconds // 60} မိနစ် {seconds % 60} စက္ကန့်"
    return f"{seconds} စက္ကန့်"

def crop_ready(plot, now=None):
    if not plot["crop"] or not plot["planted_at"]:
        return False
    now = now or int(time.time())
    duration = CROPS[plot["crop"]]["seconds"]
    if plot["watered"]:
        duration = int(duration * 0.8)
    return now >= plot["planted_at"] + duration

def farm_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌱 မျိုးစေ့စိုက်ရန်", callback_data="farm_plant_menu"),
         InlineKeyboardButton("💧 ရေလောင်းရန်", callback_data="farm_water")],
        [InlineKeyboardButton("🧺 ရိတ်သိမ်းရန်", callback_data="farm_harvest"),
         InlineKeyboardButton("🛒 ဈေးဆိုင်", callback_data="farm_shop")],
        [InlineKeyboardButton("💰 သီးနှံရောင်းရန်", callback_data="farm_sell"),
         InlineKeyboardButton("🐔 မွေးမြူရေး", callback_data="farm_animals")],
        [InlineKeyboardButton("⬆️ လယ်ယာအဆင့်မြှင့်", callback_data="farm_upgrade"),
         InlineKeyboardButton("🏆 လယ်သမားစာရင်း", callback_data="farm_leaderboard")],
        [InlineKeyboardButton("🔄 ပြန်လည်ကြည့်ရှု", callback_data="farm_home"),
         InlineKeyboardButton("🎮 ဂိမ်းမီနူး", callback_data="menu_games")],
    ])

def farm_status_text(user_id, username=None):
    farm = get_farm(user_id, username)
    plots = get_plots(user_id)
    seeds = json.loads(farm["seeds"])
    harvest = json.loads(farm["harvest"])
    animals = json.loads(farm["animals"])
    now = int(time.time())
    lines = [
        "🌾 **သင့်ရဲ့ ကိုယ်ပိုင်လယ်ယာ**",
        "━━━━━━━━━━━━━━━━━━",
        f"👨‍🌾 လယ်သမား: {farm['username'] or 'Farmer'}",
        f"💰 ငွေ: **{farm['coins']}**",
        f"⭐ အဆင့်: **{farm['level']}**  | XP: {farm['xp']}/{LEVEL_XP * farm['level']}",
        f"🌱 မြေကွက်: {farm['plots_count']} ကွက်",
        "",
        "**🧑‍🌾 လယ်ကွက်အခြေအနေ**",
    ]
    for plot in plots:
        if not plot["crop"]:
            lines.append(f"▫️ ကွက် {plot['plot_no']}: မြေလွတ်")
        else:
            crop = CROPS[plot["crop"]]
            if crop_ready(plot, now):
                status = "✅ ရိတ်သိမ်းရန် အသင့်"
            else:
                duration = int(crop["seconds"] * (0.8 if plot["watered"] else 1))
                remaining = plot["planted_at"] + duration - now
                status = f"⏳ {fmt_time(remaining)} ကျန်"
            water_status = " | 💧 ရေလောင်းပြီး" if plot["watered"] else ""
            lines.append(f"🌿 ကွက် {plot['plot_no']}: {crop['name']} — {status}{water_status}")
    lines += ["", "**📦 သိုလှောင်ရုံ**"]
    seed_text = "၊ ".join(f"{CROPS[k]['name']} မျိုးစေ့ {v}" for k, v in seeds.items() if v) or "မရှိသေးပါ"
    harvest_text = "၊ ".join(f"{CROPS[k]['name']} {v}" for k, v in harvest.items() if v) or "မရှိသေးပါ"
    animal_text = "၊ ".join(f"{ANIMALS[k]['name']} {v}" for k, v in animals.items() if v) or "မရှိသေးပါ"
    lines += [f"🌰 မျိုးစေ့: {seed_text}", f"🧺 သီးနှံ: {harvest_text}", f"🐄 တိရစ္ဆာန်: {animal_text}"]
    return "\n".join(lines)

async def show_farm(update_or_query, context, edit=False):
    user = update_or_query.effective_user
    text = farm_status_text(user.id, user.username or user.first_name)
    if edit:
        await update_or_query.edit_message_text(text, parse_mode="Markdown", reply_markup=farm_keyboard())
    else:
        await update_or_query.effective_message.reply_text(text, parse_mode="Markdown", reply_markup=farm_keyboard())

async def farm_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_farm(update, context)

async def farm_help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌾 **စိုက်ပျိုးရေးဂိမ်း လမ်းညွှန်**\n"
        "/farm — လယ်ယာဖွင့်ရန်\n"
        "/farmhelp — ကစားနည်း\n\n"
        "မျိုးစေ့ဝယ် → မြေကွက်တွင်စိုက် → ရေလောင်း → ကြီးထွားချိန်စောင့် → ရိတ်သိမ်း → ရောင်းချပါ။\n"
        "ရေလောင်းထားလျှင် ကြီးထွားချိန် ၂၀% လျော့နည်းမည်။ ရောင်းရငွေဖြင့် မြေကွက်နှင့် တိရစ္ဆာန်များ တိုးချဲ့နိုင်သည်။",
        parse_mode="Markdown",
    )

async def farm_callback(query, context, data):
    user = query.from_user
    uid = user.id
    farm = get_farm(uid, user.username or user.first_name)
    seeds = json.loads(farm["seeds"])
    harvest = json.loads(farm["harvest"])
    animals = json.loads(farm["animals"])

    if data == "farm_home":
        await show_farm(query, context, edit=True)
        return

    if data == "farm_shop":
        rows = []
        for key, crop in CROPS.items():
            rows.append([InlineKeyboardButton(
                f"🌰 {crop['name']} မျိုးစေ့ — {crop['seed_price']} 💰",
                callback_data=f"farm_buy_{key}",
            )])
        rows.append([InlineKeyboardButton("⬅️ လယ်ယာသို့", callback_data="farm_home")])
        await query.edit_message_text(
            f"🛒 **မျိုးစေ့ဆိုင်**\nသင့်ငွေ: {farm['coins']} 💰\nဝယ်ယူလိုသည့် မျိုးစေ့ကို ရွေးပါ။",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(rows),
        )
        return

    if data.startswith("farm_buy_"):
        key = data.replace("farm_buy_", "", 1)
        crop = CROPS.get(key)
        if not crop:
            return
        if farm["coins"] < crop["seed_price"]:
            await query.answer("ငွေမလုံလောက်ပါ။ သီးနှံရောင်းပြီး ငွေရှာပါ။", show_alert=True)
            return
        seeds[key] = seeds.get(key, 0) + 1
        save_farm_value(uid, "coins", farm["coins"] - crop["seed_price"])
        save_farm_value(uid, "seeds", seeds)
        await query.answer(f"{crop['name']} မျိုးစေ့ ၁ ထုပ် ဝယ်ပြီးပါပြီ။")
        farm = get_farm(uid)
        await query.edit_message_text(
            f"✅ {crop['name']} မျိုးစေ့ ၁ ထုပ် ဝယ်ယူပြီးပါပြီ။\n💰 လက်ကျန်ငွေ: {farm['coins']}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛒 ဆက်ဝယ်မည်", callback_data="farm_shop")],
                [InlineKeyboardButton("🌾 လယ်ယာသို့", callback_data="farm_home")],
            ]),
        )
        return

    if data == "farm_plant_menu":
        empty = [p for p in get_plots(uid) if not p["crop"]]
        if not empty:
            await query.answer("မြေလွတ်မရှိပါ။ ရိတ်သိမ်းပါ သို့မဟုတ် မြေကွက်တိုးချဲ့ပါ။", show_alert=True)
            return
        rows = []
        for plot in empty:
            for key, count in seeds.items():
                if count > 0:
                    rows.append([InlineKeyboardButton(
                        f"ကွက် {plot['plot_no']} တွင် {CROPS[key]['name']} စိုက်မည် (မျိုးစေ့ {count})",
                        callback_data=f"farm_plant_{plot['plot_no']}_{key}",
                    )])
        if not rows:
            await query.edit_message_text(
                "🌰 မျိုးစေ့မရှိသေးပါ။ ဈေးဆိုင်မှ မျိုးစေ့ဝယ်ယူပါ။",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🛒 ဈေးဆိုင်", callback_data="farm_shop")],
                    [InlineKeyboardButton("⬅️ လယ်ယာသို့", callback_data="farm_home")],
                ]),
            )
            return
        rows.append([InlineKeyboardButton("⬅️ လယ်ယာသို့", callback_data="farm_home")])
        await query.edit_message_text("🌱 **စိုက်မည့် မြေကွက်နှင့် မျိုးစေ့ ရွေးပါ။**", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(rows))
        return

    if data.startswith("farm_plant_"):
        parts = data.split("_")
        plot_no, key = int(parts[2]), parts[3]
        current_seeds = json.loads(get_farm(uid)["seeds"])
        if key not in CROPS or current_seeds.get(key, 0) < 1:
            await query.answer("မျိုးစေ့ မရှိတော့ပါ။", show_alert=True)
            return
        plot = next((p for p in get_plots(uid) if p["plot_no"] == plot_no), None)
        if not plot or plot["crop"]:
            await query.answer("ဒီမြေကွက်မှာ စိုက်လို့မရပါ။", show_alert=True)
            return
        current_seeds[key] -= 1
        save_farm_value(uid, "seeds", current_seeds)
        set_plot(uid, plot_no, key, int(time.time()), 0)
        await query.answer("စိုက်ပျိုးပြီးပါပြီ။")
        await show_farm(query, context, edit=True)
        return

    if data == "farm_water":
        plots = [p for p in get_plots(uid) if p["crop"] and not p["watered"] and not crop_ready(p)]
        if not plots:
            await query.answer("ရေလောင်းရန် အပင်မရှိပါ။", show_alert=True)
            return
        rows = [[InlineKeyboardButton(f"💧 ကွက် {p['plot_no']} ({CROPS[p['crop']]['name']})", callback_data=f"farm_water_{p['plot_no']}")] for p in plots]
        rows.append([InlineKeyboardButton("⬅️ လယ်ယာသို့", callback_data="farm_home")])
        await query.edit_message_text("💧 ရေလောင်းမည့် အပင်ကို ရွေးပါ။", reply_markup=InlineKeyboardMarkup(rows))
        return

    if data.startswith("farm_water_"):
        plot_no = int(data.rsplit("_", 1)[1])
        plot = next((p for p in get_plots(uid) if p["plot_no"] == plot_no), None)
        if not plot or not plot["crop"] or plot["watered"] or crop_ready(plot):
            await query.answer("ဒီအပင်ကို ရေလောင်းလို့မရတော့ပါ။", show_alert=True)
            return
        set_plot(uid, plot_no, plot["crop"], plot["planted_at"], 1)
        await query.answer("💧 ရေလောင်းပြီးပါပြီ။ ကြီးထွားချိန် ၂၀% လျော့သွားပါပြီ။")
        await show_farm(query, context, edit=True)
        return

    if data == "farm_harvest":
        plots = get_plots(uid)
        now = int(time.time())
        harvested = []
        total_xp = 0
        for plot in plots:
            if plot["crop"] and crop_ready(plot, now):
                key = plot["crop"]
                qty = random.randint(*CROPS[key]["yield"])
                harvest[key] = harvest.get(key, 0) + qty
                total_xp += CROPS[key]["xp"]
                harvested.append(f"{CROPS[key]['name']} {qty}")
                set_plot(uid, plot["plot_no"], None, None, 0)
        if not harvested:
            await query.answer("ရိတ်သိမ်းရန် အသင့်ဖြစ်သော သီးနှံမရှိသေးပါ။", show_alert=True)
            return
        save_farm_value(uid, "harvest", harvest)
        leveled = add_xp(get_farm(uid), total_xp)
        result = "၊ ".join(harvested)
        await query.edit_message_text(
            f"🧺 **ရိတ်သိမ်းမှု အောင်မြင်ပါပြီ!**\n{result}\n⭐ XP +{total_xp}" + ("\n🎉 Level တက်သွားပါပြီ!" if leveled else ""),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💰 သီးနှံရောင်းရန်", callback_data="farm_sell")],
                [InlineKeyboardButton("🌾 လယ်ယာသို့", callback_data="farm_home")],
            ]),
        )
        return

    if data == "farm_sell":
        if not any(v > 0 for v in harvest.values()):
            await query.answer("ရောင်းရန် သီးနှံမရှိသေးပါ။", show_alert=True)
            return
        total = sum(CROPS[k]["sell_price"] * qty for k, qty in harvest.items() if k in CROPS)
        summary = "၊ ".join(f"{CROPS[k]['name']} {v}" for k, v in harvest.items() if k in CROPS and v)
        save_farm_value(uid, "harvest", {})
        save_farm_value(uid, "coins", farm["coins"] + total)
        await query.edit_message_text(
            f"💰 **သီးနှံရောင်းချပြီးပါပြီ!**\n{summary}\nရရှိငွေ: **{total}**\nလက်ကျန်ငွေ: **{farm['coins'] + total}**",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🌾 လယ်ယာသို့", callback_data="farm_home")]]),
        )
        return

    if data == "farm_upgrade":
        next_slots = farm["plots_count"] + 1
        price = 300 + (farm["plots_count"] - STARTING_PLOTS) * 180
        if farm["plots_count"] >= MAX_PLOTS:
            await query.answer("မြေကွက်အများဆုံးအရေအတွက် ရောက်ရှိပါပြီ။", show_alert=True)
            return
        if farm["coins"] < price:
            await query.answer(f"ငွေမလုံလောက်ပါ။ လိုအပ်ငွေ {price} ဖြစ်ပါတယ်။", show_alert=True)
            return
        with db_connect() as conn:
            conn.execute("INSERT INTO farm_plots(user_id, plot_no) VALUES(?,?)", (uid, next_slots))
            conn.execute("UPDATE farms SET coins=coins-?, plots_count=? WHERE
