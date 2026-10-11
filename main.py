import os
import io
import logging
import asyncio
from collections import defaultdict
from datetime import datetime, timezone

import requests
from telegram import Update, ChatPermissions
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# =========================
# CONFIGURATION
# =========================

BOT_TOKEN = "8824850208:AAFw2m9k_uZlgAwLjgtj20j3bRwLASd090g"
OWNER_ID_TEXT = "8062359539"
OWNER_ID = int(OWNER_ID_TEXT) if OWNER_ID_TEXT.isdigit() else None

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("CkHelpBot")

# Warning counts are kept in memory.
# They reset if Railway restarts the service.
warnings = defaultdict(int)

SONG_URL = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"


# =========================
# HELPERS
# =========================

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    if not user or not chat:
        return False

    if OWNER_ID is not None and user.id == OWNER_ID:
        return True

    if chat.type == "private":
        return False

    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        return member.status in ("administrator", "creator")
    except Exception:
        logger.exception("Could not check administrator status")
        return False


async def reply(update: Update, message: str):
    if update.effective_message:
        await update.effective_message.reply_text(message)


async def get_target(update: Update):
    message = update.effective_message
    if not message:
        return None

    if message.reply_to_message:
        return message.reply_to_message.from_user

    return None


# =========================
# BASIC COMMANDS
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await reply(
        update,
        "မင်္ဂလာပါ 👋 Ck_helpbot မှ ကြိုဆိုပါတယ်။\n\n"
        "/help - Command များကြည့်ရန်\n"
        "/song - သီချင်းနမူနာရယူရန်\n\n"
        "Admin command များကို Group ထဲတွင် အသုံးပြုနိုင်ပါတယ်။"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await reply(
        update,
        "📚 Ck_helpbot Commands\n\n"
        "👤 အားလုံးအတွက်\n"
        "/start - Bot စတင်ရန်\n"
        "/help - အကူအညီကြည့်ရန်\n"
        "/song - သီချင်းနမူနာရယူရန်\n\n"
        "🛡️ Admin အတွက်\n"
        "/warn (reply လုပ်ရန်) - သတိပေးရန်\n"
        "/warnings (reply လုပ်ရန်) - Warning အရေအတွက်ကြည့်ရန်\n"
        "/ban (reply လုပ်ရန်) - Ban လုပ်ရန်\n"
        "/unban USER_ID - Unban လုပ်ရန်\n"
        "/mute (reply လုပ်ရန်) - Mute လုပ်ရန်\n"
        "/unmute (reply လုပ်ရန်) - Unmute လုပ်ရန်\n\n"
        "မှတ်ချက်: Admin command များအတွက် Bot ကို Group ထဲတွင် "
        "လိုအပ်သော Admin permission ပေးထားရပါမယ်။"
    )


# =========================
# SONG COMMAND
# =========================

def download_song():
    response = requests.get(
        SONG_URL,
        timeout=(10, 45),
        headers={"User-Agent": "CkHelpBot/1.0"},
    )
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "").lower()
    if "audio" not in content_type and "octet-stream" not in content_type:
        raise ValueError("The URL did not return an audio file.")

    if len(response.content) > 45 * 1024 * 1024:
        raise ValueError("Audio file is too large.")

    return response.content


