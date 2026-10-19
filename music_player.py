"""Optional Telegram Group Voice Chat music player.

Uses a separate MTProto user session for group calls; the normal Bot API token alone
cannot stream into Telegram voice chats. API_ID/API_HASH/SESSION_STRING are secrets.
"""
import asyncio
import concurrent.futures
import logging
import os
import shutil
from pathlib import Path

log = logging.getLogger("ck_helpbot.music")
API_ID = os.getenv("API_ID", "").strip()
API_HASH = os.getenv("API_HASH", "").strip()
SESSION_STRING = os.getenv("SESSION_STRING", "").strip()
CACHE_DIR = Path(os.getenv("MUSIC_CACHE_DIR", "/tmp/ck_music"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)
_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="music-mtproto")
_CLIENT = None
_CALLS = None
_STARTED = False
_QUEUES = {}
_CURRENT = {}


def _start_sync():
    global _CLIENT, _CALLS, _STARTED
    if _STARTED:
        return
    if not (API_ID and API_HASH and SESSION_STRING):
        log.warning("Music player disabled: set API_ID, API_HASH and SESSION_STRING")
        return
    from pyrogram import Client
    from pytgcalls import PyTgCalls
    _CLIENT = Client(
        "ck_helpbot_music",
        api_id=int(API_ID),
        api_hash=API_HASH,
        session_string=SESSION_STRING,
        workdir=str(CACHE_DIR),
    )
    _CLIENT.start()
    _CALLS = PyTgCalls(_CLIENT)
    _CALLS.start()
    _STARTED = True
    log.info("Music MTProto client started")


def _search_download(query):
    if not _STARTED:
        raise RuntimeError("Music session မပြင်ဆင်ရသေးပါ။ Railway Variables: API_ID, API_HASH, SESSION_STRING")
    import yt_dlp
    outtmpl = str(CACHE_DIR / "%(id)s.%(ext)s")
    opts = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "default_search": "ytsearch1",
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "max_filesize": 100 * 1024 * 1024,
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(query, download=True)
        if "entries" in info:
            info = next((x for x in info["entries"] if x), None)
        if not info:
            raise RuntimeError("သီချင်းမတွေ့ပါ။ အခြားအမည်ဖြင့် ရှာကြည့်ပါ။")
        ident = info.get("id")
        title = info.get("title") or query
        path = CACHE_DIR / f"{ident}.mp3"
        if not path.exists():
            # Fall back to the actual yt-dlp output filename if postprocessing differs.
            candidates = sorted(CACHE_DIR.glob(f"{ident}.*"), key=lambda p: p.stat().st_mtime, reverse=True)
            candidates = [p for p in candidates if p.suffix.lower() not in (".part", ".ytdl")]
            if not candidates:
                raise RuntimeError("Audio ဖိုင်မရရှိပါ။ FFmpeg တပ်ဆင်ထားကြောင်း စစ်ပါ။")
            path = candidates[0]
        return title, str(path)


def _play_sync(chat_id, query):
    title, path = _search_download(query)
    from pytgcalls.types import AudioPiped
    track = (title, path)
    queue = _QUEUES.setdefault(chat_id, [])
    if chat_id in _CURRENT:
        queue.append(track)
        return f"Queue ထဲထည့်ပြီးပါပြီ: {title}"
    try:
        _CALLS.join_group_call(chat_id, AudioPiped(path))
    except Exception:
        # If already joined, replace the current stream.
        try:
            _CALLS.change_stream(chat_id, AudioPiped(path))
        except Exception:
            raise
    _CURRENT[chat_id] = track
    return title


def _pause_sync(chat_id):
    if not _STARTED: raise RuntimeError("Music session မပြင်ဆင်ရသေးပါ။")
    _CALLS.pause_stream(chat_id)


def _resume_sync(chat_id):
    if not _STARTED: raise RuntimeError("Music session မပြင်ဆင်ရသေးပါ။")
    _CALLS.resume_stream(chat_id)


def _stop_sync(chat_id):
    if not _STARTED: raise RuntimeError("Music session မပြင်ဆင်ရသေးပါ။")
    _CALLS.leave_group_call(chat_id)
    _CURRENT.pop(chat_id, None)
    _QUEUES.pop(chat_id, None)


def _skip_sync(chat_id):
    if not _STARTED: raise RuntimeError("Music session မပြင်ဆင်ရသေးပါ။")
    queue = _QUEUES.get(chat_id, [])
    if not queue:
        try: _CALLS.leave_group_call(chat_id)
        finally: _CURRENT.pop(chat_id, None)
        return None
    title, path = queue.pop(0)
    from pytgcalls.types import AudioPiped
    _CALLS.change_stream(chat_id, AudioPiped(path))
    _CURRENT[chat_id] = (title, path)
    return title


def _queue_sync(chat_id):
    items = []
    if chat_id in _CURRENT:
        items.append("▶️ " + _CURRENT[chat_id][0])
    items.extend(title for title, _ in _QUEUES.get(chat_id, []))
    return items


async def _run(fn, *args):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_EXECUTOR, lambda: fn(*args))

async def start():
    # Run all MTProto/PyTgCalls operations on one dedicated worker thread.
    await _run(_start_sync)

async def shutdown():
    def _stop():
        global _STARTED
        if _STARTED:
            try: _CALLS.stop()
            except Exception: log.exception("PyTgCalls stop failed")
            try: _CLIENT.stop()
            except Exception: log.exception("Pyrogram stop failed")
            _STARTED = False
    await _run(_stop)
    _EXECUTOR.shutdown(wait=False, cancel_futures=True)

async def play(chat_id, query): return await _run(_play_sync, chat_id, query)
async def pause(chat_id): return await _run(_pause_sync, chat_id)
async def resume(chat_id): return await _run(_resume_sync, chat_id)
async def stop(chat_id): return await _run(_stop_sync, chat_id)
async def skip(chat_id): return await _run(_skip_sync, chat_id)
def get_queue(chat_id): return _queue_sync(chat_id)
