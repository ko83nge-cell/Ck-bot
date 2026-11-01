import os
import random
import logging
import sqlite3
import asyncio
from urllib.parse import quote
from datetime import date, datetime
from typing import Optional

import httpx
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ContextTypes, filters
)

# ============================================================
# Mystic AI Astrology Bot
# Standalone Telegram bot | GitHub + Railway
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DB_PATH = os.getenv("DB_PATH", "mystic_astrology.db")
AI_API_URL = os.getenv("AI_API_URL", "https://text.pollinations.ai/").strip()
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=getattr(logging, LOG_LEVEL, logging.INFO),
)
logger = logging.getLogger("mystic_astrology")

# ----- Language strings -----
TEXT = {
    "my": {
        "welcome": "🔮 <b>Mystic Astrology Bot မှ ကြိုဆိုပါတယ်။</b>\n\nတားရော့၊ ရာသီခွင်၊ မွေးနေ့အခြေခံဖော်ပြချက်နှင့် နေ့စဉ်ဘဝလမ်းညွှန်များကို လေ့လာနိုင်ပါတယ်။\n\nအောက်ပါ Menu မှ ရွေးချယ်ပါ။",
        "menu": "🔮 အဓိက Menu",
        "tarot": "🔮 တားရော့",
        "zodiac": "♈ ရာသီခွင်",
        "birth": "🌟 မွေးနေ့ / ဇာတာ",
        "love": "💖 ချစ်ရေး",
        "daily": "🌙 နေ့စဉ်ဟောကိန်း",
        "ai": "🤖 AI ဗေဒင်ဆရာ",
        "past": "🧿 အတိတ် / အနာဂတ်",
        "education": "📚 ပညာရေး / အလုပ်",
        "compat": "💑 ရာသီခွင်ကိုက်ညီမှု",
        "profile": "👤 ကျွန်ုပ်၏အချက်အလက်",
        "language": "🌐 ဘာသာစကား",
        "help": "ℹ️ အကူအညီ",
        "choose": "လုပ်ဆောင်ချက်တစ်ခု ရွေးချယ်ပါ။",
        "ask_birth": "မွေးနေ့ကို DD-MM-YYYY ပုံစံဖြင့် ပို့ပါ။ ဥပမာ 14-02-2000\n\nမသိမ်းလိုပါက /cancel ကိုနှိပ်ပါ။",
        "bad_date": "ရက်စွဲပုံစံ မမှန်ပါ။ DD-MM-YYYY ပုံစံဖြင့် ပြန်ပို့ပါ။",
        "saved": "✅ မွေးနေ့ကို သိမ်းဆည်းပြီးပါပြီ။",
        "no_birth": "မွေးနေ့ မသိမ်းရသေးပါ။ /birth ကိုနှိပ်ပြီး ထည့်သွင်းပါ။",
        "choose_sign": "ရာသီခွင်ကို ရွေးချယ်ပါ။",
        "choose_second": "ဒုတိယလူ၏ ရာသီခွင်ကို ရွေးချယ်ပါ။",
        "ai_prompt": "ဗေဒင်နှင့် နေ့စဉ်ဘဝဆိုင်ရာ မေးခွန်းကို ရေးပို့ပါ။\n\nမေးခွန်းရပ်ရန် /cancel ကိုနှိပ်ပါ။",
        "thinking": "🔮 စဉ်းစားနေပါတယ်...",
        "cancel": "လုပ်ဆောင်ချက်ကို ပယ်ဖျက်လိုက်ပါပြီ။",
        "unknown": "မေးခွန်းကို နားမလည်ပါ။ Menu မှ ရွေးချယ်ပါ သို့မဟုတ် /help ကိုနှိပ်ပါ။",
        "daily_title": "🌙 ယနေ့အတွက် သင့်လမ်းညွှန်",
        "disclaimer": "⚠️ ဤဖော်ပြချက်များသည် အပျော်သဘောနှင့် ကိုယ်တိုင်ဆင်ခြင်နိုင်ရန် လမ်းညွှန်ချက်များသာ ဖြစ်သည်။ အရေးကြီးသော ကျန်းမာရေး၊ ငွေကြေး၊ ဥပဒေရေးရာ ဆုံးဖြတ်ချက်များအတွက် ပညာရှင်၏ အကြံဉာဏ်ကို ရယူပါ။",
        "ai_fallback": "AI ဝန်ဆောင်မှုကို ယခုချိန်တွင် မရရှိနိုင်ပါ။ အောက်ပါ အထွေထွေလမ်းညွှန်ချက်ကို ဖတ်ရှုပါ။",
    },
    "en": {
        "welcome": "🔮 <b>Welcome to Mystic Astrology Bot.</b>\n\nExplore tarot, zodiac signs, birth-date insights and daily reflections.\n\nChoose an option below.",
        "menu": "🔮 Main Menu",
        "tarot": "🔮 Tarot Reading",
        "zodiac": "♈ Zodiac Signs",
        "birth": "🌟 Birth Profile",
        "love": "💖 Love Reading",
        "daily": "🌙 Daily Horoscope",
        "ai": "🤖 AI Astrology Guide",
        "past": "🧿 Past & Future",
        "education": "📚 Study & Career",
        "compat": "💑 Compatibility",
        "profile": "👤 My Profile",
        "language": "🌐 Language",
        "help": "ℹ️ Help",
        "choose": "Choose an option.",
        "ask_birth": "Send your birth date in DD-MM-YYYY format. Example: 14-02-2000\n\nUse /cancel to stop.",
        "bad_date": "Invalid date. Please use DD-MM-YYYY.",
        "saved": "✅ Birth date saved.",
        "no_birth": "No birth date saved. Use /birth to add it.",
        "choose_sign": "Choose a zodiac sign.",
        "choose_second": "Choose the second person's zodiac sign.",
        "ai_prompt": "Send your question about astrology or everyday life.\n\nUse /cancel to stop.",
        "thinking": "🔮 Thinking...",
        "cancel": "Action cancelled.",
        "unknown": "I didn't understand. Choose from the menu or use /help.",
        "daily_title": "🌙 Your Daily Reflection",
        "disclaimer": "⚠️ These readings are for entertainment and personal reflection only. Seek qualified advice for important medical, financial or legal decisions.",
        "ai_fallback": "The AI service is unavailable right now. Here is a general reflection instead:",
    },
}

