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

TOKEN = os.getenv("TELEGRAM_TOKEN")

# ရာသီခွင် ၁၂ ခုစာ အချက်အလက်များနှင့် မနက်ဖြန်အတွက် ဟောကိန်းများ
ZODIAC_DATA = {
    "aries": {
        "name": "မိဿရာသီ (Aries)",
        "traits": "စွန့်စားလိုစိတ်ပြင်းထန်ပြီး ခေါင်းဆောင်မှု အပြည့်အဝရှိသူ။",
        "tomorrow_event": "မနက်ဖြန်တွင် လုပ်ငန်းသစ်များ စတင်ရန်နှင့် ရဲရဲဝံ့ဝံ့ ဆုံးဖြတ်ရမည့် ကိစ္စများတွင် အထူးအဆင်ပြေမည်။ မထင်မှတ်သော ငွေကြေးဝင်ရောက်လာနိုင်.",
        "tomorrow_avoid": "စိတ်အလျင်စလိုဖြစ်ခြင်းနှင့် အပြောအဆို ကြမ်းတမ်းခြင်းတို့ကို အထူးရှောင်ရှားပါ။",
    },
    "taurus": {
        "name": "ပြိဿရာသီ (Taurus)",
        "traits": "တည်ငြိမ်ပြီး လက်တွေ့ကျကျ တွေးခေါ်တတ်သူ။",
        "tomorrow_event": "မနက်ဖြန်သည် ငွေကြေးစီမံခန့်ခွဲမှုနှင့် စီးပွားရေးလုပ်ငန်းများအတွက် အလွန်ကောင်းမွန်သော အချိန်ဖြစ်ပြီး အေးချမ်းစွာ ဖြတ်သန်းရမည်။",
        "tomorrow_avoid": "အပြောင်းအလဲအသစ်များကို လက်ခံရန် နှေးကွေးခြင်းနှင့် မလိုအပ်ဘဲ စိတ်ပူပန်ခြင်းကို ရှောင်ပါ။",
    },
    "gemini": {
        "name": "မေထုန်ရာသီ (Gemini)",
        "traits": "စကားပြောဆိုရတာ ဝါသနာပါပြီး ဉာဏ်ပညာထက်မြက်သူ။",
        "tomorrow_event": "မနက်ဖြန်တွင် မိတ်ဆွေသစ်များနှင့် ဆုံတွေ့ရခြင်း၊ ဆက်သွယ်ရေးလုပ်ငန်းများ အောင်မြင်ခြင်းတို့ ကြုံရမည်။",
        "tomorrow_avoid": "အာရုံစူးစိုက်မှု အလွယ်တကူ ကွဲတတ်ခြင်းနှင့် ကတိကဝတ်များကို ပေါ့ဆခြင်းမှ ရှောင်ကြဉ်ပါ။",
    },
    "cancer": {
        "name": "ကရကဋ်ရာသီ (Cancer)",
        "traits": "ကြင်နာတတ်ပြီး အခြားသူများ၏ ခံစားချက်ကို နားလည်ပေးနိုင်သူ။",
        "tomorrow_event": "မနက်ဖြန်တွင် မိသားစုနှင့် အနီးစပ်ဆုံးသူများထံမှ အထောက်အပံ့ကောင်းများနှင့် မေတ္တာတရားများ ခံစားရမည်။",
        "tomorrow_avoid": "အတိတ်က အကြောင်းအရာဟောင်းများကို ပြန်လည်တွေးတောပြီး စိတ်ညစ်ရခြင်းကို ရှောင်ပါ။",
    },
    "leo": {
        "name": "သိဟ်ရာသီ (Leo)",
        "traits": "မွန်မြတ်တဲ့ စိတ်ထားရှိပြီး တောက်ပတဲ့ ကိုယ်ရည်ကိုယ်သွေးပိုင်ရှင်။",
        "tomorrow_event": "မနက်ဖြန်တွင် လူအများ၏ အာရုံစိုက်မှုကို ခံရမည်ဖြစ်ပြီး လုပ်ငန်းခွင်၌ ထჩွန်ပေါက်မြောက်မည့် ကာလဖြစ်သည်။",
        "tomorrow_avoid": "မာနကြီးတတ်ခြင်းနှင့် သူတစ်ပါး၏ အကြံဉာဏ်ကို လျစ်လျူရှုခြင်းတို့ကို ရှောင်ရှားပါ။",
    },
    "virgo": {
        "name": "ကန်ရာသီ (Virgo)",
        "traits": "အသေးစိတ်ကို အစွန်းရောက် ဂရုစိုက်တတ်ပြီး စနစ်တကျ နေထိုင်လိုသူ။",
        "tomorrow_event": "မနက်ဖြန်တွင် ရှုပ်ထွေးနေသော စာရင်းဇယားများနှင့် အလုပ်ကိစ္စများကို ရှင်းလင်းအောင် လုပ်ဆောင်နိုင်မည်။",
        "tomorrow_avoid": "အရာရာကို အပြစ်တင်စစ်ဆေးလွန်းခြင်းကြောင့် ကိုယ်တိုင်နှင့် အခြားသူများ စိတ်ဖိစီးရမှုကို ရှောင်ပါ။",
    },
    "libra": {
        "name": "တူရာသီ (Libra)",
        "traits": "တရားမျှတမှုကို နှစ်သက်ပြီး လူအများနဲ့ သင့်မြတ်အောင် ပေါင်းသင်းတတ်သူ။",
        "tomorrow_event": "မနက်ဖြန်တွင် မိတ်ဆွေကောင်းများ၏ အကူအညီဖြင့် အကျပ်အတည်းများ ပြေလည်သွားမည်။ အချစ်ရေး သာယာမည်။",
        "tomorrow_avoid": "ဆုံးဖြတ်ချက်တစ်ခုချရန် အချိန်ဆွဲခြင်းနှင့် တွေဝေနေခြင်းတို့ကို ရှောင်ပါ။",
    },
    "scorpio": {
        "name": "ဗြိစ္ဆာရာသီ (Scorpio)",
        "traits": "စိတ်ပိုင်းဆိုင်ရာ ခိုင်မာပြင်းပြပြီး လျှို့ဝှက်ချက်များကို ထိန်းသိမ်းနိုင်သူ။",
        "tomorrow_event": "မနက်ဖြန်တွင် လျှို့ဝှက်ထားသော အကျိုးအမြတ်များ သို့မဟုတ် ကိုယ်ပိုင်ကြိုးစားမှု ရလဒ်ကောင်းများ ပေါ်ထွက်လာမည်။",
        "tomorrow_avoid": "သံသ័យလွန်ကဲခြင်းနှင့် မကျေနပ်ချက်များကို စိတ်ထဲဝှက်ထားခြင်းမှ ရှောင်ကြဉ်ပါ။",
    },
    "sagittarius": {
        "name": "ဓနုရာသီ (Sagittarius)",
        "traits": "ခရီးသွားရတာ ဝါသနာပါပြီး ပျော်ရွှင်စရာကောင်းတဲ့ အကောင်းမြင်ဝါဒီ။",
        "tomorrow_event": "မနက်ဖြန်တွင် ခရီးထွက်ရခြင်း သို့မဟုတ် ပျော်စရာအတွေ့အကြုံသစ်များနှင့် ကြုံတွေ့ရလိမ့်မည်။",
        "tomorrow_avoid": "စကားပြောဆိုရာတွင် ဆင်ခြင်တုံတရား နည်းပါးခြင်းကြောင့် အထင်အမြင်လွဲမှားမှုကို ရှောင်ပါ။",
    },
    "capricorn": {
        "name": "မကာရရာသီ (Capricorn)",
        "traits": "ဇွဲလုံ့လကြီးပြီး တာဝန်ယူမှု တာဝန်ခံမှု အပြည့်အဝရှိသူ။",
        "tomorrow_event": "မနက်ဖြန်တွင် လုပ်ငန်းခွင်၌ အထက်လူကြီး၏ မျက်နှာသာပေးမှုနှင့် ရည်မှန်းချက် အောင်မြင်မှုကို ရရှိမည်။",
        "tomorrow_avoid": "အလုပ်ကိုသာ အလွန်အကျွံဦးစားပေးပြီး ကျန်းမာရေးကို ဥပက္ခာပြုခြင်းမှ ရှောင်ကြဉ်ပါ။",
    },
    "aquarius": {
        "name": "ကုမ်ရာသီ (Aquarius)",
        "traits": "ဆန်းသစ်တီထွင်လိုစိတ်ရှိပြီး လူ့အဖွဲ့အစည်းအပေါ် ကူညီလိုစိတ်ပြင်းထန်သူ။",
        "tomorrow_event": "မနက်ဖြန်တွင် အကြံဉာဏ်အသစ်များ ထွက်ပေါ်လာမည်ဖြစ်ပြီး နည်းပညာနှင့် တီထွင်မှုလုပ်ငန်းများ အောင်မြင်မည်။",
        "tomorrow_avoid": "တစ်ယောက်တည်း သီးသန့်ဆန်လွန်းနေခြင်းနှင့် အများနဲ့ အဆက်အသွယ်ပြတ်သွားခြင်းကို ရှောင်ပါ။",
    },
    "pisces": {
        "name": "မိန်ရာသီ (Pisces)",
        "traits": "စိတ်ကူးယဉ်ဆန်ပြီး အလွန်နားလည်စာနာတတ်သော စိတ်နှလုံးပိုင်ရှင်။",
        "tomorrow_event": "မနက်ဖြန်တွင် အနုပညာခံစားမှုများ မြင့်တက်နေမည်ဖြစ်ပြီး စိတ်နှလုံး အေးချမ်းသာယာမှု ရရှိမည်။",
        "tomorrow_avoid": "အဖြစ်မှန်ကို မမြင်ဘဲ စိတ်ကူးယဉ်လောကထဲတွင်သာ အချိန်ကုန်နေခြင်းကို ရှောင်ရှားသင့်သည်။",
    },
}

