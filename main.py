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

# ရာသီခွင် အချက်အလက်များ (ပုံသေမဟုတ်ဘဲ အမြဲအသစ်ဖြစ်စေမည့် Pool များ)
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
    "ခရီးသွားလာရမည့် ကိစ္စများ ကြုံရနိုင်ပြီး၊ သွားရာလမ်းမှာ အကျိုးအမြတ်နဲ့ မိတ်ဆွေသစ်တွေ တိုးပွားလာပါလိမ့်မယ်။",
]

TOMORROW_AVOIDS = [
    "စကားပြောဆိုရာမှာ အလောတကြီး ဆုံးဖြတ်ပြောဆိုမိခြင်းနဲ့ အထင်အမြင်လွဲမှားမှုများကို အထူးသတိပြုပါ။",
    "အရေးကြီးတဲ့ ဆုံးဖြတ်ချက်တွေ ချမှတ်တဲ့အခါ သူတစ်ပါးရဲ့ စကားကို အလွယ်တကူ မယုံကြည်ဘဲ ကိုယ်တိုင်သေချာ စဉ်းစားပါ။",
    "ငွေကြေးသုံးစွဲမှုအပိုင်းမှာ မလိုအပ်ဘဲ လက်လွန်စရာတွေ ဖြစ်ပေါ်တတ်လို့ စဉ်းစားချင့်ချိန်ပြီး သုံးစွဲပါ။",
]

TRAITS_POOL = [
    "ခေါင်းဆောင်မှု အပြည့်အဝရှိပြီး ကိုယ်ပိုင်ဆုံးဖြတ်ချက် ခိုင်မာသူ ဖြစ်ပါတယ်။",
    "အရာရာကို လက်တွေ့ကျကျနဲ့ စနစ်တကျ ဦးဆောင်လုပ်ကိုင်တတ်တဲ့ သဘာဝရှိပါတယ်။",
    "ဉာဏ်ပညာထက်မြက်ပြီး ပတ်ဝန်းကျင်အသစ်နဲ့ လွယ်ကူစွာ သင့်မြတ်အောင် နေထိုင်နိုင်ပါတယ်။",
    "ကြင်နာတတ်ပြီး အနီးအနားက လူတွေရဲ့ ခံစားချက်ကို အကောင်းဆုံး နားလည်ပေးတတ်ပါတယ်။",
]

LOVE_POOL = [
    "အချစ်ရေးမှာ တဖက်လူအပေါ် အလွန်ဂရုစိုက်ပေးတတ်ပေမယ့် တစ်ခါတရံ မာနကိုတော့ လျှော့ချသင့်ပါတယ်။",
    "ရင်ခုန်စရာ အချစ်ဇာတ်လမ်းတွေနဲ့ သစ္စာရှိမှုကို အပြန်အလှန် ဖလှယ်ရမယ့် ကာလဖြစ်ပါတယ်။",
    "အချစ်ရေးနဲ့ ပတ်သက်လာရင် ကိုယ်တိုင်က ပိုပြီး သည်းခံနားလည်ပေးဖို့ လိုအပ်နေပါတယ်။",
]

CAREER_POOL = [
    "လုပ်ငန်းခွင်နဲ့ စီးပွားရေးမှာ ကိုယ်ပိုင်ဖန်တီးမှုအသစ်တွေနဲ့ ထိပ်ဆုံးကို ရောက်ရှိနိုင်ပါတယ်။",
    "ငွေကြေးစီမံခန့်ခွဲမှုနဲ့ ရင်းနှီးမြှုပ်နှံမှုတွေမှာ အထူးကံကောင်းမယ့် အချိန်ဖြစ်ပါတယ်။",
    "အဖွဲ့အစည်းဆိုင်ရာ တာဝန်တွေနဲ့ ဦးဆောင်ရမည့်နေရာတွေမှာ အောင်မြင်မှု ရရှိပါမယ်။",
]

