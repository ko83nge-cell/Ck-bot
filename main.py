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
    "မမျှော်လင့်ထားတဲ့ ငွေကြေးဝင်ရောက်မှု သို့မဟုတ် အကျိုးအမြတ်အသစ်တွေ ကိုယ့်ဆီ ရောက်လာပါလိမ့်မယ်။ လုပ်ကိုင်နေတဲ့ လုပ်ငန်းတွေမှာလည်း ထင်မှတ်မထားတဲ့ အောင်မြင်မှုတွေနဲ့ ကြုံတွေ့ရနိုင်ပါတယ်။",
    "လုပ်ငန်းခွင် သို့မဟုတ် ပညာရေးမှာ ကိုယ့်ရဲ့ ကြိုးစားအားထုတ်မှုကို အထက်လူကြီးများက အသိအမှတ်ပြုလာမယ့် နေ့တစ်နေ့ ဖြစ်ပါတယ်။ မိတ်ဆွေသစ်တွေနဲ့လည်း ဆက်ဆံရေး အထူးကောင်းမွန်နေပါတယ်။",
    "ရှုပ်ထွေးနေတဲ့ ပြဿနာဟောင်းတစ်ခုကို မိတ်ဆွေကောင်းတွေရဲ့ အကူအညီနဲ့ အလွယ်တကူ ဖြေရှင်းနိုင်သွားပါမယ်။ စိတ်နှလုံး အေးချမ်းရမယ့် ရက်ကောင်းတစ်ရက် ဖြစ်ပါတယ်။",
]

TOMORROW_AVOIDS = [
    "စကားပြောဆိုရာမှာ အလောတကြီး ဆုံးဖြတ်ပြောဆိုမိခြင်းနဲ့ အထင်အမြင်လွဲမှားမှုများကို အထူးသတိပြုပါ။ ကိုယ့်ရဲ့ စိတ်ခံစားချက်ကို ထိန်းချုပ်ဖို့ လိုအပ်ပါတယ်။",
    "အရေးကြီးတဲ့ ဆုံးဖြတ်ချက်တွေ ချမှတ်တဲ့အခါ သူတစ်ပါးရဲ့ စကားကို အလွယ်တကူ မယုံကြည်ဘဲ ကိုယ်တိုင်သေချာ စဉ်းစားသုံးသပ်ပါ။",
]

TRAITS_POOL = [
    "ခေါင်းဆောင်မှု အပြည့်အဝရှိပြီး ကိုယ်ပိုင်ဆုံးဖြတ်ချက် ခိုင်မာသူ ဖြစ်ပါတယ်။ အခက်အခဲတွေကို ရဲရဲဝံ့ဝံ့ ရင်ဆိုင်ကျော်ဖြတ်တတ်တဲ့ စိတ်ဓာတ်ရှိပါတယ်။",
    "အရာရာကို လက်တွေ့ကျကျနဲ့ စနစ်တကျ ဦးဆောင်လုပ်ကိုင်တတ်တဲ့ သဘာဝရှိပါတယ်။ တာဝန်ယူမှု တာဝန်ခံမှု အပြည့်အဝ ရှိသူ ဖြစ်ပါတယ်။",
]

LOVE_POOL = [
    "အချစ်ရေးမှာ တဖက်လူအပေါ် အလွန်ဂရုစိုက်ပေးတတ်ပေမယ့် တစ်ခါတရံ မာနကိုတော့ လျှော့ချသင့်ပါတယ်။ နားလည်မှုအပြည့်နဲ့ တည်ဆောက်ရမယ့် ကာလဖြစ်ပါတယ်။",
]

CAREER_POOL = [
    "လုပ်ငန်းခွင်နဲ့ စီးပွားရေးမှာ ကိုယ်ပိုင်ဖန်တီးမှုအသစ်တွေနဲ့ ထိပ်ဆုံးကို ရောက်ရှိနိုင်ပါတယ်။ လုပ်ငန်းတိုးချဲ့မှုတွေအတွက် အကောင်းဆုံး အချိန်အခါ ဖြစ်ပါတယ်။",
]

TAROT_DECK = [
    {"name": "The Fool (လူမိုက်)", "vibe": "ခရီးအသစ်စတင်ခြင်း၊ စွန့်စားရဲခြင်း၊ အကောင်းမြင်စိတ်ဖြင့် ရှေ့ဆက်ခြင်း"},
    {"name": "The Magician (ပညာရှင်)", "vibe": "စွမ်းရည်များကို အပြည့်အဝအသုံးချပြီး ရည်မှန်းချက်အောင်မြင်မည့် ကာလ"},
    {"name": "The High Priestess (ပုရောဟိတ်မ)", "vibe": "အတွင်းစိတ်အသိကို နားထောင်ရန်နှင့် သည်းခံရန် အချိန်"},
]

