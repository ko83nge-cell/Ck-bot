import os
import telebot

TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
# Owner ၏ Telegram User ID ထည့်ရန် (ဥပမာ - 123456789)
OWNER_ID = int(os.getenv("OWNER_ID", "123456789"))

bot = telebot.TeleBot(TOKEN)

# Group ID များကို သိမ်းဆည်းရန် Set တစ်ခု (Database သုံးနိုင်သော်လည်း ရိုးရှင်းရန် memory တွင်သိမ်းမည်)
joined_groups = set()


@bot.message_handler(commands=["start"])
def send_welcome(message):
  if message.chat.type in ["group", "supergroup"]:
    joined_groups.add(message.chat.id)
    bot.reply_to(message, "မင်္ဂလာပါ! Warning & Music Bot အဆင်သင့်ပါပြီ။")
  else:
    bot.reply_to(
        message, "မင်္ဂလာပါ! ဤ Bot သည် Warning, Music နှင့် Broadcast များကို လုပ်ဆောင်ပေးနိုင်ပါသည်။"
    )


# Owner သီးသန့် ကြော်ငြာတင်ရန် Command (/broadcast [စာသား])
@bot.message_handler(commands=["broadcast"])
def broadcast_ads(message):
  if message.from_user.id != OWNER_ID:
    bot.reply_to(message, "⚠️ ဤ Command ကို Owner တစ်ဦးတည်းသာ အသုံးပြုနိုင်ပါသည်။")
    return

  # /broadcast နောက်မှ စာသားကို ယူမည်
  text_to_broadcast = message.text.replace("/broadcast", "").strip()
  if not text_to_broadcast:
    bot.reply_to(
        message,
        "⚠️ ကျေးဇူးပြု၍ ပို့လိုသည့် ကြော်ငြာစာသားကိုပါ ထည့်သွင်းရေးသားပါ။"
        " (ဥပမာ: /broadcast ကြော်ငြာစာသား)",
    )
    return

  success_count = 0
  # Bot ရောက်ရှိနေသော Group တိုင်းသို့ ပို့မည်
  for group_id in list(joined_groups):
    try:
      bot.send_message(group_id, f"📢 **ကြော်ငြာ**\n\n{text_to_broadcast}", parse_mode="Markdown")
      success_count += 1
    except Exception as e:
      # Bot ကို Group မှ ထုတ်ထားပါက set ထဲမှ ဖယ်မည်
      joined_groups.discard(group_id)

  bot.reply_to(message, f"✅ ကြော်ငြာကို Group {success_count} ခုသို့ အောင်မြင်စွာ ပို့ပြီးပါပြီ။")


# သီချင်းရှာဖွေရန်
@bot.message_handler(commands=["song"])
def get_song(message):
  song_name = message.text.replace("/song", "").strip()
  if not song_name:
    bot.reply_to(message, "⚠️ ကျေးဇူးပြု၍ ရှာလိုသည့် သီချင်းနာမည် ထည့်ပါ (ဥပမာ: /song My Way)")
    return
  bot.reply_to(message, f"🔍 '{song_name}' ကို ရှာဖွေနေပါပြီ...")


# Warning Commands (Admin စစ်ဆေးချက်များဖြင့်)
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


# Bot အလုပ်လုပ်နေခြင်းကို စစ်ဆေးရန်
print("Bot is running...")
bot.infinity_polling()