TAROT_DECK = [
    {"name": "The Fool (လူမိုက်)", "vibe": "ခရီးအသစ်စတင်ခြင်း၊ စွန့်စားရဲခြင်း၊ အကောင်းမြင်စိတ်ဖြင့် ရှေ့ဆက်ခြင်း"},
    {"name": "The Magician (ပညာရှင်)", "vibe": "စွမ်းရည်များကို အပြည့်အဝအသုံးချပြီး ရည်မှန်းချက်အောင်မြင်မည့် ကာလ"},
    {"name": "The High Priestess (ပုရောဟိတ်မ)", "vibe": "အတွင်းစိတ်အသိကို နားထောင်ရန်နှင့် သည်းခံရန် အချိန်"},
    {"name": "The Empress (မိဖုရား)", "vibe": "စည်းစိမ်ဥစ္စာ ပြည့်စုံခြင်း၊ မေတ္တာရေးရာ အဆင်ပြေခြင်း"},
    {"name": "The Emperor (ဧကရာဇ်)", "vibe": "ခေါင်းဆောင်မှု၊ တည်ငြိမ်ခိုင်မာမှု၊ စည်းကမ်းရှိရှိ လုပ်ဆောင်ရခြင်း"},
    {"name": "The Lovers (ချစ်သူများ)", "vibe": "အရေးကြီးဆုံး ဆုံးဖြတ်ချက်ချရခြင်း၊ စိတ်နှလုံးချင်း တိုက်ဆိုင်မှုရှိခြင်း"},
    {"name": "The Wheel of Fortune (ကံကြမ္မာစက်ဝိုင်း)", "vibe": "ကံကြမ္မာ ရုတ်တရက် ပြောင်းလဲခြင်း၊ အပြောင်းအလဲကောင်းများ ကြုံရခြင်း"},
    {"name": "The Star (ကြယ်ပွင့်)", "vibe": "မျှော်လင့်ချက်အသစ်များ ပေါ်ပေါက်လာခြင်း၊ စိတ်နှလုံး အေးချမ်းခြင်း"},
]