# မေးခွန်းများနှင့် အဖြေများ သိမ်းဆည်းရန် စာရင်း
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

# ကံစမ်းမဲဂိမ်းအတွက် ဆုလာဘ်များ
LUCKY_PRIZES = [
    "🎉 ဂုဏ်ယူပါတယ်! ယနေ့ သင်၏ ကံကောင်းခြင်း လက်ဆောင်မှာ **'ထီပေါက်ကံစမ်းခြင်း အထူးကောင်းမွန်ခြင်း'** ဖြစ်ပါသည်။",
    "✨ ဝမ်းသာစရာပါ! သင်သည် ယနေ့တွင် **'မေတ္တာရေးရာ အံ့အားသင့်စရာ ကံကောင်းမှု'** ကို ပိုင်ဆိုင်ရပါမည်။",
    "💰 ရွှေလိုမိုးလို ကျမည့်နေ့ပါ! **'ငွေကြေးဝင်ရောက်မည့်ကံ'** အထူးတလည် တောက်ပနေပါသည်။",
    "🌟 စိတ်ချမ်းသာမှုနှင့်အတူ **'ခရီးသွားလာရမည့်အခွင့်အလမ်းကောင်း'** များ ပေါ်ပေါက်လာပါမည်။",
]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🌟 ရာသီခွင် အသေးစိတ်ဟောကိန်း", callback_data="mode_zodiac")],
        [InlineKeyboardButton("📅 မနက်ဖြန် ဖြစ်ပျက်မည့်ဟောကိန်း", callback_data="mode_tomorrow")],
        [InlineKeyboardButton("🃏 တားရော့ (၃) ကတ် ဟောရန်", callback_data="mode_tarot")],
        [InlineKeyboardButton("🎮 ဂိမ်းများ ဆော့ကစားရန် (/game)", callback_data="menu_games")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "မင်္ဂလာပါရှင့်/ခဗျာ 🙏\n\n"
        "ဤဘော့တ်မှတဆင့် ဗေဒင်ဟောကိန်းများ၊ တားရော့နှင့် ဂရုများတွင် ဂိမ်းများ ဆော့ကစားနိုင်ပါသည်။\n"
        "မေးခွန်းအသစ်ထည့်ရန် `/addq` ကို အသုံးပြုပါ။",
        reply_markup=reply_markup,
    )


# /game Command ဖြင့် ဂိမ်းအမျိုးအစား ရွေးချယ်စရာ မီနူးပြသခြင်း
async def game_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🧠 အဖွဲ့လိုက် ဉာဏ်စမ်းဂိမ်း (Trivia)", callback_data="game_trivia")],
        [InlineKeyboardButton("🎁 ကံစမ်းမဲ ကံကောင်းခြင်းဂိမ်း", callback_data="game_lucky")],
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

    # ဂိမ်းအမျိုးအစား ရွေးချယ်မှုများ
    if data == "menu_games":
        keyboard = [
            [InlineKeyboardButton("🧠 အဖွဲ့လိုက် ဉာဏ်စမ်းဂိမ်း (Trivia)", callback_data="game_trivia")],
            [InlineKeyboardButton("🎁 ကံစမ်းမဲ ကံကောင်းခြင်းဂိမ်း", callback_data="game_lucky")],
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
            [
                InlineKeyboardButton("🎲 ထပ်မံ ကံစမ်းမည်", callback_data="game_lucky"),
                InlineKeyboardButton("🎮 ဂိမ်းမီနူးသို့", callback_data="menu_games"),
            ],
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
        cards = random.sample(TAROT_DECK, 3)
        response = (
            f"✨ **တားရော့ ကတ် (၃) ကတ် ဟောကိန်း** ✨\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"1️⃣ **အတိတ်:** {cards[0]['name']} - {cards[0]['vibe']}\n\n"
            f"2️⃣ **ပစ္စုပ္ပန်:** {cards[1]['name']} - {cards[1]['vibe']}\n\n"
            f"3️⃣ **အနာဂတ်:** {cards[2]['name']} - {cards[2]['vibe']}"
        )
        keyboard = [
            [
                InlineKeyboardButton("🔄 ထပ်မံ မဲကြည့်မည်", callback_data="mode_tarot"),
                InlineKeyboardButton("🏠 ပင်မမီနူးသို့", callback_data="menu_start"),
            ]
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
        [
            InlineKeyboardButton("🔄 အခြားတစ်ခု ထပ်မံမေးမည်", callback_data="menu_start"),
            InlineKeyboardButton("🏠 ပင်မမီနူးသို့", callback_data="menu_start"),
        ]
    ]
    await update.message.reply_text(response, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("game", game_command))
    app.add_handler(CommandHandler("addq", add_question_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("Multi-Game Astrology Bot is running...")
    app.run_polling()
