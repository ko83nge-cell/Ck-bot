import os
import random
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

# ရာသီခွင် အမည်များနှင့် အဓိပ္ပာယ်များ
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
]

# မေးခွန်းများနှင့် အဖြေများ သိမ်းဆည်းရန် စာရင်း
SAVED_TRIVIA_QUESTIONS = [
    {
        "q": "မြန်မာနိုင်ငံ၏ အမြင့်ဆုံးတောင်ထိပ်မှာ အမည်မှာ အဘယ်နည်း?",
        "options": ["ခါကာဘိုရာဇီ", "ဇွဲကပင်", "ပုပ္ပား", "တောင်ကြီး"],
        "answer": 0,
    },
]

# ကံစမ်းမဲဂိမ်းအတွက် ဆုလာဘ်များ
LUCKY_PRIZES = [
    "🎉 ဂုဏ်ယူပါတယ်! ယနေ့ သင်၏ ကံကောင်းခြင်း လက်ဆောင်မှာ **'ထီပေါက်ကံစမ်းခြင်း အထူးကောင်းမွန်ခြင်း'** ဖြစ်ပါသည်။",
    "💰 ရွှေလိုမိုးလို ကျမည့်နေ့ပါ! **'ငွေကြေးဝင်ရောက်မည့်ကံ'** အထူးတလည် တောက်ပနေပါသည်။",
]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ခလုတ်များကို တစ်ခုချင်းစီ (အောက်ချင်းဆင်းလျက်) စီစဉ်ထားသည်
    keyboard = [
        [InlineKeyboardButton("🌟 ရာသီခွင် အသေးစိတ်ဟောကိန်း", callback_data="mode_zodiac")],
        [InlineKeyboardButton("📅 မနက်ဖြန် ဖြစ်ပျက်မည့်ဟောကိန်း", callback_data="mode_tomorrow")],
        [InlineKeyboardButton("🃏 တားရော့ (၃) ကတ် ဟောရန်", callback_data="mode_tarot")],
        [InlineKeyboardButton("🎮 ဂိမ်းများ ဆော့ကစားရန် (/game)", callback_data="menu_games")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "မင်္ဂလာပါရှင့်/ခဗျာ 🙏\n\n"
        "ဤဘော့တ်မှတဆင့် ဗေဒင်၊ တားရော့နှင့် ဂိမ်းများ ဆော့ကစားနိုင်ပါသည်။\n"
        "မေးခွန်းအသစ်ထည့်ရန် `/addq` ကို အသုံးပြုပါ။",
        reply_markup=reply_markup,
    )


# /game Command ဖြင့် ဂိမ်းအမျိုးအစား ရွေးချယ်စရာ မီနူးပြသခြင်း
async def game_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🧠 အဖွဲ့လိုက် ဉာဏ်စမ်းဂိမ်း (Trivia)", callback_data="game_trivia")],
        [InlineKeyboardButton("🎁 ကံစမ်းမဲ ကံကောင်းခြင်းဂိမ်း", callback_data="game_lucky")],
        [InlineKeyboardButton("🦹 သူခိုးဂိမ်း: 'လန်ဘား' ၏ အိမ်ခိုးမှု", callback_data="thief_start")],
        [InlineKeyboardButton("🏠 ပင်မမီနူးသို့", callback_data="menu_start")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🎮 **ဂိမ်းကစားရန် ရွေးချယ်စရာများ** 🎮\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "ကျေးဇူးပြု၍ အောက်ပါတို့မှ ကြိုက်နှစ်သက်ရာ ဂိမ်းအမျိုးအစားကို ရွေးချယ်ပါ -",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def add_question_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.replace("/addq", "").strip()
    parts = [p.strip() for p in text.split("/")]

    if len(parts) < 6:
        await update.message.reply_text(
            "⚠️ ပုံစံမမှန်ပါ။ ဤကဲ့သို့ ပို့ပေးပါ:\n\n"
            "`/addq မေးခွန်းစာသား / ဖြေစရာကွက် ၁ / ဖြေစရာကွက် ၂ / ဖြေစရာကွက် ၃ / ဖြေစရာကွက် ၄ / အမှန်အဖြေနံပါတ်(0,1,2,3)`",
            parse_mode="Markdown"
        )
        return

    q_text = parts[0]
    options = parts[1:5]
    try:
        ans_idx = int(parts[5])
        if not (0 <= ans_idx <= 3):
            raise ValueError()
    except ValueError:
        await update.message.reply_text("⚠️ အမှန်အဖြေနံပါတ်သည် 0 မှ 3 အတွင်းသာ ဖြစ်ရပါမည်။")
        return

    new_q = {"q": q_text, "options": options, "answer": ans_idx}
    SAVED_TRIVIA_QUESTIONS.append(new_q)
    await update.message.reply_text(f"✅ **အောင်မြင်သည်!** မေးခွန်းအသစ်ကို မှတ်သားလိုက်ပါပြီ။ စုစုပေါင်း: {len(SAVED_TRIVIA_QUESTIONS)} ခု", parse_mode="Markdown")


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    # ဉာဏ်စမ်းမေးခွန်း အဖြေစစ်ဆေးခြင်း
    if data.startswith("ans_"):
        _, selected_idx, correct_idx = data.split("_")
        if selected_idx == correct_idx:
            result_text = "🎉 **ဂုဏ်ယူပါတယ်!** အဖွဲ့သားများ စုပေါင်းဖြေဆိုချက်မှာ **မှန်ကန်ပါသည်**။ 🏆\n\nထပ်မံဆော့ရန် `/game` ဟု ရိုက်ပါ။"
        else:
            result_text = "❌ **မှားယွင်းနေပါတယ်!** နောက်တစ်ကြိမ် ထပ်မံကြိုးစားကြည့်ပါ။\n\nထပ်မံဆော့ရန် `/game` ဟု ရိုက်ပါ။"
        await query.edit_message_text(result_text, parse_mode="Markdown")
        return

    # 🦹 သူခိုးဂိမ်း (Thief Game Logic - ခလုတ်များကို တစ်ခုချင်းစီ သီးသန့်ချထားသည်)
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
        text = (
            "🚪 **အနောက်ဖေး တံခါးပေါက်**\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "လန်ဘားဟာ သော့တံကို ကျွမ်းကျင်ပိုင်နိုင်စွာ သုံးပြီး အနောက်ဖေးတံခါးကို အောင်မြင်စွာ ဖွင့်ဝင်လာနိုင်ခဲ့ပါပြီ။ အခု အိမ်ထဲကို ရောက်ပါပြီ။ ဘယ်နေရာကို ဆက်သွားမလဲ?"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "thief_window":
        text = (
            "🪟 **ပြတင်းပေါက်မှ တက်စဉ် မတော်တဆဖြစ်ခြင်း!** ❌\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "လန်ဘား ဒုတိယထပ်ပြတင်းပေါက်ကို တက်နေစဉ် လုံခြုံရေးခွေးကြီးက အသံကြားပြီး အော်ဟောက်လိုက်ပါတော့တယ်။ အိမ်ရှင်တွေ နိုးလာပြီး လန်ဘားကို ဖမ်းမိသွားပါပြီ!\n\n"
            "💥 **ဂိမ်းဆုံးရှုံးသွားပါပြီ (Game Over)**"
        )
        # ခလုတ်များကို တစ်ခုချင်းစီ သီးသန့်စီစဉ်ထားသည်
        keyboard = [
            [InlineKeyboardButton("🔄 ထပ်မံ ကြိုးစားမည်", callback_data="thief_start")],
            [InlineKeyboardButton("🎮 ဂိမ်းမီနူးသို့", callback_data="menu_games")]
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "thief_frontdoor":
        text = (
            "🏠 **ပင်မတံခါးမှ ဝင်ရောက်ခြင်း** ❌\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            "ပင်မတံခါးမှာ အလိုအလျောက် အချက်ပေးစနစ် (Alarm) တပ်ဆင်ထားတာကို လန်ဘား မသိလိုက်ပါဘူး။ တံခါးဖွင့်လိုက်တာနဲ့ အလံသံတွေ မြည်လာပြီး ရဲတွေ ရောက်လာပါတော့တယ်။\n\n"
            "💥 **လန်ဘား ဖမ်းဆီးခံလိုက်ရပါပြီ (Game Over)**"
        )
        keyboard = [
            [InlineKeyboardButton("🔄 ထပ်မံ ကြိုးစားမည်", callback_data="thief_start")],
            [InlineKeyboardButton("🎮 ဂိမ်းမီနူးသို့", callback_data="menu_games")]
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "thief_livingroom":
        text = (
            "💎 **ဧည့်ခန်းထဲမှ ရွှေပန်းအိုး ခိုးယူခြင်း** ❌\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "ရွှေပန်းအိုးကို ယူလိုက်တဲ့အချိန်မှာ အောက်ခံခုံမှာ တပ်ဆင်ထားတဲ့ အလေးချိန်အာရုံခံစနစ် (Sensor) ပွင့်သွားပြီး မီးနီတွေ လင်းလာပါတော့တယ်။ လုံခြုံရေးတွေ ဝိုင်းဖမ်းလိုက်ပါပြီ!\n\n"
            "💥 **မအောင်မြင်ပါ (Game Over)**"
        )
        keyboard = [
            [InlineKeyboardButton("🔄 ထပ်မံ ကြိုးစားမည်", callback_data="thief_start")],
            [InlineKeyboardButton("🎮 ဂိမ်းမီနူးသို့", callback_data="menu_games")]
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "thief_bedroom":
        keyboard = [
            [InlineKeyboardButton("🚁 အမိုးပေါ်ကနေ ရဟတ်ယာဉ်နဲ့ ထွက်ပြေးမည်", callback_data="thief_win")],
            [InlineKeyboardButton("🚗 အောက်ထပ်ကနေ အမြန်ယာဉ်နဲ့ ထွက်မည်", callback_data="thief_lose")],
        ]
        text = (
            "🛏️ **အိပ်ခန်းထဲသို့ အောင်မြင်စွာ ရောက်ရှိခြင်း** ✨\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "လန်ဘား တစ်ယောက် အိပ်ခန်းထဲက ဗီဒိုကို ဖျက်ဆီးပြီး တန်ဖိုးကြီး စိန်လက်စွပ်နဲ့ ငွေစက္ကူအထုပ်ကြီးတွေကို အောင်မြင်စွာ ခိုးယူနိုင်ခဲ့ပါပြီ! 💰\n\n"
            "🏃‍♂️ အခု အိမ်ပေါ်ကနေ ဘယ်လို ထွက်ပြေးမှာလဲ?"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "thief_win":
        text = (
            "🎉 **ဂုဏ်ယူပါတယ်! လန်ဘား တစ်ယောက် အောင်မြင်သွားပါပြီ!** 🏆\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "လန်ဘားဟာ ခိုးထားတဲ့ပစ္စည်းတွေနဲ့အတူ အမိုးပေါ်ကနေ အောင်မြင်စွာ လွတ်မြောက်သွားပြီး သန်းကြွယ်သူဌေးကြီး ဖြစ်သွားပါတော့တယ်။ 🤑✨\n\n"
            "ဆော့ကစားပေး줘တဲ့အတွက် ကျေးဇူးတင်ပါတယ်!"
        )
        keyboard = [
            [InlineKeyboardButton("🎮 အခြားဂိမ်းများ ဆော့မည်", callback_data="menu_games")],
            [InlineKeyboardButton("🏠 ပင်မမီနူးသို့", callback_data="menu_start")]
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "thief_lose":
        text = (
            "🚗 **အောက်ထပ်ကနေ ထွက်ပြေးစဉ် မိသွားခြင်း** ❌\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "အောက်ထပ်မှာ လုံခြုံရေးတွေ စောင့်နေတာကို မမြင်လိုက်ရလို့ လန်ဘား တစ်ယောက် ထွက်ပြေးတဲ့လမ်းမှာ မိသွားပါတော့တယ်။\n\n"
            "💥 **မအောင်မြင်ပါ (Game Over)**"
        )
        keyboard = [
            [InlineKeyboardButton("🔄 ထပ်မံ ကြိုးစားမည်", callback_data="thief_start")],
            [InlineKeyboardButton("🎮 ဂိမ်းမီနူးသို့", callback_data="menu_games")]
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    # ဂိမ်းအမျိုးအစား ရွေးချယ်မှု မီနူး
    elif data == "menu_games":
        keyboard = [
            [InlineKeyboardButton("🧠 အဖွဲ့လိုက် ဉာဏ်စမ်းဂိမ်း (Trivia)", callback_data="game_trivia")],
            [InlineKeyboardButton("🎁 ကံစမ်းမဲ ကံကောင်းခြင်းဂိမ်း", callback_data="game_lucky")],
            [InlineKeyboardButton("🦹 သူခိုးဂိမ်း: 'လန်ဘား' ၏ အိမ်ခိုးမှု", callback_data="thief_start")],
            [InlineKeyboardButton("🏠 ပင်မမီနူးသို့", callback_data="menu_start")],
        ]
        await query.edit_message_text(
            "🎮 **ဂိမ်းကစားရန် ရွေးချယ်စရာများ** 🎮\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "ကျေးဇူးပြု၍ အောက်ပါတို့မှ ကြိုက်နှစ်သက်ရာ ဂိမ်းအမျိုးအစားကို ရွေးချယ်ပါ -",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    elif data == "game_trivia":
        if not SAVED_TRIVIA_QUESTIONS:
            await query.edit_message_text("⚠️ မေးခွန်းမရှိသေးပါ။ `/addq` ဖြင့် အရင်ထည့်ပါ။")
            return
        q_data = random.choice(SAVED_TRIVIA_QUESTIONS)
        keyboard = []
        for idx, opt in enumerate(q_data["options"]):
            keyboard.append([InlineKeyboardButton(opt, callback_data=f"ans_{idx}_{q_data['answer']}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        game_intro = (
            "🎮 **ဉာဏ်စမ်း အဖွဲ့လိုက်ဂိမ်း စတင်ပါပြီ** 🎮\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ *စည်းမျဉ်း:* ဤဂိမ်းတွင် ပါဝင်ရန် **အဖွဲ့သား (၃) ယောက်** လိုအပ်ပါသည်။\n\n"
            f"❓ **မေးခွန်း:** {q_data['q']}"
        )
        await query.edit_message_text(game_intro, parse_mode="Markdown", reply_markup=reply_markup)
    elif data == "game_lucky":
        prize = random.choice(LUCKY_PRIZES)
        keyboard = [
            [InlineKeyboardButton("🎲 ထပ်မံ ကံစမ်းမည်", callback_data="game_lucky")],
            [InlineKeyboardButton("🎮 ဂိမ်းမီနူးသို့", callback_data="menu_games")],
            [InlineKeyboardButton("🏠 ပင်မမီနူးသို့", callback_data="menu_start")]
        ]
        lucky_text = (
            f"🎁 **ကံစမ်းမဲ ကံကောင်းခြင်းဂိမ်း** 🎁\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"{prize}"
        )
        await query.edit_message_text(lucky_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    # ပုံမှန် ဟောကိန်းမီနူးများ
    elif query.data == "mode_zodiac":
        context.user_data["mode"] = "zodiac"
        await query.edit_message_text("✨ **ရာသီခွင် အသေးစိတ် မေးမြန်းရန်**\n\nသင့်ရဲ့ ရာသီခွင်အမည်ကို Chat ထဲမှာ ပို့ပေးပါ။")
    elif query.data == "mode_tomorrow":
        context.user_data["mode"] = "tomorrow"
        await query.edit_message_text("📅 **မနက်ဖြန် ဖြစ်ပျက်မည့်ဟောကိန်း မေးမြန်းရန်**\n\nသင့်ရဲ့ ရာသီခွင်အမည်ကို Chat ထဲမှာ ပို့ပေးပါ။")
    elif query.data == "mode_tarot":
        cards = random.sample(TAROT_DECK, 2)
        response = (
            f"✨ **တားရော့ ဟောကိန်း** ✨\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"• {cards[0]['name']}: {cards[0]['vibe']}\n"
            f"• {cards[1]['name']}: {cards[1]['vibe']}"
        )
        keyboard = [
            [InlineKeyboardButton("🔄 ထပ်မံ မဲကြည့်မည်", callback_data="mode_tarot")],
            [InlineKeyboardButton("🏠 ပင်မမီနူးသို့", callback_data="menu_start")],
        ]
        await query.edit_message_text(response, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    elif query.data == "menu_start":
        keyboard = [
            [InlineKeyboardButton("🌟 ရာသီခွင် အသေးစိတ်ဟောကိန်း", callback_data="mode_zodiac")],
            [InlineKeyboardButton("📅 မနက်ဖြန် ဖြစ်ပျက်မည့်ဟောကိန်း", callback_data="mode_tomorrow")],
            [InlineKeyboardButton("🃏 တားရော့ (၃) ကတ် ဟောရန်", callback_data="mode_tarot")],
            [InlineKeyboardButton("🎮 ဂိမ်းများ ဆော့ကစားရန် (/game)", callback_data="menu_games")],
        ]
        await query.edit_message_text("ကျေးဇူးပြု၍ အောက်ပါတို့မှ ရွေးချယ်ပါ -", reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    current_mode = context.user_data.get("mode", "zodiac")

    matched_key = "aries"
    for key in ZODIAC_NAMES.keys():
        if key in text:
            matched_key = key
            break

    zodiac_title = ZODIAC_NAMES[matched_key]

    if current_mode == "tomorrow":
        event_text = random.choice(TOMORROW_EVENTS)
        avoid_text = random.choice(TOMORROW_AVOIDS)
        response = (
            f"📅 **မနက်ဖြန်အတွက် သင့်ရဲ့ ဟောကိန်းအထူး**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"✨ **ရာသီခွင်:** {zodiac_title}\n\n"
            f"🌟 **ဖြစ်ပျက်မည့်အခြေအနေ:**\n{event_text}\n\n"
            f"⚠️ **သတိပြုရှောင်ရှားရမည့်အချက်:**\n{avoid_text}"
        )
    else:
        trait_text = random.choice(TRAITS_POOL)
        love_text = random.choice(LOVE_POOL)
        career_text = random.choice(CAREER_POOL)
        response = (
            f"🔮 **ရာသီခွင် အသေးစိတ်ဟောကိန်း**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"✨ **ရာသီခွင်:** {zodiac_title}\n\n"
            f"🧠 **စိတ်နေစိတ်ထား:**\n{trait_text}\n\n"
            f"❤️ **အချစ်ရေး:**\n{love_text}\n\n"
            f"💼 **လုပ်ငန်းခွင်နှင့် စီးပွားရေး:**\n{career_text}"
        )

    keyboard = [
        [InlineKeyboardButton("🔄 အခြားတစ်ခု ထပ်မံမေးမည်", callback_data="menu_start")],
        [InlineKeyboardButton("🏠 ပင်မမီနူးသို့", callback_data="menu_start")],
    ]
    await update.message.reply_text(response, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("game", game_command))
    app.add_handler(CommandHandler("addq", add_question_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("Thief Game & Astrology Bot is running...")
    app.run_polling()