SIGNS = [
    ("aries", "♈ Aries", "မိဿ", "Mar 21 – Apr 19"),
    ("taurus", "♉ Taurus", "ပြိဿ", "Apr 20 – May 20"),
    ("gemini", "♊ Gemini", "မေထုန်", "May 21 – Jun 20"),
    ("cancer", "♋ Cancer", "ကရကဋ်", "Jun 21 – Jul 22"),
    ("leo", "♌ Leo", "သိဟ်", "Jul 23 – Aug 22"),
    ("virgo", "♍ Virgo", "ကန်", "Aug 23 – Sep 22"),
    ("libra", "♎ Libra", "တူ", "Sep 23 – Oct 22"),
    ("scorpio", "♏ Scorpio", "ဗြိစ္ဆာ", "Oct 23 – Nov 21"),
    ("sagittarius", "♐ Sagittarius", "ဓနု", "Nov 22 – Dec 21"),
    ("capricorn", "♑ Capricorn", "မကာရ", "Dec 22 – Jan 19"),
    ("aquarius", "♒ Aquarius", "ကုမ်", "Jan 20 – Feb 18"),
    ("pisces", "♓ Pisces", "မိန်", "Feb 19 – Mar 20"),
]
SIGN_INFO = {
    "aries": ("မီး", "စတင်လုပ်ဆောင်လိုစိတ်၊ သတ္တိနှင့် တက်ကြွမှု", "Fire", "initiative, courage and energy"),
    "taurus": ("မြေ", "တည်ငြိမ်မှု၊ သည်းခံမှုနှင့် လက်တွေ့ကျမှု", "Earth", "stability, patience and practicality"),
    "gemini": ("လေ", "ဆက်သွယ်ရေး၊ စူးစမ်းလိုစိတ်နှင့် လိုက်လျောညီထွေမှု", "Air", "communication, curiosity and adaptability"),
    "cancer": ("ရေ", "ခံစားချက်၊ ဂရုစိုက်မှုနှင့် မိသားစုကို တန်ဖိုးထားမှု", "Water", "emotion, care and family values"),
    "leo": ("မီး", "ယုံကြည်မှု၊ ဖန်တီးနိုင်စွမ်းနှင့် ဦးဆောင်မှု", "Fire", "confidence, creativity and leadership"),
    "virgo": ("မြေ", "အသေးစိတ်ဂရုပြုမှု၊ စနစ်တကျလုပ်ဆောင်မှု", "Earth", "attention to detail and organization"),
    "libra": ("လေ", "မျှတမှု၊ ပူးပေါင်းဆောင်ရွက်မှုနှင့် အလှအပ", "Air", "balance, cooperation and harmony"),
    "scorpio": ("ရေ", "နက်ရှိုင်းမှု၊ စိတ်ဓာတ်ခိုင်မာမှုနှင့် သစ္စာ", "Water", "depth, resilience and loyalty"),
    "sagittarius": ("မီး", "လွတ်လပ်မှု၊ စွန့်စားမှုနှင့် သင်ယူလိုစိတ်", "Fire", "freedom, adventure and learning"),
    "capricorn": ("မြေ", "တာဝန်ယူမှု၊ ရည်မှန်းချက်နှင့် ဇွဲလုံ့လ", "Earth", "responsibility, ambition and discipline"),
    "aquarius": ("လေ", "ဆန်းသစ်တီထွင်မှု၊ လွတ်လပ်သောအတွေး", "Air", "innovation and independent thinking"),
    "pisces": ("ရေ", "စိတ်ကူးစိတ်သန်း၊ ကိုယ်ချင်းစာမှုနှင့် အနုပညာ", "Water", "imagination, empathy and artistry"),
}

