import os
import io
import logging
import asyncio
from telegram import Update, ChatPermissions
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)
import yt_dlp

# =========================
# SETTINGS
# =========================

BOT_TOKEN = "8824850208:AAGkmULcNJxWx-39-80r-8oJNtSc9g3bSTM"
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
        "YouTube Music & Group Management Bot ပါ။\n\n"
        "/song သီချင်းနာမည် - YouTube မှ သီချင်းရှာပြီး ပို့ရန်\n"
        "/help - Command အားလုံးကြည့်ရန်"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "🎵 MUSIC\n"
        "/song သီချင်းနာမည် (မြန်မာ/အင်္ဂလိပ် မဆို ရှာနိုင်သည်)\n\n"
        "🛡️ ADMIN COMMANDS\n"
        "/warn - သတိပေးရန်\n"
        "/warnings - Warn အရေအတွက်ကြည့်ရန်\n"
        "/ban - Ban လုပ်ရန်\n"
        "/unban USER_ID - Ban ပြန်ဖြုတ်ရန်\n"
        "/mute - Mute လုပ်ရန်\n"
        "/unmute - Mute ပြန်ဖြုတ်ရန်"
    )


# =========================
# YOUTUBE MUSIC SEARCH & DOWNLOAD
# =========================

async def song(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message

    if not context.args:
        await message.reply_text(
            "သီချင်းနာမည် ထည့်ပေးပါ။\n"
            "ဥပမာ: /song a hmat ta ya"
        )
        return

    query = " ".join(context.args)
    status = await message.reply_text(f"🔎 YouTube မှ '{query}' ကို ရှာဖွေနေပါတယ်...")

    audio_path = None
    try:
        def download_audio():
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'outtmpl': 'downloads/%(id)s.%(ext)s',
                'quiet': True,
                'no_warnings': True,
                'default_search': 'ytsearch1',
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch1:{query}", download=True)
                if 'entries' in info:
                    info = info['entries'][0]
                filename = ydl.prepare_filename(info)
                audio_file = os.path.splitext(filename)[0] + '.mp3'
                return audio_file, info.get('title', 'Unknown Title'), info.get('uploader', 'Unknown Artist')

        loop = asyncio.get_running_loop()
        audio_path, title, artist = await loop.run_in_executor(None, download_audio)

        if not audio_path or not os.path.exists(audio_path):
            await status.edit_text("❌ သီချင်းဖိုင် ရှာမတွေ့ပါ။ အခြားနာမည်ဖြင့် ထပ်ရှာကြည့်ပါ။")
            return

        await status.edit_text("🎵 သီချင်း ပို့နေပါပြီ...")

        with open(audio_path, 'rb') as audio:
            await message.reply_audio(
                audio=audio,
                title=title,
                performer=artist,
                caption=f"🎵 {title}\n🎤 {artist}\nvia YouTube",
            )

        await status.delete()

    except Exception as e:
        logger.exception("YouTube song download failed")
        await status.edit_text(f"❌ Error: {str(e)[:100]}")

    finally:
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except:
                pass


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
                can_send_other_messages=True,
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

    os.makedirs("downloads", exist_ok=True)

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
