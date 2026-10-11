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

BOT_TOKEN = "8824850208:AAGkmULcNJxWx-39-80r-8oJNtSc9g3bSTM"
JAMENDO_CLIENT_ID = "957b221f"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Warnings are stored in memory.
# They reset when the bot restarts.
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
        await update.effective_message.reply_text(
            "ဒီ Command ကို Group ထဲမှာ သုံးပါ။"
        )
        return False

    if not await is_admin(update, context):
        await update.effective_message.reply_text(
            "ဒီ Command ကို Group Admin ပဲ သုံးနိုင်ပါတယ်။"
        )
        return False

    return True


# =========================
# START AND HELP
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "မင်္ဂလာပါ! 🤖\n\n"
        "Music နဲ့ Group Management Bot ပါ။\n\n"
        "/song relaxing music - သီချင်းရှာရန်\n"
        "/help - Command အားလုံးကြည့်ရန်"
    )


async def help_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    await update.effective_message.reply_text(
        "🎵 MUSIC\n"
        "/song သီချင်းနာမည်\n\n"
        "🛡️ ADMIN COMMANDS\n"
        "အသုံးပြုမည့်သူရဲ့ Message ကို Reply လုပ်ပြီး သုံးပါ။\n\n"
        "/warn - သတိပေးရန်\n"
        "/warnings - Warn အရေအတွက်ကြည့်ရန်\n"
        "/ban - Ban လုပ်ရန်\n"
        "/unban USER_ID - Ban ပြန်ဖြုတ်ရန်\n"
        "/mute - Mute လုပ်ရန်\n"
        "/unmute - Mute ပြန်ဖြုတ်ရန်\n\n"
        "Bot ကို Group Admin ပေးထားဖို့ လိုပါတယ်။"
    )


# =========================
# MUSIC SEARCH
# =========================

