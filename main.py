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

# ရာသီခွင် ၁၂ ခုစာ အချက်အလက်များ (အင်္ဂလိပ်နှင့် မြန်မာနာမည်များ အတိအကျဖြင့်)
ZODIAC_DATA = {
    "aries": {
        "name": "မိဿရာသီ (Aries)",
        "traits": "စွန့်စားလိုစိတ်ပြင်းထန်ပြီး ခေါင်းဆောင်မှု အပြည့်အဝရှိသူ။ စိတ်ကို တိုက်ရိုက်ဖော်ပြတတ်သည်။",
        "love": "အချစ်ရေးတွင် တဖက်လူအပေါ် ဂရုစိုက်သော်လည်း မာနကြီးတတ်ခြင်းကို သတိပြုပါ။",
        "career": "ဦးဆောင်ရမည့် နေရာများနှင့် ရဲဝံ့စွာ လုပ်ကိုင်ရမည့်ကိစ္စများတွင် အထူးအောင်မြင်သည်။",
        "caution": "ဆုံးဖြတ်ချက်များချရာတွင် စိတ်အလျင်စလိုဖြစ်ခြင်းကို ရှောင်ရှားသင့်သည်။",
    },
    "taurus": {
        "name": "ပြိဿရာသီ (Taurus)",
        "traits": "တည်ငြိမ်ပြီး လက်တွေ့ကျကျ တွေးခေါ်တတ်သူ။ ခိုင်မာတဲ့ ရည်မှန်းချက်ရှိသည်။",
        "love": "အချစ်ရေးတွင် သစ္စာရှိပြီး ရေရှည်တည်မြဲမည့် ဆက်ဆံရေးကို တည်ဆောက်လိုသည်။",
        "career": "ငွေကြေးစီမံခန့်ခွဲမှု၊ ရင်းနှီးမြှုပ်နှံမှုနှင့် စီးပွားရေးလုပ်ငန်းများတွင် အောင်မြင်မည်။",
        "caution": "အပြောင်းအလဲအသစ်များကို လက်ခံရန် နှေးကွေးခြင်းတို့ ရှိတတ်သည်။",
    },
    "gemini": {
        "name": "မေထုန်ရာသီ (Gemini)",
        "traits": "စကားပြောဆိုရတာ ဝါသနာပါပြီး ဉာဏ်ပညာထက်မြက်သူ။ ပတ်ဝန်းကျင်သစ်နှင့် လွယ်ကူစွာ သင့်မြတ်သည်။",
        "love": "အချစ်ရေးတွင် ပျော်စရာကောင်းပြီး ရိုမန်တစ်ဆန်သည်။ စိတ်ကူးယဉ်ဆန်တတ်သည်။",
        "career": "ဆက်သွယ်ရေး၊ မီဒီယာ၊ အရောင်းအဝယ်နှင့် နည်းပညာလုပ်ငန်းများတွင် ထူးချွန်သည်။",
        "caution": "အာရုံစူးစိုက်မှု အလွယ်တကူ ကွဲတတ်ခြင်းကို သတိပြုပါ။",
    },
    "cancer": {
        "name": "ကရကဋ်ရာသီ (Cancer)",
        "traits": "ကြင်နာတတ်ပြီး အခြားသူများ၏ ခံစားချက်ကို နားလည်ပေးနိုင်သူ။ မိသားစုကို အလွန်ဂရုစိုက်သည်။",
        "love": "အချစ်ရေးတွင် နက်နက်ရှိုင်းရှိုင်း ချစ်တတ်ပြီး စိတ်ထိခိုက်လွယ်သည်။",
        "career": "လူမှုရေးလုပ်ငန်းများ၊ စောင့်ရှောက်ရေးနှင့် အိမ်ခြံမြေလုပ်ငန်းများတွင် ကံကောင်းသည်။",
        "caution": "အတိတ်က အဖြစ်အပျက်ဟောင်းများကို စိတ်ထဲစွဲလမ်းတွေးတောခြင်းကို ရှောင်ပါ။",
    },
    "leo": {
        "name": "သိဟ်ရာသီ (Leo)",
        "traits": "မွန်မြတ်တဲ့ စိတ်ထားရှိပြီး တောက်ပတဲ့ ကိုယ်ရည်ကိုယ်သွေးပိုင်ရှင်။ ထင်ရှားပေါ်လွင်လိုစိတ်ရှိသည်။",
        "love": "အချစ်ရေးတွင် ရက်ရောပြီး ချစ်သူကို အထူးဂရုစိုက်ပြသတတ်သည်။ ဂုဏ်သိက္ခာကို တန်ဖိုးထားသည်။",
        "career": "စီမံခန့်ခွဲမှု၊ အနုပညာ၊ အကြီးတန်း တာဝန်ယူရသော နေရာများတွင် ထိပ်ဆုံးသို့ ရောက်မည်။",
        "caution": "မာနကြီးတတ်ခြင်းနှင့် သူတစ်ပါးအကြံဉာဏ် လက်မခံချင်ခြင်းကို သတိပြုပါ။",
    },
    "virgo": {
        "name": "ကန်ရာသီ (Virgo)",
        "traits": "အသေးစိတ်ကို အစွန်းရောက် ဂရုစိုက်တတ်ပြီး စနစ်တကျ နေထိုင်လိုသူ။",
        "love": "အချစ်ရေးတွင် စိစစ်တတ်သော်လည်း တကယ်ချစ်မိပါက အရာရာ ပေးဆပ်သည်။",
        "career": "စာရင်းအင်း၊ ဆေးပညာ၊ သုတေသနနှင့် စနစ်တကျလုပ်ကိုင်ရသည့် နေရာများတွင် ထူးချွန်သည်။",
        "caution": "တောင်းဆိုချက် အလွန်များပြားခြင်းကြောင့် စိတ်ဖိစီးမှုတက်တတ်သည်။",
    },
    "libra": {
        "name": "တူရာသီ (Libra)",
        "traits": "တရားမျှတမှုကို နှစ်သက်ပြီး လူအများနဲ့ သင့်မြတ်အောင် ပေါင်းသင်းတတ်သူ။",
        "love": "အချစ်ရေးတွင် စံပြအဖော်အဖက်ကောင်းတစ်ဦး ဖြစ်လာနိုင်ပြီး အထီးကျန်မှုကို မကြိုက်ပါ။",
        "career": "ဥပဒေရေးရာ၊ အတိုင်ပင်ခံလုပ်ငန်းနှင့် ဖက်ရှင်ဒီဇိုင်း လုပ်ငန်းများတွင် အောင်မြင်မည်။",
        "caution": "ဆုံးဖြတ်ချက်တစ်ခုချရန် တွေဝေကြန့်ကြာတတ်ခြင်းကို ပြင်ဆင်ပါ။",
    },
    "scorpio": {
        "name": "ဗြိစ္ဆာရာသီ (Scorpio)",
        "traits": "စိတ်ပိုင်းဆိုင်ရာ ခိုင်မာပြင်းပြပြီး လျှို့ဝှက်ချက်များကို ထိန်းသိမ်းနိုင်သူ။",
        "love": "အချစ်ရေးတွင် အလွန်စွဲလမ်းပြင်းပြပြီး သစ္စာရှိမှုကို အမြင့်ဆုံးတောင်းဆိုသည်။",
        "career": "ငွေကြေးရင်းနှီးမြှုပ်နှံမှု၊ သုတေသနနှင့် စုံစမ်းထောက်လှမ်းရေး လုပ်ငန်းများတွင် ကောင်းသည်။",
        "caution": "သံသ័យလွန်ကဲခြင်းနှင့် မကျေနပ်ချက် ဝှက်ထားခြင်းကို ရှောင်ကြဉ်ပါ။",
    },
    "sagittarius": {
        "name": "ဓနုရာသီ (Sagittarius)",
        "traits": "ခရီးသွားရတာ ဝါသနာပါပြီး ပျော်ရွှင်စရာကောင်းတဲ့ အကောင်းမြင်ဝါဒီ။",
        "love": "အချစ်ရေးတွင် ပျော်ပျော်နေတတ်ပြီး တင်းကျပ်သော အချုပ်အနှောင်များကို မကြိုက်ပါ။",
        "career": "ပညာရေး၊ ခရီးသွားလုပ်ငန်း၊ နိုင်ငံတကာဆက်ဆံရေးနှင့် စာပေနယ်ပယ်တို့တွင် ကံကောင်းသည်။",
        "caution": "စကားပြောဆိုရာတွင် ဆင်ခြင်တုံတရား နည်းပါးခြင်းကို သတိပြုပါ။",
    },
    "capricorn": {
        "name": "မကာရရာသီ (Capricorn)",
        "traits": "ဇွဲလုံ့လကြီးပြီး တာဝန်ယူမှု တာဝန်ခံမှု အပြည့်အဝရှိသူ။",
        "love": "အချစ်ရေးတွင် အပေါ်ယံစကားထက် လက်တွေ့ကျကျ စောင့်ရှောက်ပေးတတ်သည်။",
        "career": "အစိုးရလုပ်ငန်းများ၊ ကော်ပိုရိတ် စီမံခန့်ခွဲမှုနှင့် ဘဏ်လုပ်ငန်းများတွင် ထိပ်တန်းရောက်မည်။",
        "caution": "အလုပ်ကိုသာ အဓိကထားပြီး ပင်ပန်းနွမ်းနယ်တတ်ခြင်းကို သတိပြုပါ။",
    },
    "aquarius": {
        "name": "ကုမ်ရာသီ (Aquarius)",
        "traits": "ဆန်းသစ်တီထွင်လိုစိတ်ရှိပြီး လူ့အဖွဲ့အစည်းအပေါ် ကူညီလိုစိတ်ပြင်းထန်သူ။",
        "love": "အချစ်ရေးတွင် ချစ်သူထက် မိတ်ဆွေကောင်းတစ်ဦး ဖြစ်လာရန် ဦးစားပေးသည်။",
        "career": "နည်းပညာအသစ်များ၊ အိုင်တီနှင့် တီထွင်ဖန်တီးမှု လုပ်ငန်းများတွင် ထူးချွန်သည်။",
        "caution": "ခံစားချက်ကင်းမဲ့နေသလို သို့မဟုတ် သီးသန့်ဆန်နေတတ်ခြင်းကို သတိပြုပါ။",
    },
    "pisces": {
        "name": "မိန်ရာသီ (Pisces)",
        "traits": "စိတ်ကူးယဉ်ဆန်ပြီး အလွန်နားလည်စာနာတတ်သော စိတ်နှလုံးပိုင်ရှင်။",
        "love": "အချစ်ရေးတွင် အပြည့်အဝ ပေးဆပ်ချစ်တတ်ပြီး ရိုမန်တစ်ဆန်သည်။",
        "career": "အနုပညာ၊ ကုသရေး၊ စိတ်ပညာနှင့် ဖန်တီးမှုဆိုင်ရာ နယ်ပယ်များတွင် အောင်မြင်မည်။",
        "caution": "စိတ်ကူးယဉ်လောကထဲတွင်သာ အချိန်ကုန်နေတတ်ခြင်းကို ရှောင်ရှားသင့်သည်။",
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
            InlineKeyboardButton("🌟 ရာသီခွင်အသေးစိတ် မေးရန်", callback_data="menu_zodiac"),
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
            "✨ ကျေးဇူးပြု၍ သင့်ရဲ့ **ရာသီခွင်အမည်** (ဥပမာ - *Leo, Aries, ေမထုန်, သိဟ်*) ကို Chat ထဲမှာ စာသားပုံစံဖြင့် ရိုက်ထည့်ပြီး ပို့ပေးပါ။"
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
                InlineKeyboardButton("🌟 ရာသီခွင်အသေးစိတ် မေးရန်", callback_data="menu_zodiac"),
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

    # ၁။ အင်္ဂလိပ်အမည်ဖြင့် တိုက်ရိုက်စစ်ဆေးခြင်း (ဥပမာ leo, aries စသည်)
    for key in ZODIAC_DATA.keys():
        if key in text:
            matched_key = key
            break

    # ၂။ မြန်မာအမည်များဖြင့် စစ်ဆေးခြင်း
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

    # အကယ်၍ လုံးဝမတိုက်ဆိုင်ပါက ပုံသေမဟုတ်ဘဲ ကျပန်းတစ်ခု ထုတ်ပေးမည်
    if not matched_key:
        matched_key = random.choice(list(ZODIAC_DATA.keys()))

    info = ZODIAC_DATA[matched_key]
    response = (
        f"🔮 **သင်ထည့်သွင်းလိုက်သော အချက်အလက်အတွက် ဟောကိန်း**\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"✨ **ရာသီခွင်:** {info['name']}\n\n"
        f"🧠 **စိတ်နေစိတ်ထား:**\n• {info['traits']}\n\n"
        f"❤️ **အချစ်ရေး:**\n• {info['love']}\n\n"
        f"💼 **လုပ်ငန်းခွင်နှင့် စီးပွားရေး:**\n• {info['career']}\n\n"
        f"⚠️ **သတိပြုရှောင်ရှားစရာ:**\n• {info['caution']}"
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
