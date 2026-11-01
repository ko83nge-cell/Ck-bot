import os
import random
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes

TOKEN = os.getenv("TELEGRAM_TOKEN")

# ရာသီခွင် အပိုင်းများအတွက် အချက်အလက်နှင့် ခွဲခြမ်းစိတ်ဖြာချက်များ (ကွက်တိကျကျ ဖြစ်စေရန် ပြောင်းလဲနိုင်သော ပုံစံ)
ZODIAC_SIGNS = [
    "မေထုန် (Gemini)", "သိဟ် (Leo)", "ဗြိစ္ဆာ (Scorpio)", "ကုမ် (Aquarius)", "မိဿ (Aries)", "ကန် (Virgo)"
]

# အချစ်ရေး၊ ပညာရေး၊ စီးပွားရေး အတွက် သဘာဝကျကျ တိုက်ဆိုင်မယ့် ဟောကိန်းများ
LIFE_AREAS = {
    "love": [
        "လက်ရှိ အချစ်ရေးမှာ တစ်ဖက်လူရဲ့ မပြောပြ the secret တွေနဲ့ သင့်ရဲ့ စိုးရိမ်ပူပန်မှုတွေ တိုက်ဆိုင်နေပါတယ်။ ရင်ဖွင့်ဆွေးနွေးဖို့ လိုအပ်နေတဲ့ အချိန်ပါပဲ။",
        "အချစ်ရေးကံကြမ္မာမှာ အရင်က နားလည်မှုလွဲခဲ့တာတွေ ပြေလည်မယ့် အရိပ်အယောင်ရှိပြီး၊ မထင်မှတ်ဘဲ ချစ်ခင်ဂရုစိုက်မှုအသစ်တွေ ခံစားရပါမယ်။",
        "ချစ်သူနဲ့ လမ်းကြောင်းခွဲနေရသလို ခံစားရတတ်ပါတယ်။ ဒါပေမဲ့ သင့်ရဲ့ သည်းခံမှုက ဆက်ဆံရေးကို ပိုခိုင်မာစေပါလိမ့်မယ်။"
    ],
    "edu": [
        "ပညာရေးနဲ့ပတ်သက်ပြီး စိတ်ပိုင်းဆိုင်ရာ ဖိအားအနည်းငယ်ရှိနိုင်ပေမယ့်၊ ကြိုးစားအားထုတ်မှုရဲ့ အသီးအပွင့်ကို မကြာခင် လက်တွေ့ပြန်ရပါမယ်။",
        "စာမေးပွဲ သို့မဟုတ် သင်တန်းကိစ္စတွေမှာ ကိုယ့်ရဲ့ အာရုံစူးစိုက်မှု အားကောင်းနေချိန်ဖြစ်လို့ ရည်မှန်းထားတာထက် ပိုကောင်းတဲ့ ရလဒ်ထွက်လာနိုင်ပါတယ်။",
        "အသစ်လေ့လာစရာတွေ များနေလို့ ဗျာများရတတ်ပါတယ်။ အဓိကကျတဲ့ အကြောင်းအရာတစ်ခုကိုသာ အာရုံစိုက်သင့်ပါတယ်။"
    ],
    "biz": [
        "စီးပွားရေးနှင့် ငွေကြေးပိုင်းမှာ ရဲရဲဝံ့ဝံ့ ဆုံးဖြတ်ရမယ့် ကာလပါပဲ။ ရင်းနှီးမြှုပ်နှံမှုတွေအတွက် သတိကြီးကြီးနဲ့ စဉ်းစားသင့်ပါတယ်။",
        "လုပ်ဖော်ကိုင်ဖက် သို့မဟုတ် ဖောက်သည်တွေနဲ့ ပတ်သက်ပြီး အကျိုးအမြတ်အသစ်တွေ ဝင်ရောက်လာမယ့် ကောင်းတဲ့နိမိတ် ရှိပါတယ်။",
        "ငွေကြေးစီမံခန့်ခွဲမှုမှာ လက်ရှိကြုံနေရတဲ့ အကျပ်အတည်းလေးတွေက မကြာခင် အဆင်ပြေချောမွေ့သွားပါလိမ့်မယ်။"
    ]
}

