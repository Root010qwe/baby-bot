"""
Tracks last status message per chat so we can delete stale ones.
Stored in memory — resets on bot restart (acceptable for this use case).
"""
from aiogram import Bot

# chat_id → message_id  for sleep status messages
_sleep_status: dict[int, int] = {}
# chat_id → message_id  for section headers (weight, analytics, music, settings)
_section_msg: dict[int, int] = {}


async def replace_sleep_status(bot: Bot, chat_id: int, new_msg_id: int):
    """Delete previous sleep status message and remember the new one."""
    old = _sleep_status.get(chat_id)
    if old and old != new_msg_id:
        try:
            await bot.delete_message(chat_id, old)
        except Exception:
            pass
    _sleep_status[chat_id] = new_msg_id


async def replace_section(bot: Bot, chat_id: int, new_msg_id: int):
    """Delete previous section message (weight menu, analytics, etc.)."""
    old = _section_msg.get(chat_id)
    if old and old != new_msg_id:
        try:
            await bot.delete_message(chat_id, old)
        except Exception:
            pass
    _section_msg[chat_id] = new_msg_id