async def song(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message

    if not context.args:
        await message.reply_text(
            "သီချင်းနာမည် ထည့်ပေးပါ။\n"
            "ဥပမာ: /song relaxing music"
        )
        return

    if not JAMENDO_CLIENT_ID:
        await message.reply_text(
            "JAMENDO_CLIENT_ID မသတ်မှတ်ရသေးပါ။"
        )
        return

    query = " ".join(context.args)
    status = await message.reply_text(
        f"🔎 '{query}' ကို ရှာနေပါတယ်..."
    )

    try:
        response = requests.get(
            "https://api.jamendo.com/v3.0/tracks/",
            params={
                "client_id": JAMENDO_CLIENT_ID,
                "format": "json",
                "search": query,
                "limit": 10,
                "track_type": "single albumtrack",
                "audioformat": "mp31",
            },
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()

        tracks = data.get("results", [])

        # Only tracks with download permission
        tracks = [
            track for track in tracks
            if track.get("audiodownload_allowed") is True
            and track.get("audiodownload")
        ]

        if not tracks:
            await status.edit_text(
                "သီချင်း မတွေ့ပါဘူး၊ သို့မဟုတ် Download "
                "ခွင့်ပြုထားတဲ့ သီချင်း မရှိပါဘူး。\n"
                "အခြားနာမည်နဲ့ ထပ်ရှာကြည့်ပါ။"
            )
            return

        # Try the first permitted result
        track = tracks[0]
        audio_url = track["audiodownload"]

        audio_response = requests.get(
            audio_url,
            timeout=30,
            stream=True,
        )
        audio_response.raise_for_status()

        content_length = int(
            audio_response.headers.get("content-length", 0)
        )

        # Avoid downloading very large files
        max_size = 45 * 1024 * 1024

        if content_length > max_size:
            await status.edit_text(
                "ဒီသီချင်းဖိုင်က အရမ်းကြီးနေပါတယ်။"
            )
            return

        audio_data = io.BytesIO()
        total_size = 0

        for chunk in audio_response.iter_content(64 * 1024):
            if not chunk:
                continue

            total_size += len(chunk)

            if total_size > max_size:
                await status.edit_text(
                    "သီချင်းဖိုင်က သတ်မှတ်ထားတဲ့ "
                    "အရွယ်အစားထက် ကြီးနေပါတယ်။"
                )
                return

            audio_data.write(chunk)

        audio_data.seek(0)
        audio_data.name = "song.mp3"

        title = track.get("name", "Unknown")
        artist = track.get("artist_name", "Unknown")

        await message.reply_audio(
            audio=audio_data,
            title=title,
            performer=artist,
            caption=(
                f"🎵 {title}\n"
                f"🎤 {artist}\n"
                f"Source: Jamendo"
            ),
        )

        await status.delete()

    except requests.RequestException:
        logger.exception("Music API or download error")
        await status.edit_text(
            "အင်တာနက် သို့မဟုတ် Music API မှာ "
            "ပြဿနာရှိနေပါတယ်။ နောက်မှ ထပ်ကြိုးစားပါ။"
        )

    except Exception:
        logger.exception("Song command error")
        await status.edit_text(
            "သီချင်းပို့ရာမှာ အမှားဖြစ်သွားပါတယ်။"
        )


# =========================
# WARN
# =========================

async def warn(update, context):
    if not await admin_only(update, context):
        return

    target = await get_target(update)

    if not target:
        await update.effective_message.reply_text(
            "သတိပေးမယ့်သူရဲ့ Message ကို Reply လုပ်ပြီး /warn သုံးပါ။"
        )
        return

    if target.is_bot:
        await update.effective_message.reply_text(
            "Bot ကို Warn လုပ်လို့မရပါဘူး။"
        )
        return

    key = (update.effective_chat.id, target.id)
    warnings[key] = warnings.get(key, 0) + 1

    await update.effective_message.reply_text(
        f"⚠️ {target.full_name} ကို Warn ပေးပြီးပါပြီ။\n"
        f"Warn အရေအတွက်: {warnings[key]}"
    )


async def warnings_command(update, context):
    target = await get_target(update)

    if target:
        user_id = target.id
    else:
        user_id = update.effective_user.id

    key = (update.effective_chat.id, user_id)

    await update.effective_message.reply_text(
        f"⚠️ Warn အရေအတွက်: {warnings.get(key, 0)}"
    )


# =========================
# BAN / UNBAN
# =========================

async def ban(update, context):
    if not await admin_only(update, context):
        return

    target = await get_target(update)

    if not target:
        await update.effective_message.reply_text(
            "Ban လုပ်မယ့်သူရဲ့ Message ကို Reply လုပ်ပြီး /ban သုံးပါ။"
        )
        return

    if target.id == update.effective_user.id or target.is_bot:
        await update.effective_message.reply_text(
            "ဒီသူကို Ban လုပ်လို့မရပါဘူး။"
        )
        return

    try:
        member = await context.bot.get_chat_member(
            update.effective_chat.id, target.id
        )

        if member.status in ("administrator", "creator"):
            await update.effective_message.reply_text(
                "Group Admin ကို ဒီ Command နဲ့ Ban မလုပ်နိုင်ပါဘူး။"
            )
            return

        await context.bot.ban_chat_member(
            update.effective_chat.id,
            target.id,
        )

        await update.effective_message.reply_text(
            f"🚫 {target.full_name} ကို Ban လုပ်ပြီးပါပြီ။"
        )

    except Exception:
        logger.exception("Ban error")
        await update.effective_message.reply_text(
            "Ban မလုပ်နိုင်ပါဘူး။ Bot ရဲ့ Admin Permission ကို စစ်ပါ။"
        )


async def unban(update, context):
    if not await admin_only(update, context):
        return

    if not context.args:
        await update.effective_message.reply_text(
            "အသုံးပြုပုံ: /unban USER_ID"
        )
        return

    try:
        user_id = int(context.args[0])

        await context.bot.unban_chat_member(
            update.effective_chat.id,
            user_id,
            only_if_banned=True,
        )

        await update.effective_message.reply_text(
            f"✅ User ID {user_id} ကို Unban လုပ်ပြီးပါပြီ။"
        )

    except ValueError:
        await update.effective_message.reply_text(
            "USER_ID ကို ဂဏန်းနဲ့ ထည့်ပေးပါ။"
        )
    except Exception:
        logger.exception("Unban error")
        await update.effective_message.reply_text(
            "Unban မလုပ်နိုင်ပါဘူး။ User ID နဲ့ Permission ကို စစ်ပါ။"
        )


# =========================
# MUTE / UNMUTE
# =========================

async def mute(update, context):
    if not await admin_only(update, context):
        return

    target = await get_target(update)

    if not target:
        await update.effective_message.reply_text(
            "Mute လုပ်မယ့်သူရဲ့ Message ကို Reply လုပ်ပြီး /mute သုံးပါ။"
        )
        return

    if target.id == update.effective_user.id or target.is_bot:
        await update.effective_message.reply_text(
            "ဒီသူကို Mute လုပ်လို့မရပါဘူး။"
        )
        return

    try:
        member = await context.bot.get_chat_member(
            update.effective_chat.id, target.id
        )

        if member.status in ("administrator", "creator"):
            await update.effective_message.reply_text(
                "Group Admin ကို Mute မလုပ်နိုင်ပါဘူး။"
            )
            return

        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target.id,
            permissions=ChatPermissions(
                can_send_messages=False,
                can_send_audios=False,
                can_send_documents=False,
                can_send_photos=False,
                can_send_videos=False,
                can_send_video_notes=False,
                can_send_voice_notes=False,
                can_send_polls=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False,
            ),
        )

        await update.effective_message.reply_text(
            f"🔇 {target.full_name} ကို Mute လုပ်ပြီးပါပြီ။"
        )

    except Exception:
        logger.exception("Mute error")
        await update.effective_message.reply_text(
            "Mute မလုပ်နိုင်ပါဘူး။ Bot Permission ကို စစ်ပါ။"
        )


async def unmute(update, context):
    if not await admin_only(update, context):
        return

    target = await get_target(update)

    if not target:
        await update.effective_message.reply_text(
            "Unmute လုပ်မယ့်သူရဲ့ Message ကို Reply လုပ်ပြီး /unmute သုံးပါ။"
        )
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

        await update.effective_message.reply_text(
            f"🔊 {target.full_name} ကို Unmute လုပ်ပြီးပါပြီ။"
        )

    except Exception:
        logger.exception("Unmute error")
        await update.effective_message.reply_text(
            "Unmute မလုပ်နိုင်ပါဘူး။ Bot Permission ကို စစ်ပါ။"
        )


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
    