async def song(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message:
        return

    status = await message.reply_text("🎵 သီချင်းကို ပြင်ဆင်နေပါတယ်...")

    try:
        audio_data = await asyncio.to_thread(download_song)
        audio = io.BytesIO(audio_data)
        audio.name = "sample-song.mp3"

        await message.reply_audio(
            audio=audio,
            title="Sample Song",
            performer="Ck_helpbot",
            read_timeout=60,
            write_timeout=60,
            connect_timeout=20,
            pool_timeout=20,
        )
        await status.delete()

    except Exception:
        logger.exception("Song command failed")
        try:
            await status.edit_text(
                "❌ သီချင်းပို့မရသေးပါ။ ခဏကြာပြီး ပြန်စမ်းကြည့်ပါ။"
            )
        except Exception:
            pass


# =========================
# ADMIN COMMANDS
# =========================

async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await reply(update, "❌ ဒီ command ကို Admin သာ အသုံးပြုနိုင်ပါတယ်။")
        return

    target = await get_target(update)
    if not target:
        await reply(update, "သတိပေးမယ့်သူရဲ့ message ကို Reply လုပ်ပြီး /warn ပို့ပါ။")
        return

    if target.is_bot:
        await reply(update, "Bot ကို Warning ပေးလို့မရပါ။")
        return

    warnings[(update.effective_chat.id, target.id)] += 1
    count = warnings[(update.effective_chat.id, target.id)]

    await reply(
        update,
        f"⚠️ {target.full_name} ကို Warning ပေးပြီးပါပြီ။\n"
        f"စုစုပေါင်း Warning: {count}"
    )


async def warnings_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    target = await get_target(update)

    if target:
        user_id = target.id
    elif context.args and context.args[0].isdigit():
        user_id = int(context.args[0])
    else:
        await reply(
            update,
            "အသုံးပြုပုံ: User ရဲ့ message ကို Reply လုပ်ပြီး /warnings ပို့ပါ။"
        )
        return

    count = warnings[(update.effective_chat.id, user_id)]
    await reply(update, f"⚠️ Warning အရေအတွက်: {count}")


async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await reply(update, "❌ Admin သာ အသုံးပြုနိုင်ပါတယ်။")
        return

    target = await get_target(update)
    if not target:
        await reply(update, "Ban လုပ်မယ့်သူရဲ့ message ကို Reply လုပ်ပါ။")
        return

    if target.is_bot or target.id == OWNER_ID:
        await reply(update, "ဒီအကောင့်ကို Ban လုပ်လို့မရပါ။")
        return

    try:
        await context.bot.ban_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target.id,
        )
        await reply(update, f"🚫 {target.full_name} ကို Ban လုပ်ပြီးပါပြီ။")
    except Exception:
        logger.exception("Ban failed")
        await reply(update, "❌ Ban မလုပ်နိုင်ပါ။ Bot ရဲ့ Admin permission ကို စစ်ပါ။")


async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await reply(update, "❌ Admin သာ အသုံးပြုနိုင်ပါတယ်။")
        return

    if not context.args or not context.args[0].isdigit():
        await reply(update, "အသုံးပြုပုံ: /unban USER_ID")
        return

    try:
        await context.bot.unban_chat_member(
            chat_id=update.effective_chat.id,
            user_id=int(context.args[0]),
            only_if_banned=True,
        )
        await reply(update, "✅ Unban လုပ်ပြီးပါပြီ။")
    except Exception:
        logger.exception("Unban failed")
        await reply(update, "❌ Unban မလုပ်နိုင်ပါ။ User ID နဲ့ Bot permission ကို စစ်ပါ။")


async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await reply(update, "❌ Admin သာ အသုံးပြုနိုင်ပါတယ်။")
        return

    target = await get_target(update)
    if not target:
        await reply(update, "Mute လုပ်မယ့်သူရဲ့ message ကို Reply လုပ်ပါ။")
        return

    if target.is_bot or target.id == OWNER_ID:
        await reply(update, "ဒီအကောင့်ကို Mute လုပ်လို့မရပါ။")
        return

    try:
        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target.id,
            permissions=ChatPermissions(can_send_messages=False),
        )
        await reply(update, f"🔇 {target.full_name} ကို Mute လုပ်ပြီးပါပြီ။")
    except Exception:
        logger.exception("Mute failed")
        await reply(update, "❌ Mute မလုပ်နိုင်ပါ။ Bot ရဲ့ Admin permission ကို စစ်ပါ။")


async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await reply(update, "❌ Admin သာ အသုံးပြုနိုင်ပါတယ်။")
        return

    target = await get_target(update)
    if not target:
        await reply(update, "Unmute လုပ်မယ့်သူရဲ့ message ကို Reply လုပ်ပါ။")
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
        await reply(update, f"🔊 {target.full_name} ကို Unmute လုပ်ပြီးပါပြီ။")
    except Exception:
        logger.exception("Unmute failed")
        await reply(update, "❌ Unmute မလုပ်နိုင်ပါ။ Bot ရဲ့ Admin permission ကို စစ်ပါ။")


# =========================
# ERROR HANDLING
# =========================

async def error_handler(
    update: object, context: ContextTypes.DEFAULT_TYPE
):
    logger.error(
        "Unhandled error while processing update",
        exc_info=context.error,
    )


# =========================
# START BOT
# =========================

def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN မရှိပါ။")

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

    app.add_error_handler(error_handler)

    logger.info("Ck_helpbot is starting...")
    app.run_polling(
        drop_pending_updates=False,
        allowed_updates=["message"],
    )


if __name__ == "__main__":
    main()

