"""Main entry: /start, role-aware keyboard, ReplyKeyboard routing."""
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.config import BABY_NAME, is_allowed, is_full_access, get_role
from bot.keyboards.reply import kb_for, SLEEP_BTN, WEIGHT_BTN, MUSIC_BTN, STATS_BTN, SETTINGS_BTN
from bot.services.baby import baby_age_str

router = Router()

ROLE_HELLO = {
    "admin": "👑 Привет, Admin!",
    "mom":   "👩 Привет, мама!",
    "dad":   "👨 Привет, папа!",
}


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id
    if not is_allowed(uid):
        await message.answer("Нет доступа.")
        return
    age = baby_age_str()
    role_str = ROLE_HELLO.get(get_role(uid), "")
    await message.answer(
        f"{role_str}\n👶 *{BABY_NAME}* — {age}",
        reply_markup=kb_for(uid),
        parse_mode="Markdown",
    )


# ── ReplyKeyboard routing — always clears FSM state first ─────────────────────

@router.message(F.text == SLEEP_BTN)
async def route_sleep(message: Message, state: FSMContext):
    if not is_allowed(message.from_user.id):
        return
    await state.clear()
    from bot.handlers.sleep import show_sleep_status
    await show_sleep_status(message)


@router.message(F.text == WEIGHT_BTN)
async def route_weight(message: Message, state: FSMContext):
    if not is_full_access(message.from_user.id):
        return
    await state.clear()
    from bot.handlers.weight import show_weight_menu
    await show_weight_menu(message)


@router.message(F.text == MUSIC_BTN)
async def route_music(message: Message, state: FSMContext):
    if not is_allowed(message.from_user.id):
        return
    await state.clear()
    from bot.handlers.music import show_music_menu
    await show_music_menu(message)


@router.message(F.text == STATS_BTN)
async def route_analytics(message: Message, state: FSMContext):
    if not is_full_access(message.from_user.id):
        return
    await state.clear()
    from bot.handlers.analytics import show_analytics_menu
    await show_analytics_menu(message)


@router.message(F.text == SETTINGS_BTN)
async def route_settings(message: Message, state: FSMContext):
    if not is_full_access(message.from_user.id):
        return
    await state.clear()
    from bot.handlers.settings import show_settings
    await show_settings(message)
