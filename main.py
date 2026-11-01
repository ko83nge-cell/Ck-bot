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

# ရာသီခွင် အချက်အလက်များ
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
    "လုပ်ငန်းခွင် သို့မဟုတ် ပညာရေးမှာ ကိုယ့်ရဲ့ ကြိုးစားအားထုတ်မှုကို လူကြီးတွေက အသိအမှတ်ပြုလာမယ့် နေ့တစ်နေ့ ဖြစ်ပါတယ်။",
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
    "ရင်ခုန်စရာ အချစ်ဇာတ်လမ်းတွေနဲ့ သစ္စာရှိမှုကို အပြန်အလှန် ဖလှယ်ရမယ့် ကာလဖြစ်ပါတယ်။",
]

CAREER_POOL = [
    "လုပ်ငန်းခွင်နဲ့ စီးပွားရေးမှာ ကိုယ်ပိုင်ဖန်တီးမှုအသစ်တွေနဲ့ ထိပ်ဆုံးကို ရောက်ရှိနိုင်ပါတယ်။",
    "ငွေကြေးစီမံခန့်ခွဲမှုနဲ့ ရင်းနှီးမြှုပ်နှံမှုတွေမှာ အထူးကံကောင်းမယ့် အချိန်ဖြစ်ပါတယ်။",
]

TAROT_DECK = [
    {"name": "The Fool (လူမိုက်)", "vibe": "ခရီးအသစ်စတင်ခြင်း၊ စွန့်စားရဲခြင်း၊ အကောင်းမြင်စိတ်ဖြင့် ရှေ့ဆက်ခြင်း"},
    {"name": "The Magician (ပညာရှင်)", "vibe": "စွမ်းရည်များကို အပြည့်အဝအသုံးချပြီး ရည်မှန်းချက်အောင်မြင်မည့် ကာလ"},
]

# **မှတ်ဉာဏ်ထဲတွင် မေးခွန်းများနှင့် အဖြေများ သိမ်းဆည်းရန် စာရင်း (Default မေးခွန်းအချို့ ထည့်ထားသည်)**
SAVED_TRIVIA_QUESTIONS = [
    {
        "q": "မြန်မာနိုင်ငံ၏ အမြင့်ဆုံးတောင်ထိပ်မှာ အမည်မှာ အဘယ်နည်း?",
        "options": ["ခါကာဘိုရာဇီ", "ဇွဲကပင်", "ပုပ္ပား", "တောင်ကြီး"],
        "answer": 0,
    },
    {
        "q": "နေအဖွဲ့အစည်းတွင် နေနှင့် အနီးဆုံးဂြိုဟ်မှာ အဘယ်နည်း?",
        "options": ["အင်္ဂါဂြိုဟ်", "ဗုဒ္ဓဟူးဂြိုဟ်", "ကြာသပတေးဂြိုဟ်", "စနေဂြိုဟ်"],
        "answer": 1,
    },
]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🌟 ရာသီခွင် အသေးစိတ်ဟောကိန်း", callback_data="mode_zodiac")],
        [InlineKeyboardButton("📅 မနက်ဖြန် ဖြစ်ပျက်မည့်ဟောကိန်း", callback_data="mode_tomorrow")],
        [InlineKeyboardButton("🃏 တားရော့ (၃) ကတ် ဟောရန်", callback_data="mode_tarot")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "မင်္ဂလာပါရှင့်/ခဗျာ 🙏\n\n- ဗေဒင်/တားရော့ မေးရန် နှိပ်ပါ။\n- ဉာဏ်စမ်းဂိမ်းဆော့ရန် ဂရုထဲတွင် `/game` ဟု ရိုက်ပါ။\n- မေးခွန်းအသစ်ထည့်ရန် `/addq` ဟု အသုံးပြုပါ။",
        reply_markup=reply_markup,
    )


