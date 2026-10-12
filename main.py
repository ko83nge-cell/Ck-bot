import os
import sqlite3
import requests
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [
    int(uid.strip())
    for uid in os.getenv("ADMIN_IDS", "0").split(",")
    if uid.strip()
]

# Database Setup for Movies
conn = sqlite3.connect("movies_bot.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS movies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        file_id TEXT,
        caption TEXT
    )
""")
conn.commit()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
  await update.message.reply_text(
      "🤖 **Advanced History & Movie Bot** မှ ကြိုဆိုပါတယ်။\n\n"
      "📚 **သမိုင်း/အချက်အလက်ရှာရန်:** နိုင်ငံအမည် (သို့) သူရဲကောင်းနာမည်ကို ရိုက်ထည့်ပါ (မြန်မာလို အပြည့်အစုံ ဖော်ပြပေးမည်)။\n"
      "🎬 **ရုပ်ရှင်ရှာရန်:** ကြိုက်နှစ်သက်ရာ ရုပ်ရှင်နာမည်ကို ရိုက်ပို့ပါ။\n"
      "➕ **ရုပ်ရှင်အသစ်ထည့်ရန် (Admin သာ):** Bot ထဲသို့ ရုပ်ရှင်ဗီဒီယို (သို့) ဖိုင်ကို တိုက်ရိုက်ပို့ပါ။",
      parse_mode="Markdown",
  )


# --- Complete Burmese Database for Countries and Heroes ---
BURMESE_DATABASE = {
    "myanmar": {
        "title": "မြန်မာနိုင်ငံ (သမိုင်း/အချက်အလက်)",
        "extract": "မြန်မာနိုင်ငံ (တရားဝင်အမည်: ပြည်ထောင်စု သမ္မတ မြန်မာနိုင်ငံတော်) သည် အရှေ့တောင်အာရှတွင် တည်ရှိသော နိုင်ငံတစ်နိုင်ငံ ဖြစ်သည်။ နယ်နမိတ်အားဖြင့် အိန္ဒိယ၊ ဘင်္ဂလားဒေ့ရှ်၊ တရုတ်၊ လာအိုနှင့် ထိုင်းနိုင်ငံတို့နှင့် ထိစပ်နေသည်။ မြို့တော်မှာ နေပြည်တော် ဖြစ်ပြီး စီးပွားရေးမြို့တော်မှာ ရန်ကုန်မြို့ ဖြစ်သည်။",
        "heroes": "⚔️ **ထင်ရှားသော သူရဲကောင်းများ:** အလောင်းဘုရား (Alaungpaya), ဘုရင့်နောင် (Bayinnaung), ကျန်စစ်သား (Kyanzittha), ဗိုလ်ချုပ်အောင်ဆန်း (General Aung San)"
    },
    "မြန်မာ": {
        "title": "မြန်မာနိုင်ငံ (သမိုင်း/အချက်အလက်)",
        "extract": "မြန်မာနိုင်ငံ (တရားဝင်အမည်: ပြည်ထောင်စု သမ္မတ မြန်မာနိုင်ငံတော်) သည် အရှေ့တောင်အာရှတွင် တည်ရှိသော နိုင်ငံတစ်နိုင်ငံ ဖြစ်သည်။ နယ်နမိတ်အားဖြင့် အိန္ဒိယ၊ ဘင်္ဂလားဒေ့ရှ်၊ တရုတ်၊ လာအိုနှင့် ထိုင်းနိုင်ငံတို့နှင့် ထိစပ်နေသည်။ မြို့တော်မှာ နေပြည်တော် ဖြစ်ပြီး စီးပွားရေးမြို့တော်မှာ ရန်ကုန်မြို့ ဖြစ်သည်။",
        "heroes": "⚔️ **ထင်ရှားသော သူရဲကောင်းများ:** အလောင်းဘုရား (Alaungpaya), ဘုရင့်နောင် (Bayinnaung), ကျန်စစ်သား (Kyanzittha), ဗိုလ်ချုပ်အောင်ဆန်း (General Aung San)"
    },
    "thailand": {
        "title": "ထိုင်းနိုင်ငံ (သမိုင်း/အချက်အလက်)",
        "extract": "ထိုင်းနိုင်ငံသည် အရှေ့တောင်အာရှ အလယ်ပိုင်းတွင် တည်ရှိသော နိုင်ငံတစ်ခု ဖြစ်သည်။ ယခင်က ဆยาม (Siam) ဟု ခေါ်ဆိုခဲ့ကြသည်။ မြို့တော်မှာ ဘန်က็อกမြို့ ဖြစ်သည်။",
        "heroes": "⚔️ **ထင်ရှားသော သူရဲကောင်းများ:** King Naresuan (នរេសូរ), King Taksin (ตากสิน)"
    },
    "ထိုင်း": {
        "title": "ထိုင်းနိုင်ငံ (သမိုင်း/အချက်အလက်)",
        "extract": "ထိုင်းနိုင်ငံသည် အရှေ့တောင်အာရှ အလယ်ပိုင်းတွင် တည်ရှိသော နိုင်ငံတစ်ခု ဖြစ်သည်။ ယခင်က ဆยาม (Siam) ဟု ခေါ်ဆိုခဲ့ကြသည်။ မြို့တော်မှာ ဘန်က็อกမြို့ ဖြစ်သည်။",
        "heroes": "⚔️ **ထင်ရှားသော သူရဲကောင်းများ:** King Naresuan, King Taksin"
    },
    "japan": {
        "title": "ဂျပန်နိုင်ငံ (သမိုင်း/အချက်အလက်)",
        "extract": "ဂျပန်နိုင်ငံသည် အရှေ့အာရှတွင် တည်ရှိသော ကျွန်းနိုင်ငံတစ်ခု ဖြစ်သည်။ တိုကျိုမြို့သည် နိုင်ငံ၏ မြို့တော် ဖြစ်သည်။",
        "heroes": "⚔️ **ထင်ရှားသော သူရဲကောင်းများ:** Oda Nobunaga, Miyamoto Musashi"
    },
    "ဂျပန်": {
        "title": "ဂျပန်နိုင်ငံ (သမိုင်း/အချက်အလက်)",
        "extract": "ဂျပန်နိုင်ငံသည် အရှေ့အာရှတွင် တည်ရှိသော ကျွန်းနိုင်ငံတစ်ခု ဖြစ်သည်။ တိုကျိုမြို့သည် နိုင်ငံ၏ မြို့တော် ဖြစ်သည်။",
        "heroes": "⚔️ **ထင်ရှားသော သူရဲကောင်းများ:** Oda Nobunaga, Miyamoto Musashi"
    },
    "alaungpaya": {
        "title": "အလောင်းဘုရား (သမိုင်းအချက်အလက်)",
        "extract": "အလောင်းဘုရားသည် ကုန်းဘောင်မင်းဆက်ကို တည်ထောင်ခဲ့သော မြန်မာဘုရင် ဖြစ်သည်။ မြန်မာနိုင်ငံကို ဒုတိယအကြိမ် ပြန်လည်စုစည်းပေးခဲ့ပြီး နိုင်ငံတော်ကို ချဲ့ထွင်နိုင်ခဲ့သူ ဖြစ်သည်။",
        "heroes": ""
    },
    "အလောင်းဘုရား": {
        "title": "အလောင်းဘုရား (သမိုင်းအချက်အလက်)",
        "extract": "အလောင်းဘုရားသည် ကုန်းဘောင်မင်းဆက်ကို တည်ထောင်ခဲ့သော မြန်မာဘုရင် ဖြစ်သည်။ မြန်မာနိုင်ငံကို ဒုတိယအကြိမ် ပြန်လည်စုစည်းပေးခဲ့ပြီး နိုင်ငံတော်ကို ချဲ့ထွင်နိုင်ခဲ့သူ ဖြစ်သည်။",
        "heroes": ""
    },
    "bayinnaung": {
        "title": "ဘုရင့်နောင် (သမိုင်းအချက်အလက်)",
        "extract": "ဘုရင့်နောင်သည် တောင်ငူခေတ်၏ တတိယမြောက်ဘုရင်ဖြစ်ပြီး မြန်မာ့သမိုင်းတွင် နယ်မြေအကျယ်ပြန့်ဆုံးနှင့် အင်အားအကြီးမားဆုံး နိုင်ငံတော်ကို တည်ဆောက်ခဲ့သူ ဖြစ်သည်။",
        "heroes": ""
    },
    "ဘုရင့်နောင်": {
        "title": "ဘုရင့်နောင် (သမိုင်းအချက်အလက်)",
        "extract": "ဘုရင့်နောင်သည် တောင်ငူခေတ်၏ တတိယမြောက်ဘုရင်ဖြစ်ပြီး မြန်မာ့သမိုင်းတွင် နယ်မြေအကျယ်ပြန့်ဆုံးနှင့် အင်အားအကြီးမားဆုံး နိုင်ငံတော်ကို တည်ဆောက်ခဲ့သူ ဖြစ်သည်။",
        "heroes": ""
    }
}


# --- Combined Search Handler ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
  query = update.message.text.strip().lower()
  
  if query.startswith("/"):
    return

  # 1. Check in local Burmese Database first
  if query in BURMESE_DATABASE:
    item = BURMESE_DATABASE[query]
    reply_text = f"📚 **{item['title']}**\n\n{item['extract']}"
    if item['heroes']:
      reply_text += f"\n\n{item['heroes']}"
    await update.message.reply_text(reply_text, parse_mode="Markdown")
    return

  # 2. Fallback to Movie Database
  await search_and_send_movie(update, context)


# --- Save Movie (Admin Only) ---
async def save_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user_id = update.effective_user.id
  if ADMIN_IDS and user_id not in ADMIN_IDS:
    await update.message.reply_text(
        "⚠️ ဤဘော့ထဲသို့ ဖိုင်များ တိုက်ရိုက်တင်ခွင့်ကို Admin များသာ ပြုလုပ်နိုင်ပါသည်။"
    )
    return

  message = update.message
  file_id = None
  title = ""

  if message.video:
    file_id = message.video.file_id
    title = message.caption or message.video.file_name or "Untitled Movie"
  elif message.document:
    file_id = message.document.file_id
    title = message.caption or message.document.file_name or "Untitled Movie"

  if file_id:
    cursor.execute(
        "INSERT INTO movies (title, file_id, caption) VALUES (?, ?, ?)",
        (title.lower(), file_id, title),
    )
    conn.commit()
    await message.reply_text(
        f"✅ အောင်မြင်စွာ သိမ်းဆည်းပြီးပါပြီ!\n📌 **နာမည်:** {title}"
    )
  else:
    await message.reply_text(
        "⚠️ ကျေးဇူးပြု၍ ရုပ်ရှင် Video သို့မဟုတ် Document ဖိုင်ကို ပို့ပေးပါ။"
    )


async def search_and_send_movie(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
  query = update.message.text.strip().lower()

  cursor.execute(
      "SELECT title, file_id, caption FROM movies WHERE LOWER(title) LIKE ?",
      (f"%{query}%",),
  )
  results = cursor.fetchall()

  if not results:
    await update.message.reply_text(
        "❌ တောင်းပန်ပါတယ်၊ အဆိုပါ အချက်အလက် သို့မဟုတ် ရုပ်ရှင်ကို ရှာမတွေ့ပါ။"
    )
    return

  for title, file_id, caption in results[:5]:
    try:
      await update.message.reply_video(
          video=file_id,
          caption=f"🎥 **{caption}**\n🤖 Bot ဖြင့် ရှာဖွေပေးထားပါသည်။",
          parse_mode="Markdown",
      )
    except Exception:
      try:
        await update.message.reply_document(
            document=file_id,
            caption=f"🎥 **{caption}**\n🤖 Bot ဖြင့် ရှာဖွေပေးထားပါသည်။",
            parse_mode="Markdown",
        )
      except Exception as e:
        print(f"Error sending file: {e}")


def main():
  if not TOKEN:
    print("Error: BOT_TOKEN not set!")
    return

  app = Application.builder().token(TOKEN).build()

  app.add_handler(CommandHandler("start", start))
  app.add_handler(
      MessageHandler(filters.VIDEO | filters.Document.ALL, save_movie)
  )
  app.add_handler(
      MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
  )

  print("Advanced Burmese Bot is running...")
  app.run_polling()


if __name__ == "__main__":
  main()