TAROT_DECK = [
    {
        "name": "The Fool (လူမိုက်)",
        "vibe": "ခရီးအသစ်စတင်ခြင်း၊ စွန့်စားရဲခြင်း၊ အကောင်းမြင်စိတ်ဖြင့် ရှေ့ဆက်ခြင်း",
    },
    {
        "name": "The Magician (ပညာရှင်)",
        "vibe": "စွမ်းရည်များကို အပြည့်အဝအသုံးချပြီး ရည်မှန်းချက်အောင်မြင်မည့် ကာလ",
    },
    {
        "name": "The High Priestess (ပုရောဟိတ်မ)",
        "vibe": "အတွင်းစိတ်အသိကို နားထောင်ရန်နှင့် သည်းခံရန် အချိန်",
    },
    {
        "name": "The Empress (မိဖုရား)",
        "vibe": "စည်းစိမ်ဥစ္စာ ပြည့်စုံခြင်း၊ မေတ္တာရေးရာ အဆင်ပြေခြင်း",
    },
    {
        "name": "The Emperor (ဧကရာဇ်)",
        "vibe": "ခေါင်းဆောင်မှု၊ တည်ငြိမ်ခိုင်မာမှု၊ စည်းကမ်းရှိရှိ လုပ်ဆောင်ရခြင်း",
    },
    {
        "name": "The Lovers (ချစ်သူများ)",
        "vibe": "အရေးကြီးဆုံး ဆုံးဖြတ်ချက်ချရခြင်း၊ စိတ်နှလုံးချင်း တိုက်ဆိုင်မှုရှိခြင်း",
    },
    {
        "name": "The Wheel of Fortune (ကံကြမ္မာစက်ဝိုင်း)",
        "vibe": "ကံကြမ္မာ ရုတ်တရက် ပြောင်းလဲခြင်း၊ အပြောင်းအလဲကောင်းများ ကြုံရခြင်း",
    },
    {
        "name": "The Star (ကြယ်ပွင့်)",
        "vibe": "မျှော်လင့်ချက်အသစ်များ ပေါ်ပေါက်လာခြင်း၊ စိတ်နှလုံး အေးချမ်းခြင်း",
    },
]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("🌟 ရာသီခွင် မနက်ဖြန်ဟောကိန်း", callback_data="menu_zodiac"),
            InlineKeyboardButton("🃏 တားရော့ (၃) ကတ် ဟောရန်", callback_data="menu_tarot"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "မင်္ဂလာပါရှင့်/ခဗျာ 🙏\n\nကျေးဇူးပြု၍ အောက်ပါတို့မှ လိုချင်သော ဟောကိန်းအမျိုးအစားကို ရွေးချယ်ပါ -",
        reply_markup=reply_markup,
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "menu_zodiac":
        await query.edit_message_text(
            "✨ ကျေးဇူးပြု၍ သင့်ရဲ့ **ရာသီခွင်အမည်** (ဥပမာ - *Leo, Aries, မေထုန်, သိဟ်*) ကို Chat ထဲမှာ စာသားပုံစံဖြင့် ရိုက်ထည့်ပြီး ပို့ပေးပါ။"
        )
    elif query.data == "menu_tarot":
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
                InlineKeyboardButton("🔄 ထပ်မံ မဲကြည့်မည်", callback_data="menu_tarot"),
                InlineKeyboardButton("🏠 ပင်မမီနူးသို့", callback_data="menu_start"),
            ]
        ]
        await query.edit_message_text(
            response, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif query.data == "menu_start":
        keyboard = [
            [
                InlineKeyboardButton("🌟 ရာသီခွင် မနက်ဖြန်ဟောကိန်း", callback_data="menu_zodiac"),
                InlineKeyboardButton("🃏 တားရော့ (၃) ကတ် ဟောရန်", callback_data="menu_tarot"),
            ]
        ]
        await query.edit_message_text(
            "မင်္ဂလာပါရှင့်/ခဗျာ 🙏\n\nကျေးဇူးပြု၍ အောက်ပါတို့မှ လိုချင်သော ဟောကိန်းအမျိုးအစားကို ရွေးချယ်ပါ -",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()

    matched_key = None

    # အင်္ဂလိပ်အမည်ဖြင့် တိုက်ရိုက်စစ်ဆေးခြင်း
    for key in ZODIAC_DATA.keys():
        if key in text:
            matched_key = key
            break

    # မြန်မာအမည်များဖြင့် စစ်ဆေးခြင်း
    if not matched_key:
        if any(w in text for w in ["မိဿ", "မတ်", "ဧပြီ"]):
            matched_key = "aries"
        elif any(w in text for w in ["ပြိဿ", "မေ"]):
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

    if not matched_key:
        matched_key = random.choice(list(ZODIAC_DATA.keys()))

    info = ZODIAC_DATA[matched_key]
    response = (
        f"🔮 **မနက်ဖြန်အတွက် သင့်ရဲ့ ဟောကိန်းအထူး**\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"✨ **ရာသီခွင်:** {info['name']}\n\n"
        f"🌟 **မနက်ဖြန် ဖြစ်ပျက်မည့်အခြေအနေ:**\n• {info['tomorrow_event']}\n\n"
        f"⚠️ **မနက်ဖြန် သတိပြုရှောင်ရှားရမည့်အချက်:**\n• {info['tomorrow_avoid']}"
    )

    keyboard = [
        [
            InlineKeyboardButton("🔄 အခြားတစ်ခု ထပ်မံမေးမည်", callback_data="menu_zodiac"),
            InlineKeyboardButton("🏠 ပင်မမီနူးသို့", callback_data="menu_start"),
        ]
    ]
    await update.message.reply_text(
        response, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
    )


if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("Bot is running...")
    app.run_polling()
