import os
import telebot
import yt_dlp

TOKEN = "8824850208:AAGkmULcNJxWx-39-80r-8oJNtSc9g3bSTM"
OWNER_ID = 8062359539

bot = telebot.TeleBot(TOKEN)
joined_groups = set()


@bot.message_handler(commands=["start"])
def send_welcome(message):
  if message.chat.type in ["group", "supergroup"]:
    joined_groups.add(message.chat.id)
    bot.reply_to(message, "မင်္ဂလာပါ! Warning & Music Bot အဆင်သင့်ပါပြီ။")
  else:
    bot.reply_to(
        message,
        "မင်္ဂလာပါ! ဤ Bot သည် Warning, Music နှင့် Broadcast များကို လုပ်ဆောင်ပေးနိုင်ပါသည်။",
    )


# Owner သီးသန့် ကြော်ငြာတင်ရန် Command
@bot.message_handler(commands=["broadcast"])
def broadcast_ads(message):
  if message.from_user.id != OWNER_ID:
    bot.reply_to(message, "⚠️ ဤ Command ကို Owner တစ်ဦးတည်းသာ အသုံးပြုနိုင်ပါသည်။")
    return

  text_to_broadcast = message.text.replace("/broadcast", "").strip()
  if not text_to_broadcast:
    bot.reply_to(
        message,
        "⚠️ ကျေးဇူးပြု၍ ပို့လိုသည့် ကြော်ငြာစာသားကိုပါ ထည့်သွင်းရေးသားပါ။"
        " (ဥပမာ: /broadcast ကြော်ငြာစာသား)",
    )
    return

  success_count = 0
  for group_id in list(joined_groups):
    try:
      bot.send_message(group_id, f"📢 **ကြော်ငြာ**\n\n{text_to_broadcast}", parse_mode="Markdown")
      success_count += 1
    except Exception as e:
      joined_groups.discard(group_id)

  bot.reply_to(message, f"✅ ကြော်ငြာကို Group {success_count} ခုသို့ အောင်မြင်စွာ ပို့ပြီးပါပြီ။")


# YouTube မှ သီချင်းရှာဖွေပြီး အသံဖိုင် (Audio) ပို့ပေးရန်
@bot.message_handler(commands=["song"])
def download_and_send_song(message):
  song_name = message.text.replace("/song", "").strip()
  if not song_name:
    bot.reply_to(message, "⚠️ ကျေးဇူးပြု၍ ရှာလိုသည့် သီချင်းနာမည် ထည့်ပါ (ဥပမာ: /song My Way)")
    return

  processing_msg = bot.reply_to(
      message, f"🔍 '{song_name}' ကို ရှာဖွေပြီး ဒေါင်းလုပ်လုပ်နေပါပြီ..."
  )

  audio_file = None
  try:
    # yt-dlp ဖြင့် YouTube မှ အသံဖိုင်ကို ရှာဖွေ ಡေါင်းလုပ်ဆွဲခြင်း
    ydl_opts = {
        "format": "bestaudio/best",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "outtmpl": "song_audio",
        "default_search": "ytsearch1",
        "noplaylist": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
      info = ydl.extract_info(song_name, download=True)
      if "entries" in info:
        info = info["entries"][0]

      title = info.get("title", song_name)
      audio_file = "song_audio.mp3"

    # Telegram သို့ အသံဖိုင် ပို့ပေးခြင်း
    with open(audio_file, "rb") as audio:
      bot.send_audio(
          message.chat.id,
          audio,
          title=title,
          performer="Music Bot",
          reply_to_message_id=message.message_id,
      )

    # ယာယီ ပို့ပြီးသား မက်ဆေ့ချ်ကို ဖျက်ခြင်း
    bot.delete_message(message.chat.id, processing_msg.message_id)

  except Exception as e:
    bot.edit_message_text(
        f"❌ သီချင်းရှာဖွေရာတွင် အမှားဖြစ်ပွားပါသည်: {e}",
        message.chat.id,
        processing_msg.message_id,
    )

  finally:
    # ဖိုင်တွဲထဲမှ ယာယီသိမ်းထားသော အသံဖိုင်ကို ဖျက်ရန်
    if audio_file and os.path.exists(audio_file):
      os.remove(audio_file)


# Warning Commands
@bot.message_handler(commands=["warn"])
def warn_user(message):
  if message.reply_to_message:
    target_user = message.reply_to_message.from_user.first_name
    bot.reply_to(message, f"⚠️ {target_user} ကို သတိပေးချက် (Warn) ထည့်သွင်းပြီးပါပြီ။")
  else:
    bot.reply_to(message, "⚠️ သတိပေးလိုသူ၏ မက်ဆေ့ချ်ကို Reply လုပ်၍ /warn သုံးပါ။")


@bot.message_handler(commands=["ban"])
def ban_user(message):
  if message.reply_to_message:
    chat_id = message.chat.id
    target_id = message.reply_to_message.from_user.id
    try:
      bot.ban_chat_member(chat_id, target_id)
      bot.reply_to(message, "🚫 အဖွဲ့ဝင်ကို အောင်မြင်စွာ Ban ပြီးပါပြီ။")
    except Exception as e:
      bot.reply_to(message, f"❌ အမှားဖြစ်ပွားနေပါသည်: {e}")
  else:
    bot.reply_to(message, "⚠️ Ban လိုသူ၏ မက်ဆေ့ချ်ကို Reply လုပ်ပါ။")


print("Bot is running...")
bot.infinity_polling()
  
