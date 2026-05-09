"""Main entry point: /start and routing ReplyKeyboard button presses."""
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.config import BABY_NAME, ALLOWED_USERS
from bot.keyboards.reply import main_kb, SLEEP_BTN, WEIGHT_BTN, MUSIC_BTN, STATS_BTN, SETTINGS_BTN
from bot.services.baby import baby_age_str

router = Router()


def _check_allowed(user_id: int) -> bool:
    return not ALLOWED_USERS or user_id in ALLOWED_USERS


@router.message(CommandStart())
async def cmd_start(message: Message):
    if not _check_allowed(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    age = baby_age_str()
    await message.answer(
        f"👶 *{BABY_NAME}* — {age}\n\nБот запущен. Используй кнопки внизу.",
        reply_markup=main_kb(),
        parse_mode="Markdown",
    )


# ── ReplyKeyboard routing ──────────────────────────────────────────────────────
# Each button press is a plain text message — route to the relevant handler.
# The actual handler logic lives in the specific handler modules.

@router.message(F.text == SLEEP_BTN)
async def route_sleep(message: Message):
    from bot.handlers.sleep import show_sleep_status
    await show_sleep_status(message)


@router.message(F.text == WEIGHT_BTN)
async def route_weight(message: Message):
    from bot.handlers.weight import show_weight_menu
    await show_weight_menu(message)


@router.message(F.text == MUSIC_BTN)
async def route_music(message: Message):
    from bot.handlers.music import show_music_menu
    await show_music_menu(message)


@router.message(F.text == STATS_BTN)
async def route_analytics(message: Message):
    from bot.handlers.analytics import show_analytics_menu
    await show_analytics_menu(message)


@router.message(F.text == SETTINGS_BTN)
async def route_settings(message: Message):
    from bot.handlers.settings import show_settings
    await show_settings(message)