# ဉာဏ်စမ်းမေးခွန်းများ
TRIVIA_QUESTIONS = [
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
    {
        "q": "လူ့ခန္ဓာကိုယ်တွင် အကြီးဆုံး အင်္ဂါအစိတ်အပိုင်းမှာ မည်သည်နည်း?",
        "options": ["နှလုံး", "အသည်း", "အရေပြား", "အဆုတ်"],
        "answer": 2,
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
        "မင်္ဂလာပါရှင့်/ခဗျာ 🙏\n\nဤဘော့တ်မှတဆင့် ဗေဒင်၊ တားရော့နှင့် ဂရုများတွင် ဉာဏ်စမ်းဂိမ်း (`/game`) ဆော့ကစားနိုင်ပါသည်။ အောက်ပါတို့မှ ရွေးချယ်ပါ -",
        reply_markup=reply_markup,
    )


# /game Command ဖြင့် အဖွဲ့သား ၃ ယောက် လိုအပ်ကြောင်း ကြေညာကာ ဉာဏ်စမ်းစတင်ခြင်း
async def game_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q_data = random.choice(TRIVIA_QUESTIONS)
    # ဖြေဆိုရန် ခလုတ်များ တည်ဆောက်ခြင်း
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
            result_text = "🎉 **ဂုဏ်ယူပါတယ်!** အဖွဲ့သားများ စုပေါင်းဖြေဆိုချက်မှာ **မှန်ကန်ပါသည်**။ 🏆"
        else:
            result_text = "❌ **မှားယွင်းနေပါတယ်!** နောက်တစ်ကြိမ် ထပ်မံကြိုးစားကြည့်ပါ။ (/game ဖြင့် အသစ်စတင်နိုင်သည်)"
        
        await query.edit_message_text(result_text, parse_mode="Markdown")
        return

    if query.data == "mode_zodiac":
        context.user_data["mode"] = "zodiac"
        await query.edit_message_text(
            "✨ **ရာသီခွင် အသေးစိတ် မေးမြန်းရန်**\n\nသင့်ရဲ့ ရာသီခွင်အမည် (ဥပမာ - *Leo, Aries, မေထုန်, သိဟ်*) ကို Chat ထဲမှာ စာသားပုံစံဖြင့် ရိုက်ထည့်ပြီး ပို့ပေးပါ။"
        )
    elif query.data == "mode_tomorrow":
        context.user_data["mode"] = "tomorrow"
        await query.edit_message_text(
            "📅 **မနက်ဖြန် ဖြစ်ပျက်မည့်ဟောကိန်း မေးမြန်းရန်**\n\nသင့်ရဲ့ ရာသီခွင်အမည် (ဥပမာ - *Leo, Aries, မေထုန်, သိဟ်*) ကို Chat ထဲမှာ စာသားပုံစံဖြင့် ရိုက်ထည့်ပြီး ပို့ပေးပါ။"
        )
    elif query.data == "mode_tarot":
        cards = random.sample(TAROT_DECK, 3)
        response = (
            f"✨ **တားရော့ ကတ် (၃) ကတ် ဟောကိန်း** ✨\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"1️⃣ **အတိတ် (Past):** *{cards[0]['name']}*\n"
            f"   - အဓိပ္ပာယ်: {cards[0]['vibe']} နှင့်ဆက်စပ်သော အဖြစ်အပျက်များ ဖြတ်သန်းခဲ့ရသည်။\n\n"
            f"2️⃣ **ပစ္စုပ္ပန် (Present):** *{cards[1]['name']}*\n"
            f"   - အဓိပ္ပာယ်: ယခုလက်ရှိ သင်ရင်ဆိုင်နေရသော အခြေအနေမှာ {cards[1]['vibe']} ဖြစ်သည်။\n\n"
            f"3️⃣ **အနာဂတ် (Future):** *{cards[2]['name']}*\n"
            f"   - အဓိပ္ပာယ်: ရှေ့ဆက်လာမည့် ကာလတွင် {cards[2]['vibe']} နှင့် ကြုံတွေ့ရလိမ့်မည်။"
        )
        keyboard = [
            [
                InlineKeyboardButton("🔄 ထပ်မံ မဲကြည့်မည်", callback_data="mode_tarot"),
                InlineKeyboardButton("🏠 ပင်မမီနူးသို့", callback_data="menu_start"),
            ]
        ]
        await query.edit_message_text(
            response, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif query.data == "menu_start":
        keyboard = [
            [InlineKeyboardButton("🌟 ရာသီခွင် အသေးစိတ်ဟောကိန်း", callback_data="mode_zodiac")],
            [InlineKeyboardButton("📅 မနက်ဖြန် ဖြစ်ပျက်မည့်ဟောကိန်း", callback_data="mode_tomorrow")],
            [InlineKeyboardButton("🃏 တားရော့ (၃) ကတ် ဟောရန်", callback_data="mode_tarot")],
        ]
        await query.edit_message_text(
            "မင်္ဂလာပါရှင့်/ခဗျာ 🙏\n\nကျေးဇူးပြု၍ အောက်ပါတို့မှ လိုချင်သော ဟောကိန်းအမျိုးအစား ခလုတ်ကို ရွေးချယ်ပါ -",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    current_mode = context.user_data.get("mode", "zodiac")

    matched_key = "aries"
    for key in ZODIAC_NAMES.keys():
        if key in text:
            matched_key = key
            break

    if matched_key == "aries":
        if any(w in text for w in ["ပြိဿ", "မေ"]):
            matched_key = "taurus"
        elif any(w in text for w in ["မေထုန်", "ဇွန်"]):
            matched_key = "gemini"
        elif any(w in text for w in ["ကရကဋ်", "ဇူလိုင်"]):
            matched_key = "cancer"
        elif any(w in text for w in ["သိဟ်", "သဂုတ်", "ဩဂုတ်"]):
            matched_key = "leo"
        elif any(w in text for w in ["ကန်", "စက်တင်ဘာ"]):
            matched_key = "virgo"
        elif any(w in text for w in ["တူ", "အောက်တိုဘာ"]):
            matched_key = "libra"
        elif any(w in text for w in ["ဗြိစ္ဆာ", "နိုဝင်ဘာ"]):
            matched_key = "scorpio"
        elif any(w in text for w in ["ဓနု", "ဒီဇင်ဘာ"]):
            matched_key = "sagittarius"
        elif any(w in text for w in ["မကာရ", "ဇန်နဝါရီ"]):
            matched_key = "capricorn"
        elif any(w in text for w in ["ကုမ်", "ဖေဖော်ဝါရီ"]):
            matched_key = "aquarius"
        elif any(w in text for w in ["မိန်"]):
            matched_key = "pisces"

    zodiac_title = ZODIAC_NAMES[matched_key]

    if current_mode == "tomorrow":
        event_text = random.choice(TOMORROW_EVENTS)
        avoid_text = random.choice(TOMORROW_AVOIDS)
        response = (
            f"📅 **မနက်ဖြန်အတွက် သင့်ရဲ့ ဟောကိန်းအထူး**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"✨ **ရာသီခွင်:** {zodiac_title}\n\n"
            f"🌟 **မနက်ဖြန် ဖြစ်ပျက်မည့်အခြေအနေ:**\n• {event_text}\n\n"
            f"⚠️ **မနက်ဖြန် သတိပြုရှောင်ရှားရမည့်အချက်:**\n• {avoid_text}"
        )
    else:
        trait_text = random.choice(TRAITS_POOL)
        love_text = random.choice(LOVE_POOL)
        career_text = random.choice(CAREER_POOL)
        response = (
            f"🔮 **ရာသီခွင် အသေးစိတ်ဟောကိန်း**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"✨ **ရာသီခွင်:** {zodiac_title}\n\n"
            f"🧠 **စိတ်နေစိတ်ထား:**\n• {trait_text}\n\n"
            f"❤️ **အချစ်ရေး:**\n• {love_text}\n\n"
            f"💼 **လုပ်ငန်းခွင်နှင့် စီးပွားရေး:**\n• {career_text}"
        )

    keyboard = [
        [
            InlineKeyboardButton("🔄 အခြားတစ်ခု ထပ်မံမေးမည်", callback_data="menu_start"),
            InlineKeyboardButton("🏠 ပင်မမီနူးသို့", callback_data="menu_start"),
        ]
    ]
    await update.message.reply_text(
        response, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
    )


if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("game", game_command))  # /game command ထည့်သွင်းခြင်း
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("Bot with Group Game is running...")
    app.run_polling()