TAROT = [
    ("The Fool", "အသစ်တစ်ခုကို စတင်ရန် အခွင့်အရေး။ မစဉ်းစားဘဲ ခုန်မချဘဲ အချက်အလက်ကို စစ်ဆေးပါ။", "A fresh beginning is possible. Stay open, but check the facts before leaping."),
    ("The Magician", "သင့်တွင် လိုအပ်သော အရည်အချင်းများ ရှိနေပြီ။ စီမံကိန်းကို လက်တွေ့စတင်ပါ။", "You already have useful skills. Turn an idea into a practical first step."),
    ("The High Priestess", "အလျင်စလိုမဆုံးဖြတ်ပါနှင့်။ အချက်အလက်ကို နားထောင်ပြီး အတွင်းစိတ်ကို ပြန်လည်သုံးသပ်ပါ။", "Pause before deciding. Listen carefully and reflect on what you know."),
    ("The Empress", "ကြီးထွားမှု၊ ဂရုစိုက်မှုနှင့် ဖန်တီးမှုကို အလေးထားရမည့်ကာလ။", "A time to nurture growth, creativity and supportive relationships."),
    ("The Emperor", "စည်းကမ်းနှင့် အစီအစဉ်က အရေးကြီးသည်။ တာဝန်များကို ရှင်းလင်းစွာ သတ်မှတ်ပါ။", "Structure and responsibility help. Set clear boundaries and priorities."),
    ("The Lovers", "ဆက်ဆံရေးနှင့် တန်ဖိုးထားမှုများအပေါ် ရိုးသားသော ရွေးချယ်မှုတစ်ခု လိုအပ်နိုင်သည်။", "An honest choice about relationships or personal values may be needed."),
    ("The Chariot", "ရည်မှန်းချက်ကို အာရုံစိုက်ပြီး တစ်ဆင့်ချင်း ဆက်လက်လုပ်ဆောင်ပါ။", "Focus on your goal and keep moving one deliberate step at a time."),
    ("Strength", "နူးညံ့သော်လည်း ခိုင်မာသော စိတ်ဓာတ်ဖြင့် အခက်အခဲကို ရင်ဆိုင်ပါ။", "Meet challenges with patient, steady courage rather than force."),
    ("The Hermit", "ခဏတာ တိတ်ဆိတ်စွာနေပြီး ကိုယ့်ရည်မှန်းချက်ကို ပြန်လည်သုံးသပ်ပါ။", "Take quiet time to review your direction and priorities."),
    ("Wheel of Fortune", "အခြေအနေများ ပြောင်းလဲနိုင်သည်။ ကိုယ်ထိန်းချုပ်နိုင်သည့်အရာကို အာရုံစိုက်ပါ။", "Circumstances can change. Focus on what remains within your control."),
    ("Justice", "မျှတမှုနှင့် အချက်အလက်အပေါ် အခြေခံပြီး ဆုံးဖြတ်ပါ။", "Make decisions based on fairness, facts and accountability."),
    ("The Star", "မျှော်လင့်ချက်နှင့် ပြန်လည်အားဖြည့်မှုကို ကိုယ်စားပြုသည်။ ရည်မှန်းချက်ငယ်တစ်ခု စတင်ပါ။", "A symbol of hope and renewal. Begin with one manageable goal."),
    ("The Moon", "မသေချာမှုများ ရှိနိုင်သည်။ ကောလာဟလထက် အတည်ပြုနိုင်သော အချက်အလက်ကို ယုံပါ။", "Uncertainty may be present. Verify information rather than relying on assumptions."),
    ("The Sun", "တက်ကြွမှုနှင့် ပွင့်လင်းမှုကို အားပေးသည်။ အောင်မြင်မှုငယ်များကို အသိအမှတ်ပြုပါ။", "A positive symbol for energy and clarity. Notice and celebrate small wins."),
    ("The World", "အဆင့်တစ်ခု ပြီးဆုံးပြီး နောက်တစ်ဆင့်သို့ ကူးပြောင်းရန် အချိန်ဖြစ်နိုင်သည်။", "A cycle may be reaching completion. Review what you learned before moving on."),
]
DAILY_MY = [
    "ယနေ့ အရေးကြီးဆုံးအလုပ်တစ်ခုကို ဦးစားပေးပြီး အာရုံစိုက်ပါ။",
    "စကားပြောရာတွင် နားထောင်မှုကို ဦးစားပေးပါ။ နားလည်မှုလွဲခြင်းကို လျှော့ချနိုင်သည်။",
    "အသုံးစရိတ်ကို စစ်ဆေးပြီး မလိုအပ်သော ဝယ်ယူမှုကို ခဏရွှေ့ဆိုင်းပါ။",
    "သင်ယူမှုအသစ်တစ်ခုအတွက် အချိန် ၂၀ မိနစ်ပေးပါ။",
    "အနားယူခြင်းနှင့် အလုပ်လုပ်ခြင်းကို မျှတအောင် စီစဉ်ပါ။",
]
DAILY_EN = [
    "Prioritize one meaningful task and give it your full attention.",
    "Listen carefully in conversations to reduce misunderstandings.",
    "Review spending and pause before making an unnecessary purchase.",
    "Set aside twenty minutes to learn something useful.",
    "Balance effort with rest and make room to recharge.",
]

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, language TEXT DEFAULT 'my',
        birth_date TEXT, created_at TEXT
    )""")
    conn.commit()
    return conn

def get_user(user_id: int):
    with db() as conn:
        row = conn.execute(
            "SELECT user_id, username, language, birth_date FROM users WHERE user_id=?",
            (user_id,)
        ).fetchone()
    return row

def save_user(user_id: int, username: str = "", **fields):
    allowed = {"language", "birth_date"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    with db() as conn:
        exists = conn.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO users(user_id, username, created_at) VALUES(?,?,?)",
                (user_id, username or "", datetime.utcnow().isoformat())
            )
        if username is not None:
            conn.execute("UPDATE users SET username=? WHERE user_id=?", (username or "", user_id))
        for key, value in fields.items():
            conn.execute(f"UPDATE users SET {key}=? WHERE user_id=?", (value, user_id))
        conn.commit()

def lang_of(user_id: int) -> str:
    row = get_user(user_id)
    return row[2] if row and row[2] in TEXT else "my"

def t(user_id: int, key: str) -> str:
    return TEXT[lang_of(user_id)].get(key, TEXT["my"].get(key, key))

def main_keyboard(user_id: int):
    keys = [
        [t(user_id, "tarot"), t(user_id, "zodiac")],
        [t(user_id, "birth"), t(user_id, "love")],
        [t(user_id, "daily"), t(user_id, "ai")],
        [t(user_id, "past"), t(user_id, "education")],
        [t(user_id, "compat"), t(user_id, "profile")],
        [t(user_id, "language"), t(user_id, "help")],
    ]
    return ReplyKeyboardMarkup(keys, resize_keyboard=True)

def sign_for_date(d: date) -> str:
    m, day = d.month, d.day
    if (m == 3 and day >= 21) or (m == 4 and day <= 19): return "aries"
    if (m == 4 and day >= 20) or (m == 5 and day <= 20): return "taurus"
    if (m == 5 and day >= 21) or (m == 6 and day <= 20): return "gemini"
    if (m == 6 and day >= 21) or (m == 7 and day <= 22): return "cancer"
    if (m == 7 and day >= 23) or (m == 8 and day <= 22): return "leo"
    if (m == 8 and day >= 23) or (m == 9 and day <= 22): return "virgo"
    if (m == 9 and day >= 23) or (m == 10 and day <= 22): return "libra"
    if (m == 10 and day >= 23) or (m == 11 and day <= 21): return "scorpio"
    if (m == 11 and day >= 22) or (m == 12 and day <= 21): return "sagittarius"
    if (m == 12 and day >= 22) or (m == 1 and day <= 19): return "capricorn"
    if (m == 1 and day >= 20) or (m == 2 and day <= 18): return "aquarius"
    return "pisces"

def sign_label(sign: str, lang: str) -> str:
    for key, en, my, dates in SIGNS:
        if key == sign:
            return f"{en} ({my})" if lang == "my" else en
    return sign

def sign_keyboard(prefix="sign"):
    rows, row = [], []
    for i, (key, en, my, dates) in enumerate(SIGNS, 1):
        row.append(InlineKeyboardButton(f"{en}", callback_data=f"{prefix}:{key}"))
        if len(row) == 3:
            rows.append(row); row = []
    if row: rows.append(row)
    return InlineKeyboardMarkup(rows)

def horoscope(sign: str, lang: str, category: str = "daily") -> str:
    info = SIGN_INFO[sign]
    label = sign_label(sign, lang)
    seed = f"{date.today().isoformat()}-{sign}-{category}"
    rng = random.Random(seed)
    if lang == "my":
        themes = [
            "အလုပ်များကို အစီအစဉ်တကျ ခွဲလုပ်ပါ။ အလျင်လိုခြင်းထက် တည်ငြိမ်မှုက ပိုအကျိုးရှိနိုင်သည်။",
            "ဆက်ဆံရေးတွင် ရိုးသားစွာ ပြောဆိုပြီး တစ်ဖက်လူ၏အမြင်ကိုလည်း နားထောင်ပါ။",
            "သင်ယူမှုနှင့် ကိုယ်ပိုင်တိုးတက်မှုအတွက် အချိန်ပေးပါ။ ရလဒ်ကို တစ်နေ့တည်း မမျှော်လင့်ပါနှင့်။",
            "ငွေကြေးကိစ္စတွင် အသေးစိတ်စစ်ဆေးပြီး အရေးကြီးသော ဆုံးဖြတ်ချက်ကို အချက်အလက်အပေါ် အခြေခံပါ။",
        ]
        categories = {
            "love": "💖 ချစ်ရေး: စိတ်ခံစားချက်ကို ရှင်းလင်းစွာ ပြောဆိုပါ။ မျှော်လင့်ချက်ကို တစ်ဖက်လူထံ တိတိကျကျ မျှဝေပါ။",
            "education": "📚 ပညာရေး/အလုပ်: အလုပ်တစ်ခုကို အပိုင်းငယ်များခွဲပြီး အာရုံစိုက်ပါ။",
            "past": "🧿 ပြန်လည်သုံးသပ်ရန်: အတိတ်က အတွေ့အကြုံတစ်ခုမှ သင်ခန်းစာကို ရယူပြီး ယနေ့ရွေးချယ်မှုတွင် အသုံးချပါ။",
        }
        return (f"🌙 <b>{label} — {date.today().strftime('%d-%m-%Y')}</b>\n"
                f"ဒြပ်စင်: {info[0]}\n\n{rng.choice(themes)}\n\n"
                f"{categories.get(category, '✨ အကြံပြုချက်: ' + rng.choice(themes))}")
    themes = [
        "Plan your tasks calmly. Consistency may help more than rushing.",
        "Be honest in relationships and make room for another perspective.",
        "Give time to learning and personal growth; progress takes practice.",
        "Review financial details and base important choices on reliable information.",
    ]
    category_text = {
        "love": "💖 Love: Communicate clearly and share expectations respectfully.",
        "education": "📚 Study/Career: Break a large task into smaller focused steps.",
        "past": "🧿 Reflection: Take a lesson from an earlier experience and apply it today.",
    }
    return (f"🌙 <b>{label} — {date.today().strftime('%d-%m-%Y')}</b>\n"
            f"Element: {info[2]}\n\n{rng.choice(themes)}\n\n"
            f"{category_text.get(category, '✨ Guidance: ' + rng.choice(themes))}")

def tarot_reading(lang: str, spread: int = 3) -> str:
    cards = random.sample(TAROT, spread)
    positions_my = ["အတိတ်", "ပစ္စုပ္ပန်", "အနာဂတ်"]
    positions_en = ["Past", "Present", "Future"]
    out = ["🔮 <b>သုံးကတ် တားရော့ဖတ်ရှုချက်</b>" if lang == "my" else "🔮 <b>Three-card Tarot Reading</b>"]
    for i, (name, my, en) in enumerate(cards):
        pos = positions_my[i] if lang == "my" else positions_en[i]
        meaning = my if lang == "my" else en
        out.append(f"\n<b>{i+1}. {pos} — {name}</b>\n{meaning}")
    return "\n".join(out)

def compatibility(a: str, b: str, lang: str) -> str:
    ea, eb = SIGN_INFO[a][2], SIGN_INFO[b][2]
    same = ea == eb
    compatible_pairs = {frozenset(("Fire", "Air")), frozenset(("Earth", "Water"))}
    supportive = frozenset((ea, eb)) in compatible_pairs
    if lang == "my":
        if same:
            msg = "တူညီသော ဒြပ်စင်ဖြစ်သဖြင့် အချင်းချင်း နားလည်လွယ်နိုင်သော်လည်း အားနည်းချက်တူညီမှုကို သတိပြုပါ။"
        elif supportive:
            msg = "ဒြပ်စင်အမြင်အရ အားဖြည့်ပေးနိုင်သော ပေါင်းစပ်မှုတစ်ခုဟု သင်္ကေတပြုနိုင်သည်။"
        else:
            msg = "ကွဲပြားသော အမြင်များက သင်ယူစရာဖြစ်နိုင်သည်။ ဆက်သွယ်ပြောဆိုမှုနှင့် အပြန်အလှန်လေးစားမှုကို ဦးစားပေးပါ။"
        return f"💑 <b>ကိုက်ညီမှုဖတ်ရှုချက်</b>\n{sign_label(a, lang)} + {sign_label(b, lang)}\n\n{msg}\n\nရာခိုင်နှုန်းကို သိပ္ပံနည်းကျ တိုင်းတာထားခြင်းမဟုတ်ပါ။ လူတစ်ဦးချင်း၏ စိတ်နေစိတ်ထားနှင့် ဆက်ဆံရေးကြိုးစားမှုက ပိုအရေးကြီးပါသည်။"
    if same:
        msg = "The shared element can create easy understanding, though similar blind spots may need attention."
    elif supportive:
        msg = "In symbolic astrology, these elements are often viewed as mutually supportive."
    else:
        msg = "Different perspectives can be an opportunity to learn. Prioritize communication and mutual respect."
    return f"💑 <b>Compatibility Reflection</b>\n{sign_label(a, lang)} + {sign_label(b, lang)}\n\n{msg}\n\nThis is symbolic entertainment, not a scientific compatibility score."

async def safe_send(update: Update, text: str, **kwargs):
    if update.message:
        await update.message.reply_text(text, **kwargs)
    elif update.callback_query:
        await update.callback_query.message.reply_text(text, **kwargs)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user.id, user.username or "")
    context.user_data.clear()
    await update.message.reply_text(t(user.id, "welcome"), reply_markup=main_keyboard(user.id), parse_mode=ParseMode.HTML)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    lang = lang_of(uid)
    commands = (
        "/start — Main menu\n/birth — Save birth date\n/tarot — Tarot reading\n/daily — Daily horoscope\n/zodiac — Zodiac guide\n/language — Change language\n/cancel — Cancel current action"
        if lang == "en" else
        "/start — စတင်ရန်\n/birth — မွေးနေ့ထည့်ရန်\n/tarot — တားရော့\n/daily — နေ့စဉ်ဟောကိန်း\n/zodiac — ရာသီခွင်\n/language — ဘာသာစကားပြောင်းရန်\n/cancel — ပယ်ဖျက်ရန်"
    )
    await update.message.reply_text(commands, reply_markup=main_keyboard(uid))

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("state", None)
    await update.message.reply_text(t(update.effective_user.id, "cancel"), reply_markup=main_keyboard(update.effective_user.id))

async def birth_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    context.user_data["state"] = "birth"
    await update.message.reply_text(t(uid, "ask_birth"))

async def tarot_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    lang = lang_of(uid)
    await update.message.reply_text(
        tarot_reading(lang, 3) + "\n\n" + t(uid, "disclaimer"),
        parse_mode=ParseMode.HTML, reply_markup=main_keyboard(uid)
    )

async def daily_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    row = get_user(uid)
    lang = lang_of(uid)
    if row and row[3]:
        sign = sign_for_date(datetime.strptime(row[3], "%Y-%m-%d").date())
        result = horoscope(sign, lang)
    else:
        await update.message.reply_text(t(uid, "choose_sign"), reply_markup=sign_keyboard("daily"))
        return
    await update.message.reply_text(result + "\n\n" + t(uid, "disclaimer"), parse_mode=ParseMode.HTML)

async def zodiac_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    lang = lang_of(uid)
    lines = ["♈ <b>ရာသီခွင် ၁၂ မျိုး</b>" if lang == "my" else "♈ <b>The 12 Zodiac Signs</b>"]
    for key, en, my, dates in SIGNS:
        info = SIGN_INFO[key]
        lines.append(f"{en} ({my}) — {dates}\n" + (f"ဒြပ်စင်: {info[0]} | {info[1]}" if lang == "my" else f"Element: {info[2]} | {info[3]}"))
    await update.message.reply_text("\n\n".join(lines), parse_mode=ParseMode.HTML)

async def language_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🇲🇲 မြန်မာ", callback_data="lang:my"),
        InlineKeyboardButton("🇬🇧 English", callback_data="lang:en"),
    ]])
    await update.message.reply_text("Choose language / ဘာသာစကားရွေးပါ", reply_markup=kb)

async def profile_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    row = get_user(uid)
    lang = lang_of(uid)
    if row and row[3]:
        d = datetime.strptime(row[3], "%Y-%m-%d").date()
        sign = sign_for_date(d)
        msg = f"👤 <b>Profile</b>\nBirth date: {d.strftime('%d-%m-%Y')}\nZodiac: {sign_label(sign, lang)}"
    else:
        msg = t(uid, "no_birth")
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML, reply_markup=main_keyboard(uid))

async def ai_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    context.user_data["state"] = "ai"
    await update.message.reply_text(t(uid, "ai_prompt"))

async def love_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    row = get_user(uid)
    lang = lang_of(uid)
    if row and row[3]:
        sign = sign_for_date(datetime.strptime(row[3], "%Y-%m-%d").date())
        result = horoscope(sign, lang, "love")
        await update.message.reply_text(result + "\n\n" + t(uid, "disclaimer"), parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(t(uid, "no_birth"))

async def past_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    row = get_user(uid)
    lang = lang_of(uid)
    if row and row[3]:
        sign = sign_for_date(datetime.strptime(row[3], "%Y-%m-%d").date())
        result = horoscope(sign, lang, "past")
        await update.message.reply_text(result + "\n\n" + t(uid, "disclaimer"), parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(t(uid, "no_birth"))

async def education_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    row = get_user(uid)
    lang = lang_of(uid)
    if row and row[3]:
        sign = sign_for_date(datetime.strptime(row[3], "%Y-%m-%d").date())
        result = horoscope(sign, lang, "education")
        await update.message.reply_text(result + "\n\n" + t(uid, "disclaimer"), parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(t(uid, "no_birth"))

async def compat_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    context.user_data["state"] = "compat_first"
    await update.message.reply_text(t(uid, "choose_sign"), reply_markup=sign_keyboard("compat1"))

async def call_ai(prompt: str, lang: str) -> Optional[str]:
    # Public text-generation endpoint; availability and limits can change.
    language_instruction = "Answer in Burmese." if lang == "my" else "Answer in English."
    full_prompt = (
        "You are a kind, careful astrology-themed reflection assistant. "
        "Do not claim to know the future with certainty. Do not give medical, legal, "
        "or financial instructions. Offer practical, non-deterministic reflection. "
        f"{language_instruction}\nUser question: {prompt}"
    )
    try:
        async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
            response = await client.get(AI_API_URL.rstrip("/") + "/" + quote(full_prompt, safe=""))
            if response.status_code == 200:
                answer = response.text.strip()
                if answer and len(answer) > 2:
                    return answer[:3800]
    except Exception as exc:
        logger.warning("AI endpoint unavailable: %s", exc)
    return None

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    username = update.effective_user.username or ""
    save_user(uid, username)
    text = (update.message.text or "").strip()
    lang = lang_of(uid)
    state = context.user_data.get("state")

    if state == "birth":
        try:
            d = datetime.strptime(text, "%d-%m-%Y").date()
            if d > date.today() or d.year < 1900:
                raise ValueError("date out of range")
            save_user(uid, username, birth_date=d.isoformat())
            context.user_data.pop("state", None)
            sign = sign_for_date(d)
            await update.message.reply_text(
                t(uid, "saved") + f"\n\n🌟 {sign_label(sign, lang)}\n"
                + (f"မွေးနေ့: {d.strftime('%d-%m-%Y')}" if lang == "my" else f"Birth date: {d.strftime('%d-%m-%Y')}"),
                reply_markup=main_keyboard(uid)
            )
        except ValueError:
            await update.message.reply_text(t(uid, "bad_date"))
        return

    if state == "ai":
        context.user_data.pop("state", None)
        msg = await update.message.reply_text(t(uid, "thinking"))
        answer = await call_ai(text, lang)
        if answer:
            output = answer
        else:
            fallback = random.choice(DAILY_MY if lang == "my" else DAILY_EN)
            output = t(uid, "ai_fallback") + "\n\n" + fallback
        await msg.edit_text(output + "\n\n" + t(uid, "disclaimer"))
        return

    # Reply-keyboard menu text routing
    menu_map = {
        TEXT["my"]["tarot"]: tarot_cmd, TEXT["en"]["tarot"]: tarot_cmd,
        TEXT["my"]["zodiac"]: zodiac_cmd, TEXT["en"]["zodiac"]: zodiac_cmd,
        TEXT["my"]["birth"]: birth_cmd, TEXT["en"]["birth"]: birth_cmd,
        TEXT["my"]["love"]: love_cmd, TEXT["en"]["love"]: love_cmd,
        TEXT["my"]["daily"]: daily_cmd, TEXT["en"]["daily"]: daily_cmd,
        TEXT["my"]["ai"]: ai_cmd, TEXT["en"]["ai"]: ai_cmd,
        TEXT["my"]["past"]: past_cmd, TEXT["en"]["past"]: past_cmd,
        TEXT["my"]["education"]: education_cmd, TEXT["en"]["education"]: education_cmd,
        TEXT["my"]["compat"]: compat_cmd, TEXT["en"]["compat"]: compat_cmd,
        TEXT["my"]["profile"]: profile_cmd, TEXT["en"]["profile"]: profile_cmd,
        TEXT["my"]["language"]: language_cmd, TEXT["en"]["language"]: language_cmd,
        TEXT["my"]["help"]: help_cmd, TEXT["en"]["help"]: help_cmd,
    }
    handler = menu_map.get(text)
    if handler:
        await handler(update, context)
    else:
        await update.message.reply_text(t(uid, "unknown"), reply_markup=main_keyboard(uid))

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    lang = lang_of(uid)
    data = q.data or ""

    if data.startswith("lang:"):
        new_lang = data.split(":", 1)[1]
        if new_lang in TEXT:
            save_user(uid, q.from_user.username or "", language=new_lang)
            await q.edit_message_text(TEXT[new_lang]["welcome"], parse_mode=ParseMode.HTML)
            await q.message.reply_text(TEXT[new_lang]["menu"], reply_markup=main_keyboard(uid))
        return

    if data.startswith("daily:"):
        sign = data.split(":", 1)[1]
        if sign in SIGN_INFO:
            await q.edit_message_text(horoscope(sign, lang) + "\n\n" + t(uid, "disclaimer"), parse_mode=ParseMode.HTML)
        return

    if data.startswith("compat1:"):
        sign = data.split(":", 1)[1]
        if sign in SIGN_INFO:
            context.user_data["compat_first"] = sign
            await q.edit_message_text(t(uid, "choose_second"), reply_markup=sign_keyboard("compat2"))
        return

    if data.startswith("compat2:"):
        sign2 = data.split(":", 1)[1]
        sign1 = context.user_data.pop("compat_first", None)
        if sign1 in SIGN_INFO and sign2 in SIGN_INFO:
            await q.edit_message_text(compatibility(sign1, sign2, lang), parse_mode=ParseMode.HTML)
        return

async def post_init(app: Application):
    db().close()
    logger.info("Mystic Astrology Bot started successfully.")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Unhandled error: %s", context.error)

def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is missing. Add it in Railway Variables.")
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("birth", birth_cmd))
    app.add_handler(CommandHandler("tarot", tarot_cmd))
    app.add_handler(CommandHandler("daily", daily_cmd))
    app.add_handler(CommandHandler("zodiac", zodiac_cmd))
    app.add_handler(CommandHandler("language", language_cmd))
    app.add_handler(CommandHandler("profile", profile_cmd))
    app.add_handler(CommandHandler("ai", ai_cmd))
    app.add_handler(CommandHandler("love", love_cmd))
    app.add_handler(CommandHandler("past", past_cmd))
    app.add_handler(CommandHandler("education", education_cmd))
    app.add_handler(CommandHandler("compat", compat_cmd))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_error_handler(error_handler)

    logger.info("Starting polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
