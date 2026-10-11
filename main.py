import os
import sqlite3
from telegram import Update
from telegram.ContextTypes import ContextTypes
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN")
# Admin တွေရဲ့ Telegram User ID များကို ကော်မာ (,) ခံ၍ ထည့်နိုင်သည် (ဥပမာ: "123456789,987654321")
ADMIN_IDS = [
    int(uid.strip())
    for uid in os.getenv("ADMIN_IDS", "0").split(",")
    if uid.strip()
]

# SQLite Database ချိတ်ဆက်ခြင်း (ရုပ်ရှင်အချက်အလက်များနှင့် file_id များ သိမ်းရန်)
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
      "➕ **ရုပ်ရှင်အသစ်ထည့်ရန် (Admin သာ):** Bot ထဲသို့ ရုပ်ရှင်ဗီဒီယို (သို့) ဖိုင်ကို ပို့ပါ။ Caption တွင် ရုပ်ရှင်နာမည်ကို ထည့်ပေးပါ။",
      parse_mode="Markdown",
  )


# Admin မှ ဗီဒီယို/ဖိုင် ပို့လိုက်လျှင် Database ထဲ အလိုအလျောက် သိမ်းရန်
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
    # Database ထဲသို့ သိမ်းဆည်းမည်
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


# User များမှ စာသားဖြင့် ရှာဖွေသည့်အခါ Chat ထဲသို့ တိုက်ရိုက် ဗီဒီယို ပို့ပေးရန်
async def search_and_send_movie(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
  query = update.message.text.strip().lower()

  # / နဲ့စတဲ့ Command များကို ကျော်သွားရန်
  if query.startswith("/"):
    return

  cursor.execute(
      "SELECT title, file_id, caption FROM movies WHERE LOWER(title) LIKE ?",
      (f"%{query}%",),
  )
  results = cursor.fetchall()

  if not results:
    await update.message.reply_text(
        "❌ တောင်းပန်ပါတယ်၊ အဆိုပါ နာမည်နဲ့ ရုပ်ရှင်ကို ရှာမတွေ့ပါ။ နာမည်အမှန် (သို့) အတိုကောက်ဖြင့် ထပ်မံရှာကြည့်ပါ။"
    )
    return

  # တွေ့ရှိသော ရုပ်ရှင်များကို Chat ထဲသို့ ပို့ပေးမည် (အများဆုံး ၅ ခု)
  for title, file_id, caption in results[:5]:
    try:
      await update.message.reply_video(
          video=file_id,
          caption=f"🎥 **{caption}**\n🤖 Bot ဖြင့် ရှာဖွေပေးထားပါသည်။",
          parse_mode="Markdown",
      )
    except Exception:
      # Video အဖြစ် ပို့မရပါက Document အဖြစ် ပို့မည်
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

  # Handlers များ
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
