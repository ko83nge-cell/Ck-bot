import os
import io
import logging
import requests
from telegram import Update, ChatPermissions
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# =========================
# SETTINGS
# =========================

BOT_TOKEN = "8824850208:AAExGzmfMD8Kn0I9fHtYRHAXU8FtjBH2m78"
OWNER_ID = 8062359539

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

warnings = {}


# =========================
# HELPER FUNCTIONS
# =========================

async def is_admin(update, context):
    if not update.effective_user or not update.effective_chat:
        return False
    member = await context.bot.get_chat_member(
        update.effective_chat.id,
        update.effective_user.id,
    )
    return member.status in ("administrator", "creator")


async def get_target(update):
    message = update.effective_message
    if message and message.reply_to_message:
        return message.reply_to_message.from_user
    return None


async def admin_only(update, context):
    if not update.effective_chat:
        return False
    if update.effective_chat.type == "private":
        await update.effective_message.reply_text("ဒီ Command ကို Group ထဲမှာ သုံးပါ။")
        return False
    if not await is_admin(update, context):
        await update.effective_message.reply_text("ဒီ Command ကို Group Admin ပဲ သုံးနိုင်ပါတယ်။")
        return False
    return True


# =========================
# START AND HELP
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "မင်္ဂလာပါ! 🤖\n\n"
        "Music & Group Management Bot ပါ။\n\n"
        "/song - သီချင်း နားဆင်ရန်\n"
        "/help - Command အားလုံးကြည့်ရန်"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "🎵 MUSIC\n"
        "/song\n\n"
        "🛡️ ADMIN COMMANDS\n"
        "/warn - သတိပေးရန်\n"
        "/warnings - Warn အရေအတွက်ကြည့်ရန်\n"
        "/ban - Ban လုပ်ရန်\n"
        "/unban USER_ID - Ban ပြန်ဖြုတ်ရန်\n"
        "/mute - Mute လုပ်ရန်\n"
        "/unmute - Mute ပြန်ဖြုတ်ရန်"
    )


# =========================
# MUSIC (DIRECT STREAM)
# =========================

async def song(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    status = await message.reply_text("🔎 သီချင်းဖိုင် ဆွဲယူနေပါပြီ...")

    try:
        # လုံးဝ Error မတက်မယ့် တည်ငြိမ်တဲ့ Direct Audio URL
        audio_url = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
        title = "Relaxing Melody"
        artist = "Bot Music"

        audio_res = requests.get(audio_url, stream=True, timeout=30)
        audio_res.raise_for_status()

        audio_data = io.BytesIO()
        for chunk in audio_res.iter_content(chunk_size=8192):
            if chunk:
                audio_data.write(chunk)

        audio_data.seek(0)
        audio_data.name = "song.mp3"

        await status.edit_text("🎵 သီချင်း ပို့နေပါပြီ...")

        await message.reply_audio(
            audio=audio_data,
            title=title,
            performer=artist,
            caption=f"🎵 {title}\n🎤 {artist}",
        )

        await status.delete()

    except Exception as e:
        logger.exception("Song send failed")
        await status.edit_text("❌ Error: သီချင်းရယူရာတွင် အခက်အခဲရှိနေပါသည်။")


# =========================
# WARN / BAN / MUTE COMMANDS
# =========================

async def warn(update, context):
    if not await admin_only(update, context):
        return
    target = await get_target(update)
    if not target or target.is_bot:
        await update.effective_message.reply_text("သတိပေးမယ့်သူရဲ့ Message ကို Reply လုပ်ပါ။")
        return

    key = (update.effective_chat.id, target.id)
    warnings[key] = warnings.get(key, 0) + 1
    await update.effective_message.reply_text(
        f"⚠️ {target.full_name} ကို Warn ပေးပြီးပါပြီ။ (Warn: {warnings[key]})"
    )


async def warnings_command(update, context):
    target = await get_target(update)
    user_id = target.id if target else update.effective_user.id
    key = (update.effective_chat.id, user_id)
    await update.effective_message.reply_text(f"⚠️ Warn အရေအတွက်: {warnings.get(key, 0)}")


async def ban(update, context):
    if not await admin_only(update, context):
        return
    target = await get_target(update)
    if not target or target.id == update.effective_user.id or target.is_bot:
        await update.effective_message.reply_text("ဒီသူကို Ban လုပ်လို့မရပါ။")
        return
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, target.id)
        await update.effective_message.reply_text(f"🚫 {target.full_name} ကို Ban လိုက်ပါပြီ။")
    except Exception:
        await update.effective_message.reply_text("Ban မအောင်မြင်ပါ။ Permission စစ်ပါ။")


async def unban(update, context):
    if not await admin_only(update, context):
        return
    if not context.args:
        await update.effective_message.reply_text("အသုံးပြုပုံ: /unban USER_ID")
        return
    try:
        user_id = int(context.args[0])
        await context.bot.unban_chat_member(update.effective_chat.id, user_id, only_if_banned=True)
        await update.effective_message.reply_text(f"✅ User ID {user_id} ကို Unban လုပ်ပြီးပါပြီ။")
    except Exception:
        await update.effective_message.reply_text("Unban မအောင်မြင်ပါ။")


async def mute(update, context):
    if not await admin_only(update, context):
        return
    target = await get_target(update)
    if not target or target.id == update.effective_user.id or target.is_bot:
        await update.effective_message.reply_text("ဒီသူကို Mute လုပ်လို့မရပါ။")
        return
    try:
        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target.id,
            permissions=ChatPermissions(can_send_messages=False),
        )
        await update.effective_message.reply_text(f"🔇 {target.full_name} ကို Mute လုပ်ပြီးပါပြီ။")
    except Exception:
        await update.effective_message.reply_text("Mute မအောင်မြင်ပါ။")


async def unmute(update, context):
    if not await admin_only(update, context):
        return
    target = await get_target(update)
    if not target:
        await update.effective_message.reply_text("Unmute လုပ်မယ့်သူကို Reply လုပ်ပါ။")
        return
    try:
        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target.id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_audios=True,
                can_send_documents=True,
                can_send_photos=True,
                can_send_videos=True,
                can_send_video_notes=True,
                can_send_voice_notes=True,
                can_send_polls=True,
                can_add_web_page_previews=True,
            ),
        )
        await update.effective_message.reply_text(f"🔊 {target.full_name} ကို Unmute လုပ်ပြီးပါပြီ။")
    except Exception:
        await update.effective_message.reply_text("Unmute မအောင်မြင်ပါ။")


# =========================
# MAIN
# =========================

def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN မသတ်မှတ်ရသေးပါ။")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("song", song))
    app.add_handler(CommandHandler("warn", warn))
    app.add_handler(CommandHandler("warnings", warnings_command))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("unban", unban))
    app.add_handler(CommandHandler("mute", mute))
    app.add_handler(CommandHandler("unmute", unmute))

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()

