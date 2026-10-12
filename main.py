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
      "🤖 **Global History & Movie Bot** မှ ကြိုဆိုပါတယ်။\n\n"
      "📚 **သမိုင်း/အချက်အလက်ရှာရန်:** ကမ္ဘာ့နိုင်ငံ မည်သည့်နိုင်ငံမဆို သို့မဟုတ် ပုဂ္ဂိုလ်တစ်ဦးဦး၏ နာမည်ကို ရိုက်ထည့်ပါ (မြန်မာလို အလိုအလျောက် ဘာသာပြန်ပြမည်)။\n"
      "🎬 **ရုပ်ရှင်ရှာရန်:** ကြိုက်နှစ်သက်ရာ ရုပ်ရှင်နာမည်ကို ရိုက်ပို့ပါ။\n"
      "➕ **ရုပ်ရှင်အသစ်ထည့်ရန် (Admin သာ):** Bot ထဲသို့ ရုပ်ရှင်ဗီဒီယို (သို့) ဖိုင်ကို တိုက်ရိုက်ပို့ပါ။",
      parse_mode="Markdown",
  )


# --- Helper Function to Translate Text to Burmese ---
def translate_to_burmese(text):
  if not text:
    return text
  try:
    q_text = text[:1500]  # Take up to 1500 characters to prevent API errors
    url = "https://translate.googleapis.com/translate_a/single"
    params = {
        "client": "gtx",
        "sl": "en",
        "tl": "my",
        "dt": "t",
        "q": q_text,
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
      res_json = response.json()
      translated_text = "".join([item[0] for item in res_json[0]])
      return translated_text
  except Exception as e:
    print(f"Translation Error: {e}")
  return text


# --- Dynamic Search Handler for All Countries & Figures Worldwide ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
  query = update.message.text.strip()
  
  if query.startswith("/"):
    return

  query_lower = query.lower()

  # Handle common abbreviations or short forms
  if query_lower == "thai":
    search_query = "Thailand"
  elif query_lower == "usa":
    search_query = "United States"
  elif query_lower == "uk":
    search_query = "United Kingdom"
  else:
    search_query = query

  # Step A: Search Wikipedia API dynamically for ANY country or figure worldwide
  wiki_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(search_query)}"
  headers = {"User-Agent": "Mozilla/5.0"}
  
  try:
    response = requests.get(wiki_url, headers=headers)
    if response.status_code == 200:
      data = response.json()
      extract = data.get("extract")
      title = data.get("title", query)
      
      if extract and "not found" not in extract.lower():
        # Translate title and extract dynamically to Burmese
        translated_title = translate_to_burmese(title)
        translated_extract = translate_to_burmese(extract)
        
        reply_text = f"📚 **{translated_title} (သမိုင်း/အချက်အလက်)**\n\n{translated_extract}"
        await update.message.reply_text(reply_text, parse_mode="Markdown")
        return
  except Exception as e:
    print(f"Wikipedia API Error: {e}")

  # Step B: If not found on Wikipedia, search in SQLite Movie Database
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
        "❌ တောင်းပန်ပါတယ်၊ Wikipedia တွင်လည်း မတွေ့ရှိပါ၊ ရုပ်ရှင်ဒေတာဘေ့စ်ထဲတွင်လည်း အဆိုပါနာမည်နဲ့ ရုပ်ရှင်ကို ရှာမတွေ့ပါ။"
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

  print("Global Dynamic Translated Bot is running...")
  app.run_polling()


if __name__ == "__main__":
  main()
