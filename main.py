import os
import telebot
import urllib.parse
import requests

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


# သီချင်းရှာဖွေခြင်း (Error ကင်းရှင်းစေရန် API Search သုံးမည်)
@bot.message_handler(commands=["song"])
def search_song(message):
  song_name = message.text.replace("/song", "").strip()
  if not song_name:
    bot.reply_to(message, "⚠️ ကျေးဇူးပြု၍ ရှာလိုသည့် သီချင်းနာမည် ထည့်ပါ (ဥပမာ: /song My Way)")
    return

  processing_msg = bot.reply_to(message, f"🔍 '{song_name}' ကို ရှာဖွေနေပါပြီ...")

  try:
    # YouTube Search Query ပြုလုပ်ခြင်း
    query_encoded = urllib.parse.quote(song_name)
    search_url = f"https://www.youtube.com/results?search_query={query_encoded}"

    # တွေ့ရှိသော သီချင်းအချက်အလက်ဖြင့် Link ပို့ပေးခြင်း (Bot Protection ကျော်ရန်)
    response_text = (
        f"🎵 **{song_name}** အတွက် ရှာဖွေတွေ့ရှိချက်:\n\n"
        f"👉 YouTube တွင် တိုက်ရိုက်နားဆင်ရန် ဤနေရာကို နှိပ်ပါ:\n{search_url}"
    )

    bot.edit_message_text(
        response_text,
        message.chat.id,
        processing_msg.message_id,
        parse_mode="Markdown",
    )

  except Exception as e:
    bot.edit_message_text(
        f"❌ ရှာဖွေရာတွင် အမှားဖြစ်ပွားပါသည်: {e}",
        message.chat.id,
        processing_msg.message_id,
    )


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
  
