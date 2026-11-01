import os
import random
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from dotenv import load_dotenv
from tarot_data import TAROT_CARDS

# Logging သတ်မှတ်ခြင်း
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# .env ဖိုင်မှ Token ကို ဖတ်ရန်
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    keyboard = [
        [InlineKeyboardButton("🔮 နေ့စဉ်ကတ်ဆွဲရန် (Daily Tarot)", callback_data="daily_card")],
        [InlineKeyboardButton("✨ ကတ် ၃ ကတ် ဟောရန် (3-Card Spread)", callback_data="three_cards")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        f"မင်္ဂလာပါရှင်/ခင်ဗျား **{user_name}**။ 🙏\n\n"
        "ကျွန်ုပ်သည် သင်၏ တားရော့ (Tarot) ဗေဒင်ဆရာ ဘော့တ် ဖြစ်ပါသည်။ "
        "အောက်ပါတို့မှ လိုချင်သည့် ဟောကိန်းပုံစံကို ရွေးချယ်ပါ။"
    )
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

# Button များကို နှိပ်လိုက်သည့်အခါ အလုပ်လုပ်မည့် ပုံစံ
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "daily_card":
        card = random.choice(TAROT_CARDS)
        response = (
            f"🔮 **သင်၏ နေ့စဉ် တားရော့ကတ်** 🔮\n\n"
            f"🏷 ကတ်အမည်:\n"
            f"📜 အဓိပ္ပာယ်:"
        )
        await query.message.reply_photo(photo=card['image'], caption=response, parse_mode="Markdown")

    elif query.data == "three_cards":
        cards = random.sample(TAROT_CARDS, 3)
        response = (
            "✨ **အတိတ်၊ ပစ္စုပ္ပန်၊ အနာဂတ် ကတ် ၃ ကတ် ဟောကိန်း** ✨\n\n"
            f"1️⃣ **အတိတ် (Past):** {cards[0]['name']}\n   - *အဓိပ္ပာယ်:* {cards[0]['meaning']}\n\n"
            f"2️⃣ **ပစ္စုပ္ပန် (Present):** {cards[1]['name']}\n   - *အဓိပ္ပာယ်:* {cards[1]['meaning']}\n\n"
            f"3️⃣ **အနာဂတ် (Future):** {cards[2]['name']}\n   - *အဓိပ္ပာယ်:* {cards[2]['meaning']}"
        )
        await query.message.reply_text(response, parse_mode="Markdown")

def main():
    if not TOKEN:
        print("Error: BOT_TOKEN is missing!")
        return

    application = Application.builder().token(TOKEN).build()

    # Handlers တွေ ထည့်ခြင်း
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))

    # Bot ကို စတင်ခြင်း (Polling)
    print("Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()
    
