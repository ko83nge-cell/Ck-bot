"""Generate a Pyrogram SESSION_STRING locally for your own Telegram account.
Run locally (PC or Android Termux), never on a public service. Keep the output secret.
"""
import asyncio
from pyrogram import Client

async def main():
    api_id_text = input("Telegram API_ID: ").strip()
    api_hash = input("Telegram API_HASH: ").strip()
    if not api_id_text.isdigit() or not api_hash:
        raise SystemExit("API_ID must be numeric and API_HASH must not be empty.")
    async with Client(
        "ck_helpbot_music_session",
        api_id=int(api_id_text),
        api_hash=api_hash,
        in_memory=True,
    ) as app:
        me = await app.get_me()
        session_string = await app.export_session_string()
        print("\\nLogged in as:", me.first_name, f"(ID: {me.id})")
        print("\\nSESSION_STRING (keep secret; do not share it):\\n")
        print(session_string)
        print("\\nCopy it into Railway Variables as SESSION_STRING.")

if __name__ == "__main__":
    asyncio.run(main())
