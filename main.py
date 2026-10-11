import os
import sqlite3
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
      "🎬 **Auto Movie Bot** မှ ကြိုဆိုပါတယ်။\n\n"
      "🔍 **ရုပ်ရှင်ရှာရန်:** ကြိုက်နှစ်သက်ရာ ရုပ်ရှင်နာမည်ကို ရိုက်ပြီး ပို့လိုက်ပါ။ (ဥပမာ - `Avatar`)\n"
      "➕ **ရုပ်ရှင်အသစ်ထည့်ရန် (Admin သာ):** Bot ထဲသို့ ရုပ်ရှင်ဗီဒီယို (သို့) ဖိုင်ကို ပို့ပါ။",
      parse_mode="Markdown",
  )


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

  if query.startswith("/"):
    return

  cursor.execute(
      "SELECT title, file_id, caption FROM movies WHERE LOWER(title) LIKE ?",
      (f"%{query}%",),
  )
  results = cursor.fetchall()

  if not results:
    await update.message.reply_text(
        "❌ တောင်းပန်ပါတယ်၊ အဆိုပါ နာမည်နဲ့ ရုပ်ရှင်ကို ရှာမတွေ့ပါ။"
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
      MessageHandler(filters.TEXT & ~filters.COMMAND, search_and_send_movie)
  )

  print("Auto Movie Bot is running...")
  app.run_polling()


if __name__ == "__main__":
  main()
