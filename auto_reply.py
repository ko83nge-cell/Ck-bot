"""Private Telegram user-account auto-reply, independent from Music features."""
import asyncio
import concurrent.futures
import logging
import os
import time

log = logging.getLogger("ck_helpbot.auto_reply")
API_ID = os.getenv("API_ID", "").strip()
API_HASH = os.getenv("API_HASH", "").strip()
SESSION_STRING = os.getenv("SESSION_STRING", "").strip()
AUTO_REPLY_ENABLED = os.getenv("AUTO_REPLY_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
try:
    AUTO_REPLY_COOLDOWN_SECONDS = max(60, int(os.getenv("AUTO_REPLY_COOLDOWN_SECONDS", "1800")))
except ValueError:
    AUTO_REPLY_COOLDOWN_SECONDS = 1800
_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="ck-auto-reply")
_CLIENT = None
_STARTED = False
_LAST_SENT = {}

def _reply_for(text):
    raw = (text or "").strip()
    low = raw.casefold()
    if any(x in low for x in ("မင်္ဂလာပါ", "ဟယ်လို", "ဟိုင်း", "hello", "hi", "hey", "မင်္ဂလာည", "မင်္ဂလာနံနက်")):
        return "မင်္ဂလာပါ 😊 စာပို့ပေးတာ ကျေးဇူးပါ။ အခုချက်ချင်း မဖြေနိုင်သေးလို့ အဆင်ပြေတဲ့အချိန်မှာ ပြန်စာပို့ပေးပါမယ်နော်။"
    if any(x in low for x in ("နေကောင်းလား", "how are you")):
        return "အဆင်ပြေပါတယ်၊ မေးပေးတာ ကျေးဇူးပါ 😊 သင်လည်း အဆင်ပြေပါစေ။"
    if any(x in low for x in ("ကျေးဇူး", "thanks", "thank you", "thx")):
        return "ရပါတယ်နော် 😊 ဆက်ပြီး အကူအညီလိုရင် စာပို့ထားခဲ့ပါ။"
    if any(x in low for x in ("စျေး", "ဈေး", "ဘယ်လောက်", "တန်ဖိုး", "price", "cost")):
        return "စျေးနှုန်းကို တိတိကျကျ စစ်ဆေးပြီး ပြန်အကြောင်းကြားပေးပါမယ်။ ဘယ်ပစ္စည်း/ဝန်ဆောင်မှုလဲဆိုတာ အသေးစိတ်ပို့ပေးပါနော်။"
    if any(x in low for x in ("အလုပ်", "စီးပွား", "business", "work", "ဝန်ဆောင်မှု", "service")):
        return "အလုပ်/ဝန်ဆောင်မှုအကြောင်း စာပို့ပေးတာ ကျေးဇူးပါ။ လိုအပ်ချက်နဲ့ အသေးစိတ်ကို ရေးပေးထားပါ၊ ပြန်ဖြေပေးပါမယ်။"
    if any(x in low for x in ("ဖုန်းခေါ်", "ဖုန်းဆက်", "call me", "ဖုန်းနံပါတ်")):
        return "စာပို့ပေးတာ ကျေးဇူးပါ။ လက်ရှိ ဖုန်းမဖြေနိုင်သေးပါဘူး။ လိုအပ်တဲ့အကြောင်းအရာကို ဒီမှာ စာရေးပေးထားပါနော်။"
    if any(x in raw for x in ("?", "？", "လား", "ဘယ်လို", "ဘာလဲ")):
        return "မေးခွန်းပို့ပေးတာ ကျေးဇူးပါ။ အချက်အလက်ကို စစ်ဆေးပြီး အဆင်ပြေတဲ့အချိန်မှာ ပြန်ဖြေပေးပါမယ်နော်။"
    return "မက်ဆေ့ချ်ပို့ပေးတာ ကျေးဇူးပါ 😊 အခုချက်ချင်း မဖြေနိုင်သေးလို့ စာကို မြင်တဲ့အခါ ပြန်ဖြေပေးပါမယ်။ အရေးကြီးတာရှိရင် အသေးစိတ်ရေးပေးထားပါနော်။"

async def _handler(client, message):
    if not AUTO_REPLY_ENABLED or not getattr(message, "from_user", None):
        return
    sender = message.from_user
    if sender.is_self or sender.is_bot or sender.id == getattr(getattr(client, "me", None), "id", None):
        return
    text = (getattr(message, "text", None) or getattr(message, "caption", None) or "").strip()
    if not text or text.startswith("/"):
        return
    now = time.monotonic()
    if now - _LAST_SENT.get(sender.id, 0) < AUTO_REPLY_COOLDOWN_SECONDS:
        return
    _LAST_SENT[sender.id] = now
    try:
        await message.reply_text(_reply_for(text), quote=True)
        log.info("Private auto-reply sent; sender_id=%s", sender.id)
    except Exception:
        _LAST_SENT.pop(sender.id, None)
        log.exception("Auto-reply failed")

def _start_sync():
    global _CLIENT, _STARTED
    if _STARTED or not AUTO_REPLY_ENABLED:
        if not AUTO_REPLY_ENABLED:
            log.info("Auto-reply disabled by AUTO_REPLY_ENABLED")
        return
    if not (API_ID and API_HASH and SESSION_STRING):
        log.warning("Auto-reply disabled: set API_ID, API_HASH, SESSION_STRING to enable personal-account replies")
        return
    from pyrogram import Client, filters
    from pyrogram.handlers import MessageHandler
    _CLIENT = Client("ck_helpbot_auto_reply", api_id=int(API_ID), api_hash=API_HASH, session_string=SESSION_STRING, workdir="/tmp")
    _CLIENT.add_handler(MessageHandler(_handler, filters.private & filters.incoming & ~filters.bot))
    _CLIENT.start()
    _STARTED = True
    log.info("Private auto-reply started; cooldown=%s seconds", AUTO_REPLY_COOLDOWN_SECONDS)

async def start():
    await asyncio.get_running_loop().run_in_executor(_EXECUTOR, _start_sync)

def _shutdown_sync():
    global _STARTED
    if _STARTED and _CLIENT:
        try:
            _CLIENT.stop()
        finally:
            _STARTED = False

async def shutdown():
    await asyncio.get_running_loop().run_in_executor(_EXECUTOR, _shutdown_sync)
    _EXECUTOR.shutdown(wait=False, cancel_futures=True)
