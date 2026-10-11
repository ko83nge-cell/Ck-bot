import logging
import os
import tempfile
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
import yt_dlp

# Logging သတ်မှတ်ရန်
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Bot Token ကို Environment Variable (သို့) တိုက်ရိုက်ထည့်ပါ
TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")


# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    welcome_text = (
        f"မင်္ဂလာပါ 👋 **{user_name}**၊ Ck_helpbot မှ ကြိုဆိုပါတယ်။\n\n"
        f"🎵 သီချင်းရှာရန်\n`/song` သီချင်းအမည်\n\n"
        f"/help - အကူအညီကြည့်ရန်"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


# /help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📚 **Ck_helpbot Commands**\n\n"
        "🎵 **အသုံးပြုသူများ:**\n"
        "/start - Bot စတင်ရန်\n"
        "/help - အကူအညီ\n"
        "/song သီချင်းအမည် - သီချင်းရှာရန်\n\n"
        "🛡️ **Group Admin Commands:**\n"
        "/warn - Reply လုပ်ထားသူကို Warning ပေးရန်\n"
        "/warnings - Warning ကြည့်ရန်\n"
        "/ban - Reply လုပ်ထားသူကို Ban လုပ်ရန်\n"
        "/unban USER_ID - Unban လုပ်ရန်\n"
        "/mute - Reply လုပ်ထားသူကို Mute လုပ်ရန်\n"
        "/unmute - Unmute လုပ်ရန်"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


# /song command (yt-dlp ဖြင့် သီချင်းဒေါင်းပြီး ပို့ပေးရန်)
async def song(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "ကျေးဇူးပြု၍ သီချင်းအမည် ထည့်ပါဝင်ပါ။ ဥပမာ: `/song Shape of You`",
            parse_mode="Markdown",
        )
        return

    query = " ".join(context.args)
    msg = await update.message.reply_text(
        f"🔎 `{query}` ကို ရှာဖွေနေပါပြီ ခဏစောင့်ပါ..."
    )

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            ydl_opts = {
                "format": "bestaudio/best",
                "default_search": "ytsearch1",
                "outtmpl": os.path.join(temp_dir, "%(title)s.%(ext)s"),
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
                "quiet": True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(
                    f"ytsearch:{query}", download=True
                )
                if "entries" in info:
                    info = info["entries"][0]

                filename = ydl.prepare_filename(info)
                audio_file = os.path.splitext(filename)[0] + ".mp3"
                title = info.get("title", "Audio")

            await msg.edit_text("📤 သီချင်းဖိုင် ပို့ဆောင်နေပါပြီ...")
            with open(audio_file, "rb") as f:
                await update.message.reply_audio(
                    audio=f,
                    title=title,
                    performer="Ck_helpbot",
                )
            await msg.delete()

    except Exception as e:
        logger.error(f"Error downloading song: {e}")
        await msg.edit_text(
            "❌ သီချင်းရှာဖွေရာတွင် အမှားအယွင်းရှိသွားပါသည်။ ထပ်မံကြိုးစားကြည့်ပါ။"
        )


# Admin Check Helper
async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if update.effective_chat.type == "private":
        return True  # Private chat ဖြစ်ရင် ခွင့်ပြုမည်
    user_id = update.effective_user.id
    member = await context.bot.get_chat_member(
        update.effective_chat.id, user_id
    )
    return member.status in ["administrator", "creator"]


# /warn command
async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text(
            "⚠️ ဤ විධාန်ကို Admin များသာ အသုံးပြုနိုင်ပါသည်။"
        )
        return

    if not update.message.reply_to_message:
        await update.message.reply_text(
            "⚠️ Warning ပေးလိုသူ၏ မက်ဆေ့ချ်ကို Reply လုပ်၍ အသုံးပြုပါ။"
        )
        return

    target_user = update.message.reply_to_message.from_user
    await update.message.reply_text(
        f"⚠️ {target_user.mention_html()} ကို Warning ပေးလိုက်ပါပြီ။",
        parse_mode="HTML",
    )


# /ban command
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("⚠️ Admin များသာ အသုံးပြုနိုင်ပါသည်။")
        return

    if not update.message.reply_to_message:
        await update.message.reply_text(
            "⚠️ Ban လိုသူ၏ မက်ဆေ့ချ်ကို Reply လုပ်ပါ။"
        )
        return

    target_user = update.message.reply_to_message.from_user
    try:
        await context.bot.ban_chat_member(
            update.effective_chat.id, target_user.id
        )
        await update.message.reply_text(
            f"🚫 {target_user.mention_html()} ကို Group မှ Ban လိုက်ပါပြီ။",
            parse_mode="HTML",
        )
    except Exception as e:
        await update.message.reply_text(f"❌ အမှားဖြစ်ပွားသည်: {e}")


# /mute command
async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("⚠️ Admin များသာ အသုံးပြုနိုင်ပါသည်။")
        return

    if not update.message.reply_to_message:
        await update.message.reply_text(
            "⚠️ Mute လုပ်လိုသူ၏ မက်ဆေ့ချ်ကို Reply လုပ်ပါ။"
        )
        return

    target_user = update.message.reply_to_message.from_user
    try:
        from telegram import ChatPermissions

        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target_user.id,
            permissions=ChatPermissions(can_send_messages=False),
        )
        await update.message.reply_text(
            f"🔇 {target_user.mention_html()} ကို Mute လုပ်လိုက်ပါပြီ။",
            parse_mode="HTML",
        )
    except Exception as e:
        await update.message.reply_text(f"❌ အမှားဖြစ်ပွားသည်: {e}")


def main():
    # Application တည်ဆောက်ရန်
    application = Application.builder().token(TOKEN).build()

    # Handlers များ ထည့်သွင်းရန်
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("song", song))
    application.add_handler(CommandHandler("warn", warn))
    application.add_handler(CommandHandler("ban", ban))
    application.add_handler(CommandHandler("mute", mute))

    # Bot ကို စတင်လည်ပတ်ရန် (Polling)
    print("Bot is running...")
    application.run_polling()


if __name__ == "__main__":
    main()
