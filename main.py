import telebot
from telebot import types

# ပေးထားသော Bot Token နှင့် Owner ID
TOKEN = "8881360966:AAEXozal8_zGclJ0fFw7OFEKL4yy5Yope2s"
OWNER_ID = 8062359539

bot = telebot.TeleBot(TOKEN)

# ဘော့စတင်ချိန် (သို့မဟုတ်) /start နှိပ်ချိန်တွင် အသုံးပြုပုံရှင်းလင်းချက်ပြခြင်း
@bot.message_handler(commands=['start'])
def command_start(message):
    help_text = (
        "🤖 **ကြော်ငြာဘော့မှ ကြိုဆိုပါတယ်!**\n\n"
        "ဤဘော့၏ အသုံးပြုပုံ အချက်အလက်များ-\n"
        "• **ကြော်ငြာတင်ခြင်း:** Owner တစ်ဦးတည်းသာ Group ထဲတွင် စာ သို့မဟုတ် ပုံစံဖြင့် တိုက်ရိုက် (Start နှိပ်ခိုင်းစရာမလိုဘဲ) တင်နိုင်ပါသည်။\n"
        "• **Link ဖျက်ခြင်း:** ခွင့်ပြုချက်မရှိဘဲ တင်ထားသော Link များကို အလိုအလျောက် ဖျက်ပေးပါသည်။\n"
        "• **User Ban/Unban:** Owner မှ ညွှန်ကြားချက်ပေး၍ အသုံးပြုနိုင်ပါသည်။\n\n"
        "အဆင်ပြေပါစေ။"
    )
    bot.reply_to(message, help_text, parse_mode="Markdown")

# Group ထဲတွင် Link များကို စစ်ဆေးပြီး ဖျက်ခြင်း နှင့် Owner ကြော်ငြာတင်ခြင်း
@bot.message_handler(func=lambda message: True, content_types=['text', 'photo', 'video', 'document', 'animation'])
def handle_all_messages(message):
    # Group သို့မဟုတ် Supergroup ဖြစ်မှသာ စစ်ဆေးမည်
    if message.chat.type in ['group', 'supergroup']:
        
        # ပို့လိုက်သောစာထဲတွင် Link ပါဝင်ခြင်း ရှိမရှိ စစ်ဆေးခြင်း
        is_link = False
        if message.text:
            if "http://" in message.text or "https://" in message.text or "t.me/" in message.text:
                is_link = True
        elif message.caption:
            if "http://" in message.caption or "https://" in message.caption or "t.me/" in message.caption:
                is_link = True

        # အကယ်၍ Link ဖြစ်နေပြီး ပို့သူသည် Owner မဟုတ်ပါက မက်ဆေ့ချ်ကို ဖျက်မည်
        if is_link and message.from_user.id != OWNER_ID:
            try:
                bot.delete_message(message.chat.id, message.message_id)
                return
            except Exception as e:
                print(f"Link ဖျက်ရာတွင် အမှားရှိသည်: {e}")

        # Owner ဖြစ်ပါက ကြော်ငြာ သို့မဟုတ် မည်သည့်မက်ဆေ့ချ်မဆို Start နှိပ်စရာမလိုဘဲ တန်းတင်ခွင့်ရှိသည်
        if message.from_user.id == OWNER_ID:
            # Owner တင်သည့် မက်ဆေ့ချ်ကို ပုံမှန်အတိုင်း ဆက်လက်ပြသမည် (ဘာမှ လုပ်စရာမလိုပါ)
            pass

# Ban Command (Owner သီးသန့် - Group ထဲတွင် Ban မည့်သူ့ကို Reply လုပ်ပြီး /ban ဟု ရိုက်ပါ)
@bot.message_handler(commands=['ban'])
def ban_user(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "⚠️ ဤ විධාန်ကို အသုံးပြုခွင့် Owner တွင်သာ ရှိသည်။")
        return
    
    if message.reply_to_message:
        user_to_ban = message.reply_to_message.from_user.id
        try:
            bot.ban_chat_member(message.chat.id, user_to_ban)
            bot.reply_to(message, f"✅ User အား Group မှ အောင်မြင်စွာ Ban လိုက်ပါပြီ။")
        except Exception as e:
            bot.reply_to(message, f"❌ မအောင်မြင်ပါ: {e}")
    else:
        bot.reply_to(message, "⚠️ Ban မည့်သူ၏ မက်ဆေ့ချ်ကို Reply လုပ်ပြီး /ban ဟု ရိုက်ပါ။")

# Unban Command (Owner သီးသန့် - ဥပမာ /unban 123456789)
@bot.message_handler(commands=['unban'])
def unban_user(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "⚠️ ဤ විධාန်ကို အသုံးပြုခွင့် Owner တွင်သာ ရှိသည်။")
        return
    
    args = message.text.split()
    if len(args) > 1:
        try:
            user_to_unban = int(args[1])
            bot.unban_chat_member(message.chat.id, user_to_unban)
            bot.reply_to(message, f"✅ User အား Unban ပြန်လုပ်ပေးလိုက်ပါပြီ။")
        except Exception as e:
            bot.reply_to(message, f"❌ မအောင်မြင်ပါ (သို့မဟုတ်) User ID မှားယွင်းနေပါသည်: {e}")
    else:
        bot.reply_to(message, "⚠️ ကျေးဇူးပြု၍ Unban မည့်သူ၏ User ID ထည့်ပါ။ (ဥပမာ - /unban 123456789)")

# 24/7 အမြဲအလုပ်လုပ်နေစေရန်
bot.infinity_polling()