# **မေးခွန်းအသစ် ထည့်သွင်းရန် Command** (`/addq မေးခွန်း / ဖြေစရာ၁ / ဖြေစရာ၂ / ဖြေစရာ၃ / ဖြေစရာ၄ / အမှန်နံပါတ်(0မှ3ထိ)`)
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
        await update.message.reply_text("⚠️ အမှန်အဖြေနံပါတ်သည် 0 မှ 3 အတွင်းသာ ဖြစ်ရပါမည်။ (ဥပမာ- ပထမအဖြေဆိုလျှင် 0)")
        return

    # မေးခွန်းသစ်ကို စာရင်းထဲသို့ သိမ်းဆည်းခြင်း
    new_q = {
        "q": q_text,
        "options": options,
        "answer": ans_idx
    }
    SAVED_TRIVIA_QUESTIONS.append(new_q)
    await update.message.reply_text(f"✅ **အောင်မြင်သည်!** မေးခွန်းအသစ်ကို Bot က မှတ်သားလိုက်ပါပြီ။ စုစုပေါင်း မေးခွန်းအရေအတွက်: {len(SAVED_TRIVIA_QUESTIONS)} ခု", parse_mode="Markdown")


# **ဂိမ်းစတင်ရန် Command** (`/game`)
async def game_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not SAVED_TRIVIA_QUESTIONS:
        await update.message.reply_text("⚠️ လက်လောလောဆယ် မှတ်သားထားသော မေးခွန်းမရှိသေးပါ။ `/addq` ဖြင့် မေးခွန်းများ အရင်ထည့်ပါ။")
        return

    # သိမ်းဆည်းထားသော မေးခွန်းများထဲမှ တစ်ခုကို ကျပန်းရွေးထုတ်ခြင်း
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
    await update.message.reply_text(game_intro, parse_mode="Markdown", reply_markup=reply_markup)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if data.startswith("ans_"):
        _, selected_idx, correct_idx = data.split("_")
        if selected_idx == correct_idx:
            result_text = "🎉 **ဂုဏ်ယူပါတယ်!** အဖွဲ့သားများ စုပေါင်းဖြေဆိုချက်မှာ **မှန်ကန်ပါသည်**။ 🏆\n\nထပ်မံဆော့ကစားရန် `/game` ဟု ရိုက်ထည့်ပါ။"
        else:
            result_text = "❌ **မှားယွင်းနေပါတယ်!** နောက်တစ်ကြိမ် ထပ်မံကြိုးစားကြည့်ပါ။\n\nထပ်မံဆော့ကစားရန် `/game` ဟု ရိုက်ထည့်ပါ။"
        
        await query.edit_message_text(result_text, parse_mode="Markdown")
        return

    if query.data == "mode_zodiac":
        context.user_data["mode"] = "zodiac"
        await query.edit_message_text("✨ **ရာသီခွင် အသေးစိတ် မေးမြန်းရန်**\n\nသင့်ရဲ့ ရာသီခွင်အမည်ကို Chat ထဲမှာ ပို့ပေးပါ။")
    elif query.data == "mode_tomorrow":
        context.user_data["mode"] = "tomorrow"
        await query.edit_message_text("📅 **မနက်ဖြန် ဖြစ်ပျက်မည့်ဟောကိန်း မေးမြန်းရန်**\n\nသင့်ရဲ့ ရာသီခွင်အမည်ကို Chat ထဲမှာ ပို့ပေးပါ။")
    elif query.data == "mode_tarot":
        cards = random.sample(TAROT_DECK, 2)
        response = f"✨ **တားရော့ ဟောကိန်း** ✨\n\n• {cards[0]['name']}: {cards[0]['vibe']}"
        await query.edit_message_text(response, parse_mode="Markdown")


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
        response = f"📅 **မနက်ဖြန်ဟောကိန်း ({zodiac_title})**\n• {random.choice(TOMORROW_EVENTS)}"
    else:
        response = f"🔮 **ရာသီခွင်အသေးစိတ် ({zodiac_title})**\n• {random.choice(TRAITS_POOL)}"

    await update.message.reply_text(response, parse_mode="Markdown")


if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("game", game_command))
    app.add_handler(CommandHandler("addq", add_question_command))  # မေးခွန်းအသစ်ထည့်ရန် Command
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("Bot with Custom Question Saver is running...")
    app.run_polling()