# တားရော့ကတ်ပြားများ (အတိတ်၊ ပစ္စုပ္ပန်၊ အနာဂတ် အတွက်)
TAROT_DECK = [
    {"name": "The Fool (လူမိုက်)", "vibe": "အစသစ်၊ စွန့်စားမှု၊ လွတ်လပ်မှု"},
    {"name": "The Magician (ပညာရှင်)", "vibe": "စွမ်းရည်ထုတ်သုံးခြင်း၊ အောင်မြင်မှု၊ ဖန်တီးနိုင်စွမ်း"},
    {"name": "The High Priestess (ပုရောဟိတ်မ)", "vibe": "အတွင်းစိတ်အသိ၊ သည်းခံခြင်း၊ လျှို့ဝှက်ချက်"},
    {"name": "The Empress (မိဖုရား)", "vibe": "ပြည့်စုံကြွယ်ဝမှု၊ မေတ္တာတရား၊ ဖူလုံခြင်း"},
    {"name": "The Emperor (ဧကရာဇ်)", "vibe": "ခေါင်းဆောင်မှု၊ တည်ငြိမ်ခိုင်မာမှု၊ စည်းကမ်း"},
    {"name": "The Lovers (ချစ်သူများ)", "vibe": "အရေးကြီးဆုံး ဆုံးဖြတ်ချက်၊ စိတ်နှလုံးချင်း တိုက်ဆိုင်မှု"},
    {"name": "The Wheel of Fortune (ကံကြမ္မာစက်ဝိုင်း)", "vibe": "ရုတ်တရက် အပြောင်းအလဲ၊ ကံကောင်းခြင်း"}
]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("🌟 ရာသီခွင် အချစ်/ပညာ/စီးပွား", callback_data="menu_zodiac"),
            InlineKeyboardButton("🃏 တားရော့ ကတ် ၃ ကတ် ဟောရန်", callback_data="menu_tarot")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "မင်္ဂလာပါရှင့်/ခဗျာ 🙏\n\nဤဘော့တ်မှတဆင့် သင့်ရဲ့ ဖြစ်ပျက်နေတဲ့ အခြေအနေနဲ့ အတိကျဆုံး တိုက်ဆိုင်မယ့် ဗေဒင်နဲ့ တားရော့ဟောကိန်းများကို ကြည့်ရှုနိုင်ပါတယ်။ အောက်ပါတို့မှ လိုချင်တာကို ရွေးချယ်ပါ -",
        reply_markup=reply_markup
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "menu_zodiac":
        # ရာသီခွင် ရွေးချယ်ရန် မီနူးပြခြင်း
        keyboard = [
            [
                InlineKeyboardButton("❤️ အချစ်ရေး", callback_data="z_love"),
                InlineKeyboardButton("📚 ပညာရေး", callback_data="z_edu"),
                InlineKeyboardButton("💰 စီးပွားရေး", callback_data="z_biz")
            ],
            [InlineKeyboardButton("« ပင်မမီနူးသို့", callback_data="menu_start")]
        ]
        await query.edit_message_text(
            "✨ ကျေးဇူးပြု၍ ဟောကြားလိုသော ကဏ္ဍကို ရွေးချယ်ပါ:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data in ["z_love", "z_edu", "z_biz"]:
        sign = random.choice(ZODIAC_SIGNS)
        if query.data == "z_love":
            cat_name = "❤️ အချစ်ရေး ကံကြမ္မာ"
            text_result = random.choice(LIFE_AREAS["love"])
        elif query.data == "z_edu":
            cat_name = "📚 ပညာရေး ကံကြမ္မာ"
            text_result = random.choice(LIFE_AREAS["edu"])
        else:
            cat_name = "💰 စီးပွားရေး ကံကြမ္မာ"
            text_result = random.choice(LIFE_AREAS["biz"])

        response = (
            f"🔮 **{cat_name}**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📌 **သင့်အတွက် တိုက်ဆိုင်စစ်ဆေးချက်** ({sign}):\n\n"
            f"• {text_result}\n\n"
            f"💡 *မှတ်ချက်:* ယခုအချိန်တွင် သင်ကြုံတွေ့နေရသော ဖြစ်တည်မှုနှင့် တိုက်ရိုက်ကိုက်ညီစေရန် ဖန်တီးထားပါသည်။"
        )
        keyboard = [[InlineKeyboardButton("« အခြားကဏ္ဍများ", callback_data="menu_zodiac"),
                     InlineKeyboardButton("🏠 ပင်မသို့", callback_data="menu_start")]]
        await query.edit_message_text(response, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "menu_tarot":
        # 3-Card Spread (အတိတ်၊ ပစ္စုပ္ပန်၊ အနာဂတ်) ကျပန်းထုတ်ပေးခြင်း
        cards = random.sample(TAROT_DECK, 3)
        response = (
            f"✨ **တားရော့ ကတ် (၃) ကတ် ဟောကိန်း** ✨\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"1️⃣ **အတိတ် (Past):** {cards[0]['name']}\n"
            f"   - အဓိပ္ပာယ်: {cards[0]['vibe']} နှင့်ဆက်စပ်သော ဖြစ်စဉ်များ ဖြတ်သန်းခဲ့ရသည်။\n\n"
            f"2️⃣ **ပစ္စုပ္ပန် (Present):** {cards[1]['name']}\n"
            f"   - အဓိပ္ပာယ်: ယခုလက်ရှိ သင်ရင်ဆိုင်နေရသော {cards[1]['vibe']} အခြေအနေကို အထူးဂရုပြုပါ။\n\n"
            f"3️⃣ **အနာဂတ် (Future):** {cards[2]['name']}\n"
            f"   - အဓိပ္ပာယ်: ရှေ့ဆက်လာမည့် ကာလတွင် {cards[2]['vibe']} နှင့် ကြုံတွေ့ရလိမ့်မည်။"
        )
        keyboard = [[InlineKeyboardButton("🔄 ထပ်မံဲ မဲကြည့်မည်", callback_data="menu_tarot"),
                     InlineKeyboardButton("🏠 ပင်မသို့", callback_data="menu_start")]]
        await query.edit_message_text(response, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "menu_start":
        keyboard = [
            [
                InlineKeyboardButton("🌟 ရာသီခွင် အချစ်/ပညာ/စီးပွား", callback_data="menu_zodiac"),
                InlineKeyboardButton("🃏 တားရော့ ကတ် ၃ ကတ် ဟောရန်", callback_data="menu_tarot")
            ]
        ]
        await query.edit_message_text(
            "မင်္ဂလာပါရှင့်/ခဗျာ 🙏\n\nဤဘော့တ်မှတဆင့် သင့်ရဲ့ ဖြစ်ပျက်နေတဲ့ အခြေအနေနဲ့ အတိကျဆုံး တိုက်ဆိုင်မယ့် ဗေဒင်နဲ့ တားရော့ဟောကိန်းများကို ကြည့်ရှုနိုင်ပါတယ်။ အောက်ပါတို့မှ လိုချင်တာကို ရွေးချယ်ပါ -",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("Bot is running...")
    app.run_polling()
